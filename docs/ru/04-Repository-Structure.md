# 04 — Структура репозитория

> Перевод. Канон: [`docs/04-Repository-Structure.md`](../04-Repository-Structure.md)

| Поле | Значение |
|------|----------|
| Status | Accepted |
| Version | 0.3 |
| Updated | 2026-08-16 |
| Owner | ASF Core |

```
ai-software-factory/
├── README.md
├── AGENTS.md             # Точка входа для агента
├── pyproject.toml
├── requirements.txt
├── docker-compose.yml
├── .env.example
├── docs/                 # Foundation (в т.ч. Agent-Toolkit, Dev-Setup, Telegram UX)
├── decisions/            # Короткие ADR
├── backlog/              # Future / Ideas / Research
├── tasks/                # Эпики поставки
├── prompts/              # Промпты режимов
├── schemas/              # JSON-схемы
├── templates/            # Подсказки по типам продуктов
├── .cursor/
│   ├── rules/            # Постоянные правила Cursor
│   └── skills/asf-mvp/   # Skill реализации проекта
├── apps/
│   ├── api/              # Точка входа FastAPI
│   ├── miniapp/          # Фронтенд Telegram Mini App (UI заказчика)
│   └── console/          # Консоль графа ТЗ владельца (DEC-007)
├── core/                 # config, db, models, coordinator
├── knowledge/            # репозитории entity/relation
├── discovery/            # Discovery FSM, интервью, черновик ТЗ
├── integrations/
│   ├── telegram/         # Polling бота, Menu/WebApp, owner HITL
│   └── stt/
├── shared/
├── alembic/
├── tests/
└── docker/
```

## Правила

- Документация версионируется как код (status, version, date).
- Отклонённые архитектурные идеи живут в `decisions/` или `backlog/`, а не как конкурирующие документы.
- Код приложения — в модулях пакетов; в Telegram-хендлерах и UI Mini App нет бизнес-логики сверх I/O — вызывать `core.services`.
- Mini App ходит в FastAPI; бот остаётся тонким I/O для уведомлений и команд владельца.
- Консоль ТЗ владельца ходит в `/console/api/`; в статическом UI нет бизнес-логики сверх I/O.
