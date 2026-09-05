"""Client-facing market estimate and narrative report (DEC-012).

Separate from the owner heuristic in ``core.estimate``. Same Artifact,
different payload keys: ``client_estimate`` + ``client_estimate_report``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Sequence

from core.estimate import (
    HOURS_COULD,
    HOURS_MUST,
    HOURS_OPEN_QUESTION,
    HOURS_RISK,
    HOURS_SHOULD,
    PRODUCT_TYPE_RU,
    SIMPLE_MVP_HOUR_CAP,
    CustomerBudgetHint,
    base_hours_for,
    classify_requirement,
    compare_to_customer_budget,
    format_hours,
    format_money,
    is_active_risk,
    is_open_question,
    parse_customer_budget,
)
from core.market_rates import (
    DISCLAIMER_RU,
    ee_band,
    load_market_table,
    primary_band,
)
from sqlalchemy.orm import Session

from core.models import Entity, Project, ProjectStatus
from discovery.fsm import DiscoveryStage
from knowledge.repository import KnowledgeRepository

METHOD = "market_v1"
REPORT_TEMPLATE_METHOD = "template_v1"
REPORT_LLM_METHOD = "llm_v1"
PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "client-estimate-report.md"

CLIENT_CONFIRMABLE_STATUSES = frozenset(
    {
        ProjectStatus.WAITING_CLIENT_ESTIMATE,
        ProjectStatus.WAITING_CUSTOMER,
    }
)


class ClientEstimateAction(str, Enum):
    CONFIRM = "confirm"
    DISCUSS = "discuss"


class ClientEstimateError(ValueError):
    """Domain error for the client estimate gate."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _payload_of(entity: Any) -> dict:
    raw = getattr(entity, "payload", None) or {}
    return raw if isinstance(raw, dict) else {}


def _opt_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def collect_work_items(
    *,
    product_type: str | None,
    requirements: Sequence[Any] = (),
    open_questions: Sequence[Any] = (),
    risks: Sequence[Any] = (),
) -> list[dict[str, Any]]:
    """MVP / must-have package plus optional and buffer lines."""
    items: list[dict[str, Any]] = []
    type_label = PRODUCT_TYPE_RU.get(product_type or "", product_type or "не указан")
    items.append(
        {
            "id": "base",
            "name": f"Базовый каркас ({type_label})",
            "priority": "must",
            "hours": base_hours_for(product_type),
            "in_mvp": True,
            "kind": "base",
        }
    )
    for req in requirements:
        kind = classify_requirement(req)
        if kind is None:
            continue
        if kind == "must":
            hours = HOURS_MUST
        elif kind == "could":
            hours = HOURS_COULD
        else:
            hours = HOURS_SHOULD
        items.append(
            {
                "id": str(getattr(req, "id", "") or ""),
                "name": (getattr(req, "name", None) or "Требование")[:160],
                "priority": kind,
                "hours": hours,
                "in_mvp": kind in {"must", "should"},
                "kind": "requirement",
            }
        )
    open_n = 0
    for question in open_questions:
        if not is_open_question(question):
            continue
        open_n += 1
        items.append(
            {
                "id": str(getattr(question, "id", "") or f"q-{open_n}"),
                "name": (getattr(question, "name", None) or "Открытый вопрос")[:160],
                "priority": "buffer",
                "hours": HOURS_OPEN_QUESTION,
                "in_mvp": True,
                "kind": "open_question",
            }
        )
    risk_n = 0
    for risk in risks:
        if not is_active_risk(risk):
            continue
        risk_n += 1
        items.append(
            {
                "id": str(getattr(risk, "id", "") or f"r-{risk_n}"),
                "name": (getattr(risk, "name", None) or "Риск")[:160],
                "priority": "buffer",
                "hours": HOURS_RISK,
                "in_mvp": True,
                "kind": "risk",
            }
        )
    return items


@dataclass(frozen=True)
class ClientEstimate:
    hours: float
    hours_uncapped: float
    cost: int
    cost_low: int
    cost_high: int
    currency: str
    hourly_rate_low: float
    hourly_rate_mid: float
    hourly_rate_high: float
    rate_band: str
    capped: bool
    hour_cap: float
    product_type: str | None
    work_items: list[dict[str, Any]]
    must_count: int
    should_count: int
    could_count: int
    skipped_requirement_count: int
    open_question_count: int
    risk_count: int
    customer_budget_label: str = ""
    customer_budget_min: int | None = None
    customer_budget_max: int | None = None
    budget_fit: str = "none"
    method: str = METHOD
    status: str = "pending"
    disclaimer: str = DISCLAIMER_RU
    sources: list[dict[str, Any]] = field(default_factory=list)
    ee_comparison: dict[str, Any] | None = None
    report_method: str = REPORT_TEMPLATE_METHOD

    def as_dict(self) -> dict[str, Any]:
        return {
            "hours": self.hours,
            "hours_uncapped": self.hours_uncapped,
            "cost": self.cost,
            "cost_low": self.cost_low,
            "cost_high": self.cost_high,
            "currency": self.currency,
            "hourly_rate_low": self.hourly_rate_low,
            "hourly_rate_mid": self.hourly_rate_mid,
            "hourly_rate_high": self.hourly_rate_high,
            "rate_band": self.rate_band,
            "capped": self.capped,
            "hour_cap": self.hour_cap,
            "product_type": self.product_type,
            "work_items": [dict(item) for item in self.work_items],
            "must_count": self.must_count,
            "should_count": self.should_count,
            "could_count": self.could_count,
            "skipped_requirement_count": self.skipped_requirement_count,
            "open_question_count": self.open_question_count,
            "risk_count": self.risk_count,
            "customer_budget_label": self.customer_budget_label,
            "customer_budget_min": self.customer_budget_min,
            "customer_budget_max": self.customer_budget_max,
            "budget_fit": self.budget_fit,
            "method": self.method,
            "status": self.status,
            "disclaimer": self.disclaimer,
            "sources": [dict(src) for src in self.sources],
            "ee_comparison": dict(self.ee_comparison) if self.ee_comparison else None,
            "report_method": self.report_method,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ClientEstimate | None:
        if not data or not isinstance(data, dict):
            return None
        try:
            hours = float(data["hours"])
            cost = int(data["cost"])
        except (KeyError, TypeError, ValueError):
            return None
        work_items = data.get("work_items") or []
        if not isinstance(work_items, list):
            work_items = []
        sources = data.get("sources") or []
        if not isinstance(sources, list):
            sources = []
        ee = data.get("ee_comparison")
        return cls(
            hours=hours,
            hours_uncapped=float(data.get("hours_uncapped") or hours),
            cost=cost,
            cost_low=int(data.get("cost_low") or cost),
            cost_high=int(data.get("cost_high") or cost),
            currency=str(data.get("currency") or "RUB"),
            hourly_rate_low=float(data.get("hourly_rate_low") or 0),
            hourly_rate_mid=float(data.get("hourly_rate_mid") or 0),
            hourly_rate_high=float(data.get("hourly_rate_high") or 0),
            rate_band=str(data.get("rate_band") or "ru_cis_freelance"),
            capped=bool(data.get("capped")),
            hour_cap=float(data.get("hour_cap") or SIMPLE_MVP_HOUR_CAP),
            product_type=data.get("product_type"),
            work_items=[item for item in work_items if isinstance(item, dict)],
            must_count=int(data.get("must_count") or 0),
            should_count=int(data.get("should_count") or 0),
            could_count=int(data.get("could_count") or 0),
            skipped_requirement_count=int(data.get("skipped_requirement_count") or 0),
            open_question_count=int(data.get("open_question_count") or 0),
            risk_count=int(data.get("risk_count") or 0),
            customer_budget_label=str(data.get("customer_budget_label") or ""),
            customer_budget_min=_opt_int(data.get("customer_budget_min")),
            customer_budget_max=_opt_int(data.get("customer_budget_max")),
            budget_fit=str(data.get("budget_fit") or "none"),
            method=str(data.get("method") or METHOD),
            status=str(data.get("status") or "pending"),
            disclaimer=str(data.get("disclaimer") or DISCLAIMER_RU),
            sources=[src for src in sources if isinstance(src, dict)],
            ee_comparison=ee if isinstance(ee, dict) else None,
            report_method=str(data.get("report_method") or REPORT_TEMPLATE_METHOD),
        )


@dataclass(frozen=True)
class ClientEstimateReport:
    title: str
    body: str
    language: str = "ru"
    method: str = REPORT_TEMPLATE_METHOD
    generated_at: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "body": self.body,
            "language": self.language,
            "method": self.method,
            "generated_at": self.generated_at or _now_iso(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ClientEstimateReport | None:
        if not data or not isinstance(data, dict):
            return None
        body = str(data.get("body") or "").strip()
        if not body:
            return None
        return cls(
            title=str(data.get("title") or "Почему столько стоит"),
            body=body,
            language=str(data.get("language") or "ru"),
            method=str(data.get("method") or REPORT_TEMPLATE_METHOD),
            generated_at=str(data.get("generated_at") or ""),
        )


def _count_requirements(requirements: Sequence[Any]) -> tuple[int, int, int, int]:
    must_n = should_n = could_n = skipped = 0
    for req in requirements:
        kind = classify_requirement(req)
        if kind is None:
            skipped += 1
        elif kind == "must":
            must_n += 1
        elif kind == "could":
            could_n += 1
        else:
            should_n += 1
    return must_n, should_n, could_n, skipped


def _quoted_hours(items: Sequence[dict[str, Any]]) -> float:
    return round(sum(float(item.get("hours") or 0) for item in items if item.get("in_mvp")), 1)


def _ee_comparison(hours: float, band: dict[str, Any] | None) -> dict[str, Any] | None:
    if not band:
        return None
    hourly = band.get("hourly") or {}
    fx = float(band.get("fx_to_rub") or 0)
    mid = float(hourly.get("mid") or 0)
    if mid <= 0:
        return None
    usd_mid = int(round(hours * mid))
    rub_mid = int(round(usd_mid * fx)) if fx > 0 else None
    return {
        "band": band.get("id"),
        "label": band.get("label"),
        "currency": band.get("currency") or "USD",
        "hourly_mid": mid,
        "cost_mid": usd_mid,
        "fx_to_rub": fx or None,
        "cost_mid_rub": rub_mid,
        "source": dict(band.get("source") or {}),
    }


def estimate_client_delivery(
    *,
    product_type: str | None,
    requirements: Sequence[Any] = (),
    open_questions: Sequence[Any] = (),
    risks: Sequence[Any] = (),
    hour_cap: float | None = None,
    market_table: dict[str, Any] | None = None,
    fetch_market: bool = True,
) -> ClientEstimate:
    table = market_table if market_table is not None else load_market_table(fetch=fetch_market)
    band = primary_band(table)
    hourly = band.get("hourly") or {}
    rate_low = float(hourly.get("low") or 0)
    rate_mid = float(hourly.get("mid") or 0)
    rate_high = float(hourly.get("high") or 0)
    currency = str(band.get("currency") or "RUB")
    cap = float(SIMPLE_MVP_HOUR_CAP if hour_cap is None else hour_cap)

    items = collect_work_items(
        product_type=product_type,
        requirements=requirements,
        open_questions=open_questions,
        risks=risks,
    )
    hours_uncapped = _quoted_hours(items)
    capped = hours_uncapped > cap
    hours = cap if capped else hours_uncapped
    hours = round(hours, 1)
    cost = int(round(hours * rate_mid))
    cost_low = int(round(hours * rate_low))
    cost_high = int(round(hours * rate_high))
    budget = parse_customer_budget(requirements)
    budget_fit = compare_to_customer_budget(cost, currency, budget)
    must_n, should_n, could_n, skipped = _count_requirements(requirements)
    open_n = sum(1 for q in open_questions if is_open_question(q))
    risk_n = sum(1 for r in risks if is_active_risk(r))
    sources = [dict(src) for src in (table.get("sources") or []) if isinstance(src, dict)]
    if not sources and band.get("source"):
        sources = [dict(band["source"])]

    return ClientEstimate(
        hours=hours,
        hours_uncapped=hours_uncapped,
        cost=cost,
        cost_low=cost_low,
        cost_high=cost_high,
        currency=currency,
        hourly_rate_low=rate_low,
        hourly_rate_mid=rate_mid,
        hourly_rate_high=rate_high,
        rate_band=str(band.get("id") or "ru_cis_freelance"),
        capped=capped,
        hour_cap=cap,
        product_type=product_type,
        work_items=items,
        must_count=must_n,
        should_count=should_n,
        could_count=could_n,
        skipped_requirement_count=skipped,
        open_question_count=open_n,
        risk_count=risk_n,
        customer_budget_label=budget.label,
        customer_budget_min=budget.min_amount,
        customer_budget_max=budget.max_amount,
        budget_fit=budget_fit,
        disclaimer=str(table.get("disclaimer") or DISCLAIMER_RU),
        sources=sources,
        ee_comparison=_ee_comparison(hours, ee_band(table)),
    )


def estimate_client_project(
    kg: KnowledgeRepository,
    project: Project,
    *,
    fetch_market: bool = True,
) -> ClientEstimate:
    return estimate_client_delivery(
        product_type=project.product_type,
        requirements=kg.list_entities(project.id, type_="Requirement"),
        open_questions=kg.list_entities(project.id, type_="OpenQuestion"),
        risks=kg.list_entities(project.id, type_="Risk"),
        fetch_market=fetch_market,
    )


def render_template_report(
    estimate: ClientEstimate,
    budget: CustomerBudgetHint | None = None,
) -> ClientEstimateReport:
    type_label = PRODUCT_TYPE_RU.get(
        estimate.product_type or "", estimate.product_type or "не указан"
    )
    in_mvp = [item for item in estimate.work_items if item.get("in_mvp")]
    out = [item for item in estimate.work_items if not item.get("in_mvp")]
    work_lines = []
    for item in in_mvp[:12]:
        work_lines.append(
            f"- {item.get('name')}: {format_hours(float(item.get('hours') or 0))} ч "
            f"({item.get('priority')})"
        )
    if len(in_mvp) > 12:
        work_lines.append(f"- … ещё {len(in_mvp) - 12} позиций в пакете MVP")
    out_lines = [f"- {item.get('name')}" for item in out[:8]] or [
        "- Нет отдельно вынесенных could-пунктов"
    ]
    source_lines = []
    for src in estimate.sources:
        kind = src.get("kind") or "config"
        name = src.get("name") or "источник"
        note = src.get("note") or ""
        retrieved = src.get("retrieved") or ""
        source_lines.append(
            f"- {name} ({kind}"
            + (f", {retrieved}" if retrieved else "")
            + "). "
            + note
        )
    if not source_lines:
        source_lines = ["- Встроенная таблица ставок ASF (config)."]

    fit = estimate.budget_fit
    budget_label = (budget.label if budget else None) or estimate.customer_budget_label or "не указан"
    if fit == "above":
        budget_line = (
            f"Названный ориентир заказчика ({budget_label}) ниже середины вилки. "
            "Это повод сузить must-have или обсудить этапность — не повод молча резать часы."
        )
    elif fit == "below":
        budget_line = (
            f"Середина вилки ниже ориентира заказчика ({budget_label}). "
            "Запас можно оставить на риски или на could-пункты после MVP."
        )
    elif fit == "within":
        budget_line = f"Середина вилки попадает в ориентир заказчика ({budget_label})."
    elif fit == "quote_requested":
        budget_line = "В Discovery сумму не фиксировали — просили оценку. Ниже как раз она."
    else:
        budget_line = f"Ориентир бюджета в Discovery: {budget_label}."

    cap_line = ""
    if estimate.capped:
        cap_line = (
            f"\nЧасы обрезаны потолком простого MVP {format_hours(estimate.hour_cap)} ч "
            f"(без потолка было бы {format_hours(estimate.hours_uncapped)} ч)."
        )

    ee = estimate.ee_comparison or {}
    ee_line = ""
    if ee.get("cost_mid_rub"):
        ee_line = (
            f"\nДля сравнения подрядчики EE (середина {format_hours(float(ee.get('hourly_mid') or 0))} "
            f"{ee.get('currency')}/ч) дают примерно "
            f"{format_money(int(ee['cost_mid_rub']), 'RUB')} "
            f"при курсе {format_hours(float(ee.get('fx_to_rub') or 0))} ₽/USD из конфига — не фид биржи."
        )

    body = (
        f"Тип продукта: {type_label}. В смету входит базовый каркас и требования must/should, "
        f"плюс буфер на открытые вопросы и риски. Could-пункты в сумму не входят.\n\n"
        f"Пакет работ (MVP):\n"
        + "\n".join(work_lines)
        + "\n\n"
        f"Итого {format_hours(estimate.hours)} ч. "
        f"Вилка рынка RU/CIS: {format_money(estimate.cost_low, estimate.currency)} – "
        f"{format_money(estimate.cost_high, estimate.currency)} "
        f"({format_hours(estimate.hourly_rate_low)}–{format_hours(estimate.hourly_rate_high)} "
        f"{estimate.currency}/ч). "
        f"Середина: {format_money(estimate.cost, estimate.currency)} "
        f"по {format_hours(estimate.hourly_rate_mid)} {estimate.currency}/ч."
        f"{cap_line}{ee_line}\n\n"
        f"{budget_line}\n\n"
        f"Не входит в эту смету:\n"
        + "\n".join(out_lines)
        + "\n- Сложные интеграции, отдельный backend как второй продукт, магазин приложений «под ключ».\n"
        + "- Юридическое сопровождение и реклама.\n\n"
        f"Риски: открытых вопросов {estimate.open_question_count}, "
        f"активных рисков {estimate.risk_count}. "
        "Их не закрываем догадками — часы буфера как раз про это.\n\n"
        f"Откуда ставки:\n"
        + "\n".join(source_lines)
        + f"\n\n{estimate.disclaimer}"
    )
    return ClientEstimateReport(
        title="Почему столько стоит",
        body=body,
        method=REPORT_TEMPLATE_METHOD,
        generated_at=_now_iso(),
    )


def _load_prompt() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except OSError:
        return "Write a short Russian client estimate report. Return JSON {title, body}."


def write_client_estimate_report(
    estimate: ClientEstimate,
    *,
    complete_json=None,
) -> ClientEstimateReport:
    """LLM narrative when a provider answers; otherwise the deterministic template."""
    template = render_template_report(estimate)
    completer = complete_json
    if completer is None:
        from integrations.llm import complete_json as default_complete

        completer = default_complete
    user = (
        f"estimate={estimate.as_dict()}\n"
        f"template_fallback={template.body}"
    )
    try:
        data = completer(_load_prompt(), user)
    except Exception:  # noqa: BLE001 — narrative must not block the quote
        return template
    if not isinstance(data, dict):
        return template
    body = str(data.get("body") or "").strip()
    if not body:
        return template
    return ClientEstimateReport(
        title=str(data.get("title") or "Почему столько стоит"),
        body=body,
        method=REPORT_LLM_METHOD,
        generated_at=_now_iso(),
    )


def attach_client_estimate_to_draft(
    kg: KnowledgeRepository,
    project: Project,
    artifact: Entity,
    *,
    fetch_market: bool = True,
    complete_json=None,
) -> tuple[ClientEstimate, ClientEstimateReport]:
    estimate = estimate_client_project(kg, project, fetch_market=fetch_market)
    report = write_client_estimate_report(estimate, complete_json=complete_json)
    estimate = ClientEstimate(
        **{
            **estimate.as_dict(),
            "report_method": report.method,
            "status": "pending",
        }
    )
    payload = dict(artifact.payload or {})
    payload["client_estimate"] = estimate.as_dict()
    payload["client_estimate_report"] = report.as_dict()
    kg.update_entity(artifact, payload=payload)
    return estimate, report


def client_estimate_from_artifact(artifact: Entity | None) -> ClientEstimate | None:
    if artifact is None:
        return None
    return ClientEstimate.from_dict((artifact.payload or {}).get("client_estimate"))


def client_estimate_report_from_artifact(
    artifact: Entity | None,
) -> ClientEstimateReport | None:
    if artifact is None:
        return None
    return ClientEstimateReport.from_dict(
        (artifact.payload or {}).get("client_estimate_report")
    )


def customer_estimate_view(
    estimate: ClientEstimate | None,
    report: ClientEstimateReport | None,
) -> dict[str, Any] | None:
    if estimate is None:
        return None
    data = estimate.as_dict()
    data["formatted_cost"] = format_money(estimate.cost, estimate.currency)
    data["formatted_cost_low"] = format_money(estimate.cost_low, estimate.currency)
    data["formatted_cost_high"] = format_money(estimate.cost_high, estimate.currency)
    data["formatted_hours"] = format_hours(estimate.hours)
    data["formatted_rate_mid"] = (
        f"{format_hours(estimate.hourly_rate_mid)} {estimate.currency}/ч"
    )
    data["product_type_label"] = PRODUCT_TYPE_RU.get(
        estimate.product_type or "", estimate.product_type or "не указан"
    )
    data["report"] = report.as_dict() if report else None
    return data


def client_estimate_console_panel(
    estimate: ClientEstimate | None,
    report: ClientEstimateReport | None = None,
) -> dict[str, Any] | None:
    view = customer_estimate_view(estimate, report)
    return view


def format_client_estimate_ready_message(
    *,
    name: str,
    estimate: ClientEstimate,
) -> str:
    return (
        f"Смета по проекту «{name}» готова.\n\n"
        f"Ориентир: {format_money(estimate.cost, estimate.currency)} "
        f"(вилка {format_money(estimate.cost_low, estimate.currency)} – "
        f"{format_money(estimate.cost_high, estimate.currency)}, "
        f"~{format_hours(estimate.hours)} ч).\n\n"
        f"{estimate.disclaimer}\n\n"
        "Откройте Mini App проекта, чтобы подтвердить или обсудить."
    )


def format_owner_client_estimate_ready_message(
    *,
    name: str,
    project_id: str,
    estimate: ClientEstimate,
) -> str:
    return (
        f"ТЗ утверждено. Клиенту отправлена рыночная смета по «{name}».\n"
        f"ID: `{project_id}`\n"
        f"Середина: {format_money(estimate.cost, estimate.currency)} "
        f"(~{format_hours(estimate.hours)} ч). Статус: WAITING_CLIENT_ESTIMATE.\n"
        "Планирование MVP — только после подтверждения клиентом."
    )


def format_owner_client_decision_message(
    *,
    name: str,
    project_id: str,
    action: ClientEstimateAction,
    estimate: ClientEstimate | None,
) -> str:
    if action == ClientEstimateAction.CONFIRM:
        cost = (
            format_money(estimate.cost, estimate.currency)
            if estimate
            else "сумма в карточке"
        )
        return (
            f"Клиент подтвердил смету по «{name}» ({cost}).\n"
            f"ID: `{project_id}`\n"
            "Можно запускать планирование MVP: /plan"
        )
    return (
        f"Клиент хочет обсудить смету по «{name}».\n"
        f"ID: `{project_id}`\n"
        "Проект в WAITING_CUSTOMER — не стартуйте сборку, пока не договоритесь."
    )


def format_customer_client_decision_reply(action: ClientEstimateAction) -> str:
    if action == ClientEstimateAction.CONFIRM:
        return (
            "Смету зафиксировали. Дальше — планирование и сборка MVP. "
            "Если что-то поедет по объёму, вернёмся к разговору."
        )
    return (
        "Хорошо, сборку не стартуем. Напишите, что смущает в составе работ или в сумме — "
        "передам разработчику."
    )


@dataclass
class ClientEstimateDecisionResult:
    project_id: Any
    action: ClientEstimateAction
    project_status: ProjectStatus
    artifact_id: Any
    decision_id: Any
    message: str
    client_estimate: dict[str, Any] | None
    client_estimate_report: dict[str, Any] | None


def _sync_project_status_payload(
    kg: KnowledgeRepository,
    project: Project,
    *,
    discovery_stage: str,
    extra: dict[str, Any] | None = None,
) -> None:
    entities = kg.list_entities(project.id, type_="Project")
    if not entities:
        return
    payload = dict(entities[0].payload or {})
    payload.update(
        {
            "status": project.status.value,
            "product_type": project.product_type,
            "discovery_stage": discovery_stage,
            **(extra or {}),
        }
    )
    kg.update_entity(entities[0], payload=payload, name=project.name)


def apply_client_estimate_decision(
    db: Session,
    project: Project,
    action: ClientEstimateAction,
    *,
    note: str | None = None,
) -> ClientEstimateDecisionResult:
    """Customer confirm / discuss after the owner approved the TZ."""
    from core.hitl import get_draft_tz

    if project.status not in CLIENT_CONFIRMABLE_STATUSES:
        raise ClientEstimateError(
            f"project must be waiting on the client estimate, got {project.status.value}"
        )

    kg = KnowledgeRepository(db)
    draft = get_draft_tz(kg, project.id)
    if draft is None:
        raise ClientEstimateError("draft TZ not found")
    estimate = client_estimate_from_artifact(draft)
    if estimate is None:
        raise ClientEstimateError("client estimate is not ready yet")
    if estimate.status == "confirmed" and action == ClientEstimateAction.CONFIRM:
        raise ClientEstimateError("client estimate is already confirmed")
    if (
        project.status == ProjectStatus.WAITING_CUSTOMER
        and estimate.status not in {"pending", "discuss_requested"}
    ):
        raise ClientEstimateError("no pending client estimate to decide")

    payload = dict(draft.payload or {})
    stored = dict(payload.get("client_estimate") or {})
    if action == ClientEstimateAction.CONFIRM:
        stored["status"] = "confirmed"
        stored["decided_at"] = _now_iso()
        payload["client_estimate"] = stored
        kg.update_entity(draft, payload=payload)
        decision = kg.create_entity(
            project_id=project.id,
            type_="Decision",
            name="Customer confirmed client estimate",
            status="accepted",
            payload={
                "summary": note or "Customer confirmed the market estimate",
                "kind": "client_estimate_confirmation",
                "artifact_id": str(draft.id),
                "action": action.value,
                "cost": estimate.cost,
                "currency": estimate.currency,
            },
            confidence=1.0,
        )
        kg.create_relation(
            project_id=project.id,
            from_entity_id=decision.id,
            to_entity_id=draft.id,
            type_="related_to",
            payload={"role": "confirms_estimate"},
        )
        project.status = ProjectStatus.READY
        _sync_project_status_payload(
            kg,
            project,
            discovery_stage=DiscoveryStage.READY_FOR_OWNER.value,
            extra={"client_estimate_last_action": action.value},
        )
    else:
        stored["status"] = "discuss_requested"
        stored["decided_at"] = _now_iso()
        payload["client_estimate"] = stored
        kg.update_entity(draft, payload=payload)
        decision = kg.create_entity(
            project_id=project.id,
            type_="Decision",
            name="Customer asked to discuss estimate",
            status="open",
            payload={
                "summary": note or "Customer wants to discuss the market estimate",
                "kind": "HumanDecisionRequired",
                "artifact_id": str(draft.id),
                "action": action.value,
            },
            confidence=1.0,
        )
        kg.create_entity(
            project_id=project.id,
            type_="OpenQuestion",
            name=(note or "Обсуждение сметы")[:80],
            status="open",
            payload={
                "question": note
                or "Клиент нажал «Нужно обсудить» на рыночной смете",
                "source": "client_estimate",
            },
            confidence=1.0,
        )
        project.status = ProjectStatus.WAITING_CUSTOMER
        _sync_project_status_payload(
            kg,
            project,
            discovery_stage=DiscoveryStage.READY_FOR_OWNER.value,
            extra={"client_estimate_last_action": action.value},
        )

    db.flush()
    refreshed = ClientEstimate.from_dict(stored)
    report = client_estimate_report_from_artifact(draft)
    return ClientEstimateDecisionResult(
        project_id=project.id,
        action=action,
        project_status=project.status,
        artifact_id=draft.id,
        decision_id=decision.id,
        message=format_customer_client_decision_reply(action),
        client_estimate=customer_estimate_view(refreshed, report),
        client_estimate_report=report.as_dict() if report else None,
    )
