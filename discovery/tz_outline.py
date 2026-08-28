"""Canonical TZ sections for Discovery.

Sources tailored for ASF simple MVPs (not a full GOST/IEEE document):

- GOST 34.602-2020: purpose, object of automation, system requirements,
  interfaces, acceptance
- ISO/IEC/IEEE 29148 SRS: users, functions, external interfaces, NFR,
  data, constraints, verification
- Practical PRD: explicit non-goals, scenarios, AI HITL/guardrails

Product types stay DEC-003: website | telegram_bot | rest_service | ai_automation.
Customer "shapes" (AI agent, database+admin, integrations) map onto those types.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace

from discovery.fsm import DISCOVERY_STAGES, DiscoveryStage
from discovery.literacy import ITLiteracy

DISCUSS_WITH_DEVELOPER_ID = "discuss_with_developer"
DISCUSS_WITH_DEVELOPER_LABEL = (
    "Обсудить с разработчиком, что нужно зафиксировать"
)

SHAPE_TO_PRODUCT_TYPE: dict[str, str] = {
    "shape_website": "website",
    "shape_bot": "telegram_bot",
    "shape_miniapp": "telegram_bot",
    "shape_api": "rest_service",
    "shape_db": "rest_service",
    "shape_integration": "rest_service",
    "shape_ai": "ai_automation",
    "shape_agent": "ai_automation",
}

SHAPE_TO_TASK_SHAPE: dict[str, str] = {
    "shape_db": "database_tool",
    "shape_integration": "integration",
    "shape_agent": "ai_agent",
    "shape_ai": "process_automation",
    "shape_website": "website",
    "shape_bot": "telegram_bot",
    "shape_miniapp": "telegram_miniapp",
    "shape_api": "rest_service",
}

SURF_TO_TASK_SHAPE: dict[str, str] = {
    "surf_chat": "telegram_bot",
    "surf_miniapp": "telegram_miniapp",
    "surf_both": "telegram_miniapp",
}


@dataclass(frozen=True)
class Choice:
    id: str
    label: str
    exclusive: bool = False
    recommended: bool = False
    sufficient: bool = True
    """If False, the chip alone does not close a needs_substance topic."""


@dataclass(frozen=True)
class TzTopic:
    id: str
    stage: DiscoveryStage
    title_ru: str
    title_en: str
    questions: dict[ITLiteracy, str]
    options: tuple[Choice, ...] = ()
    applies_to: frozenset[str] | None = None
    """If set, topic is included only for these product types."""
    task_shapes: frozenset[str] | None = None
    """If set, topic is included only for these task_shape hints."""
    also_task_shapes: frozenset[str] | None = None
    """Included when task_shape matches even if product type is outside applies_to."""
    questions_by_product: dict[str, dict[ITLiteracy, str]] = field(default_factory=dict)
    keywords: tuple[str, ...] = ()
    multi: bool = False
    """If True, the customer may pick several options in one answer."""
    needs_substance: bool = False
    """Chip-only answers that are not marked sufficient do not close the section."""
    skippable: bool = False
    """Adapter may drop the topic when it is N/A for this task."""
    capabilities: frozenset[str] | None = None
    """If set, topic is included only when the outline plan has one of these capabilities."""
    parent_id: str | None = None
    """Optional parent topic id when this is a subsection."""
    dynamic: bool = False
    """True for runtime subsections proposed for this project (not the static catalog)."""


def with_discuss(options: tuple[Choice, ...]) -> list[Choice]:
    choices = list(options)
    if not any(c.id == DISCUSS_WITH_DEVELOPER_ID for c in choices):
        choices.append(
            Choice(
                DISCUSS_WITH_DEVELOPER_ID,
                DISCUSS_WITH_DEVELOPER_LABEL,
                exclusive=True,
            )
        )
    return choices


def choice_as_dict(choice: Choice) -> dict[str, object]:
    return {
        "id": choice.id,
        "label": choice.label,
        "exclusive": bool(choice.exclusive),
        "recommended": bool(choice.recommended),
    }


_Q = ITLiteracy

TZ_TOPICS: tuple[TzTopic, ...] = (
    TzTopic(
        id="purpose_problem",
        stage=DiscoveryStage.UNDERSTANDING_IDEA,
        title_ru="Цель и проблема",
        title_en="Purpose and problem",
        questions={
            _Q.LOW: (
                "Простыми словами: какую проблему должен решить продукт "
                "для клиентов или команды?"
            ),
            _Q.MEDIUM: (
                "Опишите идею и главную проблему, которую решаем в первой версии."
            ),
            _Q.HIGH: (
                "Цель продукта, ценность для пользователя и жёсткие ограничения, "
                "если они уже известны."
            ),
        },
        options=(
            Choice("problem_customers", "Клиентам неудобно оставлять заявки / получать информацию"),
            Choice("problem_ops", "Команде много ручной работы, хотим ускорить процесс"),
            Choice("problem_data", "Данные разрознены, нужен единый учёт"),
            Choice("problem_notify", "Нужны напоминания, уведомления или ответы 24/7"),
        ),
        keywords=("problem", "цель", "идея", "value", "pain"),
        multi=True,
    ),
    TzTopic(
        id="product_shape",
        stage=DiscoveryStage.UNDERSTANDING_IDEA,
        title_ru="Тип решения",
        title_en="Solution type",
        questions={
            _Q.LOW: "Как это должно выглядеть для людей — сайт, бот, учёт, автоматизация?",
            _Q.MEDIUM: (
                "Какой тип ближе: сайт, Telegram-бот, API/учёт, ИИ-агент "
                "или связка систем?"
            ),
            _Q.HIGH: (
                "Зафиксируйте тип поставки: website | telegram_bot | rest_service | "
                "ai_automation (агент, автоматизация, интеграция, админка данных)."
            ),
        },
        options=(
            Choice("shape_website", "Сайт / лендинг / витрина"),
            Choice("shape_bot", "Telegram-бот"),
            Choice("shape_miniapp", "Telegram Mini App / лендинг в Telegram"),
            Choice("shape_agent", "ИИ-агент (диалог + действия)"),
            Choice("shape_ai", "Автоматизация процесса с ИИ"),
            Choice("shape_db", "База данных и инструмент её ведения"),
            Choice("shape_integration", "Интеграция / обмен между системами"),
            Choice("shape_api", "REST API / сервис для других программ"),
        ),
        keywords=("website", "bot", "api", "сайт", "бот", "агент", "интеграц"),
    ),
    TzTopic(
        id="as_is_process",
        stage=DiscoveryStage.UNDERSTANDING_IDEA,
        title_ru="Как сейчас устроено",
        title_en="Current process (object of automation)",
        questions={
            _Q.LOW: "Как это делают сейчас (телефон, чат, таблица, никак)? Что в этом бесит?",
            _Q.MEDIUM: "Опишите текущий процесс as-is: шаги, инструменты, где теряется время.",
            _Q.HIGH: "Объект автоматизации: as-is поток, системы-источники, ручные шаги в MVP.",
        },
        options=(
            Choice("asis_none", "Сейчас этого почти нет — делаем с нуля", recommended=True),
            Choice("asis_chat", "Всё в мессенджерах / звонках"),
            Choice("asis_sheets", "Ведём в таблицах / файлах"),
            Choice("asis_system", "Уже есть система, хотим рядом или вместо неё"),
        ),
        keywords=("сейчас", "процесс", "as-is", "вручную", "таблица"),
        multi=True,
    ),
    TzTopic(
        id="success_mvp",
        stage=DiscoveryStage.BUSINESS_CONTEXT,
        title_ru="Успех первой версии",
        title_en="MVP success",
        questions={
            _Q.LOW: "Если первая версия удалась — что изменится? Как поймёте, что «ок»?",
            _Q.MEDIUM: "Какой бизнес-результат MVP и как его проверить через 1–2 недели?",
            _Q.HIGH: "Метрика успеха MVP, горизонт проверки и бизнес-ограничения v1.",
        },
        options=(
            Choice("success_leads", "Больше заявок / обращений"),
            Choice("success_time", "Меньше ручного времени у команды"),
            Choice("success_errors", "Меньше ошибок и потерянных данных"),
            Choice("success_demo", "Можно показать рабочий сценарий заказчику/команде"),
        ),
        keywords=("mvp", "успех", "metric", "результат"),
        multi=True,
    ),
    TzTopic(
        id="out_of_scope",
        stage=DiscoveryStage.BUSINESS_CONTEXT,
        title_ru="Вне объёма v1",
        title_en="Out of scope",
        questions={
            _Q.LOW: "Что точно не делаем в первой версии, даже если захочется потом?",
            _Q.MEDIUM: "Явный список вне объёма v1 (оплата, личные кабинеты, сложные роли…).",
            _Q.HIGH: "Non-goals v1: что сознательно откладываем и почему.",
        },
        options=(
            Choice("oos_payments", "Без оплаты / эквайринга в v1", recommended=True),
            Choice("oos_mobile", "Без отдельного мобильного приложения"),
            Choice("oos_saas", "Без сложного личного кабинета и ролей"),
            Choice("oos_later", "Только один главный сценарий, остальное позже"),
        ),
        keywords=("out of scope", "вне объёма", "не в v1", "потом"),
        multi=True,
    ),
    TzTopic(
        id="timeline",
        stage=DiscoveryStage.BUSINESS_CONTEXT,
        title_ru="Сроки реализации",
        title_en="Implementation timeline",
        questions={
            _Q.LOW: (
                "Когда нужна рабочая первая версия? Есть жёсткая дата "
                "(мероприятие, сезон) или ориентир «как получится»?"
            ),
            _Q.MEDIUM: (
                "Ожидаемый и обязательный срок MVP: дата/окно, что будет, "
                "если не успеем, и что можно сузить."
            ),
            _Q.HIGH: (
                "Need-by vs nice-to-have date, external deadline, and what "
                "is droppable if the window is tight."
            ),
        },
        options=(
            Choice("time_asap", "Как можно скорее, в ближайшие 1–2 недели"),
            Choice("time_month", "Ориентир — около месяца"),
            Choice("time_quarter", "1–3 месяца, без жёсткой даты"),
            Choice("time_fixed", "Есть точная дата — напишу её в сообщении"),
            Choice("time_flex", "Срок гибкий, важнее качество первой версии"),
        ),
        keywords=("срок", "deadline", "когда", "дата", "timeline"),
    ),
    TzTopic(
        id="budget",
        stage=DiscoveryStage.BUSINESS_CONTEXT,
        title_ru="Бюджет",
        title_en="Budget",
        questions={
            _Q.LOW: (
                "Есть ли бюджет на первую версию и примерно какой объём? "
                "Можно диапазон или «пока не знаю — нужна оценка»."
            ),
            _Q.MEDIUM: (
                "Бюджет MVP: есть / нет / нужна оценка. Если есть — порядок "
                "суммы и что в неё входит (только разработка или ещё хостинг)."
            ),
            _Q.HIGH: (
                "Budget envelope for v1 (range or TBD), currency, what it must "
                "cover, and whether a quote is required before commit."
            ),
        },
        options=(
            Choice("budget_none", "Бюджета пока нет — изучаем, нужна оценка"),
            Choice("budget_small", "Есть ориентир до ~50 тыс. ₽"),
            Choice("budget_mid", "Ориентир примерно 50–200 тыс. ₽"),
            Choice("budget_large", "Ориентир от 200 тыс. ₽ или готов обсудить сумму"),
            Choice("budget_quote", "Сумму не фиксирую — сначала оценка от разработчика"),
        ),
        keywords=("бюджет", "budget", "цена", "стоимость", "оценка"),
    ),
    TzTopic(
        id="contacts",
        stage=DiscoveryStage.BUSINESS_CONTEXT,
        title_ru="Контакты",
        title_en="Contact details",
        questions={
            _Q.LOW: (
                "Оставьте контакты для связи: имя, телефон и/или email. "
                "Если достаточно этого Telegram — так и напишите."
            ),
            _Q.MEDIUM: (
                "Контакт лица по проекту: имя, роль, телефон, email, Telegram. "
                "Кто принимает решения, если это не вы."
            ),
            _Q.HIGH: (
                "Stakeholder contact: name, role, phone, email, Telegram handle; "
                "decision-maker if different from the respondent."
            ),
        },
        options=(
            Choice("contact_tg", "Достаточно этого чата в Telegram"),
            Choice("contact_write", "Сейчас напишу имя, телефон и/или почту"),
            Choice("contact_other", "Свяжитесь с другим человеком — укажу контакты"),
        ),
        keywords=("контакт", "телефон", "email", "почта", "имя"),
    ),
    TzTopic(
        id="preferred_contact",
        stage=DiscoveryStage.BUSINESS_CONTEXT,
        title_ru="Предпочтительный способ связи",
        title_en="Preferred contact channel",
        questions={
            _Q.LOW: "Как удобнее, чтобы с вами связались по проекту?",
            _Q.MEDIUM: (
                "Предпочтительный канал: Telegram, звонок, email, мессенджер — "
                "и в какое время обычно удобно."
            ),
            _Q.HIGH: (
                "Preferred outreach channel, backup channel, and time window "
                "for owner/developer follow-up."
            ),
        },
        options=(
            Choice("ch_telegram", "Telegram (этот чат или ник)"),
            Choice("ch_phone", "Звонок по телефону"),
            Choice("ch_email", "Электронная почта"),
            Choice("ch_messenger", "WhatsApp / другой мессенджер — укажу какой"),
            Choice("ch_any", "Любой из оставленных контактов"),
        ),
        keywords=("связаться", "звонок", "telegram", "почта", "удобно"),
    ),
    TzTopic(
        id="promotion",
        stage=DiscoveryStage.BUSINESS_CONTEXT,
        title_ru="Продвижение продукта",
        title_en="Promotion and acquisition",
        applies_to=frozenset({"website", "telegram_bot"}),
        also_task_shapes=frozenset({"telegram_miniapp"}),
        questions={
            _Q.LOW: (
                "Нужно ли в первой версии закладывать продвижение: поиск (SEO), "
                "рекламу, счётчик посещений? Это влияет на срок и стоимость."
            ),
            _Q.MEDIUM: (
                "Acquisition v1: SEO (индексация, сниппеты), реклама/контекст, "
                "Метрика/Analytics, каталоги. Что входит в разработку, что сознательно нет."
            ),
            _Q.HIGH: (
                "Promotion in MVP: on-page SEO, webmaster tools, paid ads landing "
                "requirements, analytics pixels — in scope vs later. Impacts estimate."
            ),
        },
        questions_by_product={
            "website": {
                _Q.LOW: (
                    "Для сайта: нужна SEO-оптимизация в первой версии "
                    "(поиск Яндекс/Google), реклама, Метрика — или только сам сайт?"
                ),
            },
            "telegram_bot": {
                _Q.LOW: (
                    "Нужно ли закладывать, как люди найдут бота/лендинг: "
                    "поиск, реклама, каталоги — или продвижение не в объёме v1?"
                ),
            },
        },
        options=(
            Choice("promo_seo", "SEO в v1: поиск, сниппеты, Яндекс/Google Webmaster"),
            Choice("promo_ads", "Реклама / контекст учитываем в разработке v1"),
            Choice("promo_metrika", "Счётчик: Яндекс Метрика и/или Google Analytics"),
            Choice("promo_dirs", "Каталоги, карты, агрегаторы"),
            Choice(
                "promo_none",
                "Продвижение не входит в разработку v1 — только сам продукт",
                recommended=True,
            ),
        ),
        keywords=("seo", "продвижен", "реклам", "метрик", "яндекс", "индексац", "контекст"),
        multi=True,
    ),
    TzTopic(
        id="roles",
        stage=DiscoveryStage.USERS,
        title_ru="Пользователи и роли",
        title_en="Users and roles",
        questions={
            _Q.LOW: "Кто будет пользоваться первым и что он должен суметь сделать?",
            _Q.MEDIUM: "Основные роли и главная задача каждой в MVP.",
            _Q.HIGH: "Персоны/роли, ожидания по доступу и критичный сценарий каждой роли.",
        },
        options=(
            Choice("role_customer", "Внешний клиент / гость"),
            Choice("role_staff", "Сотрудник / оператор"),
            Choice("role_owner", "Владелец бизнеса / администратор"),
            Choice("role_system", "Другая программа / интеграция (не человек)"),
        ),
        keywords=("user", "роль", "audience", "клиент", "сотрудник"),
        multi=True,
    ),
    TzTopic(
        id="access",
        stage=DiscoveryStage.USERS,
        title_ru="Кто имеет доступ",
        title_en="Access and auth",
        questions={
            _Q.LOW: "Кто может зайти и пользоваться? Все желающие или только свои?",
            _Q.MEDIUM: "Модель доступа MVP: публично, список людей, логин, ключ API?",
            _Q.HIGH: "Auth MVP: public / allow-list / login / API key / JWT — и кто выдаёт доступ.",
        },
        options=(
            Choice("access_public", "Открыто для всех, кто нашёл ссылку"),
            Choice("access_list", "Только свои: список людей / сотрудников"),
            Choice("access_login", "Нужен вход (логин или аккаунт Telegram)"),
            Choice("access_key", "Ключ/токен для программ, людям UI не нужен"),
        ),
        keywords=("auth", "доступ", "login", "public", "admin"),
    ),
    TzTopic(
        id="must_features",
        stage=DiscoveryStage.FUNCTIONAL,
        title_ru="Обязательные функции",
        title_en="Must-have functions",
        questions={
            _Q.LOW: (
                "Что обязательно должно работать в первой версии? "
                "Перечислите только самое необходимое."
            ),
            _Q.MEDIUM: "Must-have функции MVP и nice-to-have, которые могут подождать.",
            _Q.HIGH: (
                "Must/should возможности MVP с краткими критериями приёмки "
                "по каждой возможности."
            ),
        },
        options=(
            Choice("feat_intake", "Приём заявок / сообщений / данных"),
            Choice("feat_catalog", "Показ информации (услуги, товары, FAQ, статус)"),
            Choice("feat_admin", "Ведение записей: список, поиск, добавление, правка"),
            Choice("feat_notify", "Уведомление нам о заявке / событии"),
            Choice("feat_remind", "Напоминания клиенту"),
            Choice("feat_handoff", "Передача человеку, если бот/агент не справился"),
        ),
        keywords=("must", "функц", "обязательно", "feature"),
        multi=True,
    ),
    TzTopic(
        id="primary_scenario",
        stage=DiscoveryStage.FUNCTIONAL,
        title_ru="Главный сценарий",
        title_en="Primary scenario",
        questions={
            _Q.LOW: "Опишите один путь «от начала до результата», который обязан работать.",
            _Q.MEDIUM: "Счастливый путь MVP: триггер → шаги → результат для пользователя.",
            _Q.HIGH: "Критичный user journey v1 со входами/выходами и точкой завершения.",
        },
        options=(
            Choice("sc_form", "Человек оставляет заявку → нам приходит уведомление"),
            Choice("sc_book", "Человек выбирает слот / услугу → запись сохраняется"),
            Choice("sc_ask", "Человек задаёт вопрос → получает ответ или эскалацию"),
            Choice("sc_sync", "Событие в системе A → данные появляются в системе B"),
        ),
        keywords=("сценарий", "journey", "путь", "flow"),
    ),
    TzTopic(
        id="delivery_surface",
        stage=DiscoveryStage.FUNCTIONAL,
        title_ru="Как открывают продукт",
        title_en="Delivery surface",
        applies_to=frozenset({"telegram_bot"}),
        questions={
            _Q.LOW: (
                "Это обычный бот в чате или лендинг Mini App внутри Telegram?"
            ),
            _Q.MEDIUM: (
                "Канал v1: чат-бот, Telegram Mini App как лендинг, или бот "
                "открывает Mini App?"
            ),
            _Q.HIGH: (
                "Delivery surface: bot chat vs Telegram Mini App landing vs both."
            ),
        },
        options=(
            Choice("surf_chat", "Обычный бот в чате (кнопки и сообщения)"),
            Choice("surf_miniapp", "Mini App / лендинг внутри Telegram"),
            Choice("surf_both", "Бот открывает Mini App-лендинг"),
        ),
        keywords=("mini app", "миниап", "мини-ап", "лендинг", "чат-бот"),
    ),
    TzTopic(
        id="pages_sections",
        stage=DiscoveryStage.FUNCTIONAL,
        title_ru="Страницы и CTA",
        title_en="Pages and CTA",
        applies_to=frozenset({"website"}),
        also_task_shapes=frozenset({"telegram_miniapp"}),
        questions={
            _Q.LOW: "Какие страницы нужны в первой версии и какая главная кнопка/действие?",
            _Q.MEDIUM: "Разделы сайта v1, основной CTA и куда уходит контактная форма.",
            _Q.HIGH: "IA v1: страницы/блоки, primary CTA, destination формы (email/CRM/none).",
        },
        options=(
            Choice("pages_landing", "Одна страница: о нас + контакты / заявка"),
            Choice("pages_multi", "Несколько: главная, услуги, контакты"),
            Choice("pages_catalog", "Витрина/каталог + заявка, без корзины и оплаты"),
        ),
        keywords=("page", "section", "cta", "страниц", "форма"),
    ),
    TzTopic(
        id="interaction_model",
        stage=DiscoveryStage.FUNCTIONAL,
        title_ru="Как говорят с ботом",
        title_en="Bot interaction model",
        applies_to=frozenset({"telegram_bot"}),
        questions={
            _Q.LOW: "Бот с кнопками и командами или свободный текст, как с человеком?",
            _Q.MEDIUM: "Модель: команды / кнопки / свободный текст / голос — что обязательно в v1?",
            _Q.HIGH: "Interaction model: commands vs conversational, кнопки, voice in MVP?",
        },
        options=(
            Choice("bot_mini_only", "Только Mini App — чат бота не нужен"),
            Choice("bot_buttons", "Кнопки и короткие команды"),
            Choice("bot_text", "Свободный текст, бот понимает своими словами"),
            Choice("bot_mix", "Mini App или кнопки для главного + текст, если пишут в чат"),
        ),
        keywords=("command", "кнопк", "free-text", "голос", "voice"),
    ),
    TzTopic(
        id="public_identity",
        stage=DiscoveryStage.FUNCTIONAL,
        title_ru="Имя и подпись для посетителя",
        title_en="Public identity",
        applies_to=frozenset({"website", "telegram_bot"}),
        needs_substance=True,
        questions={
            _Q.LOW: (
                "Как подписать визитку или лендинг для посетителя: имя или бренд, "
                "роль и одна фраза, чем вы занимаетесь?"
            ),
            _Q.MEDIUM: (
                "Публичная подпись v1: имя/название, роль, слоган. Не путать "
                "с контактами для связи по этому проекту."
            ),
            _Q.HIGH: (
                "Public identity: display name, role/title, one-line offer. "
                "Needed to render the landing; stakeholder chat is not enough."
            ),
        },
        options=(
            Choice(
                "id_write",
                "Сейчас напишу имя/бренд, роль и слоган",
                sufficient=False,
            ),
            Choice(
                "id_person",
                "Личная визитка — укажу имя в сообщении",
                sufficient=False,
            ),
            Choice(
                "id_brand",
                "Бренд/студия — укажу название в сообщении",
                sufficient=False,
            ),
            Choice(
                "id_stub",
                "Пока «Имя · IT-услуги», тексты заменим позже",
            ),
        ),
        keywords=("имя", "бренд", "слоган", "визитк", "подпись"),
    ),
    TzTopic(
        id="offer_catalog",
        stage=DiscoveryStage.FUNCTIONAL,
        title_ru="Услуги и портфолио",
        title_en="Offer catalog",
        applies_to=frozenset({"website", "telegram_bot"}),
        needs_substance=True,
        multi=True,
        questions={
            _Q.LOW: (
                "Какие услуги показать в первой версии? Напишите названия и "
                "по 1–2 предложения. Если нужно портфолио — кейсы или ссылки."
            ),
            _Q.MEDIUM: (
                "Каталог v1: список услуг с кратким описанием; портфолио, "
                "если оно в must-have; цены только если уже фиксированы."
            ),
            _Q.HIGH: (
                "Offer catalog: service names + blurbs; portfolio items/URLs "
                "if claimed; prices only when already decided."
            ),
        },
        options=(
            Choice("cat_sites", "Сайты и лендинги", sufficient=False),
            Choice("cat_bots", "Telegram-боты", sufficient=False),
            Choice("cat_ai", "AI-автоматизация и интеграции", sufficient=False),
            Choice(
                "cat_write",
                "Сейчас текстом распишу услуги и цены если есть",
                sufficient=False,
            ),
            Choice(
                "cat_portfolio",
                "Нужно портфолио — опишу кейсы или дам ссылки",
                sufficient=False,
            ),
            Choice(
                "cat_stub",
                "Пока 3 карточки-заглушки, тексты пришлю отдельно",
            ),
        ),
        keywords=("услуг", "каталог", "портфол", "офер", "кейс"),
    ),
    TzTopic(
        id="visitor_cta",
        stage=DiscoveryStage.FUNCTIONAL,
        title_ru="Как посетитель связывается",
        title_en="Visitor CTA and leads",
        applies_to=frozenset({"website", "telegram_bot"}),
        needs_substance=True,
        multi=True,
        questions={
            _Q.LOW: (
                "Как посетитель свяжется с вами? Нужен публичный контакт "
                "(@ник, телефон, почта) — не этот чат сбора ТЗ. "
                "Какие поля в заявке и куда она приходит?"
            ),
            _Q.MEDIUM: (
                "Публичный CTA: t.me/@ник, телефон, email; поля формы; "
                "куда уходит уведомление о заявке."
            ),
            _Q.HIGH: (
                "Visitor CTA: public handle/phone/email, lead fields, "
                "notification destination. Stakeholder chat is not the CTA."
            ),
        },
        options=(
            Choice(
                "cta_tg",
                "Кнопка «Написать в Telegram» — укажу @ник",
                sufficient=False,
            ),
            Choice(
                "cta_phone",
                "Телефон / WhatsApp — укажу номер",
                sufficient=False,
            ),
            Choice("cta_form", "Форма заявки: имя, контакт, сообщение"),
            Choice("cta_notify", "Заявки приходят мне в этот Telegram"),
            Choice(
                "cta_channel",
                "Заявки в Telegram-канал — укажу @канал или ссылку",
                sufficient=False,
            ),
            Choice(
                "cta_write",
                "Сейчас напишу @ник / телефон / почту",
                sufficient=False,
            ),
        ),
        keywords=("cta", "@", "заявк", "телефон", "ник", "связаться"),
    ),
    TzTopic(
        id="resources_ops",
        stage=DiscoveryStage.FUNCTIONAL,
        title_ru="Сущности и операции",
        title_en="Resources and operations",
        applies_to=frozenset({"rest_service"}),
        questions={
            _Q.LOW: "Что учитываем (заявки, клиенты, товары…) и что с этим делают: смотреть, добавить, изменить?",
            _Q.MEDIUM: "Ресурсы API/учёта v1 и операции (CRUD, поиск, экспорт) по каждому.",
            _Q.HIGH: "Ресурсы, операции, идемпотентность и кто consumer API в MVP.",
        },
        options=(
            Choice("res_one", "Одна главная сущность: список + карточка + создание/правка"),
            Choice("res_two", "Две связанные сущности (например клиент и заявка)"),
            Choice("res_read", "Пока только читать и отдавать данные, без сложной правки"),
        ),
        keywords=("resource", "crud", "сущност", "endpoint", "таблица"),
    ),
    TzTopic(
        id="trigger_io",
        stage=DiscoveryStage.FUNCTIONAL,
        title_ru="Триггер и результат ИИ",
        title_en="AI trigger and I/O",
        applies_to=frozenset({"ai_automation"}),
        questions={
            _Q.LOW: "Что запускает работу (сообщение, расписание, новая строка) и что должно получиться на выходе?",
            _Q.MEDIUM: "Триггер, входы, выход/побочный эффект и нужно ли одобрение человека.",
            _Q.HIGH: "Trigger, inputs/outputs, side effect, HITL, failure path for MVP.",
        },
        options=(
            Choice("ai_tg", "Сообщение в Telegram → ответ или действие"),
            Choice("ai_schedule", "По расписанию (раз в день/час) берёт данные и обрабатывает"),
            Choice("ai_event", "Событие из другой системы (форма, таблица, webhook)"),
        ),
        keywords=("trigger", "вход", "выход", "агент", "webhook"),
        multi=True,
    ),
    TzTopic(
        id="admin_operations",
        stage=DiscoveryStage.FUNCTIONAL,
        title_ru="Ведение базы",
        title_en="Data admin operations",
        task_shapes=frozenset({"database_tool"}),
        questions={
            _Q.LOW: "Что обязательно уметь в инструменте учёта: список, поиск, добавить, исправить, выгрузить?",
            _Q.MEDIUM: "Операции админки v1 и кто ими пользуется.",
            _Q.HIGH: "Admin surface v1: list/filter/create/update/export; что сознательно не делаем.",
        },
        options=(
            Choice("admin_crud", "Полный минимум: список, поиск, добавить, править"),
            Choice("admin_list", "Сначала только смотреть и искать, правки позже"),
            Choice("admin_import", "Нужен импорт из таблицы / файла в v1"),
        ),
        keywords=("админ", "учёт", "список", "import", "export"),
        multi=True,
    ),
    TzTopic(
        id="records",
        stage=DiscoveryStage.DATA,
        title_ru="Какие данные храним",
        title_en="Data and records",
        questions={
            _Q.LOW: "Какие сведения нужно запоминать (имя, телефон, статус, файлы) и на сколько примерно записей?",
            _Q.MEDIUM: "Состав данных MVP: сущности, ключевые поля, вложения, оценка объёма.",
            _Q.HIGH: "Логическая модель v1: сущности, поля, уникальность, файлы, объём.",
        },
        questions_by_product={
            "website": {
                _Q.LOW: "Какие данные собираем с сайта (заявка, подписка) и нужно ли что-то ещё хранить?",
            },
            "telegram_bot": {
                _Q.LOW: "Что бот запоминает о человеке и заявке? Нужна ли история переписки?",
            },
            "rest_service": {
                _Q.LOW: "Какие таблицы/записи главные и какие поля обязательны?",
            },
            "ai_automation": {
                _Q.LOW: "Какие данные подаём в ИИ и что сохраняем после прогона (лог, результат)?",
            },
        },
        options=(
            Choice("data_contacts", "Контакты и заявки"),
            Choice("data_catalog", "Справочник (услуги, товары, FAQ)"),
            Choice("data_ops", "Операционные записи (статусы, слоты, задачи)"),
            Choice("data_none", "Почти ничего не храним — только пересылаем"),
        ),
        keywords=("данн", "record", "поле", "хран", "entity"),
        multi=True,
    ),
    TzTopic(
        id="locale_ux",
        stage=DiscoveryStage.NON_FUNCTIONAL,
        title_ru="Язык, устройства, вид",
        title_en="Locale, devices, UX",
        questions={
            _Q.LOW: "На каком языке интерфейс? Нужен телефон, особый вид или можно просто и понятно?",
            _Q.MEDIUM: "Языки, мобильность, бренд-материалы (логотип, фото) — что есть к старту.",
            _Q.HIGH: "Локали, viewport, бренд-ассеты, a11y-минимум для MVP.",
        },
        questions_by_product={
            "telegram_bot": {
                _Q.LOW: "Язык бота и нужен ли голосовой ввод в первой версии?",
            },
            "website": {
                _Q.LOW: "Язык сайта, мобильная версия и есть ли логотип/фото или делаем просто?",
            },
        },
        options=(
            Choice("ux_ru", "Только русский, удобно с телефона", recommended=True),
            Choice("ux_bilingual", "Русский и английский"),
            Choice("ux_brand", "Есть логотип и материалы — нужно похоже на бренд"),
            Choice("ux_simple", "Без бренда: простой аккуратный вид"),
        ),
        keywords=("language", "язык", "mobile", "бренд", "logo", "voice"),
        multi=True,
    ),
    TzTopic(
        id="brand_assets",
        stage=DiscoveryStage.NON_FUNCTIONAL,
        title_ru="Логотип и оформление",
        title_en="Brand assets",
        applies_to=frozenset({"website", "telegram_bot"}),
        needs_substance=True,
        questions={
            _Q.LOW: (
                "Есть логотип, цвета, фото — или делаем простой аккуратный вид?"
            ),
            _Q.MEDIUM: (
                "Бренд-ассеты v1: логотип, палитра, фото. Если файлов ещё нет "
                "— фиксируем простой вид или «пришлю отдельно»."
            ),
            _Q.HIGH: (
                "Brand assets: logo/palette/photos available now, later, or "
                "simple unbranded MVP."
            ),
        },
        options=(
            Choice(
                "brand_simple",
                "Простой аккуратный вид, без брендбука",
                recommended=True,
            ),
            Choice(
                "brand_files",
                "Есть логотип/фото — прикрепил или пришлю файлом",
            ),
            Choice(
                "brand_colors",
                "Сейчас напишу цвета (hex или «синий / кремовый»)",
                sufficient=False,
            ),
            Choice(
                "brand_later",
                "Материалы будут позже, в v1 простой вид",
            ),
        ),
        keywords=("логотип", "бренд", "цвет", "палитр", "фото", "макет"),
    ),
    TzTopic(
        id="design_references",
        stage=DiscoveryStage.NON_FUNCTIONAL,
        title_ru="Референсы",
        title_en="Design references",
        applies_to=frozenset({"website", "telegram_bot"}),
        also_task_shapes=frozenset({"telegram_miniapp"}),
        needs_substance=True,
        questions={
            _Q.LOW: (
                "Видели сайт, бота или приложение, как хотели бы свой продукт? "
                "Пришлите ссылку или название и напишите, что именно нравится "
                "(цвета, простота, анимации, 3D) — это возьмём в работу."
            ),
            _Q.MEDIUM: (
                "Референсы v1: URL/названия и 2–3 конкретных приёма, которые "
                "нужно перенести (типографика, сетка, motion, тон). Не «просто красиво»."
            ),
            _Q.HIGH: (
                "Reference URLs plus transferable attributes (layout, type, motion, "
                "3D, copy tone). Needed to implement the look, not just a vibe word."
            ),
        },
        options=(
            Choice(
                "ref_write",
                "Сейчас дам ссылки и что в них нравится",
                sufficient=False,
            ),
            Choice(
                "ref_attach",
                "Прикреплю скрины и подпишу, что взять",
                sufficient=False,
            ),
            Choice(
                "ref_none",
                "Референсов нет — ориентируемся на выбранный стиль ниже",
            ),
            Choice(
                "ref_later",
                "Ссылки пришлю отдельно, пока без референса",
            ),
        ),
        keywords=("референс", "пример", "похож", "нравится", "как у", "reference"),
        multi=True,
    ),
    TzTopic(
        id="design_direction",
        stage=DiscoveryStage.NON_FUNCTIONAL,
        title_ru="Какой дизайн хотите",
        title_en="Design direction",
        applies_to=frozenset({"website", "telegram_bot"}),
        also_task_shapes=frozenset({"telegram_miniapp"}),
        needs_substance=True,
        questions={
            _Q.LOW: (
                "Какой характер визуала в первой версии: спокойный лаконичный, "
                "современный с анимациями, или кричащий с 3D-графикой? "
                "Это влияет на срок и стоимость."
            ),
            _Q.MEDIUM: (
                "Направление v1: лаконичный / современный motion / 3D-герой / "
                "деловой / с характером в тексте. 3D и «вау» обычно дороже."
            ),
            _Q.HIGH: (
                "Visual direction v1: quiet editorial vs contemporary motion vs "
                "loud 3D/WebGL hero vs corporate vs playful copy. Impacts estimate."
            ),
        },
        questions_by_product={
            "telegram_bot": {
                _Q.LOW: (
                    "Если это чат-бот — спокойные сообщения и кнопки или "
                    "яркий Mini App с анимациями/3D?"
                ),
            },
        },
        options=(
            Choice(
                "vis_calm",
                "Спокойный, лаконичный, много воздуха",
                recommended=True,
            ),
            Choice("vis_modern", "Современный, заметный, с лёгкими анимациями"),
            Choice(
                "vis_mvp_3d",
                "Один лёгкий 3D/motion-герой — без «вау на весь продукт»",
            ),
            Choice(
                "vis_loud_3d",
                "Кричащий: 3D/WebGL-герой, продукт сам продаёт уровень",
            ),
            Choice("vis_corporate", "Деловой, как у серьёзной компании"),
            Choice("vis_playful", "Живой: характер, хуки и юмор в тексте"),
            Choice(
                "vis_write",
                "Сейчас опишу тон и визуал своими словами",
                sufficient=False,
            ),
        ),
        keywords=(
            "дизайн",
            "лаконич",
            "3d",
            "webgl",
            "анимац",
            "спокойн",
            "кричащ",
            "визуал",
        ),
    ),
    TzTopic(
        id="ops_constraints",
        stage=DiscoveryStage.NON_FUNCTIONAL,
        title_ru="Где крутится и ограничения",
        title_en="Hosting and constraints",
        questions={
            _Q.LOW: "Где это должно жить (наш сервер, простой хостинг) и сколько людей примерно будут пользоваться?",
            _Q.MEDIUM: "Хостинг, нагрузка MVP, чувствительные данные, предпочтения по стеку если есть.",
            _Q.HIGH: "Deploy target, объём, PII/compliance, latency/availability ожидания для простого MVP.",
        },
        options=(
            Choice("ops_simple", "Обычный простой хостинг, небольшая нагрузка"),
            Choice(
                "ops_existing",
                "Рядом с уже существующим сервером / доменом — укажу адрес",
                sufficient=False,
            ),
            Choice("ops_unsure", "Не знаю про серверы — пусть предложит разработчик", recommended=True),
            Choice("ops_sensitive", "Есть персональные данные, нужна аккуратная защита"),
        ),
        keywords=("host", "deploy", "нагруз", "pii", "персональн"),
        multi=True,
    ),
    TzTopic(
        id="legal_compliance",
        stage=DiscoveryStage.NON_FUNCTIONAL,
        title_ru="Законы и персональные данные",
        title_en="Legal and personal data",
        questions={
            _Q.LOW: (
                "Нужно ли соответствие законам РФ в первой версии — например "
                "152-ФЗ об обработке персональных данных (политика, согласие)? "
                "Есть ли отраслевые требования? Это влияет на срок и стоимость."
            ),
            _Q.MEDIUM: (
                "Compliance v1: 152-ФЗ (согласие, политика, хранение ПДн), cookies/"
                "Метрика, рекламная маркировка, отрасль (медицина, финансы, дети, "
                "госсектор). Что обязательно сейчас, что риск/позже."
            ),
            _Q.HIGH: (
                "RU legal MVP: 152-FZ notices/consent, cookie/metrika consent, "
                "ad labelling, industry overlays. In-scope vs deferred; estimate impact."
            ),
        },
        questions_by_product={
            "website": {
                _Q.LOW: (
                    "На сайте будут заявки или метрика? Нужны политика и согласие "
                    "по 152-ФЗ, cookies — или юридические тексты не в v1?"
                ),
            },
            "telegram_bot": {
                _Q.LOW: (
                    "Бот будет хранить имя, телефон или другие персональные данные? "
                    "Нужны согласие и политика 152-ФЗ в первой версии?"
                ),
            },
            "rest_service": {
                _Q.LOW: (
                    "API обрабатывает персональные данные граждан РФ? Какие "
                    "юридические требования обязательны в v1?"
                ),
            },
            "ai_automation": {
                _Q.LOW: (
                    "В ИИ попадают персональные данные? Нужна фиксация 152-ФЗ "
                    "и ограничений на обработку в первой версии?"
                ),
            },
        },
        options=(
            Choice(
                "legal_152",
                "Да: политика и согласие по 152-ФЗ, если есть контакты/заявки",
                recommended=True,
            ),
            Choice("legal_cookies", "Согласие на cookies / Метрику (для сайта)"),
            Choice("legal_ads", "Требования к рекламе (маркировка и т.п.)"),
            Choice(
                "legal_industry",
                "Отрасль (медицина, финансы, дети, госсектор) — уточним с разработчиком",
            ),
            Choice("legal_min", "ПДн почти не собираем, юр. тексты не в объёме v1"),
            Choice(
                "legal_later",
                "Юр. документы позже — в ТЗ зафиксировать как риск по сроку/оценке",
            ),
        ),
        keywords=(
            "152",
            "пдн",
            "персональн",
            "политик",
            "соглас",
            "закон",
            "compliance",
            "cookie",
        ),
        multi=True,
    ),
    TzTopic(
        id="integrations",
        stage=DiscoveryStage.INTEGRATIONS,
        title_ru="Связи с другими системами",
        title_en="Integrations",
        questions={
            _Q.LOW: "Нужно ли подключать почту, таблицы, CRM, платежи или другие программы?",
            _Q.MEDIUM: "Обязательные интеграции MVP vs то, что может подождать.",
            _Q.HIGH: "Интеграции v1: система, направление, формат; что требует решения владельца.",
        },
        questions_by_product={
            "website": {
                _Q.LOW: "Куда уходит заявка с сайта: почта, таблица, CRM, или пока никуда кроме уведомления?",
            },
            "ai_automation": {
                _Q.LOW: "Откуда агент берёт данные и куда записывает результат?",
            },
        },
        options=(
            Choice("int_none", "В v1 без внешних систем", recommended=True),
            Choice("int_email", "Только почта / уведомление владельцу"),
            Choice("int_this_chat", "Заявки приходят мне в этот Telegram"),
            Choice(
                "int_tg_channel",
                "Заявки в Telegram-канал — укажу @канал или ссылку",
                sufficient=False,
            ),
            Choice(
                "int_sheets",
                "Таблица (Google Sheets / Excel) — укажу какую",
                sufficient=False,
            ),
            Choice(
                "int_crm",
                "CRM или учёт, который уже есть — укажу какой",
                sufficient=False,
            ),
        ),
        keywords=("integration", "email", "crm", "sheet", "почт", "webhook"),
        multi=True,
    ),
    TzTopic(
        id="integration_map",
        stage=DiscoveryStage.INTEGRATIONS,
        title_ru="Карта обмена",
        title_en="Integration mapping",
        task_shapes=frozenset({"integration"}),
        questions={
            _Q.LOW: "Какие две (или больше) системы связываем, что передаём и в какую сторону?",
            _Q.MEDIUM: "Системы A/B, объекты обмена, направление, частота, что при ошибке.",
            _Q.HIGH: "Контракт обмена v1: endpoints/таблицы, mapping полей, идемпотентность, retry.",
        },
        options=(
            Choice("map_oneway", "В одну сторону: из A в B"),
            Choice("map_twoway", "Туда и обратно"),
            Choice("map_event", "По событию (сразу), не пачкой раз в день"),
        ),
        keywords=("mapping", "обмен", "система a", "направление"),
    ),
    TzTopic(
        id="human_approval",
        stage=DiscoveryStage.INTEGRATIONS,
        title_ru="Контроль человека над ИИ",
        title_en="Human approval / guardrails",
        applies_to=frozenset({"ai_automation"}),
        questions={
            _Q.LOW: "ИИ может действовать сам или сначала человек должен подтвердить важное?",
            _Q.MEDIUM: "HITL: какие действия автономны, какие требуют одобрения, что эскалировать.",
            _Q.HIGH: "Guardrails: allowed actions, HITL gates, fallback, запрещённые побочные эффекты.",
        },
        options=(
            Choice("hitl_always", "Важные действия только после подтверждения человеком", recommended=True),
            Choice("hitl_draft", "ИИ готовит черновик, человек отправляет"),
            Choice("hitl_auto", "В v1 можно автоматически, но с логом и возможностью остановить"),
        ),
        keywords=("approval", "hitl", "человек", "эскал", "guard"),
    ),
    TzTopic(
        id="acceptance",
        stage=DiscoveryStage.ACCEPTANCE,
        title_ru="Как поймём, что готово",
        title_en="Acceptance",
        questions={
            _Q.LOW: "Что вы должны суметь сами проверить, чтобы сказать «можно пользоваться»?",
            _Q.MEDIUM: "Критерии приёмки MVP: демо-сценарий, что считается дефектом.",
            _Q.HIGH: "Verification v1: сценарии приёмки, кто принимает, Definition of Done.",
        },
        options=(
            Choice("acc_demo", "Проходим главный сценарий на реальных данных — и ок", recommended=True),
            Choice("acc_checklist", "Чек-лист из must-have функций, все пункты зелёные"),
            Choice("acc_week", "Неделя реальной работы без критичных сбоев"),
        ),
        keywords=("приёмк", "acceptance", "готово", "демо", "done"),
    ),
    TzTopic(
        id="operator",
        stage=DiscoveryStage.ACCEPTANCE,
        title_ru="Кто обслуживает после запуска",
        title_en="Who operates it",
        questions={
            _Q.LOW: "Кто будет отвечать на заявки / править данные / смотреть, что сломалось?",
            _Q.MEDIUM: "Роль оператора после поставки: кто админ, кто контент, кто эскалация.",
            _Q.HIGH: "Operational ownership: admin, content, incident contact for MVP.",
        },
        options=(
            Choice("ops_owner", "Владелец бизнеса сам"),
            Choice("ops_staff", "Сотрудник / менеджер"),
            Choice("ops_dev", "Пока разработчик, покажем как пользоваться"),
        ),
        keywords=("оператор", "админ", "обслужив", "кто будет"),
    ),
    TzTopic(
        id="risks",
        stage=DiscoveryStage.RISKS,
        title_ru="Риски и неизвестные",
        title_en="Risks and unknowns",
        questions={
            _Q.LOW: "Что больше всего беспокоит? Что лучше сразу уточнить у разработчика?",
            _Q.MEDIUM: "Риски и неизвестные, которые должны остановить работу до ответа владельца.",
            _Q.HIGH: "Блокирующие риски (техника, право, данные). Отметьте HumanDecisionRequired.",
        },
        options=(
            Choice("risk_none", "Критических опасений нет, можно собирать черновик ТЗ"),
            Choice("risk_data", "Беспокоит персональные данные / доступы"),
            Choice("risk_deps", "Зависим от другой системы, доступов или материалов, которых ещё нет"),
            Choice("risk_scope", "Боюсь, что расползётся объём"),
        ),
        keywords=("риск", "risk", "неизвест", "legal", "блок"),
        multi=True,
    ),
    TzTopic(
        id="booking_rules",
        stage=DiscoveryStage.FUNCTIONAL,
        title_ru="Запись: слоты и правила",
        title_en="Booking rules",
        parent_id="must_features",
        capabilities=frozenset({"booking"}),
        questions={
            _Q.LOW: (
                "Как должна работать запись: какие дни и часы, сколько длится слот, "
                "нужно ли подтверждение?"
            ),
            _Q.MEDIUM: (
                "Правила записи v1: рабочие часы, длительность слота, часовой пояс, "
                "подтверждение, что нельзя в первой версии."
            ),
            _Q.HIGH: (
                "Booking contract v1: hours, slot length, timezone, confirmation, "
                "overbooking rule, cancellation."
            ),
        },
        options=(
            Choice("book_hours", "Есть часы работы — напишу их в сообщении", sufficient=False),
            Choice("book_confirm", "Нужно подтверждение записи (нам или клиенту)"),
            Choice("book_simple", "Простая запись в очередь, без календаря слотов"),
        ),
        keywords=("запис", "слот", "календар", "booking", "расписан"),
        multi=True,
        needs_substance=True,
    ),
    TzTopic(
        id="notification_rules",
        stage=DiscoveryStage.FUNCTIONAL,
        title_ru="Когда и кому писать",
        title_en="Notification rules",
        parent_id="must_features",
        capabilities=frozenset({"notifications"}),
        questions={
            _Q.LOW: "Кому и когда слать напоминания или уведомления в первой версии?",
            _Q.MEDIUM: (
                "Уведомления v1: события, получатель, канал, можно ли без них обойтись."
            ),
            _Q.HIGH: (
                "Notify v1: trigger events, recipients, channel, quiet hours if any."
            ),
        },
        options=(
            Choice("ntf_staff", "Уведомление нам о новой заявке"),
            Choice("ntf_client", "Напоминание клиенту перед визитом / событием"),
            Choice(
                "ntf_none",
                "В v1 без автоматических напоминаний клиенту",
                recommended=True,
            ),
        ),
        keywords=("уведом", "напоминан", "remind", "notify"),
        multi=True,
    ),
    TzTopic(
        id="api_consumers",
        stage=DiscoveryStage.USERS,
        title_ru="Кто вызывает сервис",
        title_en="API consumers",
        parent_id="roles",
        capabilities=frozenset({"api_consumers"}),
        applies_to=frozenset({"rest_service"}),
        questions={
            _Q.LOW: "Кто будет пользоваться API — ваше приложение, партнёр, только вы?",
            _Q.MEDIUM: "Consumer v1: кто вызывает, откуда, сколько клиентов примерно.",
            _Q.HIGH: "API consumers, auth they already have, expected volume.",
        },
        options=(
            Choice("cons_own", "Только наше приложение / админка"),
            Choice("cons_partner", "Внешний партнёр или другая система"),
            Choice("cons_unsure", "Пока не ясно — пусть предложит разработчик", recommended=True),
        ),
        keywords=("consumer", "кто вызывает", "клиент api", "партнёр"),
    ),
    TzTopic(
        id="voice_input",
        stage=DiscoveryStage.FUNCTIONAL,
        title_ru="Голосовой ввод",
        title_en="Voice input",
        parent_id="interaction_model",
        capabilities=frozenset({"voice"}),
        applies_to=frozenset({"telegram_bot"}),
        questions={
            _Q.LOW: "В первой версии нужен голос (как голосовое в Telegram) или достаточно текста?",
            _Q.MEDIUM: "Voice in MVP: обязательно, желательно, или только текст.",
            _Q.HIGH: "Voice input v1: required vs text-only; language of speech.",
        },
        options=(
            Choice("voice_yes", "Голос обязателен в v1"),
            Choice("voice_nice", "Приятно иметь, но можно текстом"),
            Choice("voice_no", "Только текст в первой версии", recommended=True),
        ),
        keywords=("голос", "voice", "whisper", "аудио"),
    ),
    TzTopic(
        id="failure_path",
        stage=DiscoveryStage.RISKS,
        title_ru="Если автоматизация не сработала",
        title_en="Failure path",
        parent_id="risks",
        capabilities=frozenset({"ai", "integration"}),
        questions={
            _Q.LOW: "Если бот/связка не сработает — что должно произойти для человека?",
            _Q.MEDIUM: "Failure path v1: эскалация человеку, повтор, или запись ошибки.",
            _Q.HIGH: "Failure/retry/escalation for MVP; what is unacceptable silence.",
        },
        options=(
            Choice("fail_human", "Передать человеку / написать нам", recommended=True),
            Choice("fail_retry", "Повторить позже и записать ошибку"),
            Choice("fail_log", "Только лог, без эскалации в v1"),
        ),
        keywords=("ошиб", "эскал", "fail", "retry", "не сработ"),
    ),
)

SKIPPABLE_IDS = frozenset(
    {
        "as_is_process",
        "public_identity",
        "offer_catalog",
        "visitor_cta",
        "brand_assets",
        "design_references",
        "design_direction",
        "pages_sections",
        "delivery_surface",
        "locale_ux",
        "ops_constraints",
        "promotion",
        "operator",
    }
)
CORE_TOPIC_IDS = frozenset(
    {
        "purpose_problem",
        "product_shape",
        "success_mvp",
        "out_of_scope",
        "must_features",
        "primary_scenario",
        "acceptance",
        "timeline",
        "budget",
        "contacts",
        "preferred_contact",
        "legal_compliance",
        "risks",
    }
)
PUBLIC_PRESENCE_TOPIC_IDS = frozenset(
    {
        "public_identity",
        "offer_catalog",
        "visitor_cta",
        "brand_assets",
        "design_references",
        "design_direction",
        "pages_sections",
        "promotion",
    }
)
CUSTOM_TOPIC_ID_RE = re.compile(r"^custom:[a-z0-9_]{2,40}$")
MAX_CUSTOM_TOPICS = 8

TZ_TOPICS = tuple(
    replace(topic, skippable=True) if topic.id in SKIPPABLE_IDS else topic
    for topic in TZ_TOPICS
)

_TOPIC_BY_ID = {t.id: t for t in TZ_TOPICS}


@dataclass
class OutlinePlan:
    """Per-project TZ outline: catalog spine + skipped modules + extra subsections."""

    capabilities: frozenset[str] = field(default_factory=frozenset)
    skipped_ids: tuple[str, ...] = ()
    extra_topics: tuple[TzTopic, ...] = ()
    adapted: bool = False
    reasons: dict[str, str] = field(default_factory=dict)
    question_overrides: dict[str, str] = field(default_factory=dict)
    option_overrides: dict[str, dict[str, str]] = field(default_factory=dict)
    title_overrides: dict[str, str] = field(default_factory=dict)
    recommended_option_ids: dict[str, str] = field(default_factory=dict)
    hidden_option_ids: dict[str, tuple[str, ...]] = field(default_factory=dict)
    extra_options: dict[str, tuple[Choice, ...]] = field(default_factory=dict)
    task_brief: str = ""


def topic_by_id(
    topic_id: str | None,
    extras: tuple[TzTopic, ...] | list[TzTopic] | None = None,
) -> TzTopic | None:
    if not topic_id:
        return None
    found = _TOPIC_BY_ID.get(topic_id)
    if found:
        return found
    for topic in extras or ():
        if topic.id == topic_id:
            return topic
    return None


def topic_to_dict(topic: TzTopic) -> dict[str, object]:
    return {
        "id": topic.id,
        "stage": topic.stage.value,
        "title_ru": topic.title_ru,
        "title_en": topic.title_en,
        "questions": {lit.value: text for lit, text in topic.questions.items()},
        "options": [choice_as_dict(c) | {"sufficient": c.sufficient} for c in topic.options],
        "keywords": list(topic.keywords),
        "multi": topic.multi,
        "needs_substance": topic.needs_substance,
        "skippable": topic.skippable,
        "parent_id": topic.parent_id,
        "dynamic": True,
        "applies_to": sorted(topic.applies_to) if topic.applies_to else None,
        "capabilities": sorted(topic.capabilities) if topic.capabilities else None,
    }


def topic_from_dict(raw: dict) -> TzTopic | None:
    topic_id = str(raw.get("id") or "").strip()
    if not topic_id:
        return None
    try:
        stage = DiscoveryStage(str(raw.get("stage") or DiscoveryStage.FUNCTIONAL.value))
    except ValueError:
        stage = DiscoveryStage.FUNCTIONAL
    if stage in {
        DiscoveryStage.REVIEW,
        DiscoveryStage.READY_FOR_OWNER,
        DiscoveryStage.PROJECT_CREATED,
    }:
        stage = DiscoveryStage.FUNCTIONAL
    questions_raw = raw.get("questions") or {}
    questions: dict[ITLiteracy, str] = {}
    if isinstance(questions_raw, dict):
        for key, text in questions_raw.items():
            try:
                questions[ITLiteracy(str(key))] = str(text)
            except ValueError:
                continue
    if not questions:
        fallback = str(raw.get("question_ru") or raw.get("question") or "").strip()
        if fallback:
            questions = {
                ITLiteracy.LOW: fallback,
                ITLiteracy.MEDIUM: fallback,
                ITLiteracy.HIGH: fallback,
            }
    if not questions:
        return None
    options = list(choices_from_raw(raw.get("options")))
    applies = raw.get("applies_to")
    caps = raw.get("capabilities")
    return TzTopic(
        id=topic_id,
        stage=stage,
        title_ru=str(raw.get("title_ru") or topic_id)[:80],
        title_en=str(raw.get("title_en") or topic_id)[:80],
        questions=questions,
        options=tuple(options),
        keywords=tuple(str(k) for k in (raw.get("keywords") or ()) if str(k).strip()),
        multi=bool(raw.get("multi")),
        needs_substance=bool(raw.get("needs_substance")),
        skippable=bool(raw.get("skippable", False)),
        capabilities=frozenset(str(x) for x in caps) if caps else None,
        parent_id=str(raw.get("parent_id") or "") or None,
        dynamic=True,
        applies_to=frozenset(str(x) for x in applies) if applies else None,
    )


def choices_from_raw(raw: object) -> tuple[Choice, ...]:
    if not isinstance(raw, (list, tuple)):
        return ()
    options: list[Choice] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        cid = str(item.get("id") or "").strip()
        label = str(item.get("label") or "").strip()
        if not cid or not label:
            continue
        options.append(
            Choice(
                id=cid[:40],
                label=label[:180],
                exclusive=bool(item.get("exclusive")),
                recommended=bool(item.get("recommended")),
                sufficient=item.get("sufficient", True) is not False,
            )
        )
    return tuple(options)


def _str_map(payload: object) -> dict[str, str]:
    if not isinstance(payload, dict):
        return {}
    return {str(k): str(v) for k, v in payload.items() if str(v).strip()}


def _nested_str_map(payload: object) -> dict[str, dict[str, str]]:
    if not isinstance(payload, dict):
        return {}
    out: dict[str, dict[str, str]] = {}
    for key, value in payload.items():
        inner = _str_map(value)
        if inner:
            out[str(key)] = inner
    return out


def plan_to_state(plan: OutlinePlan) -> dict[str, object]:
    return {
        "capabilities": sorted(plan.capabilities),
        "skipped_topics": list(plan.skipped_ids),
        "custom_topics": [topic_to_dict(t) for t in plan.extra_topics],
        "outline_adapted": plan.adapted,
        "outline_reasons": dict(plan.reasons),
        "question_overrides": dict(plan.question_overrides),
        "option_overrides": {k: dict(v) for k, v in plan.option_overrides.items()},
        "title_overrides": dict(plan.title_overrides),
        "recommended_option_ids": dict(plan.recommended_option_ids),
        "hidden_option_ids": {k: list(v) for k, v in plan.hidden_option_ids.items()},
        "extra_options": {
            key: [choice_as_dict(c) | {"sufficient": c.sufficient} for c in value]
            for key, value in plan.extra_options.items()
        },
        "task_brief": plan.task_brief,
    }


def plan_from_state(state: dict | None) -> OutlinePlan:
    payload = state or {}
    extras: list[TzTopic] = []
    for raw in payload.get("custom_topics") or []:
        if not isinstance(raw, dict):
            continue
        topic = topic_from_dict(raw)
        if topic:
            extras.append(topic)
    caps = payload.get("capabilities") or []
    skipped = payload.get("skipped_topics") or []
    reasons = payload.get("outline_reasons") or {}
    hidden_raw = payload.get("hidden_option_ids") or {}
    hidden: dict[str, tuple[str, ...]] = {}
    if isinstance(hidden_raw, dict):
        for key, value in hidden_raw.items():
            if isinstance(value, (list, tuple)):
                hidden[str(key)] = tuple(str(x) for x in value if str(x).strip())
    extra_raw = payload.get("extra_options") or {}
    extra_choice_map: dict[str, tuple[Choice, ...]] = {}
    if isinstance(extra_raw, dict):
        for key, value in extra_raw.items():
            parsed = choices_from_raw(value)
            if parsed:
                extra_choice_map[str(key)] = parsed
    return OutlinePlan(
        capabilities=frozenset(str(x) for x in caps),
        skipped_ids=tuple(str(x) for x in skipped),
        extra_topics=tuple(extras),
        adapted=bool(payload.get("outline_adapted")),
        reasons={str(k): str(v) for k, v in dict(reasons).items()}
        if isinstance(reasons, dict)
        else {},
        question_overrides=_str_map(payload.get("question_overrides")),
        option_overrides=_nested_str_map(payload.get("option_overrides")),
        title_overrides=_str_map(payload.get("title_overrides")),
        recommended_option_ids=_str_map(payload.get("recommended_option_ids")),
        hidden_option_ids=hidden,
        extra_options=extra_choice_map,
        task_brief=str(payload.get("task_brief") or "").strip()[:90],
    )


def topics_for(
    product_type: str | None,
    *,
    task_shape: str | None = None,
    capabilities: frozenset[str] | None = None,
) -> list[TzTopic]:
    """Ordered TZ topics applicable to the current product/shape.

    Capability-gated modules are omitted until ``capabilities`` is provided
    (including an empty set after adaptation).
    """
    selected: list[TzTopic] = []
    for topic in TZ_TOPICS:
        by_product = not topic.applies_to or (
            bool(product_type) and product_type in topic.applies_to
        )
        by_also_shape = bool(
            topic.also_task_shapes
            and task_shape
            and task_shape in topic.also_task_shapes
        )
        if topic.applies_to and not by_product and not by_also_shape:
            continue
        if topic.task_shapes and (not task_shape or task_shape not in topic.task_shapes):
            continue
        if topic.capabilities:
            if capabilities is None:
                continue
            if not (topic.capabilities & capabilities):
                continue
        selected.append(topic)
    return selected


def resolve_active_topics(
    product_type: str | None,
    *,
    task_shape: str | None = None,
    plan: OutlinePlan | None = None,
) -> list[TzTopic]:
    """Catalog topics for this product plus per-project extras, minus skips."""
    caps = plan.capabilities if plan and plan.adapted else None
    skipped = set(plan.skipped_ids) if plan else set()
    extras = list(plan.extra_topics) if plan else []
    selected = [
        topic
        for topic in topics_for(product_type, task_shape=task_shape, capabilities=caps)
        if topic.id not in skipped
    ]
    extra_ids = {topic.id for topic in selected}
    for extra in extras:
        if extra.id in extra_ids or extra.id in skipped:
            continue
        insert_at = len(selected)
        if extra.parent_id:
            for idx, topic in enumerate(selected):
                if topic.id == extra.parent_id:
                    insert_at = idx + 1
                    break
        else:
            for idx, topic in enumerate(selected):
                if topic.stage == extra.stage:
                    insert_at = idx + 1
        selected.insert(insert_at, extra)
        extra_ids.add(extra.id)
    stage_rank = {stage: idx for idx, stage in enumerate(DISCOVERY_STAGES)}
    catalog_rank = {topic.id: idx for idx, topic in enumerate(TZ_TOPICS)}
    selected.sort(
        key=lambda topic: (
            stage_rank.get(topic.stage, 99),
            0 if not topic.parent_id else 1,
            catalog_rank.get(topic.parent_id or topic.id, 10_000),
            catalog_rank.get(topic.id, 10_000),
            topic.id,
        )
    )
    return selected


def question_text(
    topic: TzTopic,
    literacy: ITLiteracy,
    product_type: str | None,
    *,
    override: str | None = None,
) -> str:
    if override and override.strip():
        return override.strip()
    by_type = topic.questions_by_product.get(product_type or "")
    if by_type and literacy in by_type:
        return by_type[literacy]
    if by_type and ITLiteracy.LOW in by_type and literacy == ITLiteracy.MEDIUM:
        return by_type.get(ITLiteracy.MEDIUM) or by_type[ITLiteracy.LOW]
    return topic.questions.get(literacy) or topic.questions[ITLiteracy.MEDIUM]


def remaining_topics(
    product_type: str | None,
    *,
    task_shape: str | None = None,
    done_ids: set[str],
    plan: OutlinePlan | None = None,
) -> list[TzTopic]:
    return [
        t
        for t in resolve_active_topics(product_type, task_shape=task_shape, plan=plan)
        if t.id not in done_ids
    ]
