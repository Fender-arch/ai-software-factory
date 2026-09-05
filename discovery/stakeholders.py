"""Customer / Organization facts from the Discovery intro (DEC-015)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from core.models import Project
from knowledge.repository import KnowledgeRepository

CUSTOMER_TYPE = "Customer"
ORGANIZATION_TYPE = "Organization"

_PHONE_RE = re.compile(
    r"(?:\+7|8|\b7)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}"
)
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+\w")
_TG_RE = re.compile(r"@[\w_]{4,32}")
_NAME_RE = re.compile(
    r"(?:меня\s+зовут|зовут меня|обращайтесь(?:\s+ко мне)?)"
    r"\s*[—–:-]?\s*([A-Za-zА-Яа-яЁё]{2,40}(?:\s+[A-Za-zА-Яа-яЁё]{2,40}){0,2})",
    re.I,
)
_BARE_NAME_RE = re.compile(
    r"^[A-Za-zА-Яа-яЁё]{2,40}(?:\s+[A-Za-zА-Яа-яЁё]{2,40}){0,2}$"
)
_COMPANY_RE = re.compile(
    r"(?:компани[яи]|ооо|студи[яи]|агентств[оа]|организаци[яи]|ип)\s+"
    r"[«\"]?([A-Za-zА-Яа-яЁё0-9][^,.;\n]{1,60})",
    re.I,
)
_INDUSTRY_RE = re.compile(
    r"(?:отрасл[ьи]|сфер[аеуы]|занимаемся|работаем в)\s+"
    r"[—–:-]?\s*([^,.;\n]{3,80})",
    re.I,
)
_ROLE_RE = re.compile(
    r"(?:я\s+)?(директор|владелец|основатель|менеджер|маркетолог|"
    r"руководитель|заказчик|собственник|cto|ceo|pm)\b",
    re.I,
)

_INDIVIDUAL_SIGNALS = (
    "физлицо",
    "физ лицо",
    "физ. лицо",
    "нет компании",
    "без названия",
    "нет названия компании",
    "частное лицо",
    "индивидуальн",
    "я сам",
    "я сама",
    "без юрлица",
)
_COMPANY_CHIPS = ("я физлицо", "компании нет")
_TG_ONLY_SIGNALS = (
    "достаточно этого чата",
    "достаточно этого telegram",
    "этого чата в telegram",
)


@dataclass
class StakeholderFacts:
    display_name: str = ""
    address_as: str = ""
    role: str = ""
    phone: str = ""
    email: str = ""
    telegram: str = ""
    telegram_chat_ok: bool = False
    organization_name: str = ""
    is_individual: bool = False
    industry: str = ""
    extras: list[str] = field(default_factory=list)

    def has_name(self) -> bool:
        return bool(self.display_name or self.address_as)

    def has_contact(self) -> bool:
        return bool(
            self.phone
            or self.email
            or self.telegram
            or self.telegram_chat_ok
        )

    def has_org(self) -> bool:
        return bool(self.organization_name or self.is_individual)

    def sufficient(self) -> bool:
        return self.has_name() and self.has_contact() and self.has_org()

    def missing_ru(self) -> list[str]:
        gaps: list[str] = []
        if not self.has_name():
            gaps.append("как к вам обращаться")
        if not self.has_contact():
            gaps.append("контакт (телефон, почта или Telegram)")
        if not self.has_org():
            gaps.append("компания или явно «нет названия / физлицо»")
        return gaps

    def summary_en(self) -> str:
        parts: list[str] = []
        if self.display_name:
            parts.append(f"Customer name: {self.display_name}")
        if self.address_as and self.address_as != self.display_name:
            parts.append(f"Address as: {self.address_as}")
        if self.role:
            parts.append(f"Role: {self.role}")
        contacts = [
            f"phone {self.phone}" if self.phone else "",
            f"email {self.email}" if self.email else "",
            f"telegram {self.telegram}" if self.telegram else "",
            "Telegram chat is enough" if self.telegram_chat_ok else "",
        ]
        contacts = [c for c in contacts if c]
        if contacts:
            parts.append("Contacts: " + "; ".join(contacts))
        if self.is_individual or not self.organization_name:
            if self.is_individual:
                parts.append("Organization: individual / no company name")
        if self.organization_name:
            parts.append(f"Organization: {self.organization_name}")
        if self.industry:
            parts.append(f"Industry: {self.industry}")
        return ". ".join(parts) or "Customer introduction captured."

    def contact_line_ru(self) -> str:
        bits: list[str] = []
        if self.display_name:
            bits.append(self.display_name)
        if self.role:
            bits.append(self.role)
        if self.phone:
            bits.append(self.phone)
        if self.email:
            bits.append(self.email)
        if self.telegram:
            bits.append(self.telegram)
        if self.telegram_chat_ok and not self.telegram:
            bits.append("Telegram: этот чат")
        return ", ".join(bits)


def parse_stakeholder_text(text: str, *, choice_ids: list[str] | None = None) -> StakeholderFacts:
    raw = (text or "").strip()
    lowered = raw.lower()
    facts = StakeholderFacts()
    chips = {str(x) for x in (choice_ids or [])}

    if "intro_individual" in chips or any(s in lowered for s in _INDIVIDUAL_SIGNALS):
        facts.is_individual = True
    if "intro_tg" in chips or any(s in lowered for s in _TG_ONLY_SIGNALS):
        facts.telegram_chat_ok = True
    if any(s in lowered for s in _COMPANY_CHIPS):
        facts.is_individual = True

    phone = _PHONE_RE.search(raw)
    if phone:
        facts.phone = re.sub(r"\s+", " ", phone.group(0)).strip()
    email = _EMAIL_RE.search(raw)
    if email:
        facts.email = email.group(0).strip()
    tg = _TG_RE.search(raw)
    if tg:
        facts.telegram = tg.group(0).strip()

    name = _NAME_RE.search(raw)
    if name:
        facts.display_name = name.group(1).strip(" .,-")
        facts.address_as = facts.display_name
    elif not facts.display_name:
        first = raw.split("\n", 1)[0].strip()
        tokens = [t for t in re.split(r"[,\.;/]| и ", first) if t.strip()]
        head = (tokens[0] if tokens else "").strip()
        if _BARE_NAME_RE.fullmatch(head) and not any(
            k in head.lower()
            for k in ("компани", "нужен", "сайт", "бот", "хочу", "зовут", "меня")
        ):
            facts.display_name = head
            facts.address_as = head

    company = _COMPANY_RE.search(raw)
    if company:
        facts.organization_name = company.group(1).strip(" «»\"'")
        facts.is_individual = False

    industry = _INDUSTRY_RE.search(raw)
    if industry:
        facts.industry = industry.group(1).strip(" .,-")

    role = _ROLE_RE.search(raw)
    if role:
        facts.role = role.group(1).strip().lower()

    return facts


def merge_facts(base: StakeholderFacts, extra: StakeholderFacts) -> StakeholderFacts:
    return StakeholderFacts(
        display_name=extra.display_name or base.display_name,
        address_as=extra.address_as or base.address_as,
        role=extra.role or base.role,
        phone=extra.phone or base.phone,
        email=extra.email or base.email,
        telegram=extra.telegram or base.telegram,
        telegram_chat_ok=extra.telegram_chat_ok or base.telegram_chat_ok,
        organization_name=extra.organization_name or base.organization_name,
        is_individual=extra.is_individual or (base.is_individual and not extra.organization_name),
        industry=extra.industry or base.industry,
        extras=list(base.extras) + list(extra.extras),
    )


def facts_from_entities(kg: KnowledgeRepository, project_id) -> StakeholderFacts:
    facts = StakeholderFacts()
    customers = kg.list_entities(project_id, type_=CUSTOMER_TYPE)
    if customers:
        payload = dict(customers[0].payload or {})
        facts.display_name = str(payload.get("display_name") or customers[0].name or "")
        facts.address_as = str(payload.get("address_as") or facts.display_name)
        facts.role = str(payload.get("role") or "")
        facts.phone = str(payload.get("phone") or "")
        facts.email = str(payload.get("email") or "")
        facts.telegram = str(payload.get("telegram") or "")
        facts.telegram_chat_ok = bool(payload.get("telegram_chat_ok"))
    orgs = kg.list_entities(project_id, type_=ORGANIZATION_TYPE)
    if orgs:
        payload = dict(orgs[0].payload or {})
        facts.organization_name = str(payload.get("name") or "")
        facts.is_individual = bool(payload.get("is_individual") or payload.get("no_company_name"))
        facts.industry = str(payload.get("industry") or "")
    return facts


def upsert_stakeholders(
    kg: KnowledgeRepository,
    project: Project,
    facts: StakeholderFacts,
) -> tuple[object | None, object | None]:
    """Create or update Customer + Organization. No new tables."""
    existing_c = kg.list_entities(project.id, type_=CUSTOMER_TYPE)
    customer_payload = {
        "display_name": facts.display_name,
        "address_as": facts.address_as or facts.display_name,
        "role": facts.role,
        "phone": facts.phone,
        "email": facts.email,
        "telegram": facts.telegram,
        "telegram_chat_ok": facts.telegram_chat_ok,
        "is_individual": facts.is_individual,
    }
    name = facts.display_name or facts.address_as or "Customer"
    if existing_c:
        prev = dict(existing_c[0].payload or {})
        prev.update({k: v for k, v in customer_payload.items() if v or v is False})
        customer = kg.update_entity(
            existing_c[0],
            name=name,
            payload=prev,
        )
    else:
        customer = kg.create_entity(
            project_id=project.id,
            type_=CUSTOMER_TYPE,
            name=name,
            status="active",
            payload=customer_payload,
            confidence=0.7,
        )

    org_payload = {
        "name": facts.organization_name,
        "is_individual": facts.is_individual,
        "no_company_name": facts.is_individual and not facts.organization_name,
        "industry": facts.industry,
    }
    org_name = facts.organization_name or (
        "Individual / no company name" if facts.is_individual else "Organization"
    )
    existing_o = kg.list_entities(project.id, type_=ORGANIZATION_TYPE)
    if existing_o:
        prev = dict(existing_o[0].payload or {})
        prev.update({k: v for k, v in org_payload.items() if v or v is False})
        organization = kg.update_entity(existing_o[0], name=org_name, payload=prev)
    else:
        organization = kg.create_entity(
            project_id=project.id,
            type_=ORGANIZATION_TYPE,
            name=org_name,
            status="active",
            payload=org_payload,
            confidence=0.65,
        )

    if customer and organization:
        already = any(
            rel.from_entity_id == customer.id and rel.to_entity_id == organization.id
            for rel in kg.list_relations(project.id, type_="related_to")
        )
        if not already:
            kg.create_relation(
                project_id=project.id,
                from_entity_id=customer.id,
                to_entity_id=organization.id,
                type_="related_to",
                payload={"role": "represents"},
            )
    return customer, organization


def stakeholder_header_lines(kg: KnowledgeRepository, project: Project) -> list[str]:
    """Russian lines for the TZ шапка (contacts + company)."""
    facts = facts_from_entities(kg, project.id)
    lines: list[str] = []
    if facts.display_name:
        lines.append(f"Имя: {facts.display_name}")
    if facts.role:
        lines.append(f"Роль: {facts.role}")
    if facts.phone:
        lines.append(f"Телефон: {facts.phone}")
    if facts.email:
        lines.append(f"Email: {facts.email}")
    if facts.telegram:
        lines.append(f"Telegram: {facts.telegram}")
    elif facts.telegram_chat_ok:
        lines.append("Telegram: этот чат")
    if facts.organization_name:
        lines.append(f"Компания: {facts.organization_name}")
    elif facts.is_individual:
        lines.append("Компания: нет названия / физлицо")
    if facts.industry:
        lines.append(f"Отрасль: {facts.industry}")
    return lines
