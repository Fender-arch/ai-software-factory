from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from core.coordinator import AICoordinator, CoordinatorMode, LLMRouter
from core.export import TaskExport, export_tasks
from core.hitl import (
    HitlAction,
    HitlResult,
    apply_hitl_decision,
    owner_review_summary,
)
from core.models import Message, MessageKind, Project, ProjectStatus
from core.planner import PlannerError, run_planner
from discovery.fsm import DiscoveryStage
from discovery.interview import DiscoveryTurnResult, latest_customer_text, run_discovery_turn
from discovery.progress import compute_discovery_progress
from integrations.stt import get_stt_provider
from knowledge.context import ContextBuilder
from knowledge.coverage import evaluate_coverage, mode_exit_checklist
from core.project_files import extract_attachment_text, store_uploaded_file
from knowledge.repository import KnowledgeRepository

logger = logging.getLogger(__name__)


@dataclass
class IngestResult:
    message: Message
    discovery: DiscoveryTurnResult | None
    assistant_message: Message | None = None


def create_project(
    db: Session,
    name: str,
    customer_telegram_id: str | None = None,
    product_type: str | None = None,
) -> Project:
    from discovery.literacy import ITLiteracy
    from discovery.questions import build_prompt, welcome_for_create

    project = Project(
        name=name,
        status=ProjectStatus.WAITING_CUSTOMER,
        customer_telegram_id=customer_telegram_id,
        product_type=product_type,
    )
    db.add(project)
    db.flush()

    stage = DiscoveryStage.UNDERSTANDING_IDEA
    literacy = ITLiteracy.LOW
    prompt = build_prompt(
        stage=stage,
        literacy=literacy,
        product_type=product_type,
    )
    kg = KnowledgeRepository(db)
    kg.create_entity(
        project_id=project.id,
        type_="Project",
        name=name,
        payload={
            "status": project.status.value,
            "product_type": product_type,
            "discovery_stage": prompt.stage.value,
            "it_literacy": literacy.value,
            "topic_id": prompt.topic_id,
            "answered_topics": [],
            "escalated_topics": [],
            "paused": False,
        },
    )

    welcome = welcome_for_create(name)
    first_q = prompt.text
    for text, kind_meta, extra_meta in (
        (welcome, "welcome", {}),
        (
            first_q,
            "discovery_question",
            {
                "topic_id": prompt.topic_id,
                "choices": [
                    {
                        "id": c.id,
                        "label": c.label,
                        "exclusive": bool(c.exclusive),
                    }
                    for c in prompt.choices
                ],
                "allow_multiple": prompt.multi,
            },
        ),
    ):
        if not text:
            continue
        db.add(
            Message(
                project_id=project.id,
                kind=MessageKind.SYSTEM,
                role="assistant",
                text=text,
                meta={
                    "discovery_stage": prompt.stage.value,
                    "it_literacy": literacy.value,
                    "kind": kind_meta,
                    **extra_meta,
                },
            )
        )

    db.commit()
    db.refresh(project)
    return project


def get_project(db: Session, project_id: str | uuid.UUID) -> Project | None:
    try:
        pid = uuid.UUID(str(project_id))
    except ValueError:
        return None
    return db.get(Project, pid)


def list_projects_for_customer(
    db: Session, customer_telegram_id: str
) -> list[Project]:
    from sqlalchemy import select

    tid = (customer_telegram_id or "").strip()
    if not tid:
        return []
    return list(
        db.scalars(
            select(Project)
            .where(Project.customer_telegram_id == tid)
            .order_by(Project.created_at.desc())
        ).all()
    )


def delete_project(
    db: Session,
    project_id: str | uuid.UUID,
    *,
    customer_telegram_id: str | None = None,
) -> uuid.UUID:
    """Hard-delete project and all related messages/entities/relations/tasks."""
    from sqlalchemy import delete as sql_delete

    from core.models import Entity, EntityHistory, Relation, Task

    project = get_project(db, project_id)
    if project is None:
        raise ValueError("project not found")
    assert_project_owner(project, customer_telegram_id)
    # Require ownership id for destructive action (no open delete).
    if not (customer_telegram_id or "").strip():
        raise PermissionError("customer_telegram_id required to delete project")
    if not project.customer_telegram_id:
        raise PermissionError("project has no owner; refuse delete")

    pid = project.id
    # Order: history → relations → entities/messages/tasks → project (SQLite-safe).
    db.execute(sql_delete(EntityHistory).where(EntityHistory.project_id == pid))
    db.execute(sql_delete(Relation).where(Relation.project_id == pid))
    db.execute(sql_delete(Entity).where(Entity.project_id == pid))
    db.execute(sql_delete(Message).where(Message.project_id == pid))
    db.execute(sql_delete(Task).where(Task.project_id == pid))
    db.delete(project)
    db.commit()
    return pid


def assert_project_owner(
    project: Project, customer_telegram_id: str | None
) -> None:
    if not customer_telegram_id:
        return
    if (
        project.customer_telegram_id
        and str(project.customer_telegram_id) != str(customer_telegram_id)
    ):
        raise PermissionError("project not owned by customer")


def list_project_messages(
    db: Session, project_id: str | uuid.UUID
) -> list[Message]:
    from sqlalchemy import select

    project = get_project(db, project_id)
    if project is None:
        raise ValueError("project not found")
    return list(
        db.scalars(
            select(Message)
            .where(Message.project_id == project.id)
            .order_by(Message.created_at.asc())
        ).all()
    )


def get_project_workspace(
    db: Session,
    project_id: str | uuid.UUID,
    *,
    customer_telegram_id: str | None = None,
    mode: str = "create",
) -> dict:
    from discovery.fsm import parse_stage
    from discovery.tz_outline import plan_from_state, remaining_topics

    project = get_project(db, project_id)
    if project is None:
        raise ValueError("project not found")
    assert_project_owner(project, customer_telegram_id)

    kg = KnowledgeRepository(db)
    project_entities = kg.list_entities(project.id, type_="Project")
    state = dict(project_entities[0].payload) if project_entities else {}
    leftover = remaining_topics(
        project.product_type,
        task_shape=state.get("task_shape"),
        done_ids=set(state.get("answered_topics") or [])
        | set(state.get("escalated_topics") or []),
        plan=plan_from_state(state),
    )
    if leftover and project.status == ProjectStatus.WAITING_OWNER:
        turn = run_discovery_turn(db, project, "")
        _store_assistant_reply(db, project, turn)
        db.commit()
        db.refresh(project)
        _maybe_notify_owner_tz_ready(db, project, turn)
        project_entities = kg.list_entities(project.id, type_="Project")
        state = dict(project_entities[0].payload) if project_entities else {}
    stage = parse_stage(state.get("discovery_stage"))
    messages = list_project_messages(db, project.id)
    choices: list[dict] = []
    paused = bool(state.get("paused"))
    allow_multiple = False
    for msg in reversed(messages):
        if msg.role != "assistant":
            continue
        meta = msg.meta or {}
        raw = meta.get("choices") or []
        if isinstance(raw, list) and raw:
            choices = [c for c in raw if isinstance(c, dict) and c.get("label")]
            paused = bool(meta.get("paused", paused))
            allow_multiple = bool(meta.get("allow_multiple", False))
            break

    tz_available = project.status in {ProjectStatus.WAITING_OWNER, ProjectStatus.READY}
    return {
        "project": project,
        "mode": mode,
        "discovery_stage": stage.value,
        "it_literacy": state.get("it_literacy"),
        "messages": messages,
        "discovery_choices": choices,
        "paused": paused,
        "topic_id": state.get("topic_id"),
        "allow_multiple": allow_multiple,
        "tz_available": tz_available,
        "discovery_progress": compute_discovery_progress(project, state),
    }


def submit_project_feedback(
    db: Session,
    project_id: str | uuid.UUID,
    text: str,
    *,
    customer_telegram_id: str | None = None,
):
    from core.feedback import submit_implementation_feedback

    project = get_project(db, project_id)
    if project is None:
        raise ValueError("project not found")
    result = submit_implementation_feedback(
        db,
        project,
        text,
        customer_telegram_id=customer_telegram_id,
    )
    db.commit()
    db.refresh(project)
    return result


def ingest_text_message(
    db: Session,
    project_id: str | uuid.UUID,
    text: str,
    role: str = "customer",
    *,
    run_discovery: bool = True,
) -> IngestResult:
    project = get_project(db, project_id)
    if project is None:
        raise ValueError("project not found")

    message = Message(
        project_id=project.id,
        kind=MessageKind.TEXT,
        role=role,
        text=text,
        meta={},
    )
    db.add(message)
    db.flush()

    kg = KnowledgeRepository(db)
    entity = kg.create_entity(
        project_id=project.id,
        type_="Message",
        name=text[:80] or "message",
        payload={"role": role, "kind": MessageKind.TEXT.value, "text": text},
    )
    projects = kg.list_entities(project.id, type_="Project")
    if projects:
        kg.create_relation(
            project_id=project.id,
            from_entity_id=entity.id,
            to_entity_id=projects[0].id,
            type_="related_to",
        )

    discovery: DiscoveryTurnResult | None = None
    assistant_message: Message | None = None
    if run_discovery and role == "customer":
        discovery = run_discovery_turn(
            db, project, text, source_message_id=message.id
        )
        assistant_message = _store_assistant_reply(db, project, discovery)

    db.commit()
    db.refresh(message)
    if assistant_message is not None:
        db.refresh(assistant_message)
    _maybe_notify_owner_tz_ready(db, project, discovery)
    return IngestResult(
        message=message, discovery=discovery, assistant_message=assistant_message
    )


async def ingest_voice_message(
    db: Session,
    project_id: str | uuid.UUID,
    audio: bytes,
    telegram_file_id: str | None = None,
    filename: str = "voice.ogg",
    role: str = "customer",
    *,
    customer_telegram_id: str | None = None,
    run_discovery: bool = True,
) -> IngestResult:
    stt = get_stt_provider()
    transcript = await stt.transcribe(audio, filename=filename)

    project = get_project(db, project_id)
    if project is None:
        raise ValueError("project not found")
    assert_project_owner(project, customer_telegram_id)

    message = Message(
        project_id=project.id,
        kind=MessageKind.VOICE,
        role=role,
        text=transcript,
        raw_file_id=telegram_file_id,
        meta={"stt_provider": stt.__class__.__name__, "filename": filename},
    )
    db.add(message)
    db.flush()

    kg = KnowledgeRepository(db)
    kg.create_entity(
        project_id=project.id,
        type_="Message",
        name=transcript[:80] or "voice-message",
        payload={
            "role": role,
            "kind": MessageKind.VOICE.value,
            "text": transcript,
            "telegram_file_id": telegram_file_id,
        },
    )

    discovery: DiscoveryTurnResult | None = None
    assistant_message: Message | None = None
    if run_discovery and role == "customer":
        discovery = run_discovery_turn(
            db, project, transcript, source_message_id=message.id
        )
        assistant_message = _store_assistant_reply(db, project, discovery)

    db.commit()
    db.refresh(message)
    if assistant_message is not None:
        db.refresh(assistant_message)
    _maybe_notify_owner_tz_ready(db, project, discovery)
    return IngestResult(
        message=message, discovery=discovery, assistant_message=assistant_message
    )


async def ingest_file_message(
    db: Session,
    project_id: str | uuid.UUID,
    *,
    data: bytes,
    filename: str,
    content_type: str | None = None,
    caption: str | None = None,
    customer_telegram_id: str | None = None,
    run_discovery: bool = True,
) -> IngestResult:
    """Attach a file: text-like content joins Discovery; others are noted in the thread."""
    project = get_project(db, project_id)
    if project is None:
        raise ValueError("project not found")
    assert_project_owner(project, customer_telegram_id)

    name = (filename or "file").strip() or "file"
    extracted = extract_attachment_text(data or b"", name, content_type)

    caption_clean = (caption or "").strip()
    if extracted:
        body = extracted
        if caption_clean:
            body = f"{caption_clean}\n\n{extracted}"
        customer_text = body[:8000]
        note = f"[Файл: {name}]\n{customer_text}"
    else:
        note = f"[Файл прикреплён: {name}]"
        if caption_clean:
            note = f"{note}\n{caption_clean}"
        else:
            note = (
                f"{note}\n"
                "(Содержимое бинарного файла не разобрано автоматически — "
                "кратко опишите, что в нём важно.)"
            )
        customer_text = note

    message = Message(
        project_id=project.id,
        kind=MessageKind.TEXT,
        role="customer",
        text=note[:12000],
        meta={
            "channel": "file_attach",
            "filename": name,
            "content_type": content_type or "",
            "size_bytes": len(data),
            "text_extracted": bool(extracted),
        },
    )
    db.add(message)
    db.flush()

    kg = KnowledgeRepository(db)
    kg.create_entity(
        project_id=project.id,
        type_="Message",
        name=f"file:{name}"[:80],
        payload={
            "role": "customer",
            "kind": MessageKind.TEXT.value,
            "text": note[:2000],
            "filename": name,
            "content_type": content_type or "",
        },
    )
    if data:
        store_uploaded_file(
            db,
            project,
            data=data,
            filename=name,
            content_type=content_type,
            source="customer",
            actor="discovery",
            caption=caption_clean or None,
            source_message_id=message.id,
        )

    discovery: DiscoveryTurnResult | None = None
    assistant_message: Message | None = None
    if run_discovery:
        discovery = run_discovery_turn(
            db, project, customer_text, source_message_id=message.id
        )
        assistant_message = _store_assistant_reply(db, project, discovery)

    db.commit()
    db.refresh(message)
    if assistant_message is not None:
        db.refresh(assistant_message)
    _maybe_notify_owner_tz_ready(db, project, discovery)
    return IngestResult(
        message=message, discovery=discovery, assistant_message=assistant_message
    )


async def run_project_discovery(
    db: Session,
    project_id: str | uuid.UUID,
    coordinator: AICoordinator | None = None,
    *,
    force_turn: bool = False,
) -> dict:
    """Snapshot Discovery state (+ LLM stub). Optionally force another turn.

    Customer message ingest already advances the FSM; this endpoint avoids
    double-advancing unless ``force_turn`` is set or REVIEW still needs a TZ.
    """
    from discovery.fsm import parse_stage
    from discovery.literacy import ITLiteracy, infer_literacy
    from discovery.questions import question_for
    from discovery.tz_outline import plan_from_state

    project = get_project(db, project_id)
    if project is None:
        raise ValueError("project not found")

    kg = KnowledgeRepository(db)
    project_entities = kg.list_entities(project.id, type_="Project")
    state = dict(project_entities[0].payload) if project_entities else {}
    stage = parse_stage(state.get("discovery_stage"))
    literacy = infer_literacy("", state.get("it_literacy"))
    text, message_id = latest_customer_text(db, project.id)

    artifacts = [
        e
        for e in kg.list_entities(project.id, type_="Artifact")
        if (e.payload or {}).get("kind") == "draft_tz"
    ]
    needs_tz = stage == DiscoveryStage.REVIEW and not artifacts

    turn: DiscoveryTurnResult | None = None
    assistant = None
    if force_turn or needs_tz or stage == DiscoveryStage.PROJECT_CREATED:
        turn = run_discovery_turn(
            db,
            project,
            text if text else ("ready" if needs_tz else ""),
            source_message_id=message_id,
        )
        assistant = _store_assistant_reply(db, project, turn)
        stage = turn.stage
        literacy = turn.literacy

    reply = (
        turn.reply_to_customer
        if turn
        else question_for(
            stage,
            literacy,
            project.product_type,
            topic_id=state.get("topic_id"),
            task_shape=state.get("task_shape"),
            done_ids=set(state.get("answered_topics") or [])
            | set(state.get("escalated_topics") or []),
            plan=plan_from_state(state),
        )
        or "Discovery in progress."
    )

    coord = coordinator or AICoordinator(LLMRouter())
    open_questions = kg.list_entities(project.id, type_="OpenQuestion")
    context = ContextBuilder(db).build(
        CoordinatorMode.DISCOVERY,
        project,
        extra={
            "customer_text": text,
            "deterministic_reply": reply,
            "discovery_stage": stage.value,
            "it_literacy": literacy.value
            if isinstance(literacy, ITLiteracy)
            else str(literacy),
        },
    )
    llm_result = await coord.run(CoordinatorMode.DISCOVERY, context=context)

    db.commit()
    if assistant is not None:
        db.refresh(assistant)
    _maybe_notify_owner_tz_ready(db, project, turn)

    artifact_id = turn.artifact_id if turn else (artifacts[-1].id if artifacts else None)
    coverage_report = evaluate_coverage(
        kg, project.id, product_type=project.product_type
    )
    exit_checks = mode_exit_checklist(
        CoordinatorMode.DISCOVERY.value,
        coverage=coverage_report,
        open_question_count=coverage_report.open_question_count,
        has_draft_tz=bool(artifact_id or artifacts),
    )
    coverage = coverage_report.as_dict()
    return {
        "mode": llm_result.mode.value,
        "provider": llm_result.provider,
        "output": {
            "reply_to_customer": reply,
            "extracted": [
                {"type": "Requirement", "id": str(i)}
                for i in (turn.extracted_requirement_ids if turn else [])
            ],
            "open_questions": [
                str(i) for i in (turn.open_question_ids if turn else [])
            ]
            or [str(e.id) for e in open_questions if e.status == "open"],
            "next_status": turn.next_status if turn else project.status.value,
            "discovery_stage": stage.value,
            "it_literacy": literacy.value
            if isinstance(literacy, ITLiteracy)
            else str(literacy),
            "artifact_id": str(artifact_id) if artifact_id else None,
            "coverage": coverage,
            "exit_checklist": exit_checks,
            "llm": llm_result.output,
        },
        "assistant_message_id": str(assistant.id) if assistant else None,
    }


def submit_hitl_decision(
    db: Session,
    project_id: str | uuid.UUID,
    action: HitlAction | str,
    *,
    note: str | None = None,
    actor_telegram_id: str | None = None,
) -> HitlResult:
    project = get_project(db, project_id)
    if project is None:
        raise ValueError("project not found")
    act = HitlAction(action) if not isinstance(action, HitlAction) else action
    result = apply_hitl_decision(
        db,
        project,
        act,
        note=note,
        actor_telegram_id=actor_telegram_id,
    )
    db.commit()
    db.refresh(project)
    return result


def get_owner_review(
    db: Session, project_id: str | uuid.UUID
) -> dict:
    project = get_project(db, project_id)
    if project is None:
        raise ValueError("project not found")
    return owner_review_summary(db, project)


async def run_project_planner(
    db: Session,
    project_id: str | uuid.UUID,
    coordinator: AICoordinator | None = None,
    *,
    force: bool = False,
) -> dict:
    """Run Planner after HITL approval; persist tasks and annotate via LLM stub."""
    project = get_project(db, project_id)
    if project is None:
        raise ValueError("project not found")

    try:
        planned = run_planner(db, project, force=force)
    except PlannerError:
        raise

    coord = coordinator or AICoordinator(LLMRouter())
    context = ContextBuilder(db).build(
        CoordinatorMode.PLANNER,
        project,
        extra={"planned_tasks": planned.tasks},
    )
    llm_result = await coord.run(CoordinatorMode.PLANNER, context=context)

    coverage = evaluate_coverage(
        kg=KnowledgeRepository(db),
        project_id=project.id,
        product_type=project.product_type,
    )
    exit_checks = mode_exit_checklist(
        CoordinatorMode.PLANNER.value,
        coverage=coverage,
        task_count=len(planned.tasks),
    )

    db.commit()
    return {
        "mode": llm_result.mode.value,
        "provider": llm_result.provider,
        "output": {
            "tasks": planned.tasks,
            "task_ids": [str(i) for i in planned.task_ids],
            "entity_ids": [str(i) for i in planned.entity_ids],
            "reused_existing": planned.reused_existing,
            "next_status": project.status.value,
            "exit_checklist": exit_checks,
            "llm": llm_result.output,
        },
    }


def export_project_tasks(
    db: Session,
    project_id: str | uuid.UUID,
    *,
    format: Literal["markdown", "json"] = "markdown",
) -> TaskExport:
    project = get_project(db, project_id)
    if project is None:
        raise ValueError("project not found")
    return export_tasks(db, project, format=format)


def _store_assistant_reply(
    db: Session, project: Project, turn: DiscoveryTurnResult
) -> Message | None:
    if not turn.reply_to_customer:
        return None
    assistant = Message(
        project_id=project.id,
        kind=MessageKind.SYSTEM,
        role="assistant",
        text=turn.reply_to_customer,
        meta={
            "discovery_stage": turn.stage.value,
            "it_literacy": turn.literacy.value,
            "artifact_id": str(turn.artifact_id) if turn.artifact_id else None,
            "topic_id": turn.topic_id,
            "choices": turn.choices,
            "paused": turn.paused,
            "allow_multiple": turn.allow_multiple,
        },
    )
    db.add(assistant)
    db.flush()

    kg = KnowledgeRepository(db)
    kg.create_entity(
        project_id=project.id,
        type_="Message",
        name=turn.reply_to_customer[:80],
        payload={
            "role": "assistant",
            "kind": MessageKind.SYSTEM.value,
            "text": turn.reply_to_customer,
            "discovery_stage": turn.stage.value,
        },
    )
    return assistant


def _maybe_notify_owner_tz_ready(
    db: Session,
    project: Project,
    discovery: DiscoveryTurnResult | None,
) -> None:
    """Notify the studio owner when a new draft TZ is first persisted."""
    if discovery is None or not discovery.notify_owner:
        return
    try:
        from core.estimate import DeliveryEstimate
        from core.hitl import get_draft_tz
        from integrations.telegram.notify import notify_owner_draft_ready
        from knowledge.repository import KnowledgeRepository as Kg

        kg = Kg(db)
        draft = get_draft_tz(kg, project.id)
        estimate = DeliveryEstimate.from_dict(
            (draft.payload or {}).get("estimate") if draft else None
        )
        if estimate is None:
            from core.estimate import estimate_project

            estimate = estimate_project(kg, project)
        notify_owner_draft_ready(project, estimate)
    except Exception:  # noqa: BLE001 — owner DM must not break the customer path
        logger.exception(
            "Failed to notify owner that draft TZ is ready for project %s",
            project.id,
        )
