# 06 — Стандарты кодирования

> Перевод. Канон: [`docs/06-Coding-Standards.md`](../06-Coding-Standards.md)

| Поле | Значение |
|------|----------|
| Status | Accepted |
| Version | 0.1 |
| Updated | 2026-07-30 |
| Owner | ASF Core |

## Язык и стиль

- Python 3.11+, type hints на публичных функциях
- Предпочитать понятные модули хитрым абстракциям
- Без микросервисов в MVP
- Бизнес-правила в `core` / `discovery` / `knowledge`, не в transport-слоях

## API

- Роутеры FastAPI тонкие; сервисы владеют транзакциями
- Pydantic-модели для request/response
- Явные HTTP-ошибки; без тихого проглатывания

## База данных

- Mapped-классы SQLAlchemy 2
- Все изменения схемы через Alembic
- JSONB-payload по возможности валидировать по `schemas/`

## Тесты

- Pytest для unit + API smoke
- Предпочитать in-memory или тестовую БД; STT/LLM в тестах всегда injectable stubs

## Git

- Маленькие коммиты; сообщения объясняют почему
- Не коммитить `.env`, секреты или крупные медиа
