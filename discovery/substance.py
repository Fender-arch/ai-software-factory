"""Implementation-content gates: ask now, escalate only if the customer hands off."""

from __future__ import annotations

import re

from discovery.quality import is_underspecified
from discovery.tz_outline import PUBLIC_PRESENCE_TOPIC_IDS, Choice, TzTopic

# Chips that mean “skip remaining write-in details for this section”.
STUB_CHOICE_IDS = frozenset(
    {
        "id_stub",
        "cat_stub",
        "ref_none",
        "ref_later",
        "brand_simple",
        "brand_later",
        "int_none",
        "ops_unsure",
        "promo_none",
    }
)

_URL_RE = re.compile(r"https?://[^\s]+", re.I)
_HANDLE_RE = re.compile(r"@[\w]{3,}|(?:t\.me|telegram\.me)/[\w+]+", re.I)
_EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
_PHONE_RE = re.compile(r"(?:\+?\d[\d\s\-()]{9,}\d)")
_DOMAIN_RE = re.compile(
    r"(?:https?://)?(?:[\w-]+\.)+(?:ru|com|org|net|io|dev|app|site)(?:/[^\s]*)?",
    re.I,
)
_BRAND_TOKEN_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9]{2,}\b")
_REUSE_RE = re.compile(
    r"типограф|шрифт|сетк|анимац|motion|цвет|тон|воздух|нравит|взять|"
    r"как у|3d|кнопк|палитр|иллюстрац|герой|хук|юмор|лаконич|контраст",
    re.I,
)
_CHANNEL_HINT_RE = re.compile(r"канал|channel|чат заявок|группу заявок", re.I)
_EXISTING_HOST_RE = re.compile(
    r"существующ\w*\s+сервер|доменом|уже есть сервер|наш (?:vps|сервер|хост)",
    re.I,
)
_SHORT_DEADLINE_RE = re.compile(
    r"1\s*[–\-—]?\s*2\s*недел|как можно скорее|ближайш\w+\s+недел",
    re.I,
)
_LOUD_DESIGN_RE = re.compile(
    r"\b3d\b|webgl|вау|wow|преми|кричащ|всемирн\w+\s+прем|awwwards",
    re.I,
)
_FILE_RE = re.compile(r"файл прикреп|\[file |\.(?:png|jpe?g|webp|svg|gif)\b", re.I)

_HINTS: dict[str, str] = {
    "public_identity": (
        "Нужны имя или бренд, роль и одна фраза для посетителя — "
        "либо заглушка «Пока «Имя · IT-услуги»»."
    ),
    "offer_catalog": (
        "Нужны названия услуг с 1–2 предложениями и/или кейсы со ссылками — "
        "либо заглушка «Пока 3 карточки-заглушки»."
    ),
    "visitor_cta": (
        "Нужен публичный контакт (@ник, телефон или почта) и куда уходит заявка — "
        "не этот чат сбора ТЗ, либо форма «имя, контакт, сообщение»."
    ),
    "design_references": (
        "Ссылки есть — напишите, что с них взять (шрифт, сетка, анимация, тон), "
        "либо выберите «референсов нет» / «пришлю отдельно»."
    ),
    "design_direction": (
        "Выберите уровень визуала: спокойный, motion, один лёгкий 3D-герой "
        "или кричащий 3D — это меняет срок."
    ),
    "brand_assets": (
        "Пришлите логотип/цвета или выберите простой вид без брендбука."
    ),
    "integrations": (
        "Если заявки в канал или CRM — укажите @канал, ссылку или название системы. "
        "Иначе выберите «этот Telegram» или «без внешних систем»."
    ),
    "ops_constraints": (
        "Если крутится рядом с уже существующим сервером — напишите домен или "
        "хост, либо выберите «пусть предложит разработчик»."
    ),
    "interaction_model": (
        "Для Mini App уточните: только приложение, или ещё диалог в чате бота."
    ),
}


def leftover_without_labels(regular_hits: list[Choice], leftover_text: str) -> str:
    extra = leftover_text or ""
    for choice in regular_hits:
        extra = extra.replace(choice.label, "")
    return re.sub(r"\s+", " ", extra).strip(" \n\t.;,")


_GENERIC_LATIN = frozenset(
    {
        "mvp",
        "api",
        "faq",
        "url",
        "http",
        "https",
        "crm",
        "seo",
        "it",
        "app",
        "bot",
        "mini",
        "telegram",
        "rest",
        "json",
        "html",
        "css",
        "pdf",
        "www",
    }
)


def looks_like_identity(text: str) -> bool:
    compact = re.sub(r"\s+", " ", (text or "").strip())
    if len(compact) < 4:
        return False
    if re.search(r"[«\"][^»\"]{2,}[»\"]", compact):
        return True
    tokens = _BRAND_TOKEN_RE.findall(compact)
    real = [t for t in tokens if t.lower() not in _GENERIC_LATIN]
    if any(
        re.search(r"\d", t)
        or (t.isupper() and len(t) >= 4)
        or (t[0].isupper() and any(c.islower() for c in t[1:]))
        for t in real
    ):
        return True
    if real and re.search(r"студи|бренд|компани|\bип\b|агентств", compact, re.I):
        return True
    return False


def destination_specified(text: str) -> bool:
    blob = text or ""
    if _HANDLE_RE.search(blob) or _EMAIL_RE.search(blob) or _PHONE_RE.search(blob):
        return True
    if re.search(r"этот telegram|этот чат|мне в telegram|cta_notify", blob, re.I):
        return True
    if re.search(r"форма заявки|имя, контакт|без внешних", blob, re.I):
        return True
    return False


def _extra_ok(extra: str) -> bool:
    return bool(extra) and not is_underspecified(extra, has_choice=False)


def _stub_selected(regular_hits: list[Choice]) -> bool:
    return any(c.id in STUB_CHOICE_IDS for c in regular_hits)


def _writein_pending(regular_hits: list[Choice], extra: str) -> bool:
    if (
        _extra_ok(extra)
        or _FILE_RE.search(extra or "")
        or _DOMAIN_RE.search(extra or "")
        or _HANDLE_RE.search(extra or "")
        or _EMAIL_RE.search(extra or "")
        or _PHONE_RE.search(extra or "")
    ):
        return False
    if _stub_selected(regular_hits):
        return False
    return any(not c.sufficient for c in regular_hits)


def _content_rule_ok(
    topic: TzTopic,
    regular_hits: list[Choice],
    extra: str,
    description: str,
) -> bool:
    blob = f"{description or ''} {extra or ''}"
    hit_ids = {c.id for c in regular_hits}

    if topic.id == "design_references":
        if _stub_selected(regular_hits) or _REUSE_RE.search(blob):
            return True
        if _URL_RE.search(blob) or re.search(r"\.\w{2,4}\b", blob):
            return False
        return True

    if topic.id == "offer_catalog":
        if "cat_stub" in hit_ids or _extra_ok(extra) or _URL_RE.search(blob):
            return True
        service_only = hit_ids and hit_ids <= {"cat_sites", "cat_bots", "cat_ai"}
        if service_only or "cat_portfolio" in hit_ids or "cat_write" in hit_ids:
            return False
        return True

    if topic.id == "visitor_cta":
        promised = {"cta_tg", "cta_phone", "cta_write", "cta_channel"} & hit_ids
        if promised and not destination_specified(blob):
            return False
        if "cta_form" in hit_ids or "cta_notify" in hit_ids or "int_this_chat" in hit_ids:
            return True
        if destination_specified(blob):
            return True
        if _CHANNEL_HINT_RE.search(blob) and not _HANDLE_RE.search(blob):
            return False
        return False

    if topic.id == "public_identity":
        if _stub_selected(regular_hits) or looks_like_identity(blob):
            return True
        return False if topic.needs_substance and not regular_hits else True

    if topic.id == "integrations":
        if "int_none" in hit_ids or "int_email" in hit_ids or "int_this_chat" in hit_ids:
            return True
        if _CHANNEL_HINT_RE.search(blob) and not _HANDLE_RE.search(blob):
            return False
        if {"int_crm", "int_sheets", "int_tg_channel"} & hit_ids and not (
            _extra_ok(extra) or _HANDLE_RE.search(blob) or _DOMAIN_RE.search(blob)
        ):
            return False
        return True

    if topic.id == "ops_constraints":
        if "ops_unsure" in hit_ids:
            return True
        if "ops_existing" in hit_ids or _EXISTING_HOST_RE.search(blob):
            if _DOMAIN_RE.search(blob):
                return True
            if extra and re.search(r"vps|host|timeweb|beget|selectel|reg\.ru", extra, re.I):
                return True
            return False
        return True

    if topic.id == "brand_assets":
        if _stub_selected(regular_hits) or _FILE_RE.search(blob) or _extra_ok(extra):
            return True
        return not topic.needs_substance

    return True


def reask_hint(topic: TzTopic) -> str:
    return _HINTS.get(
        topic.id,
        "Напишите конкретные данные для сборки или выберите заглушку / "
        "«Обсудить с разработчиком, что нужно зафиксировать».",
    )


def should_reask(
    topic: TzTopic,
    regular_hits: list[Choice],
    leftover_text: str,
    description: str,
) -> str | None:
    """Return a customer-facing hint when the answer is not enough to implement."""
    extra = leftover_without_labels(regular_hits, leftover_text)
    identity_ok = topic.id == "public_identity" and looks_like_identity(description or extra)

    if _writein_pending(regular_hits, extra) and not identity_ok:
        return reask_hint(topic)
    if not _content_rule_ok(topic, regular_hits, extra, description):
        return reask_hint(topic)

    extra_ok = _extra_ok(extra) or bool(_FILE_RE.search(extra or description or ""))
    if topic.needs_substance:
        if identity_ok or extra_ok or any(c.sufficient for c in regular_hits):
            if _content_rule_ok(topic, regular_hits, extra, description):
                return None
            return reask_hint(topic)
        return reask_hint(topic)

    if is_underspecified(description, has_choice=bool(regular_hits)) and not identity_ok:
        return (
            "Выберите вариант или опишите результат своими словами. "
            "Если не знаете — «Обсудить с разработчиком, что нужно зафиксировать»."
        )
    return None


def infer_skips_topic(topic: TzTopic) -> bool:
    """Do not auto-close topics that still need implementation content from the customer."""
    if topic.needs_substance:
        return True
    return topic.id in PUBLIC_PRESENCE_TOPIC_IDS


def host_address_missing(text: str) -> bool:
    blob = text or ""
    if not _EXISTING_HOST_RE.search(blob):
        return False
    if _DOMAIN_RE.search(blob):
        return False
    if re.search(r"не знаю|предложит разработчик", blob, re.I):
        return False
    if re.search(r"vps|timeweb|beget|selectel|reg\.ru", blob, re.I):
        return False
    return True


def short_deadline(text: str) -> bool:
    return bool(_SHORT_DEADLINE_RE.search(text or ""))


def loud_design(text: str) -> bool:
    return bool(_LOUD_DESIGN_RE.search(text or ""))


def design_deadline_override(timeline_text: str) -> str | None:
    if not short_deadline(timeline_text):
        return None
    return (
        "Срок уже «как можно скорее / 1–2 недели». Кричащий 3D и «уровень премий» "
        "обычно не влезают. Какой визуал в v1: спокойный, лёгкий motion, "
        "один 3D-герой — или вау важнее и срок гибкий?"
    )
