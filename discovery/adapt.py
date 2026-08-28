"""Adaptive TZ outline: heuristics plus optional structured LLM proposal.

Deterministic Discovery still owns stage/topic advances and KG writes.
The adapter only chooses which catalog modules apply and which extra
subsections are needed so the interview can implement *this* task.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Callable

from discovery.literacy import ITLiteracy
from discovery.quality import is_underspecified
from discovery.rephrase import (
    LOCKED_OVERRIDE_TOPIC_IDS,
    CTX_OPTION_ID_RE,
    FROZEN_CHOICE_TOPIC_IDS,
    MAX_EXTRA_OPTIONS,
    build_extra_options,
    build_hidden_option_ids,
    build_option_overrides,
    build_question_overrides,
    build_recommended_option_ids,
    build_title_overrides,
    extract_task_brief,
    heuristic_extra_topics,
    merge_extra_options,
)
from discovery.substance import infer_skips_topic
from discovery.tz_outline import (
    CORE_TOPIC_IDS,
    CUSTOM_TOPIC_ID_RE,
    MAX_CUSTOM_TOPICS,
    PUBLIC_PRESENCE_TOPIC_IDS,
    SKIPPABLE_IDS,
    Choice,
    OutlinePlan,
    TzTopic,
    choices_from_raw,
    remaining_topics,
    topic_by_id,
    topic_from_dict,
)

logger = logging.getLogger(__name__)

ALLOWED_CAPABILITIES = frozenset(
    {
        "booking",
        "notifications",
        "catalog",
        "leads",
        "public_presence",
        "voice",
        "admin_data",
        "integration",
        "ai",
        "api_consumers",
        "promotion",
    }
)

CAPABILITY_SIGNALS: dict[str, tuple[str, ...]] = {
    "booking": (
        "запис",
        "слот",
        "календар",
        "booking",
        "расписан",
        "приём к",
        "запись на",
        "time slot",
    ),
    "notifications": (
        "уведом",
        "напоминан",
        "remind",
        "notify",
        "алерт",
    ),
    "catalog": (
        "услуг",
        "каталог",
        "прайс",
        "портфол",
        "офер",
        "кейсы",
        "price list",
    ),
    "leads": ("заявк", "лид", "форм обрат", "оставить контакт", "lead form"),
    "public_presence": (
        "сайт",
        "лендинг",
        "визитк",
        "landing",
        "миниап",
        "mini app",
        "мини-ап",
        "витрина",
        "брошюр",
    ),
    "voice": ("голос", "voice", "whisper", "аудиосообщ", "speech"),
    "admin_data": (
        "учёт",
        "админк",
        "crud",
        "справочник",
        "ведение базы",
        "database tool",
    ),
    "integration": (
        "crm",
        "sheets",
        "интеграц",
        "webhook",
        "обмен",
        "1с",
        "google sheet",
    ),
    "ai": ("агент", "ии-", " llm", "автоматизац", "ai agent", "нейросет"),
    "api_consumers": ("rest", "api ", "эндпоинт", "endpoint", "openapi"),
    "promotion": (
        "seo",
        "продвижен",
        "реклам",
        "метрик",
        "яндекс.веб",
        "контекстн",
        "индексац",
        "webmaster",
    ),
}

DEFAULT_CAPABILITIES: dict[str, frozenset[str]] = {
    "website": frozenset({"public_presence", "leads"}),
    "telegram_bot": frozenset(),
    "rest_service": frozenset({"api_consumers"}),
    "ai_automation": frozenset({"ai"}),
}

ADAPT_AFTER_TOPIC_IDS = frozenset(
    {
        "purpose_problem",
        "product_shape",
        "as_is_process",
        "must_features",
        "primary_scenario",
    }
)

_PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "discovery-outline.md"
_CHOICES_PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "discovery-choices.md"

LlmJsonFn = Callable[[str, str], dict[str, Any] | None]


def detect_capabilities(
    texts: list[str],
    *,
    product_type: str | None,
    task_shape: str | None = None,
) -> frozenset[str]:
    caps: set[str] = set(DEFAULT_CAPABILITIES.get(product_type or "", ()))
    if task_shape == "telegram_miniapp":
        caps.add("public_presence")
        caps.add("leads")
    elif task_shape == "database_tool":
        caps.add("admin_data")
    elif task_shape == "integration":
        caps.add("integration")
    elif task_shape in {"ai_agent", "process_automation"}:
        caps.add("ai")
    blob = " ".join(texts).lower()
    for cap, signals in CAPABILITY_SIGNALS.items():
        if any(signal in blob for signal in signals):
            caps.add(cap)
    if "catalog" in caps or "leads" in caps:
        if product_type in {"website", "telegram_bot"} or task_shape == "telegram_miniapp":
            caps.add("public_presence")
    return frozenset(caps & ALLOWED_CAPABILITIES)


def _slug(value: str) -> str:
    lowered = value.lower()
    lowered = re.sub(r"[^a-z0-9_]+", "_", lowered)
    lowered = re.sub(r"_+", "_", lowered).strip("_")
    return (lowered or "topic")[:32]


def heuristic_plan(
    *,
    product_type: str | None,
    task_shape: str | None,
    texts: list[str],
    previous: OutlinePlan | None = None,
    locked_ids: set[str] | None = None,
    previous_answers: dict[str, str] | None = None,
) -> OutlinePlan:
    """Build an outline plan from type/shape/captured text (no LLM)."""
    answers = dict(previous_answers or {})
    caps = detect_capabilities(texts, product_type=product_type, task_shape=task_shape)
    if previous:
        caps = frozenset(caps | previous.capabilities)
    skipped: set[str] = set()
    reasons: dict[str, str] = {}
    locked = locked_ids or set()

    if "public_presence" not in caps:
        for topic_id in PUBLIC_PRESENCE_TOPIC_IDS:
            if topic_id in locked:
                continue
            if topic_id == "promotion" and "promotion" in caps:
                continue
            skipped.add(topic_id)
            reasons[topic_id] = "No public landing/identity needed for this task."
    if task_shape in {"telegram_miniapp", "telegram_bot"} and task_shape == "telegram_miniapp":
        if "delivery_surface" not in locked:
            skipped.add("delivery_surface")
            reasons["delivery_surface"] = "Mini App surface already chosen."

    extras: list[TzTopic] = list(previous.extra_topics) if previous else []
    brief = extract_task_brief(texts) or (previous.task_brief if previous else "")
    existing_ids = {topic.id for topic in extras} | locked
    extras.extend(
        heuristic_extra_topics(
            capabilities=caps,
            brief=brief,
            existing_ids=existing_ids,
        )
    )
    extras = extras[:MAX_CUSTOM_TOPICS]
    locked_overrides: dict[str, str] = {}
    if previous:
        for key, value in previous.question_overrides.items():
            if key in LOCKED_OVERRIDE_TOPIC_IDS and value.strip():
                locked_overrides[key] = value
    overrides = build_question_overrides(
        brief=brief,
        capabilities=caps,
        task_shape=task_shape,
        previous=locked_overrides,
    )
    hidden = build_hidden_option_ids(
        capabilities=caps,
        product_type=product_type,
        task_shape=task_shape,
        previous=answers,
    )
    if previous:
        for key, value in previous.hidden_option_ids.items():
            hidden[key] = tuple(dict.fromkeys(list(hidden.get(key, ())) + list(value)))
    extra_choices = merge_extra_options(
        previous.extra_options if previous else {},
        build_extra_options(brief=brief, previous=answers, capabilities=caps),
    )
    option_overrides = build_option_overrides(
        brief=brief,
        capabilities=caps,
        product_type=product_type,
        task_shape=task_shape,
        previous=answers,
    )
    if previous:
        merged_opts = {key: dict(value) for key, value in previous.option_overrides.items()}
        for topic_id, labels in option_overrides.items():
            slot = merged_opts.setdefault(topic_id, {})
            slot.update(labels)
        option_overrides = merged_opts
    recommended = build_recommended_option_ids(
        capabilities=caps,
        product_type=product_type,
        task_shape=task_shape,
        previous=answers,
    )
    if previous:
        merged_rec = dict(previous.recommended_option_ids)
        merged_rec.update(recommended)
        recommended = merged_rec
    return OutlinePlan(
        capabilities=caps,
        skipped_ids=tuple(sorted(skipped)),
        extra_topics=tuple(extras),
        adapted=True,
        reasons=reasons,
        question_overrides=overrides,
        option_overrides=option_overrides,
        title_overrides=build_title_overrides(capabilities=caps),
        recommended_option_ids=recommended,
        hidden_option_ids=hidden,
        extra_options=extra_choices,
        task_brief=brief,
    )


def sanitize_llm_proposal(
    proposal: dict[str, Any] | None,
    *,
    heuristic: OutlinePlan,
    locked_ids: set[str],
) -> OutlinePlan:
    """Merge an LLM dict into the heuristic plan with hard guards."""
    plan = OutlinePlan(
        capabilities=heuristic.capabilities,
        skipped_ids=heuristic.skipped_ids,
        extra_topics=heuristic.extra_topics,
        adapted=True,
        reasons=dict(heuristic.reasons),
        question_overrides=dict(heuristic.question_overrides),
        option_overrides={k: dict(v) for k, v in heuristic.option_overrides.items()},
        title_overrides=dict(heuristic.title_overrides),
        recommended_option_ids=dict(heuristic.recommended_option_ids),
        hidden_option_ids=dict(heuristic.hidden_option_ids),
        extra_options={k: tuple(v) for k, v in heuristic.extra_options.items()},
        task_brief=heuristic.task_brief,
    )
    if not proposal:
        return plan

    extra_caps = proposal.get("capabilities") or []
    if isinstance(extra_caps, list):
        plan.capabilities = frozenset(
            plan.capabilities
            | {str(c) for c in extra_caps if str(c) in ALLOWED_CAPABILITIES}
        )

    skipped = set(plan.skipped_ids)
    for topic_id in proposal.get("skip_topic_ids") or []:
        tid = str(topic_id)
        if tid in CORE_TOPIC_IDS or tid in locked_ids:
            continue
        if tid not in SKIPPABLE_IDS and not tid.startswith("custom:"):
            continue
        skipped.add(tid)
        plan.reasons.setdefault(tid, "LLM: not needed to implement this MVP.")
    keep = proposal.get("keep_topic_ids") or []
    if isinstance(keep, list):
        for topic_id in keep:
            skipped.discard(str(topic_id))
    plan.skipped_ids = tuple(sorted(skipped))

    extras = {t.id: t for t in plan.extra_topics}
    for raw in (proposal.get("extra_topics") or [])[:MAX_CUSTOM_TOPICS]:
        if not isinstance(raw, dict):
            continue
        raw = dict(raw)
        raw_id = str(raw.get("id") or "").strip()
        if not CUSTOM_TOPIC_ID_RE.match(raw_id):
            slug = _slug(str(raw.get("title_en") or raw.get("title_ru") or raw_id or "extra"))
            raw["id"] = f"custom:{slug}"
            if not CUSTOM_TOPIC_ID_RE.match(raw["id"]):
                continue
        if raw["id"] in CORE_TOPIC_IDS:
            continue
        raw.setdefault("needs_substance", True)
        topic = topic_from_dict(raw)
        if topic is None:
            continue
        if len(topic.options) < 2:
            topic = TzTopic(
                id=topic.id,
                stage=topic.stage,
                title_ru=topic.title_ru,
                title_en=topic.title_en,
                questions=topic.questions,
                options=topic.options
                + (
                    Choice("write_details", "Сейчас опишу своими словами", sufficient=False),
                    Choice("later_ok", "Пока достаточно общего описания"),
                ),
                keywords=topic.keywords,
                multi=topic.multi,
                needs_substance=topic.needs_substance,
                skippable=False,
                parent_id=topic.parent_id,
                dynamic=True,
            )
        extras[topic.id] = topic
        why = str(raw.get("why") or "").strip()
        if why:
            plan.reasons[topic.id] = why[:240]
    plan.extra_topics = tuple(extras.values())[:MAX_CUSTOM_TOPICS]

    overrides = proposal.get("question_overrides") or {}
    if isinstance(overrides, dict):
        for key, value in overrides.items():
            text = str(value).strip()
            if text and str(key) not in plan.skipped_ids:
                if str(key) in LOCKED_OVERRIDE_TOPIC_IDS and plan.question_overrides.get(
                    str(key)
                ):
                    continue
                plan.question_overrides[str(key)] = text[:600]

    title_ov = proposal.get("title_overrides") or {}
    if isinstance(title_ov, dict):
        for key, value in title_ov.items():
            text = str(value).strip()
            if text:
                plan.title_overrides[str(key)] = text[:80]

    option_ov = proposal.get("option_overrides") or {}
    if isinstance(option_ov, dict):
        for topic_id, labels in option_ov.items():
            if not isinstance(labels, dict):
                continue
            _apply_option_labels(plan, str(topic_id), labels)

    extra_ov = proposal.get("extra_options") or {}
    if isinstance(extra_ov, dict):
        for topic_id, raw_choices in extra_ov.items():
            _merge_topic_extras(plan, str(topic_id), raw_choices)

    hidden_ov = proposal.get("hidden_option_ids") or {}
    if isinstance(hidden_ov, dict):
        for topic_id, raw_ids in hidden_ov.items():
            _merge_hidden_ids(plan, str(topic_id), raw_ids)

    rec = proposal.get("recommended_option_ids") or {}
    if isinstance(rec, dict):
        for key, value in rec.items():
            cid = str(value).strip()
            if cid:
                plan.recommended_option_ids[str(key)] = cid[:40]
    return plan


def _known_choice_ids(plan: OutlinePlan, topic_id: str) -> set[str]:
    topic = topic_by_id(topic_id, plan.extra_topics)
    ids = {c.id for c in topic.options} if topic else set()
    ids |= {c.id for c in plan.extra_options.get(topic_id, ())}
    ids |= set(plan.option_overrides.get(topic_id) or {})
    return ids


def _apply_option_labels(plan: OutlinePlan, topic_id: str, labels: dict) -> None:
    if topic_id in FROZEN_CHOICE_TOPIC_IDS:
        return
    slot = plan.option_overrides.setdefault(topic_id, {})
    known_ids = _known_choice_ids(plan, topic_id)
    for choice_id, label in labels.items():
        text = str(label).strip()
        cid = str(choice_id)
        if text and (not known_ids or cid in known_ids):
            slot[cid] = text[:180]


def _merge_topic_extras(plan: OutlinePlan, topic_id: str, raw_choices: object) -> None:
    if topic_id in FROZEN_CHOICE_TOPIC_IDS:
        return
    parsed = [
        choice
        for choice in choices_from_raw(raw_choices)
        if CTX_OPTION_ID_RE.match(choice.id)
    ]
    if not parsed:
        return
    incoming = {topic_id: tuple(parsed[:MAX_EXTRA_OPTIONS])}
    plan.extra_options = merge_extra_options(plan.extra_options, incoming)


def _merge_hidden_ids(plan: OutlinePlan, topic_id: str, raw_ids: object) -> None:
    if topic_id in FROZEN_CHOICE_TOPIC_IDS:
        return
    if not isinstance(raw_ids, (list, tuple)):
        return
    known = _known_choice_ids(plan, topic_id)
    incoming = [
        str(item)
        for item in raw_ids
        if str(item).strip()
        and str(item) in known
        and str(item) != "discuss_with_developer"
    ]
    if not incoming:
        return
    existing = list(plan.hidden_option_ids.get(topic_id) or ())
    merged = tuple(dict.fromkeys(existing + incoming))
    topic = topic_by_id(topic_id, plan.extra_topics)
    catalog_count = len(topic.options) if topic else 0
    visible = catalog_count - len([cid for cid in merged if topic and any(c.id == cid for c in topic.options)])
    if topic and visible < 2:
        return
    plan.hidden_option_ids[topic_id] = merged


def _remaining_option_catalog(
    heuristic: OutlinePlan,
    *,
    product_type: str | None,
    task_shape: str | None,
    locked_ids: set[str],
) -> list[dict[str, Any]]:
    leftover = remaining_topics(
        product_type,
        task_shape=task_shape,
        done_ids=locked_ids,
        plan=heuristic,
    )
    out: list[dict[str, Any]] = []
    for topic in leftover[:8]:
        labels = heuristic.option_overrides.get(topic.id) or {}
        hidden = set(heuristic.hidden_option_ids.get(topic.id) or ())
        options: list[dict[str, str]] = []
        for choice in topic.options:
            if choice.id in hidden:
                continue
            options.append(
                {"id": choice.id, "label": str(labels.get(choice.id) or choice.label)}
            )
        for extra in heuristic.extra_options.get(topic.id) or ():
            options.append({"id": extra.id, "label": extra.label})
        out.append(
            {
                "id": topic.id,
                "title_ru": topic.title_ru,
                "options": options,
            }
        )
    return out


def _load_outline_prompt() -> str:
    try:
        return _PROMPT_PATH.read_text(encoding="utf-8")
    except OSError:
        return (
            "Propose skip_topic_ids, extra_topics, capabilities, question_overrides "
            "as JSON so the TZ covers what is needed to implement this task."
        )


def _proposal_from_llm(
    *,
    product_type: str | None,
    task_shape: str | None,
    texts: list[str],
    heuristic: OutlinePlan,
    llm_json: LlmJsonFn | None,
    previous_answers: dict[str, str] | None = None,
    locked_ids: set[str] | None = None,
) -> dict[str, Any] | None:
    if llm_json is None:
        return None
    user = json.dumps(
        {
            "product_type": product_type,
            "task_shape": task_shape,
            "task_brief": heuristic.task_brief,
            "captured": texts[:12],
            "previous_answers": previous_answers or {},
            "remaining_topics": _remaining_option_catalog(
                heuristic,
                product_type=product_type,
                task_shape=task_shape,
                locked_ids=locked_ids or set(),
            ),
            "heuristic_capabilities": sorted(heuristic.capabilities),
            "heuristic_skipped": list(heuristic.skipped_ids),
            "core_topic_ids": sorted(CORE_TOPIC_IDS),
            "skippable_ids": sorted(SKIPPABLE_IDS),
        },
        ensure_ascii=False,
    )
    try:
        return llm_json(_load_outline_prompt(), user)
    except Exception:
        logger.exception("TZ outline LLM proposal failed; using heuristic plan")
        return None


def adapt_outline(
    *,
    product_type: str | None,
    task_shape: str | None,
    texts: list[str],
    previous: OutlinePlan | None = None,
    locked_ids: set[str] | None = None,
    llm_json: LlmJsonFn | None = None,
    previous_answers: dict[str, str] | None = None,
) -> OutlinePlan:
    locked = locked_ids or set()
    heuristic = heuristic_plan(
        product_type=product_type,
        task_shape=task_shape,
        texts=texts,
        previous=previous,
        locked_ids=locked,
        previous_answers=previous_answers,
    )
    proposal = _proposal_from_llm(
        product_type=product_type,
        task_shape=task_shape,
        texts=texts,
        heuristic=heuristic,
        llm_json=llm_json,
        previous_answers=previous_answers,
        locked_ids=locked,
    )
    return sanitize_llm_proposal(proposal, heuristic=heuristic, locked_ids=locked)


def _load_choices_prompt() -> str:
    try:
        return _CHOICES_PROMPT_PATH.read_text(encoding="utf-8")
    except OSError:
        return (
            "Rewrite this topic's Russian choice labels using previous_answers. "
            "Keep catalog ids. You may hide irrelevant ids and add ctx:* extras. JSON only."
        )


def adapt_topic_choices(
    *,
    topic: TzTopic,
    plan: OutlinePlan,
    previous_answers: dict[str, str],
    llm_json: LlmJsonFn | None = None,
) -> OutlinePlan:
    """Refine chips for the next question from already captured answers."""
    if topic.id in FROZEN_CHOICE_TOPIC_IDS or llm_json is None:
        return plan
    from discovery.rephrase import apply_choice_overrides

    current = apply_choice_overrides(topic, plan)
    user = json.dumps(
        {
            "topic_id": topic.id,
            "title_ru": topic.title_ru,
            "task_brief": plan.task_brief,
            "previous_answers": previous_answers,
            "current_options": [
                {"id": choice.id, "label": choice.label} for choice in current
            ],
        },
        ensure_ascii=False,
    )
    try:
        proposal = llm_json(_load_choices_prompt(), user)
    except Exception:
        logger.exception("Choice adaptation LLM failed; keeping heuristic chips")
        return plan
    if not isinstance(proposal, dict):
        return plan
    labels = proposal.get("option_overrides") or {}
    if isinstance(labels, dict):
        nested = labels.get(topic.id) if any(k == topic.id for k in labels) else labels
        if isinstance(nested, dict):
            _apply_option_labels(plan, topic.id, nested)
    extras = proposal.get("extra_options")
    if isinstance(extras, dict):
        _merge_topic_extras(plan, topic.id, extras.get(topic.id) or extras.get("options"))
    elif isinstance(extras, list):
        _merge_topic_extras(plan, topic.id, extras)
    hidden = proposal.get("hidden_option_ids")
    if isinstance(hidden, dict):
        _merge_hidden_ids(plan, topic.id, hidden.get(topic.id) or hidden.get("ids"))
    elif isinstance(hidden, list):
        _merge_hidden_ids(plan, topic.id, hidden)
    rec = proposal.get("recommended_option_id") or proposal.get("recommended_option_ids")
    if isinstance(rec, str) and rec.strip():
        plan.recommended_option_ids[topic.id] = rec.strip()[:40]
    elif isinstance(rec, dict):
        cid = str(rec.get(topic.id) or "").strip()
        if cid:
            plan.recommended_option_ids[topic.id] = cid[:40]
    return plan


def infer_already_answered(
    plan: OutlinePlan,
    *,
    corpus: str,
    leftover_ids: set[str],
) -> dict[str, str]:
    """Map skippable leftover topic ids to a short captured summary."""
    blob = (corpus or "").strip()
    if len(blob) < 40 or is_underspecified(blob):
        return {}
    lowered = blob.lower()
    found: dict[str, str] = {}
    from discovery.tz_outline import topic_by_id

    for topic_id in leftover_ids:
        if topic_id in CORE_TOPIC_IDS or topic_id in plan.skipped_ids:
            continue
        topic = topic_by_id(topic_id, plan.extra_topics)
        if topic is None or not topic.skippable:
            continue
        hits = [k for k in topic.keywords if k.lower() in lowered]
        if len(hits) < 2:
            continue
        if infer_skips_topic(topic):
            continue
        found[topic_id] = blob[:280]
    return found


def context_preamble(
    snapshots: list[str],
    *,
    literacy: ITLiteracy | None = None,
) -> str:
    bits = [s.strip() for s in snapshots if s and s.strip()]
    if not bits:
        return ""
    joined = "; ".join(b[:120] for b in bits[:3])
    _ = literacy
    return f"Уже зафиксировали: {joined}.\n\n"
