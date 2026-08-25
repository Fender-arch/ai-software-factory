# 12 — Инструментарий агента

> Перевод. Канон: [`docs/12-Agent-Toolkit.md`](../12-Agent-Toolkit.md)

| Поле | Значение |
|------|----------|
| Status | Accepted |
| Version | 0.2 |
| Updated | 2026-07-31 |
| Owner | ASF Core |

Что нужно Cursor, чтобы реализовать ASF MVP, не восстанавливая архитектуру из истории чатов.

## Уже в этом репозитории (обязательно)

| Актив | Зачем |
|-------|-------|
| `AGENTS.md` | Точка входа сессии + DoD |
| `docs/00–15` | Vision, scope, architecture, Discovery, KG, Mini App UX, консоль ТЗ владельца |
| `docs/13-Dev-Setup.md` | Запуск / тесты / env |
| `decisions/` | Зафиксированные ADR |
| `tasks/EPIC-*` | Слайсы поставки |
| `prompts/` | Промпты режимов Coordinator |
| `schemas/` | Контракты структурированного I/O |
| `templates/` | Подсказки Discovery по типам продуктов |
| `.cursor/rules/` | Постоянные ограничения |
| `.cursor/skills/asf-mvp/` | Как реализовывать следующий epic |

## Cursor rules в этом репозитории

| Правило | Когда |
|---------|-------|
| `asf.mdc` | Always — freeze MVP и границы пакетов |
| `python-backend.mdc` | Python / FastAPI / SQLAlchemy / Alembic |
| `discovery-kg.mdc` | Discovery FSM, entities, relations, artifacts |
| `integrations.mdc` | Telegram + STT / Whisper |
| `product-templates.mdc` | Реализация экспортированных задач / product templates |

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

**Обычно не нужны для кодинга MVP:** design/UI skills, slides, banner, latent-briefing, hosted-agents (если позже не появится Cursor CLI hosting).

## Намеренно не добавлено

| Искушение | Почему пропускаем |
|-----------|-------------------|
| Полная Architecture Bible / дамп RFC | Уже отвергнуто для MVP |
| Копия `gpt.md` в репозиторий | Шум; решения уже дистиллированы |
| Пакет skills для multi-agent runtime | Противоречит DEC-002 |
| Runbooks Redis / GraphDB | Future |

## Минимальный чеклист сессии

1. Прочитать `AGENTS.md`
2. Активировать project skill `asf-mvp`
3. Открыть текущий epic в `tasks/`
4. Трогать только разрешённые пакеты
5. Перед завершением прогнать `pytest`
