"""Merge an attached / pasted brief into the TZ outline (DEC-015)."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from core.models import Project
from discovery.fsm import DiscoveryStage
from discovery.literacy import ITLiteracy
from discovery.stakeholders import (
    StakeholderFacts,
    merge_facts,
    parse_stakeholder_text,
    upsert_stakeholders,
)
from discovery.tz_outline import (
    CUSTOM_TOPIC_ID_RE,
    MAX_BRIEF_OVERFLOW_TOPICS,
    MAX_CUSTOM_TOPICS,
    OutlinePlan,
    TzTopic,
    remaining_topics,
    resolve_active_topics,
    topic_by_id,
)
from knowledge.repository import KnowledgeRepository

logger = logging.getLogger(__name__)

LlmJsonFn = Callable[[str, str], dict[str, Any] | None]

_PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "discovery-brief-merge.md"

_HEADING_ALIASES: dict[str, tuple[str, ...]] = {
    "customer_intro": ("заказчик", "контакт", "знакомств", "stakeholder"),
    "have_brief": ("исходн", "постановк", "бриф", "brief"),
    "purpose_problem": ("цель", "проблема", "идея", "purpose", "vision"),
    "product_shape": ("тип решения", "тип продукта", "solution type", "платформ"),
    "as_is_process": ("как сейчас", "as-is", "текущий процесс"),
    "success_mvp": ("успех", "mvp", "критер", "success"),
    "out_of_scope": ("вне объём", "не делаем", "out of scope", "non-goal"),
    "must_features": ("функц", "возможн", "must", "требования к системе"),
    "primary_scenario": ("сценари", "happy path", "пользовательский путь"),
    "acceptance": ("приёмк", "acceptance", "проверка"),
    "timeline": ("срок", "timeline", "дедлайн", "дата"),
    "budget": ("бюджет", "стоимост", "бюджет", "price"),
    "contacts": ("контакт", "телефон", "email"),
    "preferred_contact": ("способ связи", "канал связи"),
    "legal_compliance": ("152-фз", "персональн", "legal", "согласи"),
    "risks": ("риск", "блокер", "неизвест"),
    "roles": ("роль", "ролей", "пользовател"),
    "integrations": ("интеграц", "crm", "webhook"),
    "pages_sections": ("страниц", "экраны", "разделы сайта"),
}

_FILE_PREFIX_RE = re.compile(r"^\[Файл(?: прикреплён)?:[^\]]+\]\s*", re.I)
_HEADING_RE = re.compile(
    r"(?m)^(?:#{1,3}\s+|#{1,3}\s*)(.+?)\s*$|^(\d{1,2})[.)]\s+(.+?)\s*$"
)


@dataclass
class BriefMergeResult:
    filled_topic_ids: list[str] = field(default_factory=list)
    overflow_topic_ids: list[str] = field(default_factory=list)
    empty_topic_ids: list[str] = field(default_factory=list)
    requirement_ids: list[Any] = field(default_factory=list)
    stakeholder: StakeholderFacts = field(default_factory=StakeholderFacts)
    reply_ru: str = ""
    plan: OutlinePlan | None = None


def strip_file_prefix(text: str) -> str:
    raw = (text or "").strip()
    return _FILE_PREFIX_RE.sub("", raw).strip()


def looks_like_brief_document(text: str) -> bool:
    raw = strip_file_prefix(text)
    if len(raw) < 80:
        return False
    if raw.lstrip().startswith("[Файл"):
        return True
    headings = len(re.findall(r"(?m)^#{1,3}\s+\S+", raw))
    if headings >= 1 and len(raw) >= 40:
        return True
    if raw.count("\n") >= 4 and len(raw) >= 200:
        return True
    return False


def _slug_custom(title: str, used: set[str]) -> str:
    from unicodedata import normalize

    folded = normalize("NFKD", title or "")
    trans = {
        "а": "a",
        "б": "b",
        "в": "v",
        "г": "g",
        "д": "d",
        "е": "e",
        "ё": "e",
        "ж": "zh",
        "з": "z",
        "и": "i",
        "й": "i",
        "к": "k",
        "л": "l",
        "м": "m",
        "н": "n",
        "о": "o",
        "п": "p",
        "р": "r",
        "с": "s",
        "т": "t",
        "у": "u",
        "ф": "f",
        "х": "h",
        "ц": "c",
        "ч": "ch",
        "ш": "sh",
        "щ": "sch",
        "ъ": "",
        "ы": "y",
        "ь": "",
        "э": "e",
        "ю": "yu",
        "я": "ya",
    }
    chars: list[str] = []
    for ch in folded.lower():
        if ch in trans:
            chars.append(trans[ch])
        elif ch.isalnum():
            chars.append(ch)
        elif ch in {" ", "-", "_"}:
            chars.append("_")
    slug = re.sub(r"_+", "_", "".join(chars)).strip("_")[:32] or "extra"
    topic_id = f"custom:{slug}"
    if not CUSTOM_TOPIC_ID_RE.match(topic_id):
        topic_id = "custom:overflow"
    n = 2
    base = topic_id
    while topic_id in used:
        topic_id = f"{base[:36]}_{n}"
        if not CUSTOM_TOPIC_ID_RE.match(topic_id):
            topic_id = f"custom:ovf_{n}"
        n += 1
    return topic_id


def _split_sections(text: str) -> list[tuple[str, str]]:
    raw = strip_file_prefix(text)
    if not raw:
        return []
    matches = list(re.finditer(r"(?m)^(?:#{1,3}\s+(.+?)\s*)$", raw))
    if len(matches) < 2:
        numbered = list(re.finditer(r"(?m)^(\d{1,2})[.)]\s+(.+?)\s*$", raw))
        if len(numbered) >= 2:
            sections: list[tuple[str, str]] = []
            for idx, match in enumerate(numbered):
                title = match.group(2).strip()
                start = match.end()
                end = numbered[idx + 1].start() if idx + 1 < len(numbered) else len(raw)
                body = raw[start:end].strip()
                if body or title:
                    sections.append((title, body or title))
            return sections
        return [("", raw)]

    preamble = raw[: matches[0].start()].strip()
    sections: list[tuple[str, str]] = []
    if preamble and len(preamble) >= 40:
        sections.append(("", preamble))
    for idx, match in enumerate(matches):
        title = match.group(1).strip()
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(raw)
        body = raw[start:end].strip()
        if body or title:
            sections.append((title, body or title))
    return sections


def _map_heading(title: str, topics: list[TzTopic]) -> str | None:
    needle = (title or "").strip().lower()
    if not needle:
        return None
    for topic in topics:
        if topic.title_ru.lower() == needle or topic.title_en.lower() == needle:
            return topic.id
        if topic.title_ru.lower() in needle or needle in topic.title_ru.lower():
            return topic.id
    for topic_id, aliases in _HEADING_ALIASES.items():
        if any(alias in needle for alias in aliases):
            if any(t.id == topic_id for t in topics) or topic_id in {
                "customer_intro",
                "have_brief",
                "contacts",
            }:
                return topic_id
    return None


def _keyword_score(blob: str, topic: TzTopic) -> int:
    lowered = blob.lower()
    return sum(1 for key in topic.keywords if key.lower() in lowered)


def heuristic_extract(
    text: str,
    *,
    topics: list[TzTopic],
) -> tuple[dict[str, str], list[tuple[str, str]]]:
    """Map brief text → topic_id→summary and overflow (title, body)."""
    mapped: dict[str, list[str]] = {}
    overflow: list[tuple[str, str]] = []
    known_ids = {t.id for t in topics}
    for title, body in _split_sections(text):
        blob = f"{title}\n{body}".strip()
        if len(blob) < 8:
            continue
        tid = _map_heading(title, topics)
        if tid is None and not title:
            best: TzTopic | None = None
            best_score = 0
            for topic in topics:
                score = _keyword_score(blob, topic)
                if score > best_score:
                    best = topic
                    best_score = score
            if best is not None and best_score >= 2:
                tid = best.id
            elif any(
                token in blob.lower()
                for token in (
                    "нужен",
                    "нужна",
                    "сайт",
                    "лендинг",
                    "бот",
                    "приложение",
                )
            ):
                tid = "purpose_problem"
        if tid and (tid in known_ids or tid in {"customer_intro", "contacts", "have_brief"}):
            mapped.setdefault(tid, []).append(body or blob)
        elif title:
            overflow.append((title, body or blob))
        else:
            leftover_best = None
            leftover_score = 0
            for topic in topics:
                score = _keyword_score(blob, topic)
                if score > leftover_score:
                    leftover_best = topic
                    leftover_score = score
            if leftover_best is not None and leftover_score >= 1:
                mapped.setdefault(leftover_best.id, []).append(blob)
            else:
                overflow.append(("Дополнительно", blob))
    summaries = {tid: "\n\n".join(parts)[:800] for tid, parts in mapped.items()}
    return summaries, overflow


def _load_merge_prompt() -> str:
    try:
        return _PROMPT_PATH.read_text(encoding="utf-8")
    except OSError:
        return (
            "Extract TZ topics from the brief. JSON: captured[], overflow[], "
            "customer{}, organization{}."
        )


def _llm_extract(
    text: str,
    *,
    topics: list[TzTopic],
    llm_json: LlmJsonFn | None,
) -> tuple[dict[str, str], list[tuple[str, str]], StakeholderFacts] | None:
    if llm_json is None:
        return None
    checklist = [
        {"id": t.id, "title_ru": t.title_ru, "title_en": t.title_en}
        for t in topics
    ]
    payload = {"topics": checklist, "brief": strip_file_prefix(text)[:6000]}
    try:
        raw = llm_json(_load_merge_prompt(), json.dumps(payload, ensure_ascii=False))
    except Exception:
        logger.exception("brief-merge LLM failed; using heuristic")
        return None
    if not isinstance(raw, dict):
        return None
    captured: dict[str, str] = {}
    known = {t.id for t in topics}
    for item in raw.get("captured") or []:
        if not isinstance(item, dict):
            continue
        tid = str(item.get("topic_id") or "").strip()
        summary = str(item.get("summary_en") or item.get("summary") or "").strip()
        if tid and summary and (tid in known or tid in {"customer_intro", "contacts"}):
            captured[tid] = summary[:800]
    overflow: list[tuple[str, str]] = []
    for item in raw.get("overflow") or []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title_ru") or item.get("title") or "Extra").strip()
        body = str(item.get("summary_en") or item.get("summary") or "").strip()
        if title and body:
            overflow.append((title, body[:800]))
    cust = raw.get("customer") if isinstance(raw.get("customer"), dict) else {}
    org = raw.get("organization") if isinstance(raw.get("organization"), dict) else {}
    facts = StakeholderFacts(
        display_name=str(cust.get("name") or ""),
        address_as=str(cust.get("address_as") or cust.get("name") or ""),
        role=str(cust.get("role") or ""),
        phone=str(cust.get("phone") or ""),
        email=str(cust.get("email") or ""),
        telegram=str(cust.get("telegram") or ""),
        telegram_chat_ok=bool(cust.get("telegram_chat_ok")),
        organization_name=str(org.get("name") or ""),
        is_individual=bool(org.get("is_individual") or org.get("no_company_name")),
        industry=str(org.get("industry") or ""),
    )
    return captured, overflow, facts


def _make_overflow_topic(title: str, body: str, used: set[str]) -> TzTopic:
    topic_id = _slug_custom(title, used)
    used.add(topic_id)
    q = (
        f"В постановке есть блок «{title}». "
        f"Подтвердите или уточните, что оставить в первой версии."
    )
    return TzTopic(
        id=topic_id,
        stage=DiscoveryStage.FUNCTIONAL,
        title_ru=title[:80],
        title_en=title[:80],
        questions={
            ITLiteracy.LOW: q,
            ITLiteracy.MEDIUM: q,
            ITLiteracy.HIGH: q,
        },
        keywords=tuple(w for w in re.findall(r"[A-Za-zА-Яа-яЁё]{4,}", title.lower())[:6]),
        needs_substance=True,
        skippable=False,
        dynamic=True,
        parent_id=None,
    )


def attach_overflow_topics(plan: OutlinePlan, extras: list[TzTopic]) -> OutlinePlan:
    existing = list(plan.extra_topics)
    seen = {t.id for t in existing}
    for topic in extras:
        if topic.id in seen:
            continue
        existing.append(topic)
        seen.add(topic.id)
    plan.extra_topics = tuple(existing[: MAX_CUSTOM_TOPICS + MAX_BRIEF_OVERFLOW_TOPICS])
    return plan


def _record_topic_requirement(
    kg: KnowledgeRepository,
    project: Project,
    *,
    topic: TzTopic,
    text: str,
    source_message_id,
) -> Any:
    from discovery.interview import _link_message_derived, _record_requirement

    req = _record_requirement(
        kg,
        project=project,
        stage=topic.stage,
        text=text,
        product_type=project.product_type,
        source_message_id=source_message_id,
        topic_id=topic.id,
    )
    _ = _link_message_derived
    return req


def merge_brief_into_graph(
    kg: KnowledgeRepository,
    project: Project,
    text: str,
    *,
    plan: OutlinePlan,
    done_ids: set[str],
    source_message_id=None,
    llm_json: LlmJsonFn | None = None,
    task_shape: str | None = None,
) -> BriefMergeResult:
    """Extract requirements from a brief and merge into outline topics."""
    body = strip_file_prefix(text)
    topics = resolve_active_topics(
        project.product_type, task_shape=task_shape, plan=plan
    )
    extracted = _llm_extract(body, topics=topics, llm_json=llm_json)
    facts = parse_stakeholder_text(body)
    if extracted is None:
        mapped, overflow = heuristic_extract(body, topics=topics)
    else:
        mapped, overflow, llm_facts = extracted
        facts = merge_facts(facts, llm_facts)
        if not mapped and not overflow:
            mapped, overflow = heuristic_extract(body, topics=topics)
    from discovery.stakeholders import facts_from_entities

    facts = merge_facts(facts, facts_from_entities(kg, project.id))

    upsert_stakeholders(kg, project, facts)

    filled: list[str] = []
    req_ids: list[Any] = []
    extras: list[TzTopic] = []
    used = {t.id for t in plan.extra_topics} | {t.id for t in topics}

    for tid, summary in mapped.items():
        topic = topic_by_id(tid, tuple(list(plan.extra_topics) + extras))
        if topic is None:
            continue
        req = _record_topic_requirement(
            kg,
            project,
            topic=topic,
            text=summary,
            source_message_id=source_message_id,
        )
        req_ids.append(req.id)
        if tid not in done_ids:
            filled.append(tid)

    for title, chunk in overflow:
        topic = _make_overflow_topic(title, chunk, used)
        extras.append(topic)
        req = _record_topic_requirement(
            kg,
            project,
            topic=topic,
            text=chunk,
            source_message_id=source_message_id,
        )
        req_ids.append(req.id)
        filled.append(topic.id)

    if facts.sufficient() or facts.has_name() or facts.has_contact() or facts.has_org():
        intro = topic_by_id("customer_intro", plan.extra_topics)
        if intro is not None and "customer_intro" not in done_ids:
            if "customer_intro" not in filled:
                req = _record_topic_requirement(
                    kg,
                    project,
                    topic=intro,
                    text=facts.summary_en(),
                    source_message_id=source_message_id,
                )
                req_ids.append(req.id)
                filled.append("customer_intro")
        contacts = topic_by_id("contacts", plan.extra_topics)
        if contacts is not None and facts.has_contact() and "contacts" not in done_ids:
            if "contacts" not in filled:
                req = _record_topic_requirement(
                    kg,
                    project,
                    topic=contacts,
                    text=facts.contact_line_ru() or facts.summary_en(),
                    source_message_id=source_message_id,
                )
                req_ids.append(req.id)
                filled.append("contacts")

    have_brief = topic_by_id("have_brief", plan.extra_topics)
    if have_brief is not None and "have_brief" not in done_ids:
        req = _record_topic_requirement(
            kg,
            project,
            topic=have_brief,
            text="Customer attached or pasted a written brief; merged into the TZ outline.",
            source_message_id=source_message_id,
        )
        req_ids.append(req.id)
        filled.append("have_brief")

    from discovery.closing import SOURCE_BRIEF_TOPIC
    from discovery.fsm import DiscoveryStage as _Stage

    excerpt = body.strip()[:500]
    if excerpt:
        brief_topic = topic_by_id(SOURCE_BRIEF_TOPIC, plan.extra_topics)
        if brief_topic is None:
            brief_topic = TzTopic(
                id=SOURCE_BRIEF_TOPIC,
                stage=_Stage.REVIEW,
                title_ru="Исходная постановка",
                title_en="Source brief",
                questions={
                    ITLiteracy.LOW: excerpt,
                    ITLiteracy.MEDIUM: excerpt,
                    ITLiteracy.HIGH: excerpt,
                },
            )
        req = _record_topic_requirement(
            kg,
            project,
            topic=brief_topic,
            text=excerpt,
            source_message_id=source_message_id,
        )
        req_ids.append(req.id)

    plan = attach_overflow_topics(plan, extras)
    done_after = set(done_ids) | set(filled)
    leftover = remaining_topics(
        project.product_type,
        task_shape=task_shape,
        done_ids=done_after,
        plan=plan,
    )
    empty = [t.id for t in leftover if t.id not in {"have_brief"}]
    overflow_ids = [t.id for t in extras]
    reply = _summary_reply_ru(filled, empty, overflow_ids, leftover)
    return BriefMergeResult(
        filled_topic_ids=filled,
        overflow_topic_ids=overflow_ids,
        empty_topic_ids=empty,
        requirement_ids=req_ids,
        stakeholder=facts,
        reply_ru=reply,
        plan=plan,
    )


def _summary_reply_ru(
    filled: list[str],
    empty: list[str],
    overflow: list[str],
    leftover_topics: list[TzTopic],
) -> str:
    """Short recap — never echo the whole file, never dump catalog titles."""
    n_filled = len({x for x in filled if x not in {"have_brief"}})
    n_overflow = len(overflow)
    lines = ["Разобрал постановку и добавил в черновик ТЗ."]
    if n_filled:
        lines.append(f"Удалось закрыть несколько блоков ({n_filled}).")
    if n_overflow:
        lines.append(
            f"Есть детали сверх обычных разделов — зафиксировал отдельно ({n_overflow})."
        )
    if leftover_topics:
        nxt = leftover_topics[0]
        q = nxt.questions.get(ITLiteracy.LOW) or nxt.questions.get(ITLiteracy.MEDIUM) or ""
        lines.append("Ещё не хватает пары уточнений для сборки — начнём с этого.")
        if q:
            lines.append("")
            lines.append(q)
    else:
        lines.append("По каркасу вроде всё закрыто — если нужно, дополните текстом.")
    return "\n".join(lines)
