"""Deterministic delivery-cost heuristic for a draft TZ.

No LLM is required for the number. Open questions and risks add hours;
nothing is guessed away. Persist the payload on the draft TZ Artifact.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Sequence

from core.config import get_settings
from core.models import Entity, Project
from knowledge.repository import KnowledgeRepository

BASE_HOURS: dict[str, float] = {
    "website": 16,
    "telegram_bot": 20,
    "rest_service": 24,
    "ai_automation": 24,
}
UNKNOWN_BASE_HOURS = 20.0
SIMPLE_MVP_HOUR_CAP = 80.0

HOURS_MUST = 2.0
HOURS_SHOULD = 1.0
HOURS_COULD = 0.5
HOURS_OPEN_QUESTION = 2.0
HOURS_RISK = 3.0

SKIP_STATUSES = frozenset(
    {"superseded", "archived", "rejected", "closed", "resolved", "answered", "wont"}
)
CLOSED_QUESTION_STATUSES = frozenset(
    {"superseded", "archived", "rejected", "closed", "resolved", "answered"}
)
MUST_PRIORITIES = frozenset({"must", "p1"})
SHOULD_PRIORITIES = frozenset({"should", "p2"})
COULD_PRIORITIES = frozenset({"could", "p3"})
SKIP_PRIORITIES = frozenset({"wont", "won't", "wont_have"})

PRODUCT_TYPE_RU = {
    "website": "сайт",
    "telegram_bot": "Telegram-бот",
    "rest_service": "REST-сервис",
    "ai_automation": "AI-автоматизация",
}

METHOD = "heuristic_v1"

# Customer budget chips (Discovery topic `budget`) — context only, never the quote.
_BUDGET_MID_RE = re.compile(r"50\s*[–\-]\s*200", re.I)
_BUDGET_SMALL_RE = re.compile(r"до\s*~?\s*50(\s*тыс)?", re.I)
_BUDGET_LARGE_RE = re.compile(r"от\s*~?\s*200(\s*тыс)?", re.I)
_BUDGET_QUOTE_RE = re.compile(
    r"нужна оценка|не фиксирую|бюджета пока нет|изучаем",
    re.I,
)
_FIGURE_RE = re.compile(
    r"(?P<num>\d{1,3}(?:[\s\u00a0]\d{3})+|\d+(?:[.,]\d+)?)\s*"
    r"(?P<unit>тыс(?:яч)?|₽|руб(?:лей|ля)?|rub)?",
    re.I,
)


@dataclass(frozen=True)
class CustomerBudgetHint:
    """Stated envelope from Discovery. Not a price quote."""

    label: str
    min_amount: int | None = None
    max_amount: int | None = None
    kind: str = "none"  # none | range | figure | quote_requested


@dataclass(frozen=True)
class DeliveryEstimate:
    hours: float
    hours_uncapped: float
    cost: int
    currency: str
    hourly_rate: float
    capped: bool
    hour_cap: float
    product_type: str | None
    must_count: int
    should_count: int
    could_count: int
    skipped_requirement_count: int
    open_question_count: int
    risk_count: int
    rationale: list[str]
    customer_budget_label: str = ""
    customer_budget_min: int | None = None
    customer_budget_max: int | None = None
    budget_fit: str = "none"
    method: str = METHOD

    def as_dict(self) -> dict[str, Any]:
        return {
            "hours": self.hours,
            "hours_uncapped": self.hours_uncapped,
            "cost": self.cost,
            "currency": self.currency,
            "hourly_rate": self.hourly_rate,
            "capped": self.capped,
            "hour_cap": self.hour_cap,
            "product_type": self.product_type,
            "must_count": self.must_count,
            "should_count": self.should_count,
            "could_count": self.could_count,
            "skipped_requirement_count": self.skipped_requirement_count,
            "open_question_count": self.open_question_count,
            "risk_count": self.risk_count,
            "rationale": list(self.rationale),
            "customer_budget_label": self.customer_budget_label,
            "customer_budget_min": self.customer_budget_min,
            "customer_budget_max": self.customer_budget_max,
            "budget_fit": self.budget_fit,
            "method": self.method,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> DeliveryEstimate | None:
        if not data or not isinstance(data, dict):
            return None
        try:
            hours = float(data["hours"])
            cost = int(data["cost"])
        except (KeyError, TypeError, ValueError):
            return None
        rationale = data.get("rationale") or []
        if not isinstance(rationale, list):
            rationale = []
        return cls(
            hours=hours,
            hours_uncapped=float(data.get("hours_uncapped") or hours),
            cost=cost,
            currency=str(data.get("currency") or "RUB"),
            hourly_rate=float(data.get("hourly_rate") or 0),
            capped=bool(data.get("capped")),
            hour_cap=float(data.get("hour_cap") or SIMPLE_MVP_HOUR_CAP),
            product_type=data.get("product_type"),
            must_count=int(data.get("must_count") or 0),
            should_count=int(data.get("should_count") or 0),
            could_count=int(data.get("could_count") or 0),
            skipped_requirement_count=int(data.get("skipped_requirement_count") or 0),
            open_question_count=int(data.get("open_question_count") or 0),
            risk_count=int(data.get("risk_count") or 0),
            rationale=[str(x) for x in rationale],
            customer_budget_label=str(data.get("customer_budget_label") or ""),
            customer_budget_min=_opt_int(data.get("customer_budget_min")),
            customer_budget_max=_opt_int(data.get("customer_budget_max")),
            budget_fit=str(data.get("budget_fit") or "none"),
            method=str(data.get("method") or METHOD),
        )


def _opt_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def base_hours_for(product_type: str | None) -> float:
    key = (product_type or "").strip()
    if key in BASE_HOURS:
        return BASE_HOURS[key]
    return UNKNOWN_BASE_HOURS


def _status_of(entity: Any) -> str:
    return str(getattr(entity, "status", "") or "").strip().lower()


def _payload_of(entity: Any) -> dict:
    raw = getattr(entity, "payload", None) or {}
    return raw if isinstance(raw, dict) else {}


def _priority_of(entity: Any) -> str:
    payload = _payload_of(entity)
    return str(payload.get("priority") or "should").strip().lower()


def classify_requirement(entity: Any) -> str | None:
    """Return must/should/could, or None if the requirement is skipped."""
    if _status_of(entity) in SKIP_STATUSES:
        return None
    prio = _priority_of(entity)
    if prio in SKIP_PRIORITIES:
        return None
    if prio in MUST_PRIORITIES:
        return "must"
    if prio in COULD_PRIORITIES:
        return "could"
    if prio in SHOULD_PRIORITIES:
        return "should"
    return "should"


def is_open_question(entity: Any) -> bool:
    return _status_of(entity) not in CLOSED_QUESTION_STATUSES


def is_active_risk(entity: Any) -> bool:
    return _status_of(entity) not in SKIP_STATUSES


def format_hours(hours: float) -> str:
    value = round(float(hours), 1)
    if value == int(value):
        return str(int(value))
    text = f"{value:.1f}".rstrip("0").rstrip(".")
    return text.replace(".", ",")


def format_money(amount: int, currency: str) -> str:
    grouped = f"{int(amount):,}".replace(",", " ")
    return f"{grouped} {currency}"


def _budget_requirement_texts(requirements: Sequence[Any]) -> list[str]:
    texts: list[str] = []
    for ent in requirements:
        payload = _payload_of(ent)
        topic = str(payload.get("topic_id") or "")
        if topic != "budget":
            continue
        desc = str(payload.get("description") or getattr(ent, "name", "") or "")
        if desc.strip():
            texts.append(desc.strip())
    return texts


def _parse_explicit_figure(text: str) -> int | None:
    """Parse a customer-typed amount; ignore the standard chip numbers 50 / 200."""
    chip_span = False
    if _BUDGET_MID_RE.search(text) or _BUDGET_SMALL_RE.search(text) or _BUDGET_LARGE_RE.search(
        text
    ):
        chip_span = True
    best: int | None = None
    for match in _FIGURE_RE.finditer(text):
        raw = match.group("num").replace("\u00a0", " ").replace(" ", "").replace(",", ".")
        try:
            value = float(raw)
        except ValueError:
            continue
        unit = (match.group("unit") or "").lower()
        if unit.startswith("тыс"):
            value *= 1000
        elif not unit and value < 1000:
            # Bare 50 / 200 from chips — not a typed quote.
            if chip_span and value in {50, 200}:
                continue
            continue
        amount = int(round(value))
        if amount <= 0:
            continue
        if chip_span and amount in {50, 200, 50_000, 200_000} and unit.startswith("тыс"):
            continue
        best = amount
    return best


def parse_customer_budget(requirements: Sequence[Any] = ()) -> CustomerBudgetHint:
    """Read Discovery budget chips / figures. Never treat them as the studio quote."""
    texts = _budget_requirement_texts(requirements)
    if not texts:
        return CustomerBudgetHint(label="не указан", kind="none")
    blob = " \n ".join(texts)
    figure = _parse_explicit_figure(blob)
    if figure is not None:
        return CustomerBudgetHint(
            label=f"названная сумма ≈ {format_money(figure, 'RUB')}",
            min_amount=figure,
            max_amount=figure,
            kind="figure",
        )
    if _BUDGET_MID_RE.search(blob):
        return CustomerBudgetHint(
            label="ориентир примерно 50–200 тыс. ₽ (чип интервью, не котировка)",
            min_amount=50_000,
            max_amount=200_000,
            kind="range",
        )
    if _BUDGET_SMALL_RE.search(blob):
        return CustomerBudgetHint(
            label="ориентир до ~50 тыс. ₽ (чип интервью, не котировка)",
            min_amount=None,
            max_amount=50_000,
            kind="range",
        )
    if _BUDGET_LARGE_RE.search(blob):
        return CustomerBudgetHint(
            label="ориентир от 200 тыс. ₽ (чип интервью, не котировка)",
            min_amount=200_000,
            max_amount=None,
            kind="range",
        )
    if _BUDGET_QUOTE_RE.search(blob):
        return CustomerBudgetHint(
            label="сумму не фиксировал — просит оценку разработчика",
            kind="quote_requested",
        )
    snippet = blob.replace("\n", " ").strip()
    if len(snippet) > 120:
        snippet = snippet[:117] + "…"
    return CustomerBudgetHint(label=snippet or "не указан", kind="none")


def compare_to_customer_budget(
    cost: int,
    currency: str,
    hint: CustomerBudgetHint,
) -> str:
    if hint.kind in {"none", "quote_requested"}:
        return "none" if hint.kind == "none" else "quote_requested"
    if (currency or "").upper() != "RUB":
        return "uncompared"
    lo, hi = hint.min_amount, hint.max_amount
    if lo is not None and hi is not None:
        if cost < lo:
            return "below"
        if cost > hi:
            return "above"
        return "within"
    if hi is not None:
        return "above" if cost > hi else "within"
    if lo is not None:
        return "below" if cost < lo else "within"
    return "none"


def _budget_rationale(hint: CustomerBudgetHint, fit: str, cost: int, currency: str) -> str:
    fit_ru = {
        "above": "оценка ВЫШЕ ориентира заказчика",
        "below": "оценка НИЖЕ ориентира заказчика",
        "within": "оценка внутри ориентира заказчика",
        "quote_requested": "сравнивать не с чем — просил оценку",
        "uncompared": f"сравнение только в RUB, сейчас {currency}",
        "none": "ориентир не разобран как диапазон",
    }.get(fit, fit)
    return (
        f"Ориентир заказчика: {hint.label}. {fit_ru} "
        f"(наша оценка {format_money(cost, currency)}; чип/цифра заказчика — не котировка)."
    )


def estimate_delivery(
    *,
    product_type: str | None,
    requirements: Sequence[Any] = (),
    open_questions: Sequence[Any] = (),
    risks: Sequence[Any] = (),
    hourly_rate: float | None = None,
    currency: str | None = None,
    hour_cap: float | None = None,
) -> DeliveryEstimate:
    settings = get_settings()
    rate = float(settings.asf_estimate_hourly_rate if hourly_rate is None else hourly_rate)
    curr = str(settings.asf_estimate_currency if currency is None else currency).strip() or "RUB"
    cap = float(SIMPLE_MVP_HOUR_CAP if hour_cap is None else hour_cap)

    base = base_hours_for(product_type)
    must_n = should_n = could_n = skipped = 0
    for req in requirements:
        kind = classify_requirement(req)
        if kind is None:
            skipped += 1
            continue
        if kind == "must":
            must_n += 1
        elif kind == "could":
            could_n += 1
        else:
            should_n += 1

    open_n = sum(1 for q in open_questions if is_open_question(q))
    risk_n = sum(1 for r in risks if is_active_risk(r))

    hours_uncapped = (
        base
        + must_n * HOURS_MUST
        + should_n * HOURS_SHOULD
        + could_n * HOURS_COULD
        + open_n * HOURS_OPEN_QUESTION
        + risk_n * HOURS_RISK
    )
    hours_uncapped = round(hours_uncapped, 1)
    capped = hours_uncapped > cap
    hours = cap if capped else hours_uncapped
    hours = round(hours, 1)
    cost = int(round(hours * rate))
    budget = parse_customer_budget(requirements)
    budget_fit = compare_to_customer_budget(cost, curr, budget)

    type_label = PRODUCT_TYPE_RU.get(product_type or "", product_type or "не указан")
    type_note = (
        f"известному типу «{type_label}»"
        if product_type in BASE_HOURS
        else "неизвестному типу (базовая оценка как у типичного MVP)"
    )
    rationale: list[str] = [
        f"Тип продукта: {type_label} — база {format_hours(base)} ч по {type_note}.",
        (
            f"Требования: must/P1 {must_n} (+{format_hours(must_n * HOURS_MUST)} ч), "
            f"should {should_n} (+{format_hours(should_n * HOURS_SHOULD)} ч), "
            f"could {could_n} (+{format_hours(could_n * HOURS_COULD)} ч)."
        ),
        (
            f"Неопределённость: открытых вопросов {open_n} "
            f"(+{format_hours(open_n * HOURS_OPEN_QUESTION)} ч), "
            f"рисков {risk_n} (+{format_hours(risk_n * HOURS_RISK)} ч) — "
            "не закрываем догадками."
        ),
        _budget_rationale(budget, budget_fit, cost, curr),
    ]
    if capped:
        rationale.append(
            f"Потолок простого MVP: {format_hours(cap)} ч "
            f"(без потолка было бы {format_hours(hours_uncapped)} ч)."
        )
    rationale.append(
        f"Итого {format_hours(hours)} ч × {format_hours(rate)} {curr}/ч "
        f"= {format_money(cost, curr)}."
    )
    rationale = rationale[:8]

    return DeliveryEstimate(
        hours=hours,
        hours_uncapped=hours_uncapped,
        cost=cost,
        currency=curr,
        hourly_rate=rate,
        capped=capped,
        hour_cap=cap,
        product_type=product_type,
        must_count=must_n,
        should_count=should_n,
        could_count=could_n,
        skipped_requirement_count=skipped,
        open_question_count=open_n,
        risk_count=risk_n,
        rationale=rationale,
        customer_budget_label=budget.label,
        customer_budget_min=budget.min_amount,
        customer_budget_max=budget.max_amount,
        budget_fit=budget_fit,
    )


def estimate_project(
    kg: KnowledgeRepository,
    project: Project,
    *,
    hourly_rate: float | None = None,
    currency: str | None = None,
) -> DeliveryEstimate:
    return estimate_delivery(
        product_type=project.product_type,
        requirements=kg.list_entities(project.id, type_="Requirement"),
        open_questions=kg.list_entities(project.id, type_="OpenQuestion"),
        risks=kg.list_entities(project.id, type_="Risk"),
        hourly_rate=hourly_rate,
        currency=currency,
    )


def attach_estimate_to_draft(
    kg: KnowledgeRepository,
    project: Project,
    artifact: Entity,
) -> DeliveryEstimate:
    estimate = estimate_project(kg, project)
    payload = dict(artifact.payload or {})
    payload["estimate"] = estimate.as_dict()
    kg.update_entity(artifact, payload=payload)
    return estimate


def estimate_from_artifact(artifact: Entity | None) -> DeliveryEstimate | None:
    if artifact is None:
        return None
    return DeliveryEstimate.from_dict((artifact.payload or {}).get("estimate"))


def format_owner_draft_ready_message(
    *,
    name: str,
    project_id: str,
    estimate: DeliveryEstimate,
) -> str:
    bullets = "\n".join(f"• {line}" for line in estimate.rationale)
    type_label = PRODUCT_TYPE_RU.get(
        estimate.product_type or "", estimate.product_type or "не указан"
    )
    return (
        f"Черновик ТЗ готов — оценка для владельца\n"
        f"HITL обязателен: это не цена клиенту и не автоодобрение.\n\n"
        f"Проект: {name}\n"
        f"ID: `{project_id}`\n"
        f"Тип: {type_label}\n\n"
        f"Оценка: {format_money(estimate.cost, estimate.currency)} "
        f"(~{format_hours(estimate.hours)} ч × "
        f"{format_hours(estimate.hourly_rate)} {estimate.currency}/ч)\n"
        f"Ориентир заказчика: {estimate.customer_budget_label or 'не указан'}\n\n"
        f"Почему так:\n{bullets}\n\n"
        f"/review {project_id}"
    )


def format_estimate_review_block(estimate: DeliveryEstimate | dict | None) -> str:
    if isinstance(estimate, dict):
        estimate = DeliveryEstimate.from_dict(estimate)
    if estimate is None:
        return ""
    bullets = "\n".join(f"• {line}" for line in estimate.rationale)
    return (
        f"Оценка для владельца: {format_money(estimate.cost, estimate.currency)} "
        f"(~{format_hours(estimate.hours)} ч, {estimate.currency}). HITL обязателен.\n"
        f"Ориентир заказчика: {estimate.customer_budget_label or 'не указан'}\n"
        f"{bullets}"
    )
