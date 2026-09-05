"""MVP Factory + Intervention Queue (DEC-013)."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from core.config import get_settings
from core.export import export_tasks
from core.hitl import assert_owner_actor, get_draft_tz
from core.models import (
    BuildJob,
    BuildJobStatus,
    Intervention,
    InterventionAnswerType,
    InterventionStatus,
    Project,
    ProjectStatus,
)
from core.mvp_slice import active_requirements, mark_in_mvp, select_mvp_requirements
from core.planner import run_planner
from core.secrets_box import seal_secret
from core.speckit_export import persist_cursor_brief, render_speckit_files
from knowledge.repository import KnowledgeRepository

logger = logging.getLogger(__name__)

ACTIVE_JOB_STATUSES = frozenset(
    {
        BuildJobStatus.QUEUED.value,
        BuildJobStatus.PREPARING.value,
        BuildJobStatus.WAITING_INTERVENTION.value,
        BuildJobStatus.RUNNING.value,
        BuildJobStatus.READY_FOR_CLIENT.value,
    }
)

KIND_LABELS_RU = {
    "telegram_token": "Токен Telegram-бота",
    "dns": "Домен / DNS",
    "server": "Сервер / хостинг",
    "password": "Пароль или ключ интеграции",
    "apple_store": "Apple Developer / App Store",
    "google_play": "Google Play Console",
    "custom": "Нужно решение владельца",
}

_CATALOG: dict[str, list[dict[str, str]]] = {
    "telegram_bot": [
        {
            "kind": "telegram_token",
            "answer_type": InterventionAnswerType.SECRET.value,
            "question": (
                "Нужен токен бота заказчика от @BotFather. "
                "Без него telegram_bot MVP не запустить. "
                "Секрет не попадёт в ТЗ и в граф знаний."
            ),
        }
    ],
    "website": [
        {
            "kind": "dns",
            "answer_type": InterventionAnswerType.TEXT.value,
            "question": (
                "Какой домен или DNS указать для сайта? "
                "Если деплоя ещё нет — напишите «локально» или заглушку."
            ),
        }
    ],
    "rest_service": [
        {
            "kind": "server",
            "answer_type": InterventionAnswerType.TEXT.value,
            "question": (
                "Куда деплоить REST-сервис (хост, VPS, только локально)? "
                "Не угадываем инфраструктуру."
            ),
        }
    ],
    "ai_automation": [
        {
            "kind": "password",
            "answer_type": InterventionAnswerType.SECRET.value,
            "question": (
                "Нужен ключ или пароль внешней системы для автоматизации. "
                "Секрет хранится только в Intervention Queue."
            ),
        }
    ],
    "mobile_native": [
        {
            "kind": "apple_store",
            "answer_type": InterventionAnswerType.SECRET.value,
            "question": (
                "Если цель — iOS: Apple Developer / App Store Connect. "
                "Если платформа не iOS — ответьте «не нужно»."
            ),
        },
        {
            "kind": "google_play",
            "answer_type": InterventionAnswerType.SECRET.value,
            "question": (
                "Если цель — Android: доступ к Google Play Console. "
                "Если платформа не Android — ответьте «не нужно»."
            ),
        },
    ],
}


class FactoryError(ValueError):
    """Domain error for the MVP factory."""


@dataclass
class FactorySnapshot:
    project_id: uuid.UUID
    job: dict[str, Any] | None
    interventions: list[dict[str, Any]]
    can_create: bool
    can_send: bool
    gate: str
    message: str = ""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ttl_deadline() -> datetime:
    hours = max(1, int(get_settings().asf_intervention_ttl_hours or 72))
    return _now() + timedelta(hours=hours)


def latest_build_job(db: Session, project_id: uuid.UUID) -> BuildJob | None:
    return (
        db.query(BuildJob)
        .filter(BuildJob.project_id == project_id)
        .order_by(BuildJob.created_at.desc())
        .first()
    )


def expire_stale_interventions(db: Session, project_id: uuid.UUID | None = None) -> int:
    q = db.query(Intervention).filter(Intervention.status == InterventionStatus.OPEN.value)
    if project_id is not None:
        q = q.filter(Intervention.project_id == project_id)
    count = 0
    now = _now()
    for row in q.all():
        expires = row.ttl_expires_at
        if expires is None:
            continue
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires <= now:
            row.status = InterventionStatus.EXPIRED.value
            count += 1
    if count:
        db.flush()
    return count


def client_confirm_ready(kg: KnowledgeRepository, project: Project) -> bool:
    """Hook for DEC-012 client estimate confirm (PR #5 — not required yet).

    If a ``client_estimate`` artifact exists, factory waits until
    ``payload.confirmed`` is true. When the feature is absent, owner
    ``READY`` is enough.
    """
    artifacts = [
        e
        for e in kg.list_entities(project.id, type_="Artifact")
        if (e.payload or {}).get("kind") == "client_estimate"
    ]
    if not artifacts:
        return True
    latest = artifacts[-1]
    payload = latest.payload or {}
    return bool(payload.get("confirmed") or payload.get("client_confirmed"))


def factory_gate(db: Session, project: Project) -> tuple[bool, str]:
    if project.status != ProjectStatus.READY:
        return False, "need_owner_approve"
    kg = KnowledgeRepository(db)
    if not client_confirm_ready(kg, project):
        return False, "need_client_confirm"
    return True, "owner_approved"


def needed_intervention_specs(product_type: str | None) -> list[dict[str, str]]:
    pt = product_type or "website"
    return list(_CATALOG.get(pt) or _CATALOG["website"])


def _serialize_job(job: BuildJob | None) -> dict[str, Any] | None:
    if job is None:
        return None
    payload = dict(job.payload or {})
    return {
        "id": str(job.id),
        "project_id": str(job.project_id),
        "status": job.status,
        "executor": job.executor,
        "external_id": job.external_id,
        "brief_artifact_id": str(job.brief_artifact_id) if job.brief_artifact_id else None,
        "deep_link": payload.get("deep_link"),
        "message": payload.get("message"),
        "requirement_ids": list(payload.get("requirement_ids") or []),
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }


def serialize_intervention(row: Intervention) -> dict[str, Any]:
    payload = dict(row.payload or {})
    secret = row.answer_type == InterventionAnswerType.SECRET.value
    answer_preview = None
    if row.status == InterventionStatus.RESOLVED.value and not secret:
        answer_preview = payload.get("answer")
    return {
        "id": str(row.id),
        "project_id": str(row.project_id),
        "build_job_id": str(row.build_job_id),
        "kind": row.kind,
        "kind_label": KIND_LABELS_RU.get(row.kind, row.kind),
        "question": row.question,
        "answer_type": row.answer_type,
        "status": row.status,
        "ttl_expires_at": row.ttl_expires_at.isoformat() if row.ttl_expires_at else None,
        "has_answer": bool(row.answer_ciphertext)
        or bool(payload.get("answer"))
        or row.status == InterventionStatus.RESOLVED.value,
        "answer_preview": answer_preview,
        "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
    }


def list_interventions(
    db: Session,
    project_id: uuid.UUID,
    *,
    status: str | None = "open",
) -> list[Intervention]:
    expire_stale_interventions(db, project_id)
    q = db.query(Intervention).filter(Intervention.project_id == project_id)
    if status:
        q = q.filter(Intervention.status == status)
    return list(q.order_by(Intervention.created_at.asc()).all())


def factory_snapshot(
    db: Session,
    project: Project,
    *,
    message: str = "",
) -> FactorySnapshot:
    expire_stale_interventions(db, project.id)
    job = latest_build_job(db, project.id)
    rows = []
    if job is not None:
        rows = (
            db.query(Intervention)
            .filter(Intervention.build_job_id == job.id)
            .order_by(Intervention.created_at.asc())
            .all()
        )
    ok, gate = factory_gate(db, project)
    can_send = bool(job and job.status == BuildJobStatus.READY_FOR_CLIENT.value)
    return FactorySnapshot(
        project_id=project.id,
        job=_serialize_job(job),
        interventions=[serialize_intervention(r) for r in rows],
        can_create=ok,
        can_send=can_send,
        gate=gate,
        message=message,
    )


def snapshot_as_dict(snap: FactorySnapshot) -> dict[str, Any]:
    return {
        "project_id": str(snap.project_id),
        "job": snap.job,
        "interventions": snap.interventions,
        "can_create": snap.can_create,
        "can_send": snap.can_send,
        "gate": snap.gate,
        "message": snap.message,
    }


def _sync_project_mvp_payload(
    kg: KnowledgeRepository,
    project: Project,
    job: BuildJob,
) -> None:
    entities = kg.list_entities(project.id, type_="Project")
    if not entities:
        return
    payload = dict(entities[0].payload or {})
    payload["mvp_factory"] = {
        "build_job_id": str(job.id),
        "status": job.status,
        "executor": job.executor,
    }
    kg.update_entity(entities[0], payload=payload)


def _launch_executor(db: Session, job: BuildJob, project: Project, brief: dict[str, Any]) -> None:
    from integrations.cursor.executor import get_cursor_executor

    result = get_cursor_executor().launch(job, brief)
    job.executor = result.executor
    job.external_id = result.external_id
    job.status = result.status
    payload = dict(job.payload or {})
    payload["deep_link"] = result.deep_link
    payload["message"] = result.message
    if result.raw and result.executor == "cursor":
        payload["cursor_ref"] = {
            k: result.raw.get(k) for k in ("id", "bcId", "url", "status") if k in result.raw
        }
    job.payload = payload
    db.flush()


def refresh_build_job(db: Session, job: BuildJob) -> BuildJob:
    if job.status != BuildJobStatus.RUNNING.value:
        return job
    from integrations.cursor.executor import get_cursor_executor

    polled = get_cursor_executor().poll(job)
    if polled is None:
        return job
    if polled.status in {
        BuildJobStatus.READY_FOR_CLIENT.value,
        BuildJobStatus.FAILED.value,
    }:
        job.status = polled.status
        payload = dict(job.payload or {})
        payload["message"] = polled.message
        job.payload = payload
        db.flush()
    return job


def _maybe_assert_owner(actor_telegram_id: str | None) -> None:
    """Telegram path checks OWNER_TELEGRAM_ID. Console is already token-gated."""
    if actor_telegram_id is not None:
        assert_owner_actor(actor_telegram_id)


def create_mvp_job(
    db: Session,
    project: Project,
    *,
    actor_telegram_id: str | None = None,
    force: bool = False,
) -> FactorySnapshot:
    _maybe_assert_owner(actor_telegram_id)
    ok, gate = factory_gate(db, project)
    if not ok:
        if gate == "need_client_confirm":
            raise FactoryError(
                "клиент ещё не подтвердил смету — фабрика ждёт client_confirm"
            )
        raise FactoryError(
            f"проект должен быть READY после approve ТЗ, сейчас {project.status.value}"
        )

    existing = latest_build_job(db, project.id)
    if (
        existing
        and existing.status in ACTIVE_JOB_STATUSES
        and not force
    ):
        refresh_build_job(db, existing)
        return factory_snapshot(db, project, message="Уже есть активный BuildJob.")

    if existing and existing.status in ACTIVE_JOB_STATUSES and force:
        existing.status = BuildJobStatus.CANCELLED.value
        for row in (
            db.query(Intervention)
            .filter(
                Intervention.build_job_id == existing.id,
                Intervention.status == InterventionStatus.OPEN.value,
            )
            .all()
        ):
            row.status = InterventionStatus.CANCELLED.value
        db.flush()

    kg = KnowledgeRepository(db)
    requirements = kg.list_entities(project.id, type_="Requirement")
    selected = select_mvp_requirements(requirements)
    if not selected:
        raise FactoryError("нет требований для MVP-среза")
    marked = mark_in_mvp(kg, selected, requirements)
    selected_ids = [str(e.id) for e in marked]

    job = BuildJob(
        project_id=project.id,
        status=BuildJobStatus.PREPARING.value,
        executor="stub",
        payload={"requirement_ids": selected_ids},
    )
    db.add(job)
    db.flush()

    planned = run_planner(db, project, mvp_only=True)
    exported = export_tasks(db, project, format="markdown")
    slice_ids = set(selected_ids)
    brief_tasks = [
        t
        for t in exported.tasks
        if not t.get("requirement_ids")
        or slice_ids.intersection(str(x) for x in (t.get("requirement_ids") or []))
    ] or list(exported.tasks)
    draft = get_draft_tz(kg, project.id)
    draft_content = (draft.payload or {}).get("content", "") if draft else ""
    open_qs = [
        (e.payload or {}).get("question") or e.name
        for e in kg.list_entities(project.id, type_="OpenQuestion")
        if e.status == "open"
    ]
    risks = [
        e.name for e in kg.list_entities(project.id, type_="Risk") if e.status != "archived"
    ]
    files = render_speckit_files(
        project,
        requirements=marked,
        tasks=brief_tasks,
        draft_excerpt=str(draft_content or ""),
        escalated=[str(q) for q in open_qs if q],
        risks=risks,
    )
    artifact = persist_cursor_brief(
        kg,
        project,
        build_job_id=str(job.id),
        files=files,
        requirement_ids=selected_ids,
        task_export_markdown=exported.content,
    )
    job.brief_artifact_id = artifact.id
    payload = dict(job.payload or {})
    payload.update(
        {
            "requirement_ids": selected_ids,
            "task_ids": [str(i) for i in planned.task_ids],
            "speckit_files": list(files.keys()),
        }
    )
    job.payload = payload
    db.flush()

    specs = needed_intervention_specs(project.product_type)
    created_ivs: list[Intervention] = []
    for spec in specs:
        row = Intervention(
            project_id=project.id,
            build_job_id=job.id,
            kind=spec["kind"],
            question=spec["question"],
            answer_type=spec["answer_type"],
            status=InterventionStatus.OPEN.value,
            ttl_expires_at=_ttl_deadline(),
            payload={"product_type": project.product_type},
        )
        db.add(row)
        created_ivs.append(row)
    db.flush()

    brief = {
        "project_id": str(project.id),
        "project_name": project.name,
        "product_type": project.product_type,
        "task_export_markdown": exported.content,
        "prompt": (
            f"Implement the approved MVP for {project.name} "
            f"({project.product_type}). Follow spec.md / plan.md / tasks.md.\n\n"
            f"{exported.content}"
        ),
        "deep_link": f"/projects/{project.id}/export/tasks?format=markdown",
        "files": files,
    }

    if created_ivs:
        job.status = BuildJobStatus.WAITING_INTERVENTION.value
        job.payload = {**dict(job.payload or {}), "message": "Ждём ответы владельца."}
        _sync_project_mvp_payload(kg, project, job)
        db.flush()
        _notify_open_interventions(project, created_ivs)
        return factory_snapshot(
            db,
            project,
            message="BuildJob создан. Ответьте на вопросы Intervention Queue.",
        )

    _launch_executor(db, job, project, brief)
    _sync_project_mvp_payload(kg, project, job)
    return factory_snapshot(db, project, message="MVP запущен, вмешательств нет.")


def _notify_open_interventions(project: Project, rows: list[Intervention]) -> None:
    try:
        from integrations.telegram.notify import notify_owner_interventions

        notify_owner_interventions(project, [serialize_intervention(r) for r in rows])
    except Exception:  # noqa: BLE001
        logger.exception("Failed to notify owner about interventions for %s", project.id)


def get_intervention(
    db: Session, intervention_id: str | uuid.UUID
) -> Intervention | None:
    try:
        iid = uuid.UUID(str(intervention_id))
    except ValueError:
        return None
    return db.get(Intervention, iid)


def resolve_intervention(
    db: Session,
    intervention_id: str | uuid.UUID,
    answer: str,
    *,
    actor_telegram_id: str | None = None,
) -> FactorySnapshot:
    _maybe_assert_owner(actor_telegram_id)
    row = get_intervention(db, intervention_id)
    if row is None:
        raise FactoryError("intervention not found")
    expire_stale_interventions(db, row.project_id)
    db.refresh(row)
    if row.status == InterventionStatus.EXPIRED.value:
        raise FactoryError("срок ответа истёк")
    if row.status != InterventionStatus.OPEN.value:
        raise FactoryError(f"intervention is {row.status}, not open")
    text = (answer or "").strip()
    if not text:
        raise FactoryError("пустой ответ")

    secret = row.answer_type == InterventionAnswerType.SECRET.value
    payload = dict(row.payload or {})
    if secret:
        row.answer_ciphertext = seal_secret(text)
        payload.pop("answer", None)
        payload["answer_redacted"] = True
        logger.info("Resolved intervention %s (secret redacted)", row.id)
    else:
        payload["answer"] = text
        logger.info("Resolved intervention %s kind=%s", row.id, row.kind)
    row.payload = payload
    row.status = InterventionStatus.RESOLVED.value
    row.resolved_at = _now()
    db.flush()

    kg = KnowledgeRepository(db)
    kg.create_entity(
        project_id=row.project_id,
        type_="Decision",
        name=f"Intervention resolved: {row.kind}",
        status="accepted",
        payload={
            "kind": "intervention_resolved",
            "intervention_id": str(row.id),
            "build_job_id": str(row.build_job_id),
            "answer_type": row.answer_type,
            "has_answer": True,
        },
        confidence=1.0,
    )

    project = db.get(Project, row.project_id)
    if project is None:
        raise FactoryError("project not found")
    job = db.get(BuildJob, row.build_job_id)
    still_open = (
        db.query(Intervention)
        .filter(
            Intervention.build_job_id == row.build_job_id,
            Intervention.status == InterventionStatus.OPEN.value,
        )
        .count()
    )
    if job is not None and still_open == 0:
        _continue_after_interventions(db, kg, project, job)
    return factory_snapshot(db, project, message="Ответ принят.")


def _continue_after_interventions(
    db: Session,
    kg: KnowledgeRepository,
    project: Project,
    job: BuildJob,
) -> None:
    brief_files: dict[str, str] = {}
    task_md = ""
    if job.brief_artifact_id:
        art = kg.get_entity(job.brief_artifact_id, project_id=project.id)
        if art is not None:
            brief_files = dict((art.payload or {}).get("files") or {})
            task_md = str((art.payload or {}).get("task_export_markdown") or "")
    if not task_md:
        try:
            task_md = export_tasks(db, project, format="markdown").content
        except Exception:  # noqa: BLE001
            task_md = ""
    brief = {
        "project_id": str(project.id),
        "project_name": project.name,
        "product_type": project.product_type,
        "task_export_markdown": task_md,
        "prompt": task_md,
        "deep_link": f"/projects/{project.id}/export/tasks?format=markdown",
        "files": brief_files,
    }
    _launch_executor(db, job, project, brief)
    _sync_project_mvp_payload(kg, project, job)


def send_mvp_to_client(
    db: Session,
    project: Project,
    *,
    actor_telegram_id: str | None = None,
) -> FactorySnapshot:
    _maybe_assert_owner(actor_telegram_id)
    job = latest_build_job(db, project.id)
    if job is None:
        raise FactoryError("нет BuildJob — сначала создайте MVP")
    refresh_build_job(db, job)
    if job.status != BuildJobStatus.READY_FOR_CLIENT.value:
        raise FactoryError(
            f"MVP ещё не готов к отправке клиенту (статус {job.status})"
        )
    job.status = BuildJobStatus.SENT_TO_CLIENT.value
    payload = dict(job.payload or {})
    payload["sent_to_client_at"] = _now().isoformat()
    payload["message"] = "Отправлено клиенту на review."
    job.payload = payload
    db.flush()

    from core.models import Message, MessageKind

    db.add(
        Message(
            project_id=project.id,
            kind=MessageKind.SYSTEM,
            role="assistant",
            text="MVP готов и отправлен вам на review. Напишите замечания к реализации.",
            meta={"kind": "mvp_client_review", "build_job_id": str(job.id)},
        )
    )
    kg = KnowledgeRepository(db)
    kg.create_entity(
        project_id=project.id,
        type_="Decision",
        name="MVP sent to client for review",
        status="accepted",
        payload={
            "kind": "mvp_client_review",
            "build_job_id": str(job.id),
        },
        confidence=1.0,
    )
    _sync_project_mvp_payload(kg, project, job)
    db.flush()
    _notify_client_review(project, job)
    return factory_snapshot(db, project, message="Клиенту отправлено уведомление о review.")


def _notify_client_review(project: Project, job: BuildJob) -> None:
    try:
        from integrations.telegram.notify import notify_customer_mvp_review

        notify_customer_mvp_review(project, job)
    except Exception:  # noqa: BLE001
        logger.exception("Failed to notify customer about MVP review for %s", project.id)


def peek_secret_for_executor(row: Intervention) -> str | None:
    """Unseal for the executor only. Callers must not log or persist plaintext."""
    if row.answer_type != InterventionAnswerType.SECRET.value:
        return (row.payload or {}).get("answer")
    if not row.answer_ciphertext:
        return None
    from core.secrets_box import unseal_secret

    return unseal_secret(row.answer_ciphertext)
