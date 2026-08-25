"""Deterministic coverage checklists (Level-1 rules) for product types and modes."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from knowledge.repository import KnowledgeRepository

# Aligned with templates/*.md Discovery checklist sections.
PRODUCT_CHECKLISTS: dict[str, list[dict[str, object]]] = {
    "website": [
        {
            "id": "audience_cta",
            "label": "Audience and primary CTA",
            "keywords": ("audience", "cta", "customer", "user", "контакт", "form"),
            "stages": ("USERS", "UNDERSTANDING_IDEA", "FUNCTIONAL"),
        },
        {
            "id": "pages_sections",
            "topic_id": "pages_sections",
            "label": "Pages / sections",
            "keywords": ("page", "section", "home", "menu", "landing"),
            "stages": ("FUNCTIONAL",),
        },
        {
            "id": "public_identity",
            "topic_id": "public_identity",
            "label": "Public name / brand for visitors",
            "keywords": ("имя", "бренд", "слоган", "визитк"),
            "stages": ("FUNCTIONAL",),
        },
        {
            "id": "offer_catalog",
            "topic_id": "offer_catalog",
            "label": "Services / portfolio to display",
            "keywords": ("услуг", "каталог", "портфол", "кейс"),
            "stages": ("FUNCTIONAL",),
        },
        {
            "id": "visitor_cta",
            "topic_id": "visitor_cta",
            "label": "Visitor contact / lead form",
            "keywords": ("cta", "@", "заявк", "телефон"),
            "stages": ("FUNCTIONAL",),
        },
        {
            "id": "brand_assets",
            "topic_id": "brand_assets",
            "label": "Brand assets availability",
            "keywords": ("brand", "logo", "photo", "asset", "логотип"),
            "stages": ("NON_FUNCTIONAL", "RISKS"),
        },
        {
            "id": "design_references",
            "topic_id": "design_references",
            "label": "Design references and what to copy",
            "keywords": ("референс", "пример", "похож", "нравится", "reference"),
            "stages": ("NON_FUNCTIONAL",),
        },
        {
            "id": "design_direction",
            "topic_id": "design_direction",
            "label": "Design direction (calm vs motion vs 3D)",
            "keywords": ("дизайн", "лаконич", "3d", "анимац", "спокойн", "визуал"),
            "stages": ("NON_FUNCTIONAL",),
        },
        {
            "id": "promotion",
            "topic_id": "promotion",
            "label": "Promotion / SEO / ads / analytics in v1",
            "keywords": ("seo", "продвижен", "реклам", "метрик", "яндекс"),
            "stages": ("BUSINESS_CONTEXT",),
        },
        {
            "id": "form_destination",
            "label": "Form destinations (email, CRM, none)",
            "keywords": ("email", "crm", "form", "destination", "notify"),
            "stages": ("INTEGRATIONS", "FUNCTIONAL"),
        },
        {
            "id": "languages",
            "label": "Languages",
            "keywords": ("language", "russian", "english", "locale", "i18n"),
            "stages": ("NON_FUNCTIONAL",),
        },
        {
            "id": "hosting",
            "label": "Hosting expectation",
            "keywords": ("host", "deploy", "vercel", "vps", "static"),
            "stages": ("NON_FUNCTIONAL", "INTEGRATIONS"),
        },
    ],
    "telegram_bot": [
        {
            "id": "user_jobs",
            "label": "Primary user jobs",
            "keywords": ("user", "job", "booking", "remind", "customer"),
            "stages": ("USERS", "UNDERSTANDING_IDEA"),
        },
        {
            "id": "delivery_surface",
            "topic_id": "delivery_surface",
            "label": "Bot chat vs Mini App landing",
            "keywords": ("mini app", "миниап", "лендинг", "чат"),
            "stages": ("FUNCTIONAL",),
        },
        {
            "id": "interaction_model",
            "label": "Commands vs free-text",
            "keywords": ("command", "free-text", "conversational", "button"),
            "stages": ("FUNCTIONAL",),
        },
        {
            "id": "public_identity",
            "topic_id": "public_identity",
            "label": "Public name / brand for visitors",
            "keywords": ("имя", "бренд", "слоган", "визитк"),
            "stages": ("FUNCTIONAL",),
        },
        {
            "id": "offer_catalog",
            "topic_id": "offer_catalog",
            "label": "Services / portfolio to display",
            "keywords": ("услуг", "каталог", "портфол", "кейс"),
            "stages": ("FUNCTIONAL",),
        },
        {
            "id": "visitor_cta",
            "topic_id": "visitor_cta",
            "label": "Visitor contact / lead form",
            "keywords": ("cta", "@", "заявк", "телефон"),
            "stages": ("FUNCTIONAL",),
        },
        {
            "id": "brand_assets",
            "topic_id": "brand_assets",
            "label": "Brand assets availability",
            "keywords": ("brand", "logo", "photo", "asset", "логотип"),
            "stages": ("NON_FUNCTIONAL", "RISKS"),
        },
        {
            "id": "design_references",
            "topic_id": "design_references",
            "label": "Design references and what to copy",
            "keywords": ("референс", "пример", "похож", "нравится", "reference"),
            "stages": ("NON_FUNCTIONAL",),
        },
        {
            "id": "design_direction",
            "topic_id": "design_direction",
            "label": "Design direction (calm vs motion vs 3D)",
            "keywords": ("дизайн", "лаконич", "3d", "анимац", "спокойн", "визуал"),
            "stages": ("NON_FUNCTIONAL",),
        },
        {
            "id": "auth_who",
            "label": "Auth / who can use the bot",
            "keywords": ("auth", "admin", "public", "member", "allow"),
            "stages": ("NON_FUNCTIONAL", "USERS"),
        },
        {
            "id": "external_systems",
            "label": "External systems to call",
            "keywords": ("api", "integration", "crm", "calendar", "sheet"),
            "stages": ("INTEGRATIONS",),
        },
        {
            "id": "voice_input",
            "label": "Voice input needed?",
            "keywords": ("voice", "whisper", "audio", "speech"),
            "stages": ("NON_FUNCTIONAL", "FUNCTIONAL"),
        },
        {
            "id": "languages",
            "label": "Languages",
            "keywords": ("language", "russian", "english", "locale"),
            "stages": ("NON_FUNCTIONAL",),
        },
    ],
    "rest_service": [
        {
            "id": "resources",
            "label": "Resources and operations",
            "keywords": ("resource", "crud", "endpoint", "operation", "api"),
            "stages": ("FUNCTIONAL",),
        },
        {
            "id": "auth_model",
            "label": "Auth model",
            "keywords": ("auth", "jwt", "api key", "oauth", "token"),
            "stages": ("NON_FUNCTIONAL",),
        },
        {
            "id": "consumers",
            "label": "Consumers (who calls the API)",
            "keywords": ("consumer", "client", "caller", "mobile", "partner"),
            "stages": ("USERS", "BUSINESS_CONTEXT"),
        },
        {
            "id": "volume",
            "label": "SLA / volume expectations",
            "keywords": ("sla", "volume", "rps", "throughput", "latency"),
            "stages": ("NON_FUNCTIONAL",),
        },
        {
            "id": "deployment",
            "label": "Deployment target",
            "keywords": ("deploy", "host", "docker", "cloud", "vps"),
            "stages": ("INTEGRATIONS", "NON_FUNCTIONAL"),
        },
    ],
    "ai_automation": [
        {
            "id": "trigger",
            "label": "Trigger",
            "keywords": ("trigger", "webhook", "schedule", "cron", "telegram"),
            "stages": ("FUNCTIONAL", "UNDERSTANDING_IDEA"),
        },
        {
            "id": "io",
            "label": "Inputs / outputs",
            "keywords": ("input", "output", "payload", "result"),
            "stages": ("FUNCTIONAL",),
        },
        {
            "id": "human_approval",
            "label": "Human approval needed?",
            "keywords": ("approval", "hitl", "human", "review"),
            "stages": ("NON_FUNCTIONAL", "RISKS"),
        },
        {
            "id": "failure_handling",
            "label": "Failure handling",
            "keywords": ("fail", "retry", "error", "dead letter"),
            "stages": ("RISKS", "NON_FUNCTIONAL"),
        },
        {
            "id": "cost_limits",
            "label": "Cost / rate limits",
            "keywords": ("cost", "rate", "limit", "budget", "token"),
            "stages": ("NON_FUNCTIONAL", "RISKS"),
        },
        {
            "id": "data_sensitivity",
            "label": "Data sensitivity",
            "keywords": ("sensitive", "pii", "privacy", "gdpr", "secret"),
            "stages": ("NON_FUNCTIONAL", "RISKS"),
        },
    ],
}

# Generic items always checked when product_type is unknown / any.
GENERIC_CHECKLIST: list[dict[str, object]] = [
    {
        "id": "mvp_scope",
        "topic_id": "out_of_scope",
        "label": "MVP scope stated",
        "keywords": ("mvp", "scope", "out of scope", "v1", "not in"),
        "stages": ("BUSINESS_CONTEXT", "FUNCTIONAL", "REVIEW"),
    },
    {
        "id": "primary_user",
        "topic_id": "roles",
        "label": "Primary user / job",
        "keywords": ("user", "customer", "owner", "job"),
        "stages": ("USERS", "UNDERSTANDING_IDEA"),
    },
    {
        "id": "purpose_problem",
        "topic_id": "purpose_problem",
        "label": "Purpose / problem",
        "keywords": ("problem", "цель", "идея"),
        "stages": ("UNDERSTANDING_IDEA",),
    },
    {
        "id": "records",
        "topic_id": "records",
        "label": "Data / records",
        "keywords": ("данн", "record", "поле", "хран"),
        "stages": ("DATA",),
    },
    {
        "id": "legal_compliance",
        "topic_id": "legal_compliance",
        "label": "RU legal / 152-FZ / industry constraints",
        "keywords": ("152", "пдн", "персональн", "политик", "соглас", "закон"),
        "stages": ("NON_FUNCTIONAL", "RISKS"),
    },
    {
        "id": "acceptance",
        "topic_id": "acceptance",
        "label": "Acceptance criteria",
        "keywords": ("приёмк", "acceptance", "демо"),
        "stages": ("ACCEPTANCE",),
    },
]


# Quality items ("unit tests for English") — stricter than section presence.
QUALITY_CHECKLIST: list[dict[str, object]] = [
    {
        "id": "measurable_success",
        "kind": "quality",
        "strict": True,
        "topic_id": "success_mvp",
        "label": "Success criteria are measurable",
        "keywords": (
            "заявк",
            "обращен",
            "демо",
            "время",
            "ошиб",
            "metric",
            "меньше",
            "больше",
            "percent",
            "%",
        ),
        "stages": ("BUSINESS_CONTEXT",),
        "blocking": True,
    },
    {
        "id": "scope_bounded",
        "kind": "quality",
        "topic_id": "out_of_scope",
        "label": "MVP scope / non-goals stated",
        "keywords": ("out of scope", "вне объёма", "не в v1", "без оплаты", "потом"),
        "stages": ("BUSINESS_CONTEXT",),
        "blocking": True,
    },
    {
        "id": "testable_requirements",
        "kind": "quality",
        "label": "Requirements are testable and unambiguous",
        "keywords": (),
        "stages": (),
        "blocking": True,
    },
]


@dataclass
class CoverageItemResult:
    id: str
    label: str
    covered: bool
    evidence_entity_ids: list[str] = field(default_factory=list)
    kind: str = "section"
    blocking: bool = False

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "covered": self.covered,
            "evidence_entity_ids": self.evidence_entity_ids,
            "kind": self.kind,
            "blocking": self.blocking,
        }


@dataclass
class CoverageReport:
    product_type: str | None
    items: list[CoverageItemResult]
    open_question_count: int
    requirement_count: int

    @property
    def covered_count(self) -> int:
        return sum(1 for i in self.items if i.covered)

    @property
    def missing(self) -> list[CoverageItemResult]:
        return [i for i in self.items if not i.covered]

    @property
    def quality_items(self) -> list[CoverageItemResult]:
        return [i for i in self.items if i.kind == "quality"]

    @property
    def quality_ok(self) -> bool:
        blocking = [i for i in self.quality_items if i.blocking]
        if not blocking:
            return True
        return all(i.covered for i in blocking)

    @property
    def ratio(self) -> float:
        if not self.items:
            return 1.0
        return self.covered_count / len(self.items)

    def as_dict(self) -> dict:
        return {
            "product_type": self.product_type,
            "covered_count": self.covered_count,
            "total": len(self.items),
            "ratio": round(self.ratio, 3),
            "open_question_count": self.open_question_count,
            "requirement_count": self.requirement_count,
            "quality_ok": self.quality_ok,
            "items": [i.as_dict() for i in self.items],
            "missing": [i.as_dict() for i in self.missing],
            "quality": [i.as_dict() for i in self.quality_items],
        }


def checklist_for_product(product_type: str | None) -> list[dict[str, object]]:
    items = list(GENERIC_CHECKLIST)
    if product_type and product_type in PRODUCT_CHECKLISTS:
        items.extend(PRODUCT_CHECKLISTS[product_type])
    return items


def _entity_blob(entity) -> str:
    payload = entity.payload or {}
    parts = [
        entity.name or "",
        str(payload.get("title", "")),
        str(payload.get("description", "")),
        str(payload.get("question", "")),
        str(payload.get("stage", "")),
        str(payload.get("summary", "")),
    ]
    return " ".join(parts).lower()


def evaluate_coverage(
    kg: KnowledgeRepository,
    project_id: uuid.UUID,
    *,
    product_type: str | None,
) -> CoverageReport:
    """Mark checklist items covered when a Requirement/Risk text matches keywords or stage."""
    requirements = [
        e
        for e in kg.list_entities(project_id, type_="Requirement")
        if e.status != "archived"
    ]
    risks = [
        e for e in kg.list_entities(project_id, type_="Risk") if e.status != "archived"
    ]
    open_questions = [
        e
        for e in kg.list_entities(project_id, type_="OpenQuestion")
        if e.status == "open"
    ]
    corpus = requirements + risks

    results: list[CoverageItemResult] = []
    catalog = list(checklist_for_product(product_type)) + list(QUALITY_CHECKLIST)
    for item in catalog:
        keywords = tuple(str(k).lower() for k in (item.get("keywords") or ()))
        stages = {str(s) for s in (item.get("stages") or ())}
        evidence: list[str] = []
        item_topic = str(item.get("topic_id") or item["id"])
        strict = bool(item.get("strict"))
        kind = str(item.get("kind") or "section")
        if item["id"] == "testable_requirements":
            for entity in requirements:
                description = str((entity.payload or {}).get("description", ""))
                if len(description) >= 12:
                    evidence.append(str(entity.id))
            results.append(
                CoverageItemResult(
                    id=str(item["id"]),
                    label=str(item["label"]),
                    covered=bool(evidence),
                    evidence_entity_ids=evidence,
                    kind="quality",
                    blocking=bool(item.get("blocking")),
                )
            )
            continue
        scan = list(corpus)
        scan.extend(open_questions)
        for entity in scan:
            blob = _entity_blob(entity)
            stage = str((entity.payload or {}).get("stage", ""))
            payload_topic = str((entity.payload or {}).get("topic_id") or "")
            keyword_hit = any(k in blob for k in keywords) if keywords else False
            stage_hit = bool(stages) and stage in stages
            description = str((entity.payload or {}).get("description", ""))
            handed_off = bool((entity.payload or {}).get("escalate_to"))
            if payload_topic and payload_topic == item_topic:
                if not strict or keyword_hit or handed_off:
                    evidence.append(str(entity.id))
            elif keyword_hit:
                evidence.append(str(entity.id))
            elif (not strict) and stage_hit and len(description) >= 12:
                evidence.append(str(entity.id))
        results.append(
            CoverageItemResult(
                id=str(item["id"]),
                label=str(item["label"]),
                covered=bool(evidence),
                evidence_entity_ids=evidence,
                kind=kind,
                blocking=bool(item.get("blocking")),
            )
        )

    return CoverageReport(
        product_type=product_type,
        items=results,
        open_question_count=len(open_questions),
        requirement_count=len(requirements),
    )


def mode_exit_checklist(
    mode: str,
    *,
    coverage: CoverageReport | None = None,
    open_question_count: int = 0,
    has_draft_tz: bool = False,
    task_count: int = 0,
) -> list[dict[str, object]]:
    """Deterministic exit checks per Coordinator mode (docs/07-AI-Rules.md)."""
    checks: list[dict[str, object]] = []
    if mode == "discovery":
        ratio = coverage.ratio if coverage else 0.0
        quality_ok = coverage.quality_ok if coverage else False
        checks.extend(
            [
                {
                    "id": "has_requirements",
                    "ok": (coverage.requirement_count if coverage else 0) > 0,
                    "label": "At least one Requirement captured",
                },
                {
                    "id": "coverage_floor",
                    "ok": ratio >= 0.4 or has_draft_tz,
                    "label": "Coverage ratio ≥ 0.4 or draft TZ exists",
                },
                {
                    "id": "quality_floor",
                    "ok": quality_ok or has_draft_tz,
                    "label": "Quality floor (testable, measurable success, bounded scope) or escalated draft",
                },
                {
                    "id": "draft_tz_for_owner",
                    "ok": has_draft_tz,
                    "label": "Draft TZ artifact present before owner gate",
                },
            ]
        )
    elif mode == "reviewer":
        checks.extend(
            [
                {
                    "id": "draft_present",
                    "ok": has_draft_tz,
                    "label": "Draft TZ available to review",
                },
                {
                    "id": "gaps_listed",
                    "ok": True,  # structural; LLM fills gaps later
                    "label": "Gap list slot available",
                },
                {
                    "id": "open_questions_bounded",
                    "ok": open_question_count <= 8,
                    "label": "Open questions not exploding (>8)",
                },
            ]
        )
    elif mode == "architect":
        checks.append(
            {
                "id": "product_type_locked",
                "ok": bool(coverage and coverage.product_type),
                "label": "Product type locked",
            }
        )
    elif mode == "planner":
        checks.append(
            {
                "id": "has_work_items",
                "ok": task_count > 0 or (coverage and coverage.requirement_count > 0),
                "label": "Requirements or tasks available to plan",
            }
        )
    else:
        checks.append(
            {
                "id": "context_loaded",
                "ok": True,
                "label": f"Mode {mode} context loaded",
            }
        )
    return checks
