# 12 — Инструментарий агента

> Перевод. Канон: [`docs/12-Agent-Toolkit.md`](../12-Agent-Toolkit.md)

| Поле | Значение |
|------|----------|
| Status | Accepted |
| Version | 0.6 |
| Updated | 2026-09-05 |
| Owner | ASF Core |

Что нужно Cursor, чтобы реализовать ASF (аудитория A) и проштамповать клиентский репозиторий MVP (аудитория B), не восстанавливая архитектуру из истории чатов.

ADR: [DEC-009](../../decisions/DEC-009-Agent-Toolkit-Reuse.md). Экономия токенов: `.cursor/skills/token-economy/SKILL.md`.

## Уже в этом репозитории (обязательно)

| Актив | Зачем |
|-------|-------|
| `AGENTS.md` | **Роутер** — жёсткие ограничения, таблица skills, секции Learned |
| `docs/00–16` | Vision, scope, architecture, Discovery, KG, Mini App UX, консоль ТЗ владельца, деплой VPS |
| `core/estimate.py` + `core/client_estimate.py` | Две оценки: эвристика владельца и рыночная смета клиенту (DEC-012) |
| `docs/13-Dev-Setup.md` | Запуск / тесты / env |
| `docs/16-VPS-Deploy.md` | VPS рядом с существующим сайтом |
| `decisions/` | Зафиксированные ADR (в т.ч. DEC-009–013: toolkit, mobile_native, Experience Layer, клиентская смета, factory) |
| `tasks/EPIC-*` | Слайсы поставки |
| `prompts/` | Промпты режимов Coordinator (`discovery-interview.md` — интервьюер) |
| `schemas/` | Контракты структурированного I/O |
| `templates/` | Подсказки Discovery + `DESIGN.md` + AGENTS заказчика + заготовки Spec Kit |
| `.cursor/rules/` | Тонкий always-on + правила по glob |
| `.cursor/skills/` | Процедуры по требованию |

## Экономия токенов (progressive disclosure)

| Слой | Когда читать |
|------|----------------|
| `AGENTS.md` + `asf.mdc` | Каждая сессия ASF (оба коротких) |
| Glob `.mdc` | Только подходящие типы файлов |
| Один skill | Задача совпала с его `description` |
| Foundation doc / ADR | Сомнение в решении или схеме |

Не предзагружать все skills. Не вставлять эту таблицу в промпты.

## Cursor rules в этом репозитории

| Правило | Когда |
|---------|-------|
| `asf.mdc` | Always — freeze MVP, пакеты, типы продуктов, без дампа каталогов |
| `python-backend.mdc` | Python / FastAPI / SQLAlchemy / Alembic |
| `discovery-kg.mdc` | Discovery FSM, сущности, связи, артефакты |
| `integrations.mdc` | Telegram + STT / Whisper |
| `product-templates.mdc` | Реализация экспортированных задач / product templates |
| `docs-ru-sync.mdc` | Правки английских `docs/*.md` → `docs/ru/` |
| `design-anti-slop.mdc` | CSS/JS/HTML Mini App / консоли |
| `security-basics.mdc` | `apps/api`, `core`, `integrations` |
| `miniapp-ux.mdc` | UX Mini App; маскот Experience Layer — DEC-011 |

## Project skills (по требованию)

| Skill | Применение |
|-------|------------|
| `asf-mvp` | Следующий epic фабрики |
| `human-interview` | Интервью консультанта; один вопрос; журнал допущений |
| `anti-slop-design` | Свой UI; сначала `DESIGN.md` |
| `token-economy` | Роутеры/rules/skills без раздувания контекста |
| `project-memory` | Секции Learned; без секретов |
| `autodoc` | Документы + зеркало RU после кода/ADR |
| `security-review` | Проход в духе OWASP; Telegram / initData |
| `mvp-customer-pack` | Штамп репозитория аудитории B |
| `mvp-speckit-export` | KG / ТЗ → `spec.md` `plan.md` `tasks.md` |

### Как пользоваться каждым skill (кратко)

1. **asf-mvp** — один чекбокс эпика; границы пакетов; pytest.
2. **human-interview** — признать сказанное, один вопрос, адаптация грамотности; JSON Discovery не ломать.
3. **anti-slop-design** — читать `DESIGN.md`; запрет Inter+purple и дефолтного Tailwind blue/gray как основного вида.
4. **token-economy** — always-on тонкий; skills по требованию; без энциклопедий в rules.
5. **project-memory** — только устойчивые факты; опционально плагин Cursor continual-learning (проприетарный hook TS не копировать).
6. **autodoc** — канон EN, затем `docs/ru/` в том же ходе.
7. **security-review** — находки + правки; без exploit PoC.
8. **mvp-customer-pack** — тонкий AGENTS + DESIGN + security/design skills + заготовки Spec Kit.
9. **mvp-speckit-export** — проекция KG на имена Spec Kit; spec-kit не вендорить.

## Две аудитории

| | A — фабрика ASF | B — MVP заказчика |
|--|-----------------|-------------------|
| Роутер | `AGENTS.md` репозитория | `templates/customer-agents/AGENTS.md` |
| Skill реализации | `asf-mvp` | экспорт `tasks.md` + шаблон продукта |
| Память | KG для заказчиков; Learned для репо фабрики | Learned + проштампованный spec |
| UI | Токены Mini App / консоли | `templates/DESIGN.md` |

## Личные / глобальные skills (по необходимости)

Живут вне репозитория (`~/.cursor/skills/`). Подключайте по требованию; не копируйте целиком в ASF.

| Skill | Применение для ASF MVP |
|-------|------------------------|
| `project-development` | Форма пайплайна, стоимость, структурированные handoff между стадиями |
| `multi-agent-patterns` | Подтвердить **Coordinator+modes** (не swarm); дизайн handoff |
| `harness-engineering` | HITL-гейты, locked vs editable поверхности, durable logs |
| `tool-design` | Контракты LLM/tools, JSON-схемы режимов, восстановление после ошибок |
| `memory-systems` | KG как семантическая память; правила консолидации |
| `context-optimization` | Context builder: что видит каждый режим |
| `filesystem-context` | Экспорт артефактов / file-backed представления проекта |
| `evaluation` | Чеклисты готовности / качества Discovery |
| `long-horizon-prompting` | Укрепление промптов Discovery / Reviewer |

## Плагин Cursor continual-learning

Опционально. Settings → Plugins → включить **continual-learning**, если команда хочет автосбор в стиле Learned. Свой fallback репозитория: `.cursor/skills/project-memory/SKILL.md`. TypeScript плагина не вендорить.

## Намеренно не добавлено

| Искушение | Почему пропускаем |
|-----------|-------------------|
| Полная Architecture Bible / дамп RFC | Уже отвергнуто для MVP |
| Копия `gpt.md` в репозиторий | Шум; решения уже дистиллированы |
| Пакет skills для multi-agent runtime | Противоречит DEC-002 |
| OpenReq (или похожий) runtime | Контракт уже у Discovery + KG |
| Always-on mega rules | DEC-009 / экономия токенов |
| Оптовый вендор чужих skill-репозиториев | Дрейф + лицензия |
| git subtree spec-kit | Только проекция и заготовки |
| Оптовые Rive-киты / lip-sync TTS-маскот | Слайс рантайма — DEC-011; lip-sync остаётся Future |
| Runbooks Redis / GraphDB | Future |

## Минимальный чеклист сессии

1. Прочитать `AGENTS.md` (только роутер)
2. Активировать **один** подходящий project skill (`asf-mvp` для кода фабрики)
3. Открыть текущий epic в `tasks/` (фабрика) или `tasks.md` (заказчик)
4. Трогать только разрешённые пакеты / зафиксированный тип продукта
5. Перед завершением прогнать `pytest` (или команду тестов заказчика)
