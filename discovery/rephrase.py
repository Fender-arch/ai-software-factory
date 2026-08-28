"""Rewrite remaining TZ questions, titles, and choice chips for *this* task.

The catalog stays the source of topic ids and chip ids. After the customer
describes the idea, heuristics (and later Groq) retarget the wording so the
interview does not look like a generic form.
"""

from __future__ import annotations

import re
from dataclasses import replace

from discovery.fsm import DiscoveryStage
from discovery.literacy import ITLiteracy
from discovery.quality import is_underspecified
from discovery.tz_outline import Choice, OutlinePlan, TzTopic, topic_by_id

_Q = ITLiteracy

CAPABILITY_TOPIC_IDS: tuple[str, ...] = (
    "booking_rules",
    "notification_rules",
    "api_consumers",
    "voice_input",
    "failure_path",
)

LOCKED_OVERRIDE_TOPIC_IDS = frozenset({"design_direction"})
FROZEN_CHOICE_TOPIC_IDS = frozenset(
    {
        "budget",
        "contacts",
        "preferred_contact",
        "timeline",
        "legal_compliance",
    }
)
CTX_OPTION_ID_RE = re.compile(r"^ctx:[a-z0-9_]{2,32}$")
MAX_EXTRA_OPTIONS = 4

# pattern → (slug, display name)
_TOOL_PATTERNS: tuple[tuple[str, str, str], ...] = (
    (r"whatsapp|ватсап|вацап", "whatsapp", "WhatsApp"),
    (r"telegram|телеграм", "telegram", "Telegram"),
    (r"google\s*sheet|гугл\s*таблиц", "sheets", "Google Sheets"),
    (r"excel|эксель", "excel", "Excel"),
    (r"\b1\s*с\b|\b1c\b", "onec", "1С"),
    (r"bitrix|битрикс", "bitrix", "Битрикс"),
    (r"amocrm|amo\s*crm", "amocrm", "amoCRM"),
    (r"instagram|инстаграм", "instagram", "Instagram"),
    (r"тетрад", "notebook", "тетрадки"),
    (r"звонк|по телефону", "phone", "звонков"),
    (r"crm", "crm", "CRM"),
)

_CHAT_TOOL_SLUGS = frozenset({"whatsapp", "telegram", "instagram", "phone"})
_LEDGER_TOOL_SLUGS = frozenset({"sheets", "excel", "notebook", "onec"})
_PROCESS_HINTS = (
    "сейчас",
    "ведём",
    "ведем",
    "записыва",
    "через",
    "вместо",
    "в тетрад",
    "вручную",
    "as-is",
    "as is",
)
_AMBIGUOUS_TOOL_SLUGS = frozenset({"telegram"})

# Requested delivery surface (not the as-is process). Used on product_shape.
_SURFACE_PATTERNS: tuple[tuple[str, str, str], ...] = (
    (r"android|андроид|\bapk\b", "android", "Приложение для Android"),
    (r"\bios\b|iphone|айфон|айпад|app store", "ios", "Приложение для iOS"),
    (
        r"мобильн(?:ое|ый|ая)?\s+приложен|приложен\w*\s+для\s+телефон|"
        r"native app|нативн\w*\s+приложен",
        "mobile",
        "Мобильное приложение",
    ),
)

# topic_id → template; `{brief}` is replaced with the captured task phrase.
_QUESTION_BY_TOPIC: dict[str, str] = {
    "product_shape": (
        "Вы описали: «{brief}». Какой тип решения ближе для первой версии?"
    ),
    "as_is_process": "Как сейчас делают «{brief}» — без этого продукта? Что в этом бесит?",
    "success_mvp": (
        "Если «{brief}» заработает в первой версии — что изменится и как "
        "поймёте, что получилось?"
    ),
    "out_of_scope": "Для «{brief}»: что точно не делаем в v1, даже если захочется потом?",
    "must_features": "Для «{brief}»: что обязательно должно работать в первой версии?",
    "primary_scenario": (
        "Один путь пользователя «{brief}» от начала до результата, который "
        "обязан работать."
    ),
    "roles": "Кто пользуется «{brief}» в первой версии и что каждый должен суметь?",
    "access": "Кто может пользоваться «{brief}»: все, кто нашёл ссылку, или только свои?",
    "records": "Какие данные нужно помнить, чтобы «{brief}» работал в v1?",
    "integrations": "Куда уходят данные из «{brief}»: Telegram, почта, таблица, CRM — или никуда?",
    "acceptance": "Как проверите, что «{brief}» сделан: что нажмёте / увидите?",
    "timeline": "Когда нужна рабочая первая версия «{brief}»?",
    "risks": "Что больше всего беспокоит в «{brief}» до старта разработки?",
}

_QUESTION_BY_CAPABILITY: dict[str, dict[str, str]] = {
    "booking": {
        "must_features": (
            "Для записи в рамках «{brief}»: что обязательно в v1 кроме выбора слота?"
        ),
        "primary_scenario": (
            "Один путь записи «{brief}»: от выбора услуги/слота до подтверждения."
        ),
        "success_mvp": (
            "Если клиенты начнут записываться через «{brief}» — как поймёте, "
            "что первая версия удалась?"
        ),
        "roles": "Кто в «{brief}»: клиент, мастер/администратор, владелец?",
        "records": "Что хранить о записи: услуга, слот, мастер, телефон клиента…?",
        "as_is_process": "Как сейчас записывают клиентов (звонок, чат, журнал) без «{brief}»?",
    },
    "leads": {
        "must_features": (
            "Для «{brief}»: как в v1 принимают заявку и что показывают посетителю?"
        ),
        "primary_scenario": (
            "Путь заявки «{brief}»: человек оставляет контакт → вам приходит уведомление."
        ),
        "success_mvp": "Если «{brief}» начнёт приносить обращения — как измерите успех v1?",
    },
    "ai": {
        "must_features": "Для «{brief}»: что ИИ обязан сделать в v1 и где нужен человек?",
        "primary_scenario": "Триггер → действие ИИ → результат для «{brief}». Один путь v1.",
        "trigger_io": "Что запускает «{brief}» и что должно получиться на выходе?",
    },
    "admin_data": {
        "must_features": "Для учёта «{brief}»: список, поиск, добавить, править — что в v1?",
        "records": "Какие сущности и поля вести в «{brief}»?",
    },
    "integration": {
        "must_features": "Для связки «{brief}»: что откуда берём и куда отдаём в v1?",
        "primary_scenario": "Событие в системе A → данные появляются в системе B. Как это для «{brief}»?",
        "integrations": "Какие системы связываем в «{brief}» (имена, что уже есть доступы)?",
    },
}

_TITLE_BY_CAPABILITY: dict[str, dict[str, str]] = {
    "booking": {
        "must_features": "Функции записи",
        "primary_scenario": "Сценарий записи",
        "records": "Данные записи",
        "roles": "Кто записывается",
        "success_mvp": "Успех записи v1",
        "as_is_process": "Как записывают сейчас",
    },
    "leads": {
        "must_features": "Заявка и витрина",
        "primary_scenario": "Путь заявки",
        "visitor_cta": "Как оставить заявку",
    },
    "ai": {
        "must_features": "Что делает ИИ",
        "primary_scenario": "Сценарий агента",
        "trigger_io": "Запуск и результат ИИ",
    },
    "admin_data": {
        "must_features": "Операции учёта",
        "records": "Что храним в учёте",
    },
    "integration": {
        "must_features": "Что синхронизируем",
        "primary_scenario": "Путь обмена",
        "integrations": "Системы для обмена",
    },
}

# capability → topic_id → choice_id → label (optional `{brief}`)
_OPTION_BY_CAPABILITY: dict[str, dict[str, dict[str, str]]] = {
    "booking": {
        "product_shape": {
            "shape_bot": "Telegram-бот записи (как вы описали)",
            "shape_miniapp": "Mini App с выбором слота в Telegram",
            "shape_website": "Сайт с онлайн-записью",
        },
        "must_features": {
            "feat_intake": "Запись на услугу / слот",
            "feat_catalog": "Список услуг, на которые можно записаться",
            "feat_admin": "Журнал записей: смотреть и править",
            "feat_notify": "Уведомление мастеру или админу о новой записи",
            "feat_remind": "Напоминание клиенту о визите",
            "feat_handoff": "Если слота нет — передать человеку",
        },
        "primary_scenario": {
            "sc_book": "Клиент выбирает услугу и слот → запись сохраняется",
            "sc_form": "Клиент оставляет заявку на звонок → ему перезванивают",
            "sc_ask": "Клиент спрашивает свободное время → получает слоты или эскалацию",
        },
        "success_mvp": {
            "success_leads": "Клиенты сами записываются, меньше звонков",
            "success_time": "Меньше ручной записи в журнал",
            "success_demo": "Можно показать запись от слота до подтверждения",
        },
        "roles": {
            "role_customer": "Клиент, который записывается",
            "role_staff": "Мастер / администратор слотов",
            "role_owner": "Владелец, кто смотрит журнал",
        },
        "as_is_process": {
            "asis_chat": "Записывают в мессенджерах и звонками",
            "asis_sheets": "Журнал в таблице / на бумаге",
            "asis_none": "Записи почти нет — делаем с нуля",
        },
        "records": {
            "data_ops": "Слоты, услуги, статусы записей",
            "data_contacts": "Клиенты: имя, телефон, история визитов",
        },
        "out_of_scope": {
            "oos_payments": "Без оплаты за визит в v1",
            "oos_later": "Только запись на слот, остальное позже",
        },
    },
    "leads": {
        "product_shape": {
            "shape_website": "Сайт / лендинг с заявкой (как вы описали)",
            "shape_miniapp": "Mini App-визитка с формой заявки",
            "shape_bot": "Бот, который собирает заявки в чате",
        },
        "must_features": {
            "feat_intake": "Приём заявок с контактными полями",
            "feat_catalog": "Показ услуг / оффера на витрине",
            "feat_notify": "Уведомление нам о новой заявке",
        },
        "primary_scenario": {
            "sc_form": "Человек оставляет заявку → вам приходит уведомление",
        },
        "success_mvp": {
            "success_leads": "Больше заявок / обращений с витрины",
        },
    },
    "ai": {
        "product_shape": {
            "shape_agent": "ИИ-агент под описанную задачу",
            "shape_ai": "Автоматизация процесса с ИИ",
        },
        "must_features": {
            "feat_intake": "Приём сообщения / события для ИИ",
            "feat_handoff": "Передача человеку, если агент не справился",
            "feat_notify": "Уведомление о результате или ошибке",
        },
        "primary_scenario": {
            "sc_ask": "Человек пишет → агент отвечает или делает действие",
            "sc_sync": "Событие в системе → ИИ обрабатывает и пишет результат",
        },
        "trigger_io": {
            "ai_tg": "Сообщение в Telegram → ответ или действие",
            "ai_event": "Событие из формы / таблицы / webhook",
        },
    },
    "admin_data": {
        "product_shape": {
            "shape_db": "База и инструмент ведения (как вы описали)",
        },
        "must_features": {
            "feat_admin": "Список, поиск, добавление и правка записей",
            "feat_catalog": "Справочники, которые ведём в учёте",
        },
        "admin_operations": {
            "admin_crud": "Список, поиск, добавить, править — минимум v1",
        },
    },
    "integration": {
        "product_shape": {
            "shape_integration": "Связка / обмен между системами (как вы описали)",
            "shape_api": "REST API для этой связки",
        },
        "primary_scenario": {
            "sc_sync": "Событие в системе A → данные появляются в системе B",
        },
    },
    "notifications": {
        "must_features": {
            "feat_notify": "Уведомление нам о событии",
            "feat_remind": "Напоминание клиенту",
        },
    },
}

_RECOMMEND_BY_CAPABILITY: dict[str, dict[str, str]] = {
    "booking": {"primary_scenario": "sc_book", "product_shape": "shape_bot"},
    "leads": {"primary_scenario": "sc_form"},
    "ai": {"primary_scenario": "sc_ask"},
    "admin_data": {"product_shape": "shape_db"},
    "integration": {"primary_scenario": "sc_sync", "product_shape": "shape_integration"},
}

_SHAPE_RECOMMEND: dict[str, str] = {
    "telegram_bot": "shape_bot",
    "telegram_miniapp": "shape_miniapp",
    "website": "shape_website",
    "rest_service": "shape_api",
    "database_tool": "shape_db",
    "integration": "shape_integration",
    "ai_agent": "shape_agent",
    "process_automation": "shape_ai",
    "ai_automation": "shape_agent",
}


def _fill(template: str, brief: str) -> str:
    return template.replace("{brief}", brief).strip()


def extract_task_brief(texts: list[str]) -> str:
    """Short phrase of the customer's idea (first substantial answer wins)."""
    candidates: list[str] = []
    for text in texts:
        compact = " ".join((text or "").split())
        if len(compact) < 18 or is_underspecified(compact):
            continue
        sentence = re.split(r"[.!?\n]", compact, maxsplit=1)[0].strip()
        blob = sentence if len(sentence) >= 18 else compact
        blob = blob.strip(" «»\"'")
        if blob:
            candidates.append(blob)
    if not candidates:
        return ""
    best = candidates[0]
    for item in candidates[1:]:
        if len(item) > len(best) + 40:
            best = item
    if len(best) > 90:
        best = best[:87].rsplit(" ", 1)[0] + "…"
    return best


def extract_mentioned_tools(texts: list[str]) -> list[tuple[str, str]]:
    """Unique (slug, display) tools/channels named as the current process."""
    blob = " ".join(texts).lower()
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    for pattern, slug, display in _TOOL_PATTERNS:
        if slug in seen:
            continue
        match = re.search(pattern, blob, flags=re.I)
        if not match:
            continue
        if slug in _AMBIGUOUS_TOOL_SLUGS:
            window_before = blob[max(0, match.start() - 36) : match.start()]
            if not any(hint in window_before for hint in _PROCESS_HINTS):
                continue
        seen.add(slug)
        found.append((slug, display))
    return found


def extract_requested_surfaces(texts: list[str]) -> list[tuple[str, str]]:
    """Platforms the customer asked to build (Android / iOS / mobile)."""
    blob = " ".join(texts).lower()
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    for pattern, slug, display in _SURFACE_PATTERNS:
        if slug in seen:
            continue
        if re.search(pattern, blob, flags=re.I):
            seen.add(slug)
            found.append((slug, display))
    return found


def _previous_corpus(previous: dict[str, str] | None, brief: str = "") -> list[str]:
    texts = [value for value in (previous or {}).values() if value and value.strip()]
    if brief:
        texts.append(brief)
    return texts


def build_hidden_option_ids(
    *,
    capabilities: frozenset[str],
    product_type: str | None,
    task_shape: str | None,
    previous: dict[str, str] | None = None,
) -> dict[str, tuple[str, ...]]:
    """Drop catalog chips that contradict the captured task (keep index-stable prefix)."""
    _ = previous
    hidden: dict[str, list[str]] = {}
    shape_hidden: list[str] = []
    # Keep website / bot / miniapp in original order so numbered chip tests stay stable.
    if "ai" not in capabilities and (task_shape or "") not in {
        "ai_agent",
        "process_automation",
        "ai_automation",
    }:
        shape_hidden.extend(["shape_agent", "shape_ai"])
    if "admin_data" not in capabilities and task_shape != "database_tool":
        shape_hidden.append("shape_db")
    if "integration" not in capabilities and task_shape != "integration":
        shape_hidden.append("shape_integration")
    if "api_consumers" not in capabilities and product_type != "rest_service":
        shape_hidden.append("shape_api")
    if shape_hidden:
        hidden["product_shape"] = shape_hidden

    scenario_hidden: list[str] = []
    if "booking" not in capabilities:
        scenario_hidden.append("sc_book")
    if "integration" not in capabilities and "ai" not in capabilities:
        scenario_hidden.append("sc_sync")
    if scenario_hidden:
        hidden["primary_scenario"] = scenario_hidden
    return {key: tuple(dict.fromkeys(ids)) for key, ids in hidden.items() if ids}


def _shape_extras_from_request(
    *,
    brief: str,
    previous: dict[str, str] | None,
) -> tuple[Choice, ...]:
    surfaces = extract_requested_surfaces(_previous_corpus(previous, brief))
    if not surfaces:
        return ()
    slugs = {slug for slug, _ in surfaces}
    extras: list[Choice] = []
    if "android" in slugs:
        extras.append(
            Choice(
                "ctx:shape_android",
                "Приложение для Android (как вы описали)",
                recommended=True,
            )
        )
    if "ios" in slugs:
        extras.append(
            Choice(
                "ctx:shape_ios",
                "Приложение для iOS (как вы описали)",
                recommended="android" not in slugs,
            )
        )
    if "android" in slugs and "ios" not in slugs:
        extras.append(Choice("ctx:shape_ios", "Приложение для iOS"))
    elif "ios" in slugs and "android" not in slugs:
        extras.append(Choice("ctx:shape_android", "Приложение для Android"))
    if "mobile" in slugs and "android" not in slugs and "ios" not in slugs:
        extras = [
            Choice(
                "ctx:shape_android",
                "Приложение для Android",
                recommended=True,
            ),
            Choice("ctx:shape_ios", "Приложение для iOS"),
            Choice("ctx:shape_mobile", "Мобильное приложение на Android и iOS"),
        ]
    elif "android" in slugs and "ios" in slugs:
        extras.append(
            Choice("ctx:shape_mobile", "Оба: Android и iOS"),
        )
    seen: set[str] = set()
    unique: list[Choice] = []
    for choice in extras:
        if choice.id in seen:
            continue
        seen.add(choice.id)
        unique.append(choice)
    return tuple(unique[:MAX_EXTRA_OPTIONS])


def build_extra_options(
    *,
    brief: str,
    previous: dict[str, str] | None,
    capabilities: frozenset[str],
) -> dict[str, tuple[Choice, ...]]:
    """Task-specific chips grounded in what the customer already said."""
    _ = capabilities
    extras: dict[str, list[Choice]] = {}
    shape_extras = _shape_extras_from_request(brief=brief, previous=previous)
    if shape_extras:
        extras["product_shape"] = list(shape_extras)

    tools = extract_mentioned_tools(_previous_corpus(previous, brief))
    if not tools:
        return {
            key: tuple(value)
            for key, value in extras.items()
            if key not in FROZEN_CHOICE_TOPIC_IDS and value
        }
    asis: list[Choice] = []
    for slug, display in tools[:2]:
        if slug in _CHAT_TOOL_SLUGS:
            asis.append(
                Choice(
                    f"ctx:asis_{slug}",
                    f"Сейчас через {display} — это и автоматизируем",
                )
            )
        elif slug in _LEDGER_TOOL_SLUGS:
            asis.append(
                Choice(
                    f"ctx:asis_{slug}",
                    f"Сейчас ведём в {display} — переносим в продукт",
                )
            )
    if asis:
        extras["as_is_process"] = asis[:MAX_EXTRA_OPTIONS]

    integ: list[Choice] = []
    for slug, display in tools[:2]:
        if slug in {"phone", "notebook"}:
            continue
        integ.append(
            Choice(
                f"ctx:int_{slug}",
                f"Связать с {display}, как уже обсудили",
            )
        )
    if integ:
        extras["integrations"] = integ[:MAX_EXTRA_OPTIONS]

    ledger = next((d for s, d in tools if s in _LEDGER_TOOL_SLUGS), None)
    if ledger:
        extras["records"] = [
            Choice("ctx:data_current", f"Те же данные, что сейчас в {ledger}"),
        ]

    chat = next((d for s, d in tools if s in _CHAT_TOOL_SLUGS), None)
    if chat or ledger:
        source = " и ".join(x for x in (chat, ledger) if x)
        extras["must_features"] = [
            Choice(
                "ctx:feat_replace",
                f"Заменить текущий процесс ({source}) в первой версии",
            )
        ]
    return {
        key: tuple(value)
        for key, value in extras.items()
        if key not in FROZEN_CHOICE_TOPIC_IDS and value
    }


def merge_extra_options(
    previous: dict[str, tuple[Choice, ...]],
    incoming: dict[str, tuple[Choice, ...]],
) -> dict[str, tuple[Choice, ...]]:
    merged: dict[str, dict[str, Choice]] = {
        key: {choice.id: choice for choice in value} for key, value in previous.items()
    }
    for key, value in incoming.items():
        slot = merged.setdefault(key, {})
        for choice in value:
            slot[choice.id] = choice
    return {
        key: _prefer_shape_extras(tuple(slot.values()))
        for key, slot in merged.items()
        if slot
    }


def _prefer_shape_extras(choices: tuple[Choice, ...]) -> tuple[Choice, ...]:
    shape = [c for c in choices if c.id.startswith("ctx:shape_")]
    rest = [c for c in choices if not c.id.startswith("ctx:shape_")]
    return tuple((shape + rest)[:MAX_EXTRA_OPTIONS])


def _ground_labels_with_previous(
    merged: dict[str, dict[str, str]],
    *,
    brief: str,
    previous: dict[str, str] | None,
) -> None:
    tools = extract_mentioned_tools(_previous_corpus(previous, brief))
    if not tools:
        return
    chat = [d for s, d in tools if s in _CHAT_TOOL_SLUGS]
    ledger = [d for s, d in tools if s in _LEDGER_TOOL_SLUGS]
    asis = merged.setdefault("as_is_process", {})
    if chat:
        asis["asis_chat"] = f"Сейчас в {', '.join(chat)} / мессенджерах"
    if ledger:
        asis["asis_sheets"] = f"Сейчас в {', '.join(ledger)}"
    integ = merged.setdefault("integrations", {})
    named = [d for s, d in tools if s not in {"phone", "notebook"}]
    if named:
        integ["int_this_chat"] = integ.get("int_this_chat") or (
            f"Оставить в этом Telegram, без {named[0]}"
        )
    records = merged.setdefault("records", {})
    if ledger:
        records["data_ops"] = f"Те поля, что уже в {ledger[0]}"
        feats = merged.setdefault("must_features", {})
        feats["feat_admin"] = f"Журнал вместо {ledger[0]}"
    feats = merged.setdefault("must_features", {})
    if chat and chat[0].lower() not in feats.get("feat_notify", "").lower():
        feats["feat_notify"] = f"Уведомление нам (сейчас это {chat[0]})"


def _capability_order(caps: frozenset[str]) -> tuple[str, ...]:
    preferred = (
        "booking",
        "ai",
        "admin_data",
        "integration",
        "leads",
        "notifications",
        "catalog",
        "public_presence",
    )
    return tuple(name for name in preferred if name in caps)


def build_question_overrides(
    *,
    brief: str,
    capabilities: frozenset[str],
    task_shape: str | None,
    previous: dict[str, str] | None = None,
) -> dict[str, str]:
    overrides: dict[str, str] = {}
    if brief:
        for topic_id, template in _QUESTION_BY_TOPIC.items():
            overrides[topic_id] = _fill(template, brief)
        for cap in reversed(_capability_order(capabilities)):
            for topic_id, template in _QUESTION_BY_CAPABILITY.get(cap, {}).items():
                overrides[topic_id] = _fill(template, brief)
    if task_shape == "telegram_miniapp":
        overrides["interaction_model"] = (
            "Mini App — основной экран. Нужен ли в v1 ещё диалог в чате бота, "
            "или достаточно кнопок и формы внутри Mini App?"
        )
        if brief:
            overrides["visitor_cta"] = (
                f"Для Mini App «{brief}»: как посетитель свяжется — форма (какие поля), "
                "публичный @ник / телефон / почта, куда приходит заявка?"
            )
            overrides["integrations"] = (
                f"Куда уходит заявка из Mini App «{brief}»: этот Telegram, канал, "
                "почта, таблица — или никуда кроме уведомления?"
            )
            overrides["pages_sections"] = (
                f"Для Mini App «{brief}»: какие экраны в v1 и какая главная кнопка?"
            )
        else:
            overrides["visitor_cta"] = (
                "Как посетитель свяжется: форма в Mini App (какие поля), публичный "
                "@ник / телефон / почта на экране контактов, и куда приходит заявка "
                "(@канал, этот Telegram, почта)?"
            )
            overrides["integrations"] = (
                "Куда уходит заявка из Mini App: этот Telegram, отдельный канал "
                "(@имя или ссылка), почта, таблица — или никуда кроме уведомления?"
            )
    surfaces = extract_requested_surfaces([brief])
    slugs = {slug for slug, _ in surfaces}
    if slugs & {"android", "ios", "mobile"}:
        overrides["product_shape"] = (
            f"Вы описали: «{brief or 'мобильное приложение'}». "
            "Это нативное приложение для Android, для iOS, оба, "
            "или в первой версии сайт / бот / Mini App?"
        )
    if previous:
        for key, value in previous.items():
            if key in LOCKED_OVERRIDE_TOPIC_IDS and value.strip():
                overrides[key] = value
    return {key: value[:600] for key, value in overrides.items() if value.strip()}


def build_title_overrides(
    *,
    capabilities: frozenset[str],
) -> dict[str, str]:
    titles: dict[str, str] = {}
    for cap in _capability_order(capabilities):
        titles.update(_TITLE_BY_CAPABILITY.get(cap, {}))
    return titles


def build_option_overrides(
    *,
    brief: str,
    capabilities: frozenset[str],
    product_type: str | None,
    task_shape: str | None,
    previous: dict[str, str] | None = None,
) -> dict[str, dict[str, str]]:
    merged: dict[str, dict[str, str]] = {}
    for cap in _capability_order(capabilities):
        for topic_id, labels in _OPTION_BY_CAPABILITY.get(cap, {}).items():
            if topic_id in FROZEN_CHOICE_TOPIC_IDS:
                continue
            slot = merged.setdefault(topic_id, {})
            for choice_id, label in labels.items():
                slot[choice_id] = _fill(label, brief)[:180]
    if not merged.get("product_shape") and brief:
        merged["product_shape"] = {
            "shape_website": f"Сайт / лендинг под «{brief}»",
            "shape_bot": f"Telegram-бот под «{brief}»",
            "shape_miniapp": f"Mini App под «{brief}»",
            "shape_agent": f"ИИ-агент под «{brief}»",
            "shape_ai": f"Автоматизация «{brief}» с ИИ",
            "shape_db": f"Учёт / база под «{brief}»",
            "shape_integration": f"Связка систем для «{brief}»",
            "shape_api": f"API / сервис для «{brief}»",
        }
    _ground_labels_with_previous(merged, brief=brief, previous=previous)
    _ = product_type
    _ = task_shape
    return merged


def build_recommended_option_ids(
    *,
    capabilities: frozenset[str],
    product_type: str | None,
    task_shape: str | None,
    previous: dict[str, str] | None = None,
    brief: str = "",
) -> dict[str, str]:
    recommended: dict[str, str] = {}
    for cap in _capability_order(capabilities):
        recommended.update(_RECOMMEND_BY_CAPABILITY.get(cap, {}))
    shape_key = task_shape or product_type
    shape_choice = _SHAPE_RECOMMEND.get(shape_key or "")
    if shape_choice:
        recommended["product_shape"] = shape_choice
    tools = extract_mentioned_tools(_previous_corpus(previous))
    chat = [slug for slug, _ in tools if slug in _CHAT_TOOL_SLUGS]
    ledger = [slug for slug, _ in tools if slug in _LEDGER_TOOL_SLUGS]
    if chat and "as_is_process" not in recommended:
        recommended["as_is_process"] = "asis_chat"
    elif ledger and "as_is_process" not in recommended:
        recommended["as_is_process"] = "asis_sheets"
    surfaces = extract_requested_surfaces(_previous_corpus(previous, brief))
    slugs = {slug for slug, _ in surfaces}
    if "android" in slugs:
        recommended["product_shape"] = "ctx:shape_android"
    elif "ios" in slugs:
        recommended["product_shape"] = "ctx:shape_ios"
    elif "mobile" in slugs:
        recommended["product_shape"] = "ctx:shape_android"
    return recommended


def heuristic_extra_topics(
    *,
    capabilities: frozenset[str],
    brief: str,
    existing_ids: set[str],
) -> list[TzTopic]:
    extras: list[TzTopic] = []
    if "booking" in capabilities and "custom:who_books" not in existing_ids:
        question = (
            f"В «{brief}» кто выбирает слот: клиент сам или администратор "
            "после звонка/сообщения?"
            if brief
            else "Кто выбирает слот: клиент сам в продукте или администратор после заявки?"
        )
        extras.append(
            TzTopic(
                id="custom:who_books",
                stage=DiscoveryStage.FUNCTIONAL,
                title_ru="Кто записывает",
                title_en="Who books the slot",
                questions={_Q.LOW: question, _Q.MEDIUM: question, _Q.HIGH: question},
                options=(
                    Choice("who_client", "Клиент сам выбирает слот"),
                    Choice("who_admin", "Администратор ставит в слот после заявки"),
                    Choice("who_both", "Клиент сам, админ может поправить"),
                ),
                parent_id="booking_rules",
                dynamic=True,
                skippable=True,
            )
        )
    if "integration" in capabilities and "custom:systems_pair" not in existing_ids:
        question = (
            f"Какие две системы связываем в «{brief}»? Напишите названия."
            if brief
            else "Какие системы связываем в v1? Напишите названия."
        )
        extras.append(
            TzTopic(
                id="custom:systems_pair",
                stage=DiscoveryStage.INTEGRATIONS,
                title_ru="Какие системы связываем",
                title_en="Systems to connect",
                questions={_Q.LOW: question, _Q.MEDIUM: question, _Q.HIGH: question},
                options=(
                    Choice(
                        "sys_write",
                        "Сейчас напишу названия систем",
                        sufficient=False,
                    ),
                    Choice("sys_sheets_crm", "Таблица ↔ CRM / почта"),
                    Choice("sys_later", "Точный список уточним с разработчиком"),
                ),
                parent_id="integrations",
                dynamic=True,
                needs_substance=True,
                skippable=True,
            )
        )
    return extras


def apply_choice_overrides(topic: TzTopic, plan: OutlinePlan | None) -> tuple[Choice, ...]:
    if plan is None:
        return topic.options
    labels = plan.option_overrides.get(topic.id) or {}
    hidden = set(plan.hidden_option_ids.get(topic.id) or ())
    recommend_id = (plan.recommended_option_ids or {}).get(topic.id)
    catalog: list[Choice] = []
    for choice in topic.options:
        if choice.id in hidden:
            continue
        label = str(labels.get(choice.id) or choice.label)
        recommended = choice.recommended
        if recommend_id:
            recommended = choice.id == recommend_id
        if label != choice.label or recommended != choice.recommended:
            choice = replace(choice, label=label[:180], recommended=recommended)
        catalog.append(choice)
    seen = {choice.id for choice in catalog}
    leading: list[Choice] = []
    trailing: list[Choice] = []
    for extra in plan.extra_options.get(topic.id) or ():
        if extra.id in seen or extra.id in hidden:
            continue
        recommended = extra.recommended
        if recommend_id:
            recommended = extra.id == recommend_id
        if recommended != extra.recommended:
            extra = replace(extra, recommended=recommended)
        if extra.id.startswith("ctx:shape_"):
            leading.append(extra)
        else:
            trailing.append(extra)
        seen.add(extra.id)
    return tuple(leading + catalog + trailing)


def topic_title(topic: TzTopic, plan: OutlinePlan | None) -> str:
    if plan and plan.title_overrides.get(topic.id):
        return plan.title_overrides[topic.id]
    return topic.title_ru


def format_outline_announcement(plan: OutlinePlan) -> str:
    brief = plan.task_brief or "описанную задачу"
    added: list[str] = []
    for topic_id in CAPABILITY_TOPIC_IDS:
        topic = topic_by_id(topic_id)
        if topic is None or topic_id in plan.skipped_ids:
            continue
        if topic.capabilities and topic.capabilities & plan.capabilities:
            added.append(topic.title_ru)
    for extra in plan.extra_topics:
        added.append(extra.title_ru)
    skipped: list[str] = []
    for topic_id in plan.skipped_ids:
        topic = topic_by_id(topic_id, plan.extra_topics)
        if topic:
            skipped.append(topic.title_ru)
    lines = [
        f"По задаче «{brief}» собрал перечень разделов ТЗ — дальше вопросы "
        "и варианты ответов уже про неё, а не общая анкета.",
    ]
    if added:
        lines.append("Добавляю: " + "; ".join(list(dict.fromkeys(added))[:8]) + ".")
    if skipped:
        lines.append(
            "Не спрашиваю (не про эту задачу): "
            + "; ".join(list(dict.fromkeys(skipped))[:8])
            + "."
        )
    return "\n".join(lines)
