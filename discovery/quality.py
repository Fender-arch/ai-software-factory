"""Level-0 spec quality: vague answers, clarify queue, reviewer scan.

Inspired by GitHub Spec Kit (MIT): [NEEDS CLARIFICATION] instead of guessing,
one high-impact question at a time (max 5), and checklists as
“unit tests for English” — not implementation tests.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from core.models import Entity
from discovery.tz_outline import Choice

MAX_CLARIFY_QUESTIONS = 5
MIN_FREE_TEXT_LEN = 24
VAGUE_RETRY_LIMIT = 2

VAGUE_TOKENS: frozenset[str] = frozenset(
    {
        "удобно",
        "удобный",
        "удобная",
        "удобнее",
        "быстро",
        "просто",
        "простой",
        "нормально",
        "обычно",
        "качественно",
        "красиво",
        "интуитивно",
        "современно",
        "хороший",
        "хорошо",
        "стандартно",
        "нормальный",
        "чтоб",
        "чтобы",
        "ну",
        "было",
        "как",
        "все",
        "всем",
        "простое",
        "intuitive",
        "robust",
        "simple",
        "nice",
        "cool",
        "whatever",
        "fast",
        "easy",
        "good",
        "fine",
        "ok",
        "okay",
        "scalable",
        "secure",
        "modern",
    }
)

_STOPWORDS: frozenset[str] = frozenset(
    {
        "и",
        "в",
        "на",
        "для",
        "с",
        "по",
        "а",
        "the",
        "a",
        "an",
        "to",
        "of",
        "for",
        "with",
        "it",
        "is",
        "be",
        "это",
        "что",
        "как",
        "или",
        "не",
        "да",
        "нет",
    }
)

_METRIC_RE = re.compile(
    r"(?i)(?:\d|%|\bзаявк|\bобращен|\bвремя|\bминут|\bчас|\bдень|\bнедел|"
    r"\bошиб|\bдемо|\bmetric|\bpercent|\bменьше|\bбольше|\breduce|"
    r"\bincrease|\bcount\b)"
)

_JOURNEY_RE = re.compile(r"(→|->|когда|when|затем|then|если|given)", re.I)

_VAGUE_ADJECTIVE_RE = re.compile(
    r"(?i)\b(fast|scalable|secure|intuitive|robust|удобн\w*|быстр\w*|"
    r"прост\w*|качественн\w*|современн\w*)\b"
)

BLOCKING_QUALITY_IDS: frozenset[str] = frozenset(
    {
        "testable_requirements",
        "measurable_success",
        "scope_bounded",
    }
)


@dataclass(frozen=True)
class ClarifyItem:
    id: str
    category: str
    question: str
    why: str
    options: tuple[Choice, ...]
    topic_id: str
    assumption: str = ""


@dataclass
class QualityItemResult:
    id: str
    label: str
    covered: bool
    blocking: bool = False
    detail: str = ""

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "covered": self.covered,
            "blocking": self.blocking,
            "detail": self.detail,
        }


@dataclass
class QualityReport:
    items: list[QualityItemResult] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    owner_recommendations: list[str] = field(default_factory=list)

    @property
    def blocking_missing(self) -> list[QualityItemResult]:
        return [i for i in self.items if i.blocking and not i.covered]

    @property
    def ok(self) -> bool:
        return not self.blocking_missing

    @property
    def score(self) -> float:
        if not self.items:
            return 1.0
        return sum(1 for i in self.items if i.covered) / len(self.items)

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "score": round(self.score, 3),
            "items": [i.as_dict() for i in self.items],
            "blocking_missing": [i.as_dict() for i in self.blocking_missing],
            "gaps": list(self.gaps),
            "contradictions": list(self.contradictions),
            "owner_recommendations": list(self.owner_recommendations),
            "ready_for_owner": self.ok and not self.contradictions,
        }


def is_underspecified(text: str, *, has_choice: bool = False) -> bool:
    """True when a free-text answer is too thin to close a TZ section."""
    if has_choice:
        return False
    compact = re.sub(r"\s+", " ", (text or "").strip())
    if len(compact) < MIN_FREE_TEXT_LEN:
        return True
    tokens = re.findall(r"[a-zа-яё0-9]+", compact.lower(), flags=re.I)
    if not tokens:
        return True
    content = [t for t in tokens if t not in _STOPWORDS]
    if not content:
        return True
    non_vague = [t for t in content if t not in VAGUE_TOKENS]
    if not non_vague:
        return True
    if len(non_vague) < 2 and len(compact) < 40:
        return True
    return False


def _blob(entity: Entity) -> str:
    payload = entity.payload or {}
    return " ".join(
        [
            entity.name or "",
            str(payload.get("title", "")),
            str(payload.get("description", "")),
            str(payload.get("question", "")),
        ]
    ).lower()


def _topic_id(entity: Entity) -> str:
    return str((entity.payload or {}).get("topic_id") or "")


def _description(entity: Entity) -> str:
    return str((entity.payload or {}).get("description") or entity.name or "")


def _active_requirements(requirements: list[Entity]) -> list[Entity]:
    return [
        e
        for e in requirements
        if e.status not in {"archived", "superseded"}
    ]


def _escalated_topic_ids(open_questions: list[Entity]) -> set[str]:
    done: set[str] = set()
    for ent in open_questions:
        payload = ent.payload or {}
        if ent.status != "open":
            continue
        if payload.get("escalate_to") or payload.get("source") == "clarify_deferred":
            tid = str(payload.get("topic_id") or "")
            if tid:
                done.add(tid)
            cid = str(payload.get("clarify_id") or "")
            if cid:
                done.add(cid)
    return done


def _answered_topic_ids(requirements: list[Entity]) -> set[str]:
    return {
        _topic_id(e)
        for e in _active_requirements(requirements)
        if _topic_id(e) and not str(_topic_id(e)).startswith("clarify")
    }


def _for_topic(requirements: list[Entity], topic_id: str) -> list[Entity]:
    return [e for e in _active_requirements(requirements) if _topic_id(e) == topic_id]


def _text_for_topic(requirements: list[Entity], topic_id: str) -> str:
    return " ".join(_description(e) for e in _for_topic(requirements, topic_id))


def _topic_done(
    topic_id: str,
    *,
    requirements: list[Entity],
    open_questions: list[Entity],
) -> bool:
    if _for_topic(requirements, topic_id):
        return True
    return topic_id in _escalated_topic_ids(open_questions)


def _measurable(text: str) -> bool:
    return bool(_METRIC_RE.search(text or ""))


def _has_object(text: str) -> bool:
    compact = re.sub(r"\s+", " ", (text or "").strip())
    return len(compact) >= 12 and not is_underspecified(compact, has_choice=False)


def evaluate_spec_quality(
    *,
    requirements: list[Entity],
    open_questions: list[Entity] | None = None,
    risks: list[Entity] | None = None,
) -> QualityReport:
    """Deterministic quality checklist + reviewer findings (Level 0/1)."""
    open_questions = open_questions or []
    risks = risks or []
    reqs = _active_requirements(requirements)
    items: list[QualityItemResult] = []

    testable = [e for e in reqs if _has_object(_description(e))]
    items.append(
        QualityItemResult(
            id="testable_requirements",
            label="At least one testable, unambiguous requirement",
            covered=bool(testable),
            blocking=True,
            detail="" if testable else "No requirement has a concrete object/outcome.",
        )
    )

    success_text = _text_for_topic(reqs, "success_mvp")
    success_done = _topic_done(
        "success_mvp", requirements=reqs, open_questions=open_questions
    )
    chip_success = bool(
        re.search(r"заявк|обращен|время|ошиб|демо|сценари", success_text, re.I)
    )
    success_ok = bool(
        success_done
        and (
            chip_success
            or _measurable(success_text)
            or "success_mvp" in _escalated_topic_ids(open_questions)
        )
    )
    items.append(
        QualityItemResult(
            id="measurable_success",
            label="Success criteria are measurable",
            covered=success_ok,
            blocking=True,
            detail="" if success_ok else "MVP success is missing or not measurable.",
        )
    )

    scope_done = _topic_done(
        "out_of_scope", requirements=reqs, open_questions=open_questions
    )
    items.append(
        QualityItemResult(
            id="scope_bounded",
            label="MVP scope / non-goals stated",
            covered=scope_done,
            blocking=True,
            detail="" if scope_done else "Out of scope is not captured or escalated.",
        )
    )

    journey_text = _text_for_topic(reqs, "primary_scenario")
    journey_ok = _topic_done(
        "primary_scenario", requirements=reqs, open_questions=open_questions
    ) and (bool(_JOURNEY_RE.search(journey_text)) or len(journey_text) >= 24 or "primary_scenario" in _escalated_topic_ids(open_questions))
    items.append(
        QualityItemResult(
            id="primary_journey",
            label="Primary user journey is described",
            covered=journey_ok,
            blocking=False,
            detail="" if journey_ok else "Primary scenario is thin or missing steps.",
        )
    )

    acceptance_done = _topic_done(
        "acceptance", requirements=reqs, open_questions=open_questions
    )
    items.append(
        QualityItemResult(
            id="acceptance_testable",
            label="Acceptance can be checked by the customer",
            covered=acceptance_done,
            blocking=False,
        )
    )

    blocking_open = [
        e
        for e in open_questions
        if e.status == "open"
        and not (e.payload or {}).get("escalate_to")
        and str((e.payload or {}).get("source") or "") not in {"hitl", "clarify_deferred"}
        and not str((e.payload or {}).get("topic_id") or "").startswith("clarify")
    ]
    items.append(
        QualityItemResult(
            id="no_blocking_clarifications",
            label="No unresolved blocking clarifications",
            covered=len(blocking_open) == 0,
            blocking=False,
            detail="" if not blocking_open else f"{len(blocking_open)} open questions without owner/dev handoff.",
        )
    )

    review = scan_reviewer(requirements=reqs, open_questions=open_questions, risks=risks)
    return QualityReport(
        items=items,
        gaps=review.gaps,
        contradictions=review.contradictions,
        owner_recommendations=review.owner_recommendations,
    )


def scan_reviewer(
    *,
    requirements: list[Entity],
    open_questions: list[Entity] | None = None,
    risks: list[Entity] | None = None,
) -> QualityReport:
    """Flag vague adjectives, near-duplicates, and must vs non-goal clashes."""
    open_questions = open_questions or []
    risks = risks or []
    reqs = _active_requirements(requirements)
    gaps: list[str] = []
    contradictions: list[str] = []
    recs: list[str] = []

    for ent in reqs:
        desc = _description(ent)
        if _VAGUE_ADJECTIVE_RE.search(desc) and not _measurable(desc):
            gaps.append(
                f"Vague wording in '{ent.name[:60]}': quantify or replace adjectives."
            )
        if _topic_id(ent) == "must_features" and not _has_object(desc):
            gaps.append("Must-have functions lack a concrete object or outcome.")
        if _topic_id(ent) == "success_mvp" and not (
            _measurable(desc)
            or re.search(r"заявк|демо|время|ошиб", desc, re.I)
        ):
            gaps.append("Success criterion is not measurable.")

    blob = " ".join(_description(e) for e in reqs).lower()
    if re.search(r"лендинг|визитк|mini app|миниап|мини-ап|портфол", blob):
        for tid, label in (
            ("public_identity", "Public name/brand for visitors is missing."),
            ("offer_catalog", "Service/portfolio catalog is missing."),
            ("visitor_cta", "Public visitor CTA / lead destination is missing."),
        ):
            if not _topic_done(tid, requirements=reqs, open_questions=open_questions):
                gaps.append(label)

    seen: dict[str, str] = {}
    for ent in reqs:
        key = re.sub(r"\W+", " ", _description(ent).lower())[:48].strip()
        if len(key) < 16:
            continue
        if key in seen:
            gaps.append(f"Possible duplicate requirement: '{ent.name[:50]}'.")
        else:
            seen[key] = str(ent.id)

    oos = _text_for_topic(reqs, "out_of_scope").lower()
    must = _text_for_topic(reqs, "must_features").lower()
    clash_stems = ("оплат", "payment", "кабинет", "мобильн", "saas", "корзин")
    for stem in clash_stems:
        if stem in oos and stem in must:
            contradictions.append(
                f"Must-have functions mention '{stem}' which is also out of scope."
            )

    if any((e.payload or {}).get("escalate_to") for e in open_questions if e.status == "open"):
        recs.append("Answer escalated TZ sections before planning, or keep them as owner questions.")
    if contradictions:
        recs.append("Resolve must-vs-non-goal contradictions before approving the draft TZ.")
    if gaps:
        recs.append("Tighten vague or untestable statements; prefer chips or measurable outcomes.")
    if not recs:
        recs.append("Approve, request changes, or answer open questions before planning.")

    return QualityReport(
        items=[],
        gaps=gaps,
        contradictions=contradictions,
        owner_recommendations=recs,
    )


def _category_status(
    item_id: str,
    *,
    requirements: list[Entity],
    open_questions: list[Entity],
) -> str:
    """Clear / Partial / Missing for the Spec Kit-style clarify taxonomy."""
    reqs = _active_requirements(requirements)
    escalated = _escalated_topic_ids(open_questions)

    def _status(topic_id: str, *, extra_ok: bool = True) -> str:
        if topic_id in escalated:
            return "Clear"
        text = _text_for_topic(reqs, topic_id)
        if not text:
            return "Missing"
        if extra_ok:
            return "Clear"
        return "Partial"

    if item_id == "functional_scope":
        text = _text_for_topic(reqs, "must_features")
        if "must_features" in escalated:
            return "Clear"
        if not text:
            return "Missing"
        if is_underspecified(text) or not _has_object(text):
            return "Partial"
        return "Clear"
    if item_id == "out_of_scope":
        return _status("out_of_scope")
    if item_id == "roles_access":
        roles_ok = bool(_text_for_topic(reqs, "roles")) or "roles" in escalated
        access_ok = bool(_text_for_topic(reqs, "access")) or "access" in escalated
        if roles_ok and access_ok:
            return "Clear"
        if roles_ok or access_ok:
            return "Partial"
        return "Missing"
    if item_id == "data_entities":
        text = _text_for_topic(reqs, "records")
        if "records" in escalated:
            return "Clear"
        if not text:
            return "Missing"
        if is_underspecified(text):
            return "Partial"
        return "Clear"
    if item_id == "primary_journey":
        text = _text_for_topic(reqs, "primary_scenario")
        if "primary_scenario" in escalated:
            return "Clear"
        if not text:
            return "Missing"
        if _JOURNEY_RE.search(text) or len(text) >= 40:
            return "Clear"
        return "Partial"
    if item_id == "acceptance":
        return _status("acceptance")
    if item_id == "nfr_hosting":
        text = _text_for_topic(reqs, "ops_constraints")
        if "ops_constraints" in escalated:
            return "Clear"
        if not text:
            return "Missing"
        if re.search(r"хост|сервер|host|нагруз|pii|персонал|не знаю", text, re.I):
            from discovery.substance import host_address_missing

            if host_address_missing(text):
                return "Partial"
            return "Clear"
        return "Partial"
    if item_id == "visitor_destination":
        from discovery.substance import destination_specified

        if "visitor_cta" in escalated:
            return "Clear"
        text = _text_for_topic(reqs, "visitor_cta")
        if not text:
            return "Clear"
        blob = text + " " + _text_for_topic(reqs, "integrations")
        if destination_specified(blob) or re.search(
            r"форма заявки|этот telegram|cta_form|cta_notify", blob, re.I
        ):
            return "Clear"
        return "Partial"
    if item_id == "reference_reuse":
        if "design_references" in escalated:
            return "Clear"
        text = _text_for_topic(reqs, "design_references")
        if not text:
            return "Clear"
        if re.search(r"референсов нет|пришлю отдельно|без референса", text, re.I):
            return "Clear"
        has_url = bool(re.search(r"https?://", text, re.I))
        has_reuse = bool(
            re.search(
                r"типограф|шрифт|сетк|анимац|motion|цвет|тон|воздух|нравит|взять",
                text,
                re.I,
            )
        )
        if has_url and not has_reuse:
            return "Partial"
        return "Clear"
    if item_id == "design_vs_timeline":
        from discovery.substance import loud_design, short_deadline

        if "design_direction" in escalated or "timeline" in escalated:
            return "Clear"
        timeline = _text_for_topic(reqs, "timeline")
        design = (
            _text_for_topic(reqs, "design_direction")
            + " "
            + _text_for_topic(reqs, "purpose_problem")
        )
        if not (short_deadline(timeline) and loud_design(design)):
            return "Clear"
        if re.search(r"лёгк\w+\s+3d|срок гибк|спокойн", _text_for_topic(reqs, "design_direction"), re.I):
            return "Clear"
        return "Partial"
    if item_id == "integration_failure":
        text = _text_for_topic(reqs, "integrations")
        if "integrations" in escalated:
            return "Clear"
        if not text:
            return "Missing"
        if re.search(r"без внеш|почт|crm|sheet|таблиц|ошиб|fail|retry", text, re.I):
            return "Clear"
        return "Partial"
    if item_id == "edge_error":
        text = _text_for_topic(reqs, "risks") + " ".join(_description(r) for r in [])
        if "risks" in escalated:
            return "Clear"
        if not text:
            return "Missing"
        if re.search(r"нет критич|ошиб|пуст|edge|неизвест|данн", text, re.I):
            return "Clear"
        return "Partial"
    return "Clear"


def clarify_catalog() -> tuple[ClarifyItem, ...]:
    return (
        ClarifyItem(
            id="functional_scope",
            category="Functional Scope & Behavior",
            question="Какие действия пользователь обязан суметь сделать в первой версии — назовите один главный результат?",
            why="Без конкретного результата must-have нельзя проверить на приёмке.",
            topic_id="must_features",
            assumption="v1 is a single primary job, not a full platform.",
            options=(
                Choice("feat_intake", "Оставить заявку / данные и получить подтверждение", recommended=True),
                Choice("feat_catalog", "Посмотреть информацию (услуги, FAQ, статус)"),
                Choice("feat_admin", "Вести список записей: найти, добавить, поправить"),
                Choice("feat_notify", "Получить напоминание или уведомление"),
            ),
        ),
        ClarifyItem(
            id="out_of_scope",
            category="Functional Scope & Behavior",
            question="Что точно не входит в первую версию, даже если захочется потом?",
            why="Явные non-goals удерживают объём MVP.",
            topic_id="out_of_scope",
            assumption="Payments and extra apps stay out of v1 unless the owner says otherwise.",
            options=(
                Choice("oos_payments", "Без оплаты / эквайринга в v1", recommended=True),
                Choice("oos_mobile", "Без отдельного мобильного приложения"),
                Choice("oos_saas", "Без сложного кабинета и ролей"),
                Choice("oos_later", "Только один главный сценарий, остальное позже"),
            ),
        ),
        ClarifyItem(
            id="roles_access",
            category="Functional Scope & Behavior",
            question="Кто главный пользователь первой версии и кто ещё может зайти?",
            why="Роли и доступ определяют экраны, авторизацию и приёмку.",
            topic_id="roles",
            options=(
                Choice("role_customer", "Внешний клиент, вход свободный или по ссылке", recommended=True),
                Choice("role_staff", "Сотрудник / оператор, только свои"),
                Choice("role_owner", "Владелец как администратор"),
                Choice("role_mixed", "Клиент снаружи + сотрудник внутри"),
            ),
        ),
        ClarifyItem(
            id="data_entities",
            category="Domain & Data Model",
            question="Какую одну главную запись система должна хранить в v1?",
            why="Без сущности нельзя спроектировать данные и приёмку.",
            topic_id="records",
            options=(
                Choice("data_contacts", "Заявка / контакт человека", recommended=True),
                Choice("data_catalog", "Справочник (услуги, товары, FAQ)"),
                Choice("data_ops", "Операционная запись (слот, статус, задача)"),
                Choice("data_none", "Почти ничего не храним — только пересылаем"),
            ),
        ),
        ClarifyItem(
            id="primary_journey",
            category="Interaction & UX Flow",
            question="Как выглядит один путь «от начала до результата», который обязан работать?",
            why="Счастливый путь становится сценарием приёмки Given–When–Then.",
            topic_id="primary_scenario",
            options=(
                Choice("sc_form", "Человек оставляет заявку → нам приходит уведомление", recommended=True),
                Choice("sc_book", "Человек выбирает услугу/слот → запись сохраняется"),
                Choice("sc_ask", "Человек задаёт вопрос → получает ответ или эскалацию"),
                Choice("sc_sync", "Событие в системе A → данные появляются в системе B"),
            ),
        ),
        ClarifyItem(
            id="acceptance",
            category="Completion Signals",
            question="Что вы лично проверите, чтобы сказать «можно пользоваться»?",
            why="Приёмка должна быть проверяемой, не «сделайте качественно».",
            topic_id="acceptance",
            options=(
                Choice("acc_demo", "Проходим главный сценарий на реальных данных", recommended=True),
                Choice("acc_checklist", "Чек-лист must-have — все пункты зелёные"),
                Choice("acc_week", "Неделя реальной работы без критичных сбоев"),
            ),
        ),
        ClarifyItem(
            id="nfr_hosting",
            category="Non-Functional Quality",
            question="Где это должно жить в первой версии и насколько это «небольшой» сервис?",
            why="Хостинг и нагрузка влияют на простой стек MVP; иначе это угадывание.",
            topic_id="ops_constraints",
            assumption="Simple shared hosting and modest volume unless the customer says otherwise.",
            options=(
                Choice("ops_simple", "Обычный простой хостинг, небольшая нагрузка", recommended=True),
                Choice("ops_existing", "Рядом с уже существующим сервером / доменом"),
                Choice("ops_unsure", "Не знаю про серверы — пусть предложит разработчик"),
                Choice("ops_sensitive", "Есть персональные данные, нужна аккуратная защита"),
            ),
        ),
        ClarifyItem(
            id="visitor_destination",
            category="Interaction & UX Flow",
            question="Куда уходит заявка посетителя и какой публичный контакт показать на визитке?",
            why="Без получателя заявки и публичного контакта визитку нельзя собрать.",
            topic_id="visitor_cta",
            options=(
                Choice("cta_form", "Форма: имя, контакт, сообщение — заявки мне в этот Telegram", recommended=True),
                Choice("cta_channel", "Заявки в Telegram-канал — сейчас напишу @канал"),
                Choice("cta_write", "Сейчас напишу @ник / телефон / почту"),
            ),
        ),
        ClarifyItem(
            id="reference_reuse",
            category="Non-Functional Quality",
            question="Что взять с присланных референсов — шрифт, сетка, анимация, тон?",
            why="Одни URL без «что копировать» нельзя превратить в макет.",
            topic_id="design_references",
            options=(
                Choice("ref_type", "Типографика и воздух, без кричащего motion", recommended=True),
                Choice("ref_motion", "Анимации / 3D-герой как на референсе"),
                Choice("ref_none", "Референсов нет — ориентируемся на выбранный стиль"),
            ),
        ),
        ClarifyItem(
            id="design_vs_timeline",
            category="Non-Functional Quality",
            question="Срок короткий, а визуал «вау/3D». Что важнее в первой версии?",
            why="Иначе оценка и приёмка разъедутся: 1–2 недели vs премиальный 3D.",
            topic_id="design_direction",
            options=(
                Choice(
                    "vis_mvp_3d",
                    "Один лёгкий 3D/motion-герой, срок как в ТЗ",
                    recommended=True,
                ),
                Choice("vis_flex", "Вау/3D важнее — срок гибкий"),
                Choice("vis_calm_ok", "Спокойный вид, чтобы успеть"),
            ),
        ),
        ClarifyItem(
            id="integration_failure",
            category="Integration & External Dependencies",
            question="Если внешняя система не ответит — что должен сделать продукт в v1?",
            why="Без поведения при ошибке интеграция непроверяема.",
            topic_id="integrations",
            assumption="v1 shows an error and notifies the operator; no complex retry fabric.",
            options=(
                Choice("int_none", "В v1 без внешних систем — неактуально", recommended=True),
                Choice("int_notify", "Показать ошибку и уведомить владельца"),
                Choice("int_queue", "Попробовать позже / оставить в очереди"),
                Choice("int_human", "Передать человеку и не терять заявку"),
            ),
        ),
        ClarifyItem(
            id="edge_error",
            category="Edge Cases & Failure Handling",
            question="Что должно произойти, если пользователь ничего не ввёл или шаг оборвался?",
            why="Пустой и ошибочный путь иначе останется дырой в ТЗ.",
            topic_id="risks",
            assumption="Empty input is rejected with a short hint; no silent failure.",
            options=(
                Choice("edge_hint", "Короткая подсказка «нужно заполнить» и повтор", recommended=True),
                Choice("edge_human", "Сразу передать человеку / оператору"),
                Choice("edge_ignore", "Игнорировать пустое и ждать следующее сообщение"),
                Choice("risk_none", "Критических опасений нет"),
            ),
        ),
    )


def clarify_item_by_id(item_id: str | None) -> ClarifyItem | None:
    if not item_id:
        return None
    for item in clarify_catalog():
        if item.id == item_id:
            return item
    return None


def build_clarify_queue(
    *,
    requirements: list[Entity],
    open_questions: list[Entity] | None = None,
    already_asked: list[str] | None = None,
    limit: int = MAX_CLARIFY_QUESTIONS,
) -> list[str]:
    """Prioritised clarify ids whose taxonomy status is Partial or Missing."""
    open_questions = open_questions or []
    asked = set(already_asked or [])
    ranked: list[tuple[int, str]] = []
    impact = {
        "functional_scope": 100,
        "out_of_scope": 95,
        "primary_journey": 90,
        "acceptance": 85,
        "roles_access": 80,
        "data_entities": 75,
        "nfr_hosting": 60,
        "visitor_destination": 88,
        "reference_reuse": 73,
        "design_vs_timeline": 74,
        "integration_failure": 55,
        "edge_error": 50,
    }
    for item in clarify_catalog():
        if item.id in asked:
            continue
        status = _category_status(
            item.id, requirements=requirements, open_questions=open_questions
        )
        if status == "Clear":
            continue
        score = impact.get(item.id, 10)
        if status == "Missing":
            score += 20
        ranked.append((score, item.id))
    ranked.sort(key=lambda pair: pair[0], reverse=True)
    return [item_id for _, item_id in ranked[:limit]]


def render_clarify_prompt(item: ClarifyItem) -> tuple[str, list[Choice]]:
    lines = [
        f"Уточнение {item.category}",
        "",
        item.question,
        "",
        item.why,
    ]
    return "\n".join(lines), list(item.options)


def quality_floor_messages(report: QualityReport) -> list[str]:
    return [item.detail or item.label for item in report.blocking_missing]
