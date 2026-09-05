"""LLM-driven Discovery turn (DEC-008).

The LLM owns the customer-facing reply: acknowledgement, counter-answers,
the next question, and per-turn choice chips. This module owns the
guarantees: KG writes, coverage gate, quality floor, and chip sanitization.
Any failure returns ``None`` so the caller can fall back to the
deterministic FSM turn.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from sqlalchemy.orm import Session

from core.models import (
    Message,
    POST_TZ_HOLD_STATUSES,
    Project,
    ProjectStatus,
    TZ_DOWNLOAD_STATUSES,
)
from discovery.adapt import ADAPT_AFTER_TOPIC_IDS
from discovery.fsm import DiscoveryStage, parse_stage, stage_after_project_created
from discovery.literacy import ITLiteracy, infer_literacy
from discovery.quality import (
    evaluate_spec_quality,
    is_underspecified,
    quality_floor_messages,
)
from discovery.rephrase import apply_choice_overrides, topic_title
from discovery.tz_outline import (
    DISCUSS_WITH_DEVELOPER_ID,
    Choice,
    READY_CHOICE,
    OutlinePlan,
    choice_as_dict,
    plan_from_state,
    plan_to_state,
    remaining_topics,
    resolve_active_topics,
    topic_by_id,
    with_discuss,
)
from discovery.interview import (
    DiscoveryTurnResult,
    _detect_product_type,
    _detect_task_shape,
    _emit_draft_tz,
    _ensure_project_entity,
    _escalate_topic,
    _link_message_derived,
    _looks_like_risk,
    _persist_state,
    _previous_answers,
    _record_requirement,
    _refresh_latest_draft_tz,
    _refresh_outline_plan,
)
from knowledge.repository import KnowledgeRepository

logger = logging.getLogger(__name__)

_PROMPT_PATH = (
    Path(__file__).resolve().parents[1] / "prompts" / "discovery-interview.md"
)

LlmJsonFn = Callable[[str, str], dict[str, Any] | None]

TRANSCRIPT_LIMIT = 12
MAX_LLM_CHIPS = 5
MAX_CHIP_LABEL = 180
MAX_SUMMARY_LEN = 600
MAX_VAGUE_ATTEMPTS = 2
REVIEW_NOTE_TOPIC_ID = "review_note"

_ALLOWED_ACTIONS = {"continue", "review", "ready_for_owner", "pause"}
_RESERVED_CHIP_IDS = {
    DISCUSS_WITH_DEVELOPER_ID,
    "ready",
    "escalate_remaining",
    "pause",
    "resume",
}
_CHIP_ID_RE = re.compile(r"[^a-z0-9_:]+")

_READY_NOTE_FIRST = (
    "Черновик ТЗ готов и отправлен владельцу на ревью. "
    "Скачать его можно в Mini App (Markdown, Word или PDF)."
)
_READY_NOTE_REFRESH = (
    "Черновик ТЗ обновлён и по-прежнему у владельца на ревью. "
    "Копию можно скачать в Mini App."
)


def llm_engine_enabled() -> bool:
    """DISCOVERY_ENGINE: auto | llm | fsm. Auto = llm when a real provider is set."""
    from core.config import get_settings

    settings = get_settings()
    engine = (getattr(settings, "discovery_engine", "auto") or "auto").strip().lower()
    if engine == "llm":
        return True
    if engine == "fsm":
        return False
    return (settings.llm_provider or "stub").strip().lower() != "stub"


def _load_prompt() -> str:
    try:
        return _PROMPT_PATH.read_text(encoding="utf-8")
    except OSError:
        return (
            "You are the ASF requirements interviewer. Reply in Russian, ask one "
            "focused question from the remaining checklist, capture structured "
            "topic updates. JSON only."
        )


@dataclass
class _Captured:
    topic_id: str
    summary_en: str
    sufficient: bool


@dataclass
class _LlmTurn:
    reply: str
    captured: list[_Captured] = field(default_factory=list)
    escalated: list[str] = field(default_factory=list)
    chips: list[Choice] = field(default_factory=list)
    next_action: str = "continue"


def _slug_chip_id(value: str) -> str:
    slug = _CHIP_ID_RE.sub("_", (value or "").strip().lower()).strip("_")
    return slug[:40]


def _sanitize_chips(raw: object) -> list[Choice]:
    if not isinstance(raw, list):
        return []
    chips: list[Choice] = []
    seen: set[str] = set()
    recommended_used = False
    for item in raw:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip()
        if not label:
            continue
        cid = _slug_chip_id(str(item.get("id") or label))
        if not cid or cid in seen or cid in _RESERVED_CHIP_IDS:
            continue
        seen.add(cid)
        recommended = bool(item.get("recommended")) and not recommended_used
        recommended_used = recommended_used or recommended
        chips.append(
            Choice(id=cid, label=label[:MAX_CHIP_LABEL], recommended=recommended)
        )
        if len(chips) >= MAX_LLM_CHIPS:
            break
    return chips


def _with_ready_chip(choices: list[Choice]) -> list[Choice]:
    """Offer the exclusive «готово» action once TZ coverage is complete."""
    out = [READY_CHOICE]
    for choice in choices:
        if choice.id != READY_CHOICE.id:
            out.append(choice)
    return out


def _parse_turn(raw: dict[str, Any] | None, plan: OutlinePlan) -> _LlmTurn | None:
    if not isinstance(raw, dict):
        return None
    reply = str(raw.get("reply_to_customer") or "").strip()
    if not reply:
        return None

    captured: list[_Captured] = []
    raw_captured = raw.get("captured")
    if isinstance(raw_captured, list):
        for item in raw_captured:
            if not isinstance(item, dict):
                continue
            topic_id = str(item.get("topic_id") or "").strip()
            summary = str(item.get("summary_en") or "").strip()
            if not topic_id or not summary:
                continue
            if topic_id != REVIEW_NOTE_TOPIC_ID and topic_by_id(
                topic_id, plan.extra_topics
            ) is None:
                continue
            captured.append(
                _Captured(
                    topic_id=topic_id,
                    summary_en=summary[:MAX_SUMMARY_LEN],
                    sufficient=item.get("sufficient", True) is not False,
                )
            )

    escalated: list[str] = []
    raw_escalated = raw.get("escalated")
    if isinstance(raw_escalated, list):
        for item in raw_escalated:
            topic_id = str(item).strip()
            if topic_id and topic_by_id(topic_id, plan.extra_topics) is not None:
                escalated.append(topic_id)

    action = str(raw.get("next_action") or "continue").strip().lower()
    if action not in _ALLOWED_ACTIONS:
        action = "continue"

    return _LlmTurn(
        reply=reply,
        captured=captured,
        escalated=escalated,
        chips=_sanitize_chips(raw.get("chips")),
        next_action=action,
    )


def _transcript(db: Session, project_id: uuid.UUID) -> list[dict[str, str]]:
    rows = (
        db.query(Message)
        .filter(Message.project_id == project_id)
        .order_by(Message.created_at.desc())
        .limit(TRANSCRIPT_LIMIT)
        .all()
    )
    out: list[dict[str, str]] = []
    for msg in reversed(rows):
        text = (msg.text or "").strip()
        if not text:
            continue
        out.append({"role": msg.role, "text": text[:600]})
    return out


def _topic_checklist(
    kg: KnowledgeRepository,
    project: Project,
    *,
    plan: OutlinePlan,
    answered: list[str],
    escalated: list[str],
    task_shape: str | None,
) -> list[dict[str, Any]]:
    answers = _previous_answers(kg, project.id)
    topics = resolve_active_topics(
        project.product_type, task_shape=task_shape, plan=plan
    )
    out: list[dict[str, Any]] = []
    for topic in topics:
        if topic.id in answered:
            status = "done"
        elif topic.id in escalated:
            status = "escalated"
        else:
            status = "remaining"
        hints: list[str] = []
        if status == "remaining":
            hints = [c.label for c in apply_choice_overrides(topic, plan)[:4]]
        out.append(
            {
                "id": topic.id,
                "title_ru": topic_title(topic, plan),
                "status": status,
                "captured": answers.get(topic.id, "")[:200],
                "needs_substance": topic.needs_substance,
                "option_hints": hints,
            }
        )
    return out


def _spec_floor_missing(kg: KnowledgeRepository, project: Project) -> list[str]:
    report = evaluate_spec_quality(
        requirements=kg.list_entities(project.id, type_="Requirement"),
        open_questions=kg.list_entities(project.id, type_="OpenQuestion"),
        risks=kg.list_entities(project.id, type_="Risk"),
    )
    if report.ok:
        return []
    return quality_floor_messages(report)


def run_llm_turn(
    db: Session,
    project: Project,
    customer_text: str,
    *,
    source_message_id: uuid.UUID | None = None,
    llm_json: LlmJsonFn | None = None,
) -> DiscoveryTurnResult | None:
    """One LLM-driven Discovery turn. None means: fall back to the FSM path."""
    if llm_json is None:
        from integrations.llm import complete_json

        llm_json = complete_json

    kg = KnowledgeRepository(db)
    project_entity = _ensure_project_entity(kg, project)
    state = dict(project_entity.payload or {})

    stage = parse_stage(state.get("discovery_stage"))
    stage = stage_after_project_created(stage)
    text = (customer_text or "").strip()
    literacy = infer_literacy(text, state.get("it_literacy"))
    answered = [str(x) for x in (state.get("answered_topics") or [])]
    escalated = [str(x) for x in (state.get("escalated_topics") or [])]
    task_shape = state.get("task_shape")
    vague_retries: dict[str, int] = {
        str(k): int(v) for k, v in dict(state.get("vague_retries") or {}).items()
    }
    owner_draft_emitted = bool(state.get("owner_draft_emitted"))
    plan = plan_from_state(state)

    shape_locked = "product_shape" in answered or "product_shape" in escalated
    if not shape_locked and text:
        product_type = _detect_product_type(text) or project.product_type
        if product_type and product_type != project.product_type:
            project.product_type = product_type
        detected_shape = _detect_task_shape(text)
        if detected_shape:
            task_shape = detected_shape

    plan = _refresh_outline_plan(
        kg,
        project,
        task_shape=task_shape,
        previous=plan,
        extra_text=text,
        locked_ids=set(answered) | set(escalated),
        llm_json=llm_json if not plan.adapted else None,
    )

    context = {
        "task_brief": plan.task_brief,
        "product_type": project.product_type,
        "task_shape": task_shape,
        "it_literacy": literacy.value,
        "stage": stage.value,
        "transcript": _transcript(db, project.id),
        "topics": _topic_checklist(
            kg,
            project,
            plan=plan,
            answered=answered,
            escalated=escalated,
            task_shape=task_shape,
        ),
        "quality_floor": _spec_floor_missing(kg, project),
        "customer_text": text,
    }
    try:
        raw = llm_json(_load_prompt(), json.dumps(context, ensure_ascii=False))
    except Exception:
        logger.exception("LLM interview call failed; falling back to FSM")
        return None
    turn = _parse_turn(raw, plan)
    if turn is None:
        logger.warning("LLM interview returned invalid JSON; falling back to FSM")
        return None

    extracted_ids: list[uuid.UUID] = []
    open_ids: list[uuid.UUID] = []
    done = set(answered) | set(escalated)

    for item in turn.captured:
        if item.topic_id == REVIEW_NOTE_TOPIC_ID:
            req = _record_requirement(
                kg,
                project=project,
                stage=stage,
                text=item.summary_en,
                product_type=project.product_type,
                source_message_id=source_message_id,
                topic_id=REVIEW_NOTE_TOPIC_ID,
            )
            extracted_ids.append(req.id)
            continue
        topic = topic_by_id(item.topic_id, plan.extra_topics)
        if topic is None or topic.id in done:
            continue
        substance_gap = topic.needs_substance and is_underspecified(item.summary_en)
        if item.sufficient and not substance_gap:
            req = _record_requirement(
                kg,
                project=project,
                stage=topic.stage,
                text=item.summary_en,
                product_type=project.product_type,
                source_message_id=source_message_id,
                topic_id=topic.id,
            )
            extracted_ids.append(req.id)
            answered.append(topic.id)
            done.add(topic.id)
            if topic.id == "risks" and _looks_like_risk(item.summary_en):
                risk = kg.create_entity(
                    project_id=project.id,
                    type_="Risk",
                    name=item.summary_en[:80],
                    payload={
                        "description": item.summary_en,
                        "stage": topic.stage.value,
                    },
                    confidence=0.5,
                )
                _link_message_derived(kg, project, risk.id, source_message_id)
        else:
            retries = int(vague_retries.get(topic.id, 0)) + 1
            vague_retries[topic.id] = retries
            if retries >= MAX_VAGUE_ATTEMPTS:
                oid = _escalate_topic(
                    kg,
                    project,
                    topic,
                    source_message_id=source_message_id,
                    note=item.summary_en or text,
                )
                open_ids.append(oid)
                escalated.append(topic.id)
                done.add(topic.id)

    for topic_id in turn.escalated:
        topic = topic_by_id(topic_id, plan.extra_topics)
        if topic is None or topic_id in done:
            continue
        oid = _escalate_topic(
            kg,
            project,
            topic,
            source_message_id=source_message_id,
            note=text,
        )
        open_ids.append(oid)
        escalated.append(topic_id)
        done.add(topic_id)

    captured_ids = {c.topic_id for c in turn.captured}
    if captured_ids & set(ADAPT_AFTER_TOPIC_IDS):
        plan = _refresh_outline_plan(
            kg,
            project,
            task_shape=task_shape,
            previous=plan,
            extra_text="",
            locked_ids=done,
            llm_json=llm_json,
        )

    leftover = remaining_topics(
        project.product_type,
        task_shape=task_shape,
        done_ids=done,
        plan=plan,
    )

    paused = False
    artifact_id: uuid.UUID | None = None
    notify_owner = False
    reply = turn.reply
    action = turn.next_action

    if action == "pause":
        paused = True
        choices: list[Choice] = [
            Choice("resume", "Продолжить интервью", exclusive=True)
        ]
    elif action in {"ready_for_owner", "review"} and not leftover:
        floor_missing = _spec_floor_missing(kg, project)
        if action == "ready_for_owner" and not floor_missing:
            if owner_draft_emitted:
                artifact = _refresh_latest_draft_tz(kg, project, literacy=literacy, plan=plan)
                note = _READY_NOTE_REFRESH
            else:
                artifact = _emit_draft_tz(kg, project, literacy=literacy, plan=plan)
                owner_draft_emitted = True
                notify_owner = True
                note = _READY_NOTE_FIRST
            artifact_id = artifact.id if artifact else None
            stage = DiscoveryStage.READY_FOR_OWNER
            reply = f"{reply}\n\n{note}"
            choices = []
        else:
            stage = DiscoveryStage.REVIEW
            if action == "ready_for_owner" and floor_missing:
                reply = (
                    f"{reply}\n\nПрежде чем закрыть черновик, уточним: "
                    + "; ".join(floor_missing)
                    + "."
                )
            choices = _with_ready_chip(with_discuss(turn.chips))
    else:
        if action in {"ready_for_owner", "review"} and leftover:
            names = "; ".join(topic_title(t, plan) for t in leftover[:8])
            reply = (
                f"{reply}\n\nЧтобы закрыть черновик, осталось пройти разделы: "
                f"{names}."
            )
        if leftover and project.status not in POST_TZ_HOLD_STATUSES:
            stage = leftover[0].stage
        choices = with_discuss(turn.chips)
        if not leftover:
            choices = _with_ready_chip(choices)
        elif not turn.chips:
            choices = with_discuss(apply_choice_overrides(leftover[0], plan))

    if project.status in POST_TZ_HOLD_STATUSES:
        pass
    elif stage == DiscoveryStage.READY_FOR_OWNER:
        project.status = ProjectStatus.WAITING_OWNER
    elif stage == DiscoveryStage.REVIEW:
        project.status = ProjectStatus.ANALYZING
    else:
        project.status = ProjectStatus.WAITING_CUSTOMER

    _persist_state(
        kg,
        project_entity,
        project,
        stage,
        literacy,
        topic_id=leftover[0].id if leftover else None,
        answered_topics=answered,
        escalated_topics=escalated,
        task_shape=task_shape,
        paused=paused,
        extra={
            "vague_retries": vague_retries,
            "clarify_asked": int(state.get("clarify_asked") or 0),
            "clarify_queue": [str(x) for x in (state.get("clarify_queue") or [])],
            "clarify_current": state.get("clarify_current"),
            "clarify_initialized": bool(state.get("clarify_initialized")),
            "assumptions": [str(x) for x in (state.get("assumptions") or [])],
            "clarifications": [
                c for c in (state.get("clarifications") or []) if isinstance(c, dict)
            ],
            "owner_draft_emitted": owner_draft_emitted,
            "closing_queue": [str(x) for x in (state.get("closing_queue") or [])],
            "closing_current": state.get("closing_current"),
            "closing_initialized": bool(state.get("closing_initialized")),
            "outline_announced": bool(state.get("outline_announced")),
            **plan_to_state(plan),
        },
    )
    db.flush()

    tz_available = project.status in TZ_DOWNLOAD_STATUSES
    return DiscoveryTurnResult(
        reply_to_customer=reply,
        stage=stage,
        project_status=project.status,
        literacy=literacy,
        extracted_requirement_ids=extracted_ids,
        open_question_ids=open_ids,
        artifact_id=artifact_id,
        next_status=project.status.value,
        topic_id=leftover[0].id if leftover else None,
        choices=[choice_as_dict(c) for c in choices],
        paused=paused,
        allow_multiple=False,
        tz_available=tz_available,
        notify_owner=notify_owner,
    )
