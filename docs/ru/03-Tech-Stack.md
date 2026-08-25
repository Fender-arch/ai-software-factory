# 03 — Технологический стек

> Перевод. Канон: [`docs/03-Tech-Stack.md`](../03-Tech-Stack.md)

| Поле | Значение |
|------|----------|
| Status | Accepted |
| Version | 0.4 |
| Updated | 2026-08-21 |
| Owner | ASF Core |

Зафиксированные выборы для MVP. Альтернативы — в Future, не в бесконечных bake-off.

| Слой | Выбор |
|------|-------|
| Язык | Python 3.11+ |
| API | FastAPI + Uvicorn |
| ORM / миграции | SQLAlchemy 2 + Alembic |
| БД | PostgreSQL 16 (`entity`, `relation`, JSONB) |
| Очередь / кэш | **Нет в MVP** (статусы в Postgres); Redis = Future |
| UI заказчика | Telegram **Mini App** (fullscreen) + Bot API (aiogram) для входа/уведомлений/owner HITL |
| UI владельца | Внутренняя консоль графа ТЗ (`apps/console/`, vis-network); [DEC-007](../../decisions/DEC-007-Owner-TZ-Console.md) |
| STT | Mini App: Web Speech если окружение подходит, иначе **Groq Whisper**; также `whisper` (OpenAI) / `stub` |
| LLM | Подключаемый router; `stub` или **Groq** JSON (`LLM_PROVIDER=groq`) для адаптации каркаса ТЗ / подразделов |
| Coding executor | Cursor (rules + экспорт задач); CLI позже |
| Контейнеры | Docker + Docker Compose |
| Тесты | Pytest |

## Переменные окружения

См. `.env.example`: `DATABASE_URL`, `TELEGRAM_BOT_TOKEN`, `GROQ_API_KEY`, `OPENAI_API_KEY`, `STT_PROVIDER` (`stub`\|`groq`\|`whisper`), `STT_MODEL`, `LLM_PROVIDER` (`stub`\|`groq`), `LLM_MODEL`, `OWNER_TELEGRAM_ID`, `MINIAPP_URL`, `CONSOLE_TOKEN`.
