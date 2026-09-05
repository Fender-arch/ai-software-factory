# 05 — Дорожная карта

> Перевод. Канон: [`docs/05-Roadmap.md`](../05-Roadmap.md)

| Поле | Значение |
|------|----------|
| Status | Accepted |
| Version | 0.4 |
| Updated | 2026-09-05 |
| Owner | ASF Core |

## Сейчас — Foundation

- Набор документации Accepted (в т.ч. UX Telegram Mini App / DEC-006)
- Запускаемый скелет: API + Postgres + stub Telegram-бота + STT
- Миграции для projects, messages, entities, relations, tasks
- Эпики 01–06 поставлены (infra → Discovery → KG → HITL/planner/export/factory → Mini App → консоль ТЗ владельца)
- Две оценки: эвристика владельца + рыночная смета/отчёт клиенту до Planner (DEC-012)

## Поставка MVP по неделям

| Неделя | Фокус | Epic |
|--------|-------|------|
| 1 | Infra, Docker, Postgres, Telegram create-project, путь voice→STT | EPIC-01 |
| 2 | Цикл Discovery, сообщения, извлечение требований | EPIC-02 |
| 3 | Knowledge Core: entity/relation, context builder, search | EPIC-03 |
| 4 | Генерация спецификации, HITL-ревью, разбиение на задачи, экспорт, MVP Factory + Intervention Queue | EPIC-04 |
| 5 | Telegram Mini App: home на RU (создать / изменить / замечания к реализации), project workspace | EPIC-05 |
| 6 | Консоль графа ТЗ владельца (граф требований, статусы, конфликты/зависимости) | EPIC-06 |

## Позже (ASF Future)

См. [backlog/Future.md](../../backlog/Future.md): Redis, GraphDB, event sourcing, multi-agent runtime, **клиентский** review portal, автоматизация Cursor CLI, forum topics на проект, owner-портал в Mini App и т.д.
