"""Commercial TZ/quote/MVP pipeline for the owner console (post-MVP).

Discovery ``ProjectStatus`` stays the FSM. The console spine is derived
from HITL, package send, customer decision, BuildJob, and feedback.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from core.models import BuildJob, Message, Project, ProjectStatus
from discovery.stakeholders import facts_from_entities, stakeholder_header_lines
from knowledge.history import list_entity_history
from knowledge.repository import KnowledgeRepository
from knowledge.types import normalize_requirement_status

SPINE = (
    "new_project",
    "tz_review",
    "tz_approved",
    "agreement",
    "mvp",
    "accepted",
    "archived",
)

SPINE_RU = {
    "new_project": "Новый проект",
    "tz_review": "ТЗ на ревью",
    "tz_approved": "ТЗ утверждено",
    "agreement": "Согласование",
    "mvp": "MVP",
    "accepted": "Принято",
    "archived": "Архив",
}

QUOTE_STATUS_RU = {
    "ai_initial": "Первоначальная оценка AI",
    "owner_approved": "Утверждённая оценка",
    "sent": "Отправлено заказчику",
    "customer_rejected": "Отклонено заказчиком",
    "customer_confirmed": "Подтверждено заказчиком",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _parse_iso(raw: str | None) -> datetime | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def project_entity(kg: KnowledgeRepository, project: Project):
    entities = kg.list_entities(project.id, type_="Project")
    return entities[0] if entities else None


def commercial_payload(kg: KnowledgeRepository, project: Project) -> dict[str, Any]:
    ent = project_entity(kg, project)
    payload = dict(ent.payload or {}) if ent else {}
    raw = payload.get("commercial")
    return dict(raw) if isinstance(raw, dict) else {}


def set_commercial(
    kg: KnowledgeRepository,
    project: Project,
    patch: dict[str, Any],
) -> dict[str, Any]:
    ent = project_entity(kg, project)
    if ent is None:
        return {}
    payload = dict(ent.payload or {})
    current = dict(payload.get("commercial") or {})
    current.update(patch)
    payload["commercial"] = current
    kg.update_entity(ent, payload=payload, name=project.name)
    return current


def discovery_blocked(kg: KnowledgeRepository, project: Project) -> bool:
    """Package negotiation: store messages, do not run the interviewer."""
    commercial = commercial_payload(kg, project)
    if commercial.get("reopen_discovery"):
        return False
    if commercial.get("negotiation"):
        return True
    return False


def quoted_cost(hours: float, hourly_rate: float, discount_percent: float) -> int:
    rate = max(0.0, float(hourly_rate))
    hours_n = max(0.0, float(hours))
    discount = min(100.0, max(0.0, float(discount_percent)))
    return int(round(hours_n * rate * (1.0 - discount / 100.0)))


def default_package_caption(
    project: Project,
    *,
    cost_label: str,
    hours_label: str,
    version: int,
    studio: str,
) -> str:
    studio_name = studio.strip() or "Uni 4 IT"
    return (
        f"{studio_name}: готовы ТЗ и смета по проекту «{project.name}» (пакет v{version}).\n\n"
        f"Ориентир стоимости: {cost_label} при ~{hours_label} ч. "
        "Это рыночный ориентир для согласования объёма, не оферта и не счёт.\n\n"
        "Откройте Mini App → «Изменить проект»: там файлы, сопроводительное письмо "
        "и кнопки подтвердить или отклонить (можно прокомментировать ТЗ и смету отдельно).\n\n"
        "Если цифры или состав работ нужно поправить — напишите прямо в карточке, "
        "вернёмся с обновлённым пакетом."
    )


def customer_summary(kg: KnowledgeRepository, project: Project) -> dict[str, Any]:
    facts = facts_from_entities(kg, project.id)
    lines = stakeholder_header_lines(kg, project)
    name = facts.display_name or ""
    org = facts.organization_name or ("физлицо" if facts.is_individual else "")
    contact = facts.telegram or facts.phone or facts.email or ""
    line = " · ".join(p for p in (name, org, contact) if p) or "заказчик не указан"
    timeline = ""
    budget = ""
    for req in kg.list_entities(project.id, type_="Requirement"):
        payload = dict(req.payload or {})
        topic = str(payload.get("topic_id") or "")
        desc = str(payload.get("description") or req.name or "").strip()
        if topic == "timeline" and not timeline:
            timeline = desc
        if topic == "budget" and not budget:
            budget = desc
    return {
        "line": line,
        "name": name,
        "organization": org,
        "contact": contact,
        "header_lines": lines,
        "timeline": timeline,
        "budget": budget,
    }


def _quote_status_from_stored(stored: dict[str, Any]) -> str:
    explicit = str(stored.get("quote_status") or "").strip()
    if explicit:
        return explicit
    status = str(stored.get("status") or "")
    if status == "confirmed":
        return "customer_confirmed"
    if status == "discuss_requested":
        return "customer_rejected"
    if int(stored.get("package_version") or 0) > 0:
        return "sent"
    if stored.get("owner_priced"):
        return "owner_approved"
    return "ai_initial"


def _active_gate(
    project: Project,
    commercial: dict[str, Any],
    quote_status: str,
    has_job: bool,
) -> str:
    if project.status == ProjectStatus.ARCHIVED:
        return "archived"
    if commercial.get("mvp_accepted"):
        return "accepted"
    if has_job or project.status == ProjectStatus.READY:
        if quote_status == "customer_confirmed" or project.status == ProjectStatus.READY:
            return "mvp" if not commercial.get("mvp_accepted") else "accepted"
    if quote_status == "customer_confirmed":
        return "mvp" if has_job else "mvp"
    if quote_status in {"sent", "customer_rejected", "owner_approved"} or (
        project.status == ProjectStatus.WAITING_CLIENT_ESTIMATE
        and quote_status != "ai_initial"
    ):
        if quote_status in {"sent", "customer_rejected"}:
            return "agreement"
        if quote_status == "owner_approved" or project.status == ProjectStatus.WAITING_CLIENT_ESTIMATE:
            return "tz_approved" if quote_status != "sent" else "agreement"
    if project.status == ProjectStatus.WAITING_CLIENT_ESTIMATE:
        if quote_status in {"sent", "customer_rejected"}:
            return "agreement"
        return "tz_approved"
    if project.status == ProjectStatus.WAITING_OWNER:
        return "tz_review"
    if project.status in {
        ProjectStatus.NEW,
        ProjectStatus.INTERVIEW,
        ProjectStatus.ANALYZING,
        ProjectStatus.WAITING_CUSTOMER,
    }:
        return "new_project"
    return "new_project"


def derive_pipeline(
    db: Session,
    kg: KnowledgeRepository,
    project: Project,
) -> dict[str, Any]:
    from core.hitl import get_draft_tz

    commercial = commercial_payload(kg, project)
    draft = get_draft_tz(kg, project.id)
    stored = dict((draft.payload or {}).get("client_estimate") or {}) if draft else {}
    quote_status = _quote_status_from_stored(stored) if stored else ""
    jobs = (
        db.query(BuildJob)
        .filter(BuildJob.project_id == project.id)
        .order_by(BuildJob.created_at.asc())
        .all()
    )
    gate = _active_gate(project, commercial, quote_status, bool(jobs))
    if project.status == ProjectStatus.READY and not jobs:
        gate = "mvp"
    if commercial.get("mvp_accepted"):
        gate = "accepted"

    package_events = [
        ev for ev in (stored.get("package_events") or []) if isinstance(ev, dict)
    ]
    agreement_rows = []
    for ev in package_events:
        kind = str(ev.get("kind") or "")
        ver = int(ev.get("version") or 0)
        if kind == "sent":
            label = f"v{ver} отправлено"
        elif kind == "rejected":
            label = f"v{ver} отклонил"
        elif kind == "confirmed":
            label = f"v{ver} подтвердил"
        else:
            label = f"v{ver} {kind}"
        agreement_rows.append(
            {
                "kind": kind,
                "version": ver,
                "label": label,
                "at": ev.get("at"),
                "tz_comment": ev.get("tz_comment") or "",
                "estimate_comment": ev.get("estimate_comment") or "",
            }
        )

    mvp_rows: list[dict[str, Any]] = []
    for index, job in enumerate(jobs, start=1):
        status = str(job.status or "")
        payload = dict(job.payload or {})
        mvp_rows.append(
            {
                "kind": "ready",
                "version": index,
                "label": f"v{index} готово",
                "job_status": status,
                "at": job.created_at.isoformat() if job.created_at else None,
            }
        )
        if status in {"sent_to_client", "SENT_TO_CLIENT"} or payload.get("sent_to_client_at"):
            mvp_rows.append(
                {
                    "kind": "review",
                    "version": index,
                    "label": f"v{index} на ревью",
                    "at": payload.get("sent_to_client_at"),
                }
            )

    feedback = kg.list_entities(project.id, type_="Feedback")
    for fb in feedback:
        payload = dict(fb.payload or {})
        ver = len(jobs) or 1
        mvp_rows.append(
            {
                "kind": "remarks",
                "version": ver,
                "label": f"v{ver} замечания",
                "at": fb.created_at.isoformat() if getattr(fb, "created_at", None) else None,
                "text": payload.get("text") or fb.name,
            }
        )

    current_agree = agreement_rows[-1]["kind"] if agreement_rows else ""
    current_mvp = mvp_rows[-1]["kind"] if mvp_rows else ""

    estimate_rows = []
    if stored:
        estimate_rows.append(
            {"kind": "ai_initial", "label": QUOTE_STATUS_RU["ai_initial"], "current": quote_status == "ai_initial"}
        )
        if quote_status != "ai_initial":
            estimate_rows.append(
                {
                    "kind": "owner_approved",
                    "label": QUOTE_STATUS_RU["owner_approved"],
                    "current": quote_status == "owner_approved",
                }
            )
        for ev in package_events:
            kind = str(ev.get("kind") or "")
            mapped = {
                "sent": "sent",
                "rejected": "customer_rejected",
                "confirmed": "customer_confirmed",
            }.get(kind, kind)
            ver = int(ev.get("version") or 0)
            estimate_rows.append(
                {
                    "kind": mapped,
                    "version": ver,
                    "label": f"{QUOTE_STATUS_RU.get(mapped, mapped)} v{ver}",
                    "tz_comment": ev.get("tz_comment") or "",
                    "estimate_comment": ev.get("estimate_comment") or "",
                    "current": mapped == quote_status and ver == int(stored.get("package_version") or 0),
                }
            )

    snaps = commercial.get("tz_snapshots")
    snap_keys = set(snaps.keys()) if isinstance(snaps, dict) else set()

    return {
        "gate": gate,
        "gate_label": SPINE_RU.get(gate, gate),
        "spine": [
            {
                "id": sid,
                "label": SPINE_RU[sid],
                "current": sid == gate,
                "has_snapshot": sid in snap_keys,
            }
            for sid in SPINE
        ],
        "agreement_column": agreement_rows,
        "mvp_column": mvp_rows,
        "estimate_column": estimate_rows,
        "quote_status": quote_status,
        "package_version": int(stored.get("package_version") or 0),
        "unread_from_customer": bool(commercial.get("unread_from_customer")),
        "negotiation": bool(commercial.get("negotiation")),
        "reopen_discovery": bool(commercial.get("reopen_discovery")),
        "current_agreement_kind": current_agree,
        "current_mvp_kind": current_mvp,
    }


def requirement_delta_since_package(
    db: Session,
    kg: KnowledgeRepository,
    project: Project,
) -> dict[str, int]:
    commercial = commercial_payload(kg, project)
    since = _parse_iso(str(commercial.get("last_package_sent_at") or ""))
    snapshot = {"new": 0, "needs_clarification": 0, "conflict": 0, "rejected": 0, "superseded": 0}
    delta = {**snapshot}
    reqs = [
        e
        for e in kg.list_entities(project.id, type_="Requirement")
        if e.status != "archived"
    ]
    for req in reqs:
        status = normalize_requirement_status(req.status)
        if status in snapshot:
            snapshot[status] += 1
        if since is None:
            continue
        created = getattr(req, "created_at", None)
        if created is not None:
            created_aware = created if created.tzinfo else created.replace(tzinfo=timezone.utc)
            if created_aware >= since and status == "new":
                delta["new"] += 1
        for row in list_entity_history(db, req.id, project_id=project.id):
            row_at = row.created_at
            if row_at is None:
                continue
            if row_at.tzinfo is None:
                row_at = row_at.replace(tzinfo=timezone.utc)
            if row_at < since:
                continue
            to_st = normalize_requirement_status(row.to_status or "")
            if to_st in delta:
                delta[to_st] += 1
            if row.action == "relation_add" and (row.payload or {}).get("type") == "conflicts_with":
                delta["conflict"] += 1
    return {"snapshot": snapshot, "since_package": delta, "has_baseline": since is not None}


def serialize_thread(db: Session, project: Project) -> list[dict[str, Any]]:
    rows = (
        db.query(Message)
        .filter(Message.project_id == project.id)
        .order_by(Message.created_at.asc())
        .all()
    )
    out = []
    for msg in rows:
        meta = dict(msg.meta or {})
        kind = str(meta.get("kind") or "")
        channel = str(meta.get("channel") or "")
        out.append(
            {
                "id": str(msg.id),
                "role": msg.role,
                "text": msg.text,
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
                "meta_kind": kind,
                "channel": channel,
                "filter": _thread_filter(kind, channel, msg.role),
            }
        )
    return out


def _thread_filter(kind: str, channel: str, role: str) -> str:
    if kind in {"tz_package", "estimate_package", "package_caption", "owner_reply"}:
        return "agreement"
    if channel == "implementation_feedback" or kind in {"mvp_client_review", "mvp_feedback"}:
        return "delivery"
    if role == "owner":
        return "agreement"
    return "other"


def mark_remarks_read(kg: KnowledgeRepository, project: Project) -> None:
    set_commercial(kg, project, {"unread_from_customer": False})


def mark_unread(kg: KnowledgeRepository, project: Project) -> None:
    set_commercial(kg, project, {"unread_from_customer": True})


class PackageSendError(ValueError):
    """TZ+estimate package could not be delivered."""


def send_tz_estimate_package(
    db: Session,
    project: Project,
    *,
    caption: str | None = None,
    fmt: str = "pdf",
) -> dict[str, Any]:
    from core.client_estimate import (
        client_estimate_from_artifact,
        client_estimate_report_from_artifact,
        customer_estimate_view,
    )
    from core.config import get_settings
    from core.estimate import format_hours
    from core.hitl import get_draft_tz
    from core.models import Message, MessageKind
    from core.tz_document import TzExportError, export_client_estimate_file, export_tz_file
    from integrations.telegram.notify import send_customer_telegram_document
    from knowledge.history import record_entity_event

    if project.status not in {
        ProjectStatus.WAITING_CLIENT_ESTIMATE,
        ProjectStatus.WAITING_CUSTOMER,
    }:
        raise PackageSendError(
            f"package can be sent after TZ approve, got {project.status.value}"
        )
    kg = KnowledgeRepository(db)
    draft = get_draft_tz(kg, project.id)
    estimate = client_estimate_from_artifact(draft)
    if estimate is None:
        raise PackageSendError("client estimate is not ready yet")
    try:
        tz_bytes, _tz_media, tz_name = export_tz_file(db, project, fmt)  # type: ignore[arg-type]
        smeta_bytes, _sm_media, smeta_name = export_client_estimate_file(db, project, fmt)  # type: ignore[arg-type]
    except TzExportError as exc:
        raise PackageSendError(str(exc)) from exc

    stored = dict((draft.payload or {}).get("client_estimate") or {}) if draft else {}
    version = int(stored.get("package_version") or 0) + 1
    view = customer_estimate_view(estimate, client_estimate_report_from_artifact(draft)) or {}
    cost_label = view.get("formatted_quoted_cost") or view.get("formatted_cost") or "—"
    hours_label = view.get("formatted_hours") or format_hours(estimate.hours)
    studio = (get_settings().studio_name or "").strip()
    text = (caption or "").strip() or default_package_caption(
        project,
        cost_label=str(cost_label),
        hours_label=str(hours_label),
        version=version,
        studio=studio,
    )
    chat_id = (project.customer_telegram_id or "").strip()
    first = send_customer_telegram_document(
        chat_id, data=tz_bytes, filename=tz_name, caption=text
    )
    if not first or not first.get("ok"):
        raise PackageSendError(
            (first or {}).get("description") or "не удалось отправить ТЗ"
        )
    second = send_customer_telegram_document(
        chat_id, data=smeta_bytes, filename=smeta_name, caption=f"Смета v{version}"
    )
    if not second or not second.get("ok"):
        raise PackageSendError(
            (second or {}).get("description") or "ТЗ ушло, смета не отправилась — повторите"
        )

    now = _now_iso()
    events = [ev for ev in (stored.get("package_events") or []) if isinstance(ev, dict)]
    events.append({"kind": "sent", "version": version, "at": now})
    stored["package_version"] = version
    stored["package_events"] = events
    stored["quote_status"] = "sent"
    stored["status"] = "pending"
    payload = dict(draft.payload or {})
    payload["client_estimate"] = stored
    kg.update_entity(draft, payload=payload)
    set_commercial(
        kg,
        project,
        {
            "negotiation": True,
            "reopen_discovery": False,
            "last_package_sent_at": now,
            "package_version": version,
        },
    )
    snapshot_tz_at_gate(db, kg, project, gate="agreement", version=version)
    record_entity_event(
        db,
        project_id=project.id,
        entity_id=draft.id,
        actor="console",
        action="updated",
        payload={"kind": "package_sent", "version": version},
    )
    db.add(
        Message(
            project_id=project.id,
            kind=MessageKind.SYSTEM,
            role="assistant",
            text=text,
            meta={"kind": "package_caption", "package_version": version},
        )
    )
    db.add(
        Message(
            project_id=project.id,
            kind=MessageKind.SYSTEM,
            role="assistant",
            text=f"ТЗ проекта, пакет v{version}",
            meta={"kind": "tz_package", "package_version": version, "filename": tz_name},
        )
    )
    db.add(
        Message(
            project_id=project.id,
            kind=MessageKind.SYSTEM,
            role="assistant",
            text=f"Смета, пакет v{version}",
            meta={
                "kind": "estimate_package",
                "package_version": version,
                "filename": smeta_name,
            },
        )
    )
    db.flush()
    return {
        "ok": True,
        "package_version": version,
        "caption": text,
        "client_estimate": customer_estimate_view(
            client_estimate_from_artifact(draft),
            client_estimate_report_from_artifact(draft),
        ),
    }


def post_owner_reply(db: Session, project: Project, text: str) -> dict[str, Any]:
    from core.models import Message, MessageKind
    from integrations.telegram.notify import send_customer_telegram

    body = (text or "").strip()
    if not body:
        raise PackageSendError("empty reply")
    kg = KnowledgeRepository(db)
    commercial = commercial_payload(kg, project)
    if project.status in {ProjectStatus.NEW, ProjectStatus.INTERVIEW, ProjectStatus.ANALYZING}:
        if not commercial.get("negotiation"):
            raise PackageSendError("owner reply is for package or MVP remarks, not live interview")
    db.add(
        Message(
            project_id=project.id,
            kind=MessageKind.TEXT,
            role="owner",
            text=body,
            meta={"kind": "owner_reply"},
        )
    )
    set_commercial(kg, project, {"unread_from_customer": False})
    db.flush()
    chat_id = (project.customer_telegram_id or "").strip()
    if chat_id:
        send_customer_telegram(
            chat_id, f"Сообщение по проекту «{project.name}»:\n\n{body}"
        )
    return {"ok": True, "text": body}


def requirement_snapshot(kg: KnowledgeRepository, project: Project) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ent in kg.list_entities(project.id, type_="Requirement"):
        if ent.status == "archived":
            continue
        payload = dict(ent.payload or {})
        rows.append(
            {
                "id": str(ent.id),
                "description": str(payload.get("description") or ent.name or ""),
                "status": normalize_requirement_status(ent.status),
                "topic_id": str(payload.get("topic_id") or ""),
                "priority": str(payload.get("priority") or ""),
            }
        )
    return rows


def snapshot_tz_at_gate(
    db: Session,
    kg: KnowledgeRepository,
    project: Project,
    *,
    gate: str | None = None,
    version: int | None = None,
) -> str:
    from core.tz_document import compose_tz_markdown

    pipe = derive_pipeline(db, kg, project)
    key_gate = gate or str(pipe.get("gate") or "new_project")
    if key_gate not in SPINE:
        key_gate = "new_project"
    snap_key = f"{key_gate}:v{version}" if version else key_gate
    commercial = commercial_payload(kg, project)
    snaps = dict(commercial.get("tz_snapshots") or {})
    snaps[snap_key] = {
        "at": _now_iso(),
        "gate": key_gate,
        "version": version,
        "project_status": project.status.value,
        "markdown": compose_tz_markdown(db, project),
        "requirements": requirement_snapshot(kg, project),
    }
    set_commercial(kg, project, {"tz_snapshots": snaps})
    return snap_key


def _requirement_diff(
    old_rows: list[dict[str, Any]], new_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    old_by = {str(r.get("id")): r for r in old_rows}
    new_by = {str(r.get("id")): r for r in new_rows}
    added = [r for i, r in new_by.items() if i not in old_by]
    removed = [r for i, r in old_by.items() if i not in new_by]
    changed = []
    for i, now in new_by.items():
        was = old_by.get(i)
        if not was:
            continue
        if (was.get("description") != now.get("description")) or (
            was.get("status") != now.get("status")
        ) or (was.get("priority") != now.get("priority")):
            changed.append({"id": i, "from": was, "to": now})
    return {"added": added, "removed": removed, "changed": changed}


def tz_preview(
    db: Session,
    kg: KnowledgeRepository,
    project: Project,
    *,
    gate: str | None = None,
) -> dict[str, Any]:
    from core.tz_document import compose_tz_markdown

    pipe = derive_pipeline(db, kg, project)
    current = str(pipe.get("gate") or "new_project")
    target = (gate or current).strip() or current
    if target not in SPINE:
        raise ValueError(f"unknown pipeline gate: {target}")
    live_md = compose_tz_markdown(db, project)
    live_reqs = requirement_snapshot(kg, project)
    commercial = commercial_payload(kg, project)
    snaps = dict(commercial.get("tz_snapshots") or {})
    stored = snaps.get(target) if isinstance(snaps.get(target), dict) else None
    is_live = target == current
    markdown = live_md if is_live else str((stored or {}).get("markdown") or live_md)
    reqs = live_reqs if is_live else list((stored or {}).get("requirements") or live_reqs)
    has_snapshot = stored is not None
    prev_idx = SPINE.index(target) - 1 if target in SPINE else -1
    prev_gate = SPINE[prev_idx] if prev_idx >= 0 else ""
    baseline = snaps.get(prev_gate) if prev_gate else None
    baseline_reqs = list((baseline or {}).get("requirements") or []) if isinstance(baseline, dict) else []
    compare_from = reqs if not is_live else baseline_reqs
    compare_to = live_reqs
    return {
        "gate": target,
        "gate_label": SPINE_RU.get(target, target),
        "current_gate": current,
        "is_live": is_live,
        "has_snapshot": has_snapshot,
        "at": (stored or {}).get("at") if stored else None,
        "markdown": markdown,
        "diff": _requirement_diff(compare_from, compare_to),
        "spine": [
            {
                "id": sid,
                "label": SPINE_RU[sid],
                "current": sid == current,
                "viewing": sid == target,
                "has_snapshot": sid in snaps,
            }
            for sid in SPINE
        ],
    }


def apply_pipeline_gate(
    db: Session,
    project: Project,
    *,
    gate: str | None = None,
    direction: str | None = None,
    actor: str = "console",
) -> dict[str, Any]:
    kg = KnowledgeRepository(db)
    pipe = derive_pipeline(db, kg, project)
    current = str(pipe.get("gate") or "new_project")
    target = (gate or "").strip()
    if direction:
        idx = SPINE.index(current) if current in SPINE else 0
        if direction == "next":
            idx = min(len(SPINE) - 1, idx + 1)
        elif direction == "prev":
            idx = max(0, idx - 1)
        else:
            raise ValueError("direction must be prev or next")
        target = SPINE[idx]
    if target not in SPINE:
        raise ValueError(f"unknown pipeline gate: {target or '(empty)'}")
    snapshot_tz_at_gate(db, kg, project, gate=current)
    _force_gate_state(kg, project, target)
    snapshot_tz_at_gate(db, kg, project, gate=target)
    ent = project_entity(kg, project)
    if ent is not None:
        from knowledge.history import record_entity_event

        record_entity_event(
            db,
            project_id=project.id,
            entity_id=ent.id,
            actor=actor,
            action="status_change",
            from_status=current,
            to_status=target,
            payload={"kind": "pipeline_gate", "manual": True},
        )
    db.flush()
    return {
        "ok": True,
        "gate": target,
        "gate_label": SPINE_RU.get(target, target),
        "status": project.status.value,
        "pipeline": derive_pipeline(db, kg, project),
    }


def _force_gate_state(kg: KnowledgeRepository, project: Project, gate: str) -> None:
    patch: dict[str, Any] = {"mvp_accepted": False, "reopen_discovery": False}
    if gate == "new_project":
        project.status = ProjectStatus.INTERVIEW
        patch["negotiation"] = False
    elif gate == "tz_review":
        project.status = ProjectStatus.WAITING_OWNER
        patch["negotiation"] = False
    elif gate == "tz_approved":
        project.status = ProjectStatus.WAITING_CLIENT_ESTIMATE
        patch["negotiation"] = False
    elif gate == "agreement":
        project.status = ProjectStatus.WAITING_CLIENT_ESTIMATE
        patch["negotiation"] = True
    elif gate == "mvp":
        project.status = ProjectStatus.READY
        patch["negotiation"] = False
    elif gate == "accepted":
        project.status = ProjectStatus.READY
        patch["mvp_accepted"] = True
        patch["negotiation"] = False
    elif gate == "archived":
        project.status = ProjectStatus.ARCHIVED
        patch["negotiation"] = False
    set_commercial(kg, project, patch)
    ent = project_entity(kg, project)
    if ent is not None:
        payload = dict(ent.payload or {})
        payload["status"] = project.status.value
        kg.update_entity(ent, payload=payload, name=project.name)
