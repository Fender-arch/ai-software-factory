from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from core.estimate import attach_estimate_to_draft
from core.models import (
    Entity,
    Message,
    MessageKind,
    POST_TZ_HOLD_STATUSES,
    Project,
    ProjectStatus,
    TZ_DOWNLOAD_STATUSES,
)
from discovery.artifacts import render_draft_tz
from discovery.closing import (
    closing_ids,
    closing_item_by_id,
    looks_like_file_answer,
    render_closing_prompt,
)
from discovery.fsm import (
    DiscoveryStage,
    parse_stage,
    regress_stage,
    stage_after_project_created,
)
from discovery.literacy import ITLiteracy, infer_literacy
from discovery.quality import (
    MAX_CLARIFY_QUESTIONS,
    ClarifyItem,
    build_clarify_queue,
    clarify_item_by_id,
    evaluate_spec_quality,
    is_underspecified,
    quality_floor_messages,
    render_clarify_prompt,
)
from discovery.substance import design_deadline_override, should_reask
from discovery.adapt import (
    ADAPT_AFTER_TOPIC_IDS,
    adapt_outline,
    adapt_topic_choices,
    infer_already_answered,
)
from discovery.questions import DiscoveryPrompt, build_prompt, first_topic
from discovery.tz_outline import (
    DISCUSS_WITH_DEVELOPER_ID,
    Choice,
    READY_CHOICE,
    OutlinePlan,
    SHAPE_TO_PRODUCT_TYPE,
    SHAPE_TO_TASK_SHAPE,
    SURF_TO_TASK_SHAPE,
    TzTopic,
    choice_as_dict,
    plan_from_state,
    plan_to_state,
    remaining_topics,
    topic_by_id,
)
from knowledge.history import record_entity_event
from knowledge.repository import KnowledgeRepository
from knowledge.traceability import link_derived_from

logger = logging.getLogger(__name__)

_PRODUCT_ALIASES: dict[str, str] = {
    "website": "website",
    "landing": "website",
    "landing page": "website",
    "site": "website",
    "сайт": "website",
    "лендинг": "website",
    "витрин": "website",
    "telegram bot": "telegram_bot",
    "telegram_bot": "telegram_bot",
    "telegram-бот": "telegram_bot",
    "бот": "telegram_bot",
    "bot": "telegram_bot",
    "rest": "rest_service",
    "rest api": "rest_service",
    "rest_service": "rest_service",
    "api": "rest_service",
    "баз данных": "rest_service",
    "база данных": "rest_service",
    "админк": "rest_service",
    "учёт": "rest_service",
    "справочник": "rest_service",
    "интеграц": "rest_service",
    "обмен данными": "rest_service",
    "ai automation": "ai_automation",
    "ai_automation": "ai_automation",
    "automation": "ai_automation",
    "автоматизац": "ai_automation",
    "агент": "ai_automation",
    "ии-агент": "ai_automation",
    "ai agent": "ai_automation",
    "mobile_native": "mobile_native",
    "native app": "mobile_native",
    "native mobile": "mobile_native",
    "ios app": "mobile_native",
    "android app": "mobile_native",
    "iphone app": "mobile_native",
    "мобильное приложение": "mobile_native",
    "нативное приложение": "mobile_native",
    "приложение для android": "mobile_native",
    "приложение для ios": "mobile_native",
    "приложение для iphone": "mobile_native",
}

_TASK_SHAPE_ALIASES: dict[str, tuple[str, ...]] = {
    "telegram_miniapp": (
        "mini app",
        "miniapp",
        "миниап",
        "мини-ап",
        "мини ап",
        "мини-приложение",
        "мини приложение",
    ),
    "database_tool": ("баз данных", "база данных", "админк", "справочник", "ведение базы"),
    "integration": ("интеграц", "обмен данными", "webhook", "синхрон"),
    "ai_agent": ("агент", "ai agent", "ии-агент"),
    "process_automation": ("автоматизац", "ai automation"),
    "mobile_native": (
        "мобильное приложение",
        "нативное приложение",
        "ios app",
        "android app",
    ),
}

_READY_EXACT = frozenset(
    {"ready", "готов", "готова", "готово", "lgtm", "ok for review"}
)
_READY_LEAD_RE = re.compile(
    r"^(?:да[,:\s]+|ок[,:\s]+|хорошо[,:\s]+)?(?:вс[её]\s+)?(ready|готов[оа]?)\b",
    re.I,
)


def is_ready_intent(text: str) -> bool:
    """True when the customer confirms the draft TZ should go to the owner.

    Matches the word «готово» / ready with quotes, ellipsis, or the exclusive
    review chip — not «Нет готовой постановки».
    """
    raw = (text or "").strip().replace("\u00a0", " ")
    if not raw:
        return False
    lowered = raw.lower()
    if "отправить черновик" in lowered or "отправить черновик тз" in lowered:
        return True
    compact = re.sub(r"^[«»\"'„“”]+|[«»\"'„“”]+$", "", lowered).strip()
    compact = re.sub(r"[\s.!?…]+$", "", compact).strip()
    if compact in _READY_EXACT:
        return True
    match = _READY_LEAD_RE.match(compact)
    if not match:
        return False
    rest = compact[match.end() :].strip(" \t.,!?;:…")
    if not rest:
        return True
    return rest[:1] in {"—", "–", "-", ":"}
_GAP_RE = re.compile(r"\b(missing|gap|unclear|contradict|wrong|не хватает|неясно)\b", re.I)
_PAUSE_RE = re.compile(
    r"(?i)^\s*(пауза|приостановить|на паузу|pause|hold)(\s|[—\-.,!]|$)"
    r"|^\s*(приостановим|продолжим позже|остановим интервью)\b"
)
_RESUME_RE = re.compile(r"(?i)^\s*(продолжить|возобновить|resume)\b")
_ESCALATE_REST_RE = re.compile(
    r"(?i)остальн\w*\s+(с\s+разработчик|обсуд)|передайте разработчик|"
    r"escalate remaining|остальное обсудить"
)
_DISCUSS_RE = re.compile(
    r"(?i)обсудить с разработчик|с разработчиком|"
    r"не знаю|без понятия|discuss with (the )?dev"
)
_IDK_RE = re.compile(r"(?i)^\s*(не знаю|хз|без понятия|idk)\s*[.!]?\s*$")
_RECOMMENDED_RE = re.compile(
    r"(?i)^\s*(yes|да|recommended|рекоменд\w*|suggested)\s*[.!]?\s*$"
)
_OWNER_DRAFT_REPLY = (
    "Черновик ТЗ готов и отправлен владельцу на ревью. "
    "Проект переведён в WAITING_OWNER.\n\n"
    "Скачайте тот же черновик в Mini App (Markdown, Word или PDF) — "
    "это документ, который ушёл разработчику."
)
_OWNER_WAITING_REPLY = (
    "Черновик ТЗ у владельца на ревью. Копию можно скачать в Mini App. "
    "Можно прислать уточнение — оно будет зафиксировано."
)


@dataclass
class DiscoveryTurnResult:
    reply_to_customer: str
    stage: DiscoveryStage
    project_status: ProjectStatus
    literacy: ITLiteracy
    extracted_requirement_ids: list[uuid.UUID] = field(default_factory=list)
    open_question_ids: list[uuid.UUID] = field(default_factory=list)
    artifact_id: uuid.UUID | None = None
    next_status: str = ProjectStatus.INTERVIEW.value
    topic_id: str | None = None
    choices: list[dict[str, object]] = field(default_factory=list)
    paused: bool = False
    allow_multiple: bool = False
    tz_available: bool = False
    notify_owner: bool = False


def run_discovery_turn(
    db: Session,
    project: Project,
    customer_text: str,
    *,
    source_message_id: uuid.UUID | None = None,
) -> DiscoveryTurnResult:
    """Deterministic Discovery turn. Advances one TZ topic per substantial answer."""
    kg = KnowledgeRepository(db)
    project_entity = _ensure_project_entity(kg, project)
    state = dict(project_entity.payload or {})

    stage = parse_stage(state.get("discovery_stage"))
    stage = stage_after_project_created(stage)
    literacy = infer_literacy(customer_text, state.get("it_literacy"))
    answered = [str(x) for x in (state.get("answered_topics") or [])]
    escalated = [str(x) for x in (state.get("escalated_topics") or [])]
    done = set(answered) | set(escalated)
    paused = bool(state.get("paused"))
    task_shape = state.get("task_shape")
    topic_id = state.get("topic_id")
    vague_retries: dict[str, int] = {
        str(k): int(v) for k, v in dict(state.get("vague_retries") or {}).items()
    }
    clarify_asked = int(state.get("clarify_asked") or 0)
    clarify_queue: list[str] = [str(x) for x in (state.get("clarify_queue") or [])]
    clarify_current: str | None = state.get("clarify_current")
    clarify_initialized = bool(state.get("clarify_initialized"))
    assumptions: list[str] = [str(x) for x in (state.get("assumptions") or [])]
    clarifications: list[dict[str, str]] = [
        {"q": str(x.get("q", "")), "a": str(x.get("a", "")), "id": str(x.get("id", ""))}
        for x in (state.get("clarifications") or [])
        if isinstance(x, dict)
    ]
    owner_draft_emitted = bool(state.get("owner_draft_emitted"))
    closing_queue: list[str] = [str(x) for x in (state.get("closing_queue") or [])]
    closing_current: str | None = state.get("closing_current")
    closing_initialized = bool(state.get("closing_initialized"))
    plan = plan_from_state(state)
    outline_announced = bool(state.get("outline_announced"))

    text = (customer_text or "").strip()
    extracted_ids: list[uuid.UUID] = []
    open_ids: list[uuid.UUID] = []
    artifact_id: uuid.UUID | None = None

    shape_locked = "product_shape" in answered or "product_shape" in escalated
    if not shape_locked:
        product_type = _detect_product_type(text) or project.product_type
        if product_type and product_type != project.product_type:
            project.product_type = product_type
        detected_shape = _detect_task_shape(text)
        if detected_shape:
            task_shape = detected_shape

    if not topic_id:
        topic_id = first_topic(project.product_type, task_shape, plan=plan).id

    leftover_now = remaining_topics(
        project.product_type,
        task_shape=task_shape,
        done_ids=set(answered) | set(escalated),
        plan=plan,
    )
    if (
        stage == DiscoveryStage.READY_FOR_OWNER
        and leftover_now
        and project.status not in POST_TZ_HOLD_STATUSES
    ):
        # Outline grew or content sections were never asked — resume interview.
        stage = leftover_now[0].stage
        topic_id = leftover_now[0].id

    def persist_and_result(
        *,
        reply: str,
        choices: list[Choice] | None = None,
        current_topic: str | None = topic_id,
        current_stage: DiscoveryStage | None = None,
        paused_now: bool | None = None,
        extra_open: list[uuid.UUID] | None = None,
        extra_req: list[uuid.UUID] | None = None,
        artifact: uuid.UUID | None = None,
        allow_multiple: bool = False,
        notify_owner: bool = False,
    ) -> DiscoveryTurnResult:
        st = current_stage or stage
        is_paused = paused if paused_now is None else paused_now
        if st == DiscoveryStage.READY_FOR_OWNER:
            if project.status not in POST_TZ_HOLD_STATUSES:
                project.status = ProjectStatus.WAITING_OWNER
        elif st == DiscoveryStage.REVIEW:
            project.status = ProjectStatus.ANALYZING
        else:
            project.status = ProjectStatus.WAITING_CUSTOMER
        _persist_state(
            kg,
            project_entity,
            project,
            st,
            literacy,
            topic_id=current_topic,
            answered_topics=answered,
            escalated_topics=escalated,
            task_shape=task_shape,
            paused=is_paused,
            extra={
                "vague_retries": vague_retries,
                "clarify_asked": clarify_asked,
                "clarify_queue": clarify_queue,
                "clarify_current": clarify_current,
                "clarify_initialized": clarify_initialized,
                "assumptions": assumptions,
                "clarifications": clarifications,
                "owner_draft_emitted": owner_draft_emitted,
                "closing_queue": closing_queue,
                "closing_current": closing_current,
                "closing_initialized": closing_initialized,
                "outline_announced": outline_announced,
                **plan_to_state(plan),
            },
        )
        db.flush()
        choice_dicts = [choice_as_dict(c) for c in (choices or [])]
        tz_available = project.status in TZ_DOWNLOAD_STATUSES
        return DiscoveryTurnResult(
            reply_to_customer=reply,
            stage=st,
            project_status=project.status,
            literacy=literacy,
            extracted_requirement_ids=extracted_ids + (extra_req or []),
            open_question_ids=open_ids + (extra_open or []),
            artifact_id=artifact or artifact_id,
            next_status=project.status.value,
            topic_id=current_topic,
            choices=choice_dicts,
            paused=is_paused,
            allow_multiple=allow_multiple,
            tz_available=tz_available,
            notify_owner=bool(notify_owner),
        )

    def prompt_for(
        st: DiscoveryStage,
        *,
        tid: str | None = None,
        done_ids: set[str] | None = None,
        announce: bool = False,
    ) -> DiscoveryPrompt:
        return build_prompt(
            stage=st,
            literacy=literacy,
            product_type=project.product_type,
            task_shape=task_shape,
            topic_id=tid,
            done_ids=done_ids if done_ids is not None else (set(answered) | set(escalated)),
            plan=plan,
            captured_snapshots=_captured_snapshots(kg, project.id),
            announce_outline=announce,
        )

    review_actions = [
        READY_CHOICE,
        Choice("escalate_remaining", "Остальное обсудить с разработчиком", exclusive=True),
        Choice("pause", "Пауза — продолжим позже", exclusive=True),
    ]

    def spec_quality():
        return evaluate_spec_quality(
            requirements=kg.list_entities(project.id, type_="Requirement"),
            open_questions=kg.list_entities(project.id, type_="OpenQuestion"),
            risks=kg.list_entities(project.id, type_="Risk"),
        )

    def defer_remaining_clarifies() -> list[uuid.UUID]:
        nonlocal clarify_queue, clarify_current, assumptions
        created: list[uuid.UUID] = []
        for cid in list(clarify_queue):
            item = clarify_item_by_id(cid)
            if item is None:
                continue
            created.append(
                _escalate_clarify_item(
                    kg,
                    project,
                    item,
                    source_message_id=source_message_id,
                    note="Deferred after clarify quota or customer skip.",
                )
            )
            if item.assumption and item.assumption not in assumptions:
                assumptions.append(item.assumption)
        clarify_queue = []
        clarify_current = None
        return created

    def enter_review(*, prefix: str = "") -> DiscoveryTurnResult:
        nonlocal clarify_queue, clarify_current, clarify_initialized, clarify_asked
        nonlocal closing_queue, closing_current, closing_initialized
        if not clarify_initialized:
            clarify_queue = build_clarify_queue(
                requirements=kg.list_entities(project.id, type_="Requirement"),
                open_questions=kg.list_entities(project.id, type_="OpenQuestion"),
                already_asked=[c["id"] for c in clarifications if c.get("id")],
            )
            clarify_initialized = True
        if clarify_asked >= MAX_CLARIFY_QUESTIONS and clarify_queue:
            extra = defer_remaining_clarifies()
            open_ids.extend(extra)
        if clarify_queue and clarify_asked < MAX_CLARIFY_QUESTIONS:
            clarify_current = clarify_queue[0]
            item = clarify_item_by_id(clarify_current)
            assert item is not None
            body, choices = render_clarify_prompt(item)
            return persist_and_result(
                reply=((prefix + "\n\n").strip() + "\n\n" + body).strip(),
                choices=choices + review_actions,
                current_topic=f"clarify:{item.id}",
                current_stage=DiscoveryStage.REVIEW,
                paused_now=False,
            )
        clarify_current = None
        if not closing_initialized:
            closing_queue = closing_ids()
            closing_initialized = True
        if closing_queue:
            closing_current = closing_queue[0]
            item = closing_item_by_id(closing_current)
            assert item is not None
            body, choices = render_closing_prompt(item)
            return persist_and_result(
                reply=((prefix + "\n\n").strip() + "\n\n" + body).strip(),
                choices=choices + review_actions,
                current_topic=f"closing:{item.id}",
                current_stage=DiscoveryStage.REVIEW,
                paused_now=False,
            )
        closing_current = None
        prompt = prompt_for(DiscoveryStage.REVIEW)
        return persist_and_result(
            reply=((prefix + "\n\n").strip() + "\n\n" + prompt.text).strip()
            if prefix
            else prompt.text,
            choices=prompt.choices,
            current_stage=DiscoveryStage.REVIEW,
            current_topic=None,
            paused_now=False,
        )

    if stage == DiscoveryStage.READY_FOR_OWNER:
        waiting_reply = _OWNER_WAITING_REPLY
        if (
            not text
            or _PAUSE_RE.search(text)
            or is_ready_intent(text)
            or _RESUME_RE.search(text)
        ):
            return persist_and_result(
                reply=waiting_reply,
                current_stage=stage,
                current_topic=topic_id,
            )
        req = _record_requirement(
            kg,
            project=project,
            stage=stage,
            text=text,
            product_type=project.product_type,
            source_message_id=source_message_id,
            topic_id="owner_review_supplement",
        )
        extracted_ids.append(req.id)
        artifact = _refresh_latest_draft_tz(kg, project, literacy=literacy, plan=plan)
        if project.status == ProjectStatus.WAITING_CLIENT_ESTIMATE:
            reply = (
                "Дополнение зафиксировано. Смета по-прежнему ждёт подтверждения "
                "в карточке ниже — «Подтверждаю» или «Нужно обсудить»."
            )
        elif project.status in {ProjectStatus.READY, ProjectStatus.ARCHIVED}:
            reply = "Дополнение зафиксировано."
        else:
            reply = (
                "Дополнение зафиксировано и добавлено к материалам ревью. "
                "Черновик ТЗ по-прежнему у владельца. Копию можно скачать в Mini App."
            )
        return persist_and_result(
            reply=reply,
            current_stage=stage,
            current_topic=topic_id,
            artifact=artifact.id if artifact else None,
        )

    if _PAUSE_RE.search(text) or (text.lower() in {"pause", "пауза"}):
        prompt = prompt_for(stage, tid=topic_id)
        reply = (
            "Интервью на паузе — черновик ТЗ пока не отправляю владельцу.\n\n"
            "Напишите «продолжить», когда будете готовы. "
            f"Сейчас открыт раздел: {prompt.topic_id or stage.value}."
        )
        return persist_and_result(
            reply=reply,
            choices=[Choice("resume", "Продолжить интервью", exclusive=True)],
            paused_now=True,
            current_topic=prompt.topic_id or topic_id,
            current_stage=stage,
        )

    if paused and not _RESUME_RE.search(text) and text:
        # Treat a real answer after pause as resume+answer; only remind if empty.
        pass
    if paused and (_RESUME_RE.search(text) or not text):
        paused = False
        prompt = prompt_for(stage, tid=topic_id)
        prefix = "Продолжаем.\n\n" if _RESUME_RE.search(text) else ""
        return persist_and_result(
            reply=prefix + prompt.text,
            choices=prompt.choices,
            allow_multiple=prompt.multi,
            paused_now=False,
            current_topic=prompt.topic_id,
            current_stage=prompt.stage,
        )

    # DEC-008: LLM interviewer drives the turn. Deterministic intents
    # (pause/resume above; escalate-rest/ready below) stay with the FSM.
    from discovery.llm_interviewer import llm_engine_enabled, run_llm_turn

    if llm_engine_enabled() and (
        not text
        or not (_ESCALATE_REST_RE.search(text) or is_ready_intent(text))
    ):
        try:
            llm_result = run_llm_turn(
                db,
                project,
                text,
                source_message_id=source_message_id,
                llm_json=_llm_json,
            )
        except Exception:
            logger.exception("LLM discovery turn failed; falling back to FSM")
            llm_result = None
        if llm_result is not None:
            return llm_result

    if not text:
        prompt = prompt_for(stage, tid=topic_id)
        return persist_and_result(
            reply=prompt.text or "Расскажите чуть подробнее о вашей идее.",
            choices=prompt.choices,
            allow_multiple=prompt.multi,
            current_topic=prompt.topic_id,
            current_stage=prompt.stage,
        )

    if _ESCALATE_REST_RE.search(text):
        leftover = remaining_topics(
            project.product_type,
            task_shape=task_shape,
            done_ids=set(answered) | set(escalated),
            plan=plan,
        )
        for topic in leftover:
            oid = _escalate_topic(
                kg,
                project,
                topic,
                source_message_id=source_message_id,
                note="Customer asked to hand remaining TZ sections to the developer.",
            )
            open_ids.append(oid)
            escalated.append(topic.id)
        if not clarify_initialized:
            clarify_queue = build_clarify_queue(
                requirements=kg.list_entities(project.id, type_="Requirement"),
                open_questions=kg.list_entities(project.id, type_="OpenQuestion"),
                already_asked=[c["id"] for c in clarifications if c.get("id")],
            )
            clarify_initialized = True
        open_ids.extend(defer_remaining_clarifies())
        closing_queue = []
        closing_current = None
        closing_initialized = True
        notify_owner = False
        if owner_draft_emitted:
            artifact = _refresh_latest_draft_tz(kg, project, literacy=literacy, plan=plan)
            reply = (
                "Оставшиеся разделы зафиксировал как вопросы разработчику "
                "и обновил черновик у владельца. Копию можно скачать в Mini App."
            )
        else:
            artifact = _emit_draft_tz(kg, project, literacy=literacy, plan=plan)
            owner_draft_emitted = True
            notify_owner = True
            reply = (
                "Оставшиеся разделы ТЗ зафиксировал как вопросы разработчику "
                "и отправил черновик владельцу на ревью.\n\n"
                "Скачайте тот же черновик в Mini App (Markdown, Word или PDF)."
            )
        return persist_and_result(
            reply=reply,
            current_stage=DiscoveryStage.READY_FOR_OWNER,
            current_topic=None,
            paused_now=False,
            artifact=artifact.id if artifact else None,
            notify_owner=notify_owner,
        )

    current_topic = topic_by_id(topic_id, plan.extra_topics)
    leftover_now = remaining_topics(
        project.product_type,
        task_shape=task_shape,
        done_ids=set(answered) | set(escalated),
        plan=plan,
    )
    if current_topic is None or current_topic.id not in {t.id for t in leftover_now}:
        current_topic = leftover_now[0] if leftover_now else None

    if is_ready_intent(text):
        leftover = leftover_now
        if leftover:
            prompt = prompt_for(
                leftover[0].stage,
                tid=leftover[0].id,
                done_ids=set(answered) | set(escalated),
            )
            names = "; ".join(t.title_ru for t in leftover)
            reply = (
                "Ещё рано закрывать ТЗ — не покрыты разделы: "
                f"{names}.\n\n"
                "Продолжим текущий вопрос, напишите «пауза», либо "
                "«остальное с разработчиком».\n\n"
                + prompt.text
            )
            return persist_and_result(
                reply=reply,
                choices=prompt.choices,
                allow_multiple=prompt.multi,
                current_topic=prompt.topic_id,
                current_stage=prompt.stage,
                paused_now=False,
            )
        report = spec_quality()
        pending_clarify = bool(
            (clarify_queue and clarify_asked < MAX_CLARIFY_QUESTIONS)
            or (clarify_current and clarify_asked < MAX_CLARIFY_QUESTIONS)
        )
        if not report.ok and pending_clarify:
            names = quality_floor_messages(report)
            prefix = (
                "Ещё рано закрывать ТЗ — не выполнен порог качества: "
                + "; ".join(names)
                + ".\n\nОтветьте на уточнение или напишите «остальное с разработчиком»."
            )
            return enter_review(prefix=prefix)
        if not report.ok:
            names = quality_floor_messages(report)
            prompt = prompt_for(DiscoveryStage.REVIEW)
            return persist_and_result(
                reply=(
                    "Ещё рано закрывать ТЗ — не выполнен порог качества: "
                    + "; ".join(names)
                    + ".\n\nНапишите «остальное с разработчиком», чтобы "
                    "передать остаток владельцу, либо уточните ответ.\n\n"
                    + prompt.text
                ),
                choices=prompt.choices,
                current_stage=DiscoveryStage.REVIEW,
                current_topic=None,
                paused_now=False,
            )
        if pending_clarify:
            open_ids.extend(defer_remaining_clarifies())
        closing_queue = []
        closing_current = None
        closing_initialized = True
        artifact = _emit_draft_tz(kg, project, literacy=literacy, plan=plan)
        owner_draft_emitted = True
        return persist_and_result(
            reply=_OWNER_DRAFT_REPLY,
            current_stage=DiscoveryStage.READY_FOR_OWNER,
            current_topic=None,
            paused_now=False,
            artifact=artifact.id,
            notify_owner=True,
        )

    if stage == DiscoveryStage.REVIEW:
        if _GAP_RE.search(text):
            stage = regress_stage(stage, steps=2)
            open_q = kg.create_entity(
                project_id=project.id,
                type_="OpenQuestion",
                name=text[:80],
                status="open",
                payload={"question": text, "stage": stage.value},
                confidence=0.4,
            )
            open_ids.append(open_q.id)
            _link_message_derived(kg, project, open_q.id, source_message_id)
            prompt = prompt_for(stage)
            reply = "Принято — вернул Discovery назад, чтобы закрыть пробел.\n\n" + prompt.text
            return persist_and_result(
                reply=reply,
                choices=prompt.choices,
                allow_multiple=prompt.multi,
                current_topic=prompt.topic_id,
                current_stage=prompt.stage,
            )

        clarify_id = None
        if str(topic_id or "").startswith("clarify:"):
            clarify_id = str(topic_id).split(":", 1)[1]
        elif clarify_current:
            clarify_id = str(clarify_current)
        item = clarify_item_by_id(clarify_id)
        if item is not None:
            matched, leftover_text = _match_choices(text, list(item.options))
            letter = re.match(r"(?i)^\s*([a-e])(?:[.)]\s*(.*))?$", text.strip())
            if letter and not matched:
                idx = ord(letter.group(1).lower()) - ord("a")
                extra = (letter.group(2) or "").strip()
                if 0 <= idx < len(item.options):
                    matched, leftover_text = [item.options[idx]], extra
            if _RECOMMENDED_RE.search(text) and not matched:
                rec = next((c for c in item.options if c.recommended), None)
                if rec is not None:
                    matched, leftover_text = [rec], ""
            discuss = bool(
                _IDK_RE.search(text) or (_DISCUSS_RE.search(text) and not matched)
            )
            if discuss:
                oid = _escalate_clarify_item(
                    kg,
                    project,
                    item,
                    source_message_id=source_message_id,
                    note=text,
                )
                open_ids.append(oid)
                answer_label = "handed to developer"
            else:
                description = leftover_text or text
                if matched:
                    labels = "; ".join(c.label for c in matched)
                    extra = leftover_text.strip() if leftover_text else ""
                    description = f"{labels}. {extra}".strip() if extra else labels
                req = _record_requirement(
                    kg,
                    project=project,
                    stage=DiscoveryStage.REVIEW,
                    text=description,
                    product_type=project.product_type,
                    source_message_id=source_message_id,
                    topic_id=item.topic_id,
                )
                extracted_ids.append(req.id)
                if item.topic_id not in answered and item.topic_id not in escalated:
                    answered.append(item.topic_id)
                answer_label = description
            clarifications.append(
                {"id": item.id, "q": item.question, "a": answer_label}
            )
            clarify_asked += 1
            clarify_queue = [cid for cid in clarify_queue if cid != item.id]
            clarify_current = None
            return enter_review()

        closing_id = None
        if str(topic_id or "").startswith("closing:"):
            closing_id = str(topic_id).split(":", 1)[1]
        elif closing_current:
            closing_id = str(closing_current)
        closing_item = closing_item_by_id(closing_id)
        if closing_item is not None:
            matched, leftover_text = _match_choices(text, list(closing_item.options))
            letter = re.match(r"(?i)^\s*([a-e])(?:[.)]\s*(.*))?$", text.strip())
            if letter and not matched:
                idx = ord(letter.group(1).lower()) - ord("a")
                extra = (letter.group(2) or "").strip()
                if 0 <= idx < len(closing_item.options):
                    matched, leftover_text = [closing_item.options[idx]], extra
            file_hit = looks_like_file_answer(text)
            skip_ids = {"add_none", "bud_keep", "brief_none"}
            skip = bool(matched) and all(c.id in skip_ids for c in matched) and not (
                leftover_text and leftover_text.strip() not in {c.label for c in matched}
            )
            discuss = bool(
                _IDK_RE.search(text) or (_DISCUSS_RE.search(text) and not matched)
            )
            extra_for_substance = leftover_text or ""
            for choice in matched:
                extra_for_substance = extra_for_substance.replace(choice.label, "")
            extra_for_substance = re.sub(r"\s+", " ", extra_for_substance).strip(" \n\t.;,")
            sufficient_chip = any(c.sufficient for c in matched)
            substance_ok = (
                (not closing_item.needs_substance)
                or skip
                or discuss
                or file_hit
                or sufficient_chip
                or (
                    bool(extra_for_substance)
                    and not is_underspecified(extra_for_substance, has_choice=False)
                )
                or (
                    not matched
                    and not is_underspecified(text, has_choice=False)
                )
            )
            if not substance_ok:
                body, choices = render_closing_prompt(closing_item)
                hint = (
                    "Нужно конкретнее: напишите сумму / дополнение, вставьте текст "
                    "постановки или прикрепите файл кнопкой «Файл».\n\n"
                )
                return persist_and_result(
                    reply=hint + body,
                    choices=choices + review_actions,
                    current_topic=f"closing:{closing_item.id}",
                    current_stage=DiscoveryStage.REVIEW,
                    paused_now=False,
                )
            if not skip and not discuss:
                description = leftover_text or text
                if matched:
                    labels = "; ".join(c.label for c in matched)
                    extra = extra_for_substance
                    if extra and extra.lower() not in {c.label.lower() for c in matched}:
                        description = f"{labels}. {extra}".strip()
                    else:
                        description = labels
                if file_hit:
                    description = leftover_text or text
                req = _record_requirement(
                    kg,
                    project=project,
                    stage=DiscoveryStage.REVIEW,
                    text=description,
                    product_type=project.product_type,
                    source_message_id=source_message_id,
                    topic_id=closing_item.topic_id,
                )
                extracted_ids.append(req.id)
            closing_queue = [cid for cid in closing_queue if cid != closing_item.id]
            closing_current = None
            return enter_review()

        req = _record_requirement(
            kg,
            project=project,
            stage=stage,
            text=text,
            product_type=project.product_type,
            source_message_id=source_message_id,
            topic_id="review_note",
        )
        extracted_ids.append(req.id)
        return enter_review()

    if current_topic is None:
        return enter_review()

    prompt_now = prompt_for(current_topic.stage, tid=current_topic.id)
    matched, leftover_text = _match_choices(text, prompt_now.choices)
    exclusive_hits = [c for c in matched if c.exclusive]
    regular_hits = [c for c in matched if not c.exclusive]
    if exclusive_hits and regular_hits:
        exclusive_hits = []
        matched = regular_hits
    choice = exclusive_hits[0] if exclusive_hits and not regular_hits else (
        regular_hits[0] if len(regular_hits) == 1 else None
    )
    stored_text = leftover_text or text

    if exclusive_hits and exclusive_hits[0].id == "pause" and not regular_hits:
        return persist_and_result(
            reply=(
                "Интервью на паузе — черновик ТЗ пока не отправляю владельцу.\n"
                "Напишите «продолжить», когда будете готовы."
            ),
            choices=[Choice("resume", "Продолжить интервью", exclusive=True)],
            paused_now=True,
            current_topic=current_topic.id,
            current_stage=current_topic.stage,
        )
    if choice and choice.id in {"ready", "escalate_remaining"}:
        # Should be handled above; ignore here.
        pass

    discuss = bool(
        (exclusive_hits and exclusive_hits[0].id == DISCUSS_WITH_DEVELOPER_ID and not regular_hits)
        or _IDK_RE.search(text)
        or (
            _DISCUSS_RE.search(text)
            and not regular_hits
            and (not matched or exclusive_hits)
        )
    )
    if discuss:
        oid = _escalate_topic(
            kg,
            project,
            current_topic,
            source_message_id=source_message_id,
            note=stored_text,
        )
        open_ids.append(oid)
        escalated.append(current_topic.id)
    else:
        for item in regular_hits or matched:
            if item.id in SHAPE_TO_PRODUCT_TYPE:
                project.product_type = SHAPE_TO_PRODUCT_TYPE[item.id]
                task_shape = SHAPE_TO_TASK_SHAPE.get(item.id, task_shape)
            if item.id in SURF_TO_TASK_SHAPE:
                task_shape = SURF_TO_TASK_SHAPE[item.id]
        description = stored_text
        if regular_hits:
            labels = "; ".join(c.label for c in regular_hits)
            extra = leftover_text.strip() if leftover_text else ""
            if extra and extra.lower() not in {c.label.lower() for c in regular_hits}:
                description = f"{labels}. {extra}".strip()
            else:
                description = labels
        hint = should_reask(
            current_topic, regular_hits, leftover_text, description
        )
        if hint:
            retries = int(vague_retries.get(current_topic.id, 0)) + 1
            vague_retries[current_topic.id] = retries
            if retries >= 2:
                oid = _escalate_topic(
                    kg,
                    project,
                    current_topic,
                    source_message_id=source_message_id,
                    note=description,
                )
                open_ids.append(oid)
                escalated.append(current_topic.id)
            else:
                prompt = prompt_for(current_topic.stage, tid=current_topic.id)
                return persist_and_result(
                    reply=(
                        "Нужно конкретнее — этой формулировки недостаточно, "
                        "чтобы закрыть раздел ТЗ. "
                        + hint
                        + "\n\n"
                        + prompt.text
                    ),
                    choices=prompt.choices,
                    allow_multiple=prompt.multi,
                    current_topic=current_topic.id,
                    current_stage=current_topic.stage,
                    paused_now=False,
                )
        else:
            req = _record_requirement(
                kg,
                project=project,
                stage=current_topic.stage,
                text=description,
                product_type=project.product_type,
                source_message_id=source_message_id,
                topic_id=current_topic.id,
            )
            extracted_ids.append(req.id)
            answered.append(current_topic.id)
            if current_topic.id == "timeline":
                override = design_deadline_override(description)
                if override:
                    plan.question_overrides["design_direction"] = override
            if current_topic.id == "risks" and _looks_like_risk(description):
                risk = kg.create_entity(
                    project_id=project.id,
                    type_="Risk",
                    name=description[:80],
                    payload={"description": description, "stage": current_topic.stage.value},
                    confidence=0.5,
                )
                _link_message_derived(kg, project, risk.id, source_message_id)

    done_after = set(answered) | set(escalated)
    announce = False
    should_adapt = current_topic.id in ADAPT_AFTER_TOPIC_IDS or not plan.adapted
    if should_adapt or plan.adapted:
        previous_adapted = plan.adapted
        previous_brief = plan.task_brief
        plan = _refresh_outline_plan(
            kg,
            project,
            task_shape=task_shape,
            previous=plan,
            extra_text=text,
            locked_ids=done_after,
            llm_json=_llm_json if should_adapt else None,
        )
        if plan.adapted and not previous_adapted and not outline_announced:
            announce = True
            outline_announced = True
        elif (
            plan.task_brief
            and plan.task_brief != previous_brief
            and not outline_announced
        ):
            announce = True
            outline_announced = True
        auto_ids, auto_req_ids = _auto_close_inferred_topics(
            kg,
            project,
            plan=plan,
            done_ids=done_after,
            source_message_id=source_message_id,
            task_shape=task_shape,
        )
        extracted_ids.extend(auto_req_ids)
        for tid in auto_ids:
            if tid not in answered:
                answered.append(tid)
        done_after = set(answered) | set(escalated)

    leftover_after = remaining_topics(
        project.product_type,
        task_shape=task_shape,
        done_ids=done_after,
        plan=plan,
    )
    if not leftover_after:
        if owner_draft_emitted:
            artifact = _refresh_latest_draft_tz(kg, project, literacy=literacy, plan=plan)
            return persist_and_result(
                reply=(
                    "Дополнили недостающие разделы и обновили черновик ТЗ. "
                    "Он по-прежнему у владельца на ревью. Копию можно скачать в Mini App."
                ),
                current_stage=DiscoveryStage.READY_FOR_OWNER,
                current_topic=None,
                paused_now=False,
                artifact=artifact.id if artifact else None,
            )
        return enter_review(prefix="Разделы ТЗ покрыты. Проверьте уточнения и подтвердите отправку.")

    nxt = leftover_after[0]
    answers_now = _previous_answers(kg, project.id)
    plan = adapt_topic_choices(
        topic=nxt,
        plan=plan,
        previous_answers=answers_now,
        llm_json=_llm_json if (plan.adapted and not should_adapt) else None,
    )
    prompt = prompt_for(nxt.stage, tid=nxt.id, done_ids=done_after, announce=announce)
    return persist_and_result(
        reply=prompt.text,
        choices=prompt.choices,
        allow_multiple=prompt.multi,
        current_topic=prompt.topic_id,
        current_stage=prompt.stage,
        paused_now=False,
    )


def _requirement_texts(kg: KnowledgeRepository, project_id: uuid.UUID) -> list[str]:
    return list(_previous_answers(kg, project_id).values())


def _previous_answers(kg: KnowledgeRepository, project_id: uuid.UUID) -> dict[str, str]:
    out: dict[str, str] = {}
    for entity in kg.list_entities(project_id, type_="Requirement"):
        if entity.status == "archived":
            continue
        payload = entity.payload or {}
        tid = str(payload.get("topic_id") or "").strip()
        blob = str(payload.get("description") or entity.name or "").strip()
        if tid and blob:
            out[tid] = blob[:400]
    return out


def _captured_snapshots(kg: KnowledgeRepository, project_id: uuid.UUID) -> list[str]:
    return _requirement_texts(kg, project_id)[:3]


def _llm_json(system: str, user: str) -> dict | None:
    from integrations.llm import complete_json

    return complete_json(system, user)


def _refresh_outline_plan(
    kg: KnowledgeRepository,
    project: Project,
    *,
    task_shape: str | None,
    previous: OutlinePlan,
    extra_text: str,
    locked_ids: set[str],
    llm_json=None,
) -> OutlinePlan:
    texts = _requirement_texts(kg, project.id)
    if extra_text:
        texts.append(extra_text)
    name = (project.name or "").strip()
    if len(name) >= 6:
        texts.append(name)
    answers = _previous_answers(kg, project.id)
    return adapt_outline(
        product_type=project.product_type,
        task_shape=task_shape,
        texts=texts,
        previous=previous,
        locked_ids=locked_ids,
        llm_json=llm_json,
        previous_answers=answers,
    )


def _auto_close_inferred_topics(
    kg: KnowledgeRepository,
    project: Project,
    *,
    plan: OutlinePlan,
    done_ids: set[str],
    source_message_id: uuid.UUID | None,
    task_shape: str | None,
) -> tuple[list[str], list[uuid.UUID]]:
    leftover = remaining_topics(
        project.product_type,
        task_shape=task_shape,
        done_ids=done_ids,
        plan=plan,
    )
    inferred = infer_already_answered(
        plan,
        corpus=" ".join(_requirement_texts(kg, project.id)),
        leftover_ids={t.id for t in leftover},
    )
    topic_ids: list[str] = []
    req_ids: list[uuid.UUID] = []
    for topic_id, summary in inferred.items():
        topic = topic_by_id(topic_id, plan.extra_topics)
        if topic is None:
            continue
        req = _record_requirement(
            kg,
            project=project,
            stage=topic.stage,
            text=summary,
            product_type=project.product_type,
            source_message_id=source_message_id,
            topic_id=topic.id,
        )
        topic_ids.append(topic.id)
        req_ids.append(req.id)
    return topic_ids, req_ids


def _unique_choices(choices: list[Choice]) -> list[Choice]:
    seen: set[str] = set()
    out: list[Choice] = []
    for choice in choices:
        if choice.id in seen:
            continue
        seen.add(choice.id)
        out.append(choice)
    return out


def _match_choices(text: str, choices: list[Choice]) -> tuple[list[Choice], str]:
    raw = (text or "").strip()
    if not raw or not choices:
        return [], raw

    first_line, _, rest = raw.partition("\n")
    compact = first_line.strip()
    if re.fullmatch(r"\d{1,2}(?:\s*[,;/]\s*\d{1,2})+", compact):
        picked: list[Choice] = []
        for num in re.findall(r"\d{1,2}", compact):
            idx = int(num) - 1
            if 0 <= idx < len(choices):
                picked.append(choices[idx])
        if picked:
            return _unique_choices(picked), rest.strip()

    numbered = re.match(r"^(\d{1,2})[.)]\s*(.*)$", raw)
    if numbered:
        idx = int(numbered.group(1)) - 1
        extra = (numbered.group(2) or "").strip()
        if 0 <= idx < len(choices):
            return [choices[idx]], extra

    lowered = raw.lower()
    found = [
        choice
        for choice in choices
        if choice.label.lower() == lowered or (
            len(choice.label) >= 12 and choice.label.lower() in lowered
        )
    ]
    if found:
        leftover = raw
        return _unique_choices(found), leftover

    single, extra = _match_choice(raw, choices)
    if single:
        return [single], extra
    return [], raw


def _match_choice(text: str, choices: list[Choice]) -> tuple[Choice | None, str]:
    raw = (text or "").strip()
    if not raw or not choices:
        return None, raw
    numbered = re.match(r"^(\d{1,2})[.)]?\s*(.*)$", raw)
    if numbered:
        idx = int(numbered.group(1)) - 1
        extra = (numbered.group(2) or "").strip()
        if 0 <= idx < len(choices) and (not extra or len(raw) < 180):
            return choices[idx], extra
    lowered = raw.lower()
    for choice in choices:
        label = choice.label.lower()
        if lowered == label or lowered == choice.id.replace("_", " "):
            return choice, ""
        if label in lowered and len(label) >= 12:
            extra = raw
            return choice, extra
    return None, raw


def _escalate_topic(
    kg: KnowledgeRepository,
    project: Project,
    topic: TzTopic,
    *,
    source_message_id: uuid.UUID | None,
    note: str,
) -> uuid.UUID:
    question = (
        f"{topic.title_en}: discuss with developer what to record. "
        f"Customer note: {note[:300]}"
    )
    ent = kg.create_entity(
        project_id=project.id,
        type_="OpenQuestion",
        name=question[:80],
        status="open",
        payload={
            "question": question,
            "topic_id": topic.id,
            "stage": topic.stage.value,
            "escalate_to": "developer",
            "product_type": project.product_type,
        },
        confidence=0.45,
    )
    _link_message_derived(kg, project, ent.id, source_message_id)
    return ent.id


def _escalate_clarify_item(
    kg: KnowledgeRepository,
    project: Project,
    item: ClarifyItem,
    *,
    source_message_id: uuid.UUID | None,
    note: str,
) -> uuid.UUID:
    question = (
        f"Clarify {item.id} ({item.category}): {item.question} "
        f"Customer note: {note[:300]}"
    )
    ent = kg.create_entity(
        project_id=project.id,
        type_="OpenQuestion",
        name=question[:80],
        status="open",
        payload={
            "question": question,
            "topic_id": item.topic_id,
            "clarify_id": item.id,
            "stage": DiscoveryStage.REVIEW.value,
            "escalate_to": "developer",
            "source": "clarify_deferred",
            "product_type": project.product_type,
        },
        confidence=0.45,
    )
    _link_message_derived(kg, project, ent.id, source_message_id)
    return ent.id


def _ensure_project_entity(kg: KnowledgeRepository, project: Project) -> Entity:
    entities = kg.list_entities(project.id, type_="Project")
    if entities:
        return entities[0]
    first = first_topic(project.product_type)
    return kg.create_entity(
        project_id=project.id,
        type_="Project",
        name=project.name,
        payload={
            "status": project.status.value,
            "product_type": project.product_type,
            "discovery_stage": DiscoveryStage.PROJECT_CREATED.value,
            "it_literacy": ITLiteracy.LOW.value,
            "topic_id": first.id,
            "answered_topics": [],
            "escalated_topics": [],
            "paused": False,
        },
    )


def _persist_state(
    kg: KnowledgeRepository,
    project_entity: Entity,
    project: Project,
    stage: DiscoveryStage,
    literacy: ITLiteracy,
    *,
    topic_id: str | None = None,
    answered_topics: list[str] | None = None,
    escalated_topics: list[str] | None = None,
    task_shape: str | None = None,
    paused: bool = False,
    extra: dict | None = None,
) -> None:
    payload = dict(project_entity.payload or {})
    payload.update(
        {
            "status": project.status.value,
            "product_type": project.product_type,
            "discovery_stage": stage.value,
            "it_literacy": literacy.value,
            "topic_id": topic_id,
            "answered_topics": answered_topics or [],
            "escalated_topics": escalated_topics or [],
            "task_shape": task_shape,
            "paused": paused,
        }
    )
    if extra:
        payload.update(extra)
    kg.update_entity(project_entity, payload=payload, name=project.name)


def _detect_product_type(text: str) -> str | None:
    lowered = text.lower()
    for alias in sorted(_PRODUCT_ALIASES, key=len, reverse=True):
        if alias in lowered:
            return _PRODUCT_ALIASES[alias]
    return None


def _detect_task_shape(text: str) -> str | None:
    lowered = text.lower()
    for shape, aliases in _TASK_SHAPE_ALIASES.items():
        if any(a in lowered for a in aliases):
            return shape
    return None


def _record_requirement(
    kg: KnowledgeRepository,
    *,
    project: Project,
    stage: DiscoveryStage,
    text: str,
    product_type: str | None,
    source_message_id: uuid.UUID | None,
    topic_id: str | None = None,
) -> Entity:
    priority = "must" if stage in {
        DiscoveryStage.UNDERSTANDING_IDEA,
        DiscoveryStage.FUNCTIONAL,
        DiscoveryStage.DATA,
    } else "should"
    entity = kg.create_entity(
        project_id=project.id,
        type_="Requirement",
        name=f"{topic_id or stage.value}: {text[:60]}",
        status="new",
        payload={
            "title": topic_id or stage.value,
            "description": text,
            "priority": priority,
            "stage": stage.value,
            "topic_id": topic_id,
            "product_type": product_type,
            "acceptance_criteria": [],
            "author_role": "customer",
            "author_id": project.customer_telegram_id,
        },
        confidence=0.55,
    )
    record_entity_event(
        kg.db,
        project_id=project.id,
        entity_id=entity.id,
        actor="discovery",
        action="created",
        to_status="new",
        payload={"topic_id": topic_id, "stage": stage.value},
    )
    _link_message_derived(kg, project, entity.id, source_message_id)
    return entity


def _link_message_derived(
    kg: KnowledgeRepository,
    project: Project,
    to_entity_id: uuid.UUID,
    source_message_id: uuid.UUID | None,
) -> None:
    if source_message_id is None:
        return
    messages = kg.list_entities(project.id, type_="Message")
    if not messages:
        return
    link_derived_from(kg, project.id, messages[-1].id, to_entity_id)


def _looks_like_risk(text: str) -> bool:
    return bool(
        re.search(
            r"\b(risk|unknown|block|legal|compliance|бюджет|риск|неизвест)\b",
            text,
            re.I,
        )
    )


def _maybe_polish_tz(markdown: str) -> str:
    """Optional LLM narrative pass over the draft TZ (DEC-008)."""
    from discovery.artifacts import polish_draft_tz
    from discovery.llm_interviewer import llm_engine_enabled

    if not llm_engine_enabled():
        return markdown
    try:
        polished = polish_draft_tz(markdown, llm_json=_llm_json)
    except Exception:
        logger.exception("TZ polish failed; keeping raw draft")
        return markdown
    return polished or markdown


def _refresh_latest_draft_tz(
    kg: KnowledgeRepository,
    project: Project,
    *,
    literacy: ITLiteracy,
    plan: OutlinePlan | None = None,
) -> Entity | None:
    """Rewrite the latest draft TZ from KG so owner-review supplements are visible."""
    drafts = [
        e
        for e in kg.list_entities(project.id, type_="Artifact")
        if (e.payload or {}).get("kind") == "draft_tz" and e.status != "archived"
    ]
    if not drafts:
        return _emit_draft_tz(kg, project, literacy=literacy, plan=plan)
    artifact = drafts[-1]
    requirements = kg.list_entities(project.id, type_="Requirement")
    open_questions = kg.list_entities(project.id, type_="OpenQuestion")
    risks = kg.list_entities(project.id, type_="Risk")
    project_entities = kg.list_entities(project.id, type_="Project")
    state = dict(project_entities[0].payload) if project_entities else {}
    markdown = render_draft_tz(
        project,
        requirements=requirements,
        open_questions=open_questions,
        risks=risks,
        literacy=literacy.value,
        discovery_stage=DiscoveryStage.READY_FOR_OWNER.value,
        answered_topics=list(state.get("answered_topics") or []),
        escalated_topics=list(state.get("escalated_topics") or []),
        task_shape=state.get("task_shape"),
        assumptions=list(state.get("assumptions") or []),
        clarifications=list(state.get("clarifications") or []),
        plan=plan or plan_from_state(state),
    )
    markdown = _maybe_polish_tz(markdown)
    payload = dict(artifact.payload or {})
    payload["content"] = markdown
    kg.update_entity(artifact, payload=payload)
    attach_estimate_to_draft(kg, project, artifact)
    return artifact


def _emit_draft_tz(
    kg: KnowledgeRepository,
    project: Project,
    *,
    literacy: ITLiteracy,
    plan: OutlinePlan | None = None,
) -> Entity:
    requirements = kg.list_entities(project.id, type_="Requirement")
    open_questions = kg.list_entities(project.id, type_="OpenQuestion")
    risks = kg.list_entities(project.id, type_="Risk")
    project_entities = kg.list_entities(project.id, type_="Project")
    state = dict(project_entities[0].payload) if project_entities else {}
    markdown = render_draft_tz(
        project,
        requirements=requirements,
        open_questions=open_questions,
        risks=risks,
        literacy=literacy.value,
        discovery_stage=DiscoveryStage.READY_FOR_OWNER.value,
        answered_topics=list(state.get("answered_topics") or []),
        escalated_topics=list(state.get("escalated_topics") or []),
        task_shape=state.get("task_shape"),
        assumptions=list(state.get("assumptions") or []),
        clarifications=list(state.get("clarifications") or []),
        plan=plan or plan_from_state(state),
    )
    markdown = _maybe_polish_tz(markdown)
    artifact = kg.create_entity(
        project_id=project.id,
        type_="Artifact",
        name=f"Draft TZ — {project.name}",
        status="draft",
        payload={
            "kind": "draft_tz",
            "format": "markdown",
            "content": markdown,
        },
        confidence=0.7,
    )
    for req in requirements:
        kg.create_relation(
            project_id=project.id,
            from_entity_id=req.id,
            to_entity_id=artifact.id,
            type_="related_to",
            payload={"role": "included_in_draft_tz"},
        )
    attach_estimate_to_draft(kg, project, artifact)
    return artifact


def latest_customer_text(db: Session, project_id: uuid.UUID) -> tuple[str, uuid.UUID | None]:
    msg = (
        db.query(Message)
        .filter(
            Message.project_id == project_id,
            Message.role == "customer",
            Message.kind.in_([MessageKind.TEXT, MessageKind.VOICE]),
        )
        .order_by(Message.created_at.desc())
        .first()
    )
    if msg is None:
        return "", None
    return msg.text, msg.id
