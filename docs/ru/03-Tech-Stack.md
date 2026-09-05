# 03 — Технологический стек

> Перевод. Канон: [`docs/03-Tech-Stack.md`](../03-Tech-Stack.md)

| Поле | Значение |
|------|----------|
| Status | Accepted |
| Version | 0.8 |
| Updated | 2026-09-05 |
| Owner | ASF Core |

Зафиксированные выборы для MVP. Альтернативы — в Future, не в бесконечных bake-off.

| Слой | Выбор |
|------|-------|
| Язык | Python 3.11+ |
| API | FastAPI + Uvicorn |
| ORM / миграции | SQLAlchemy 2 + Alembic |
| БД | PostgreSQL 16 (`entity`, `relation`, JSONB) |
| Очередь / кэш | **Нет в MVP** (статусы в Postgres); Redis = Future |
| UI заказчика | Telegram **Mini App** (fullscreen) + Bot API (aiogram) для входа/уведомлений/owner HITL; маскот через CDN `@rive-app/canvas` + SVG fallback ([DEC-011](../../decisions/DEC-011-Experience-Layer-Mascot.md)) |
| UI владельца | Внутренняя консоль графа ТЗ (`apps/console/`, vis-network); [DEC-007](../../decisions/DEC-007-Owner-TZ-Console.md) |
| STT | Mini App в Telegram: **Groq Whisper** по записанному аудио; Web Speech только вне Telegram. Также `whisper` (OpenAI) / `stub` |
| LLM | Подключаемый router; `stub` или **Groq** JSON (`LLM_PROVIDER=groq`) для адаптации каркаса ТЗ / подразделов и вариантов ответа на следующий вопрос |
| Coding executor | Cursor (rules + экспорт задач); CLI позже |
| Контейнеры | Docker + Docker Compose (локально `docker-compose.yml`; VPS `docker-compose.prod.yml`) |
| Тесты | Pytest |

## Переменные окружения

См. `.env.example`: `DATABASE_URL`, `TELEGRAM_BOT_TOKEN`, `GROQ_API_KEY`, `OPENAI_API_KEY`, `STT_PROVIDER` (`stub`\|`groq`\|`whisper`), `STT_MODEL`, `LLM_PROVIDER` (`stub`\|`groq`), `LLM_MODEL`, `OWNER_TELEGRAM_ID`, `ASF_ESTIMATE_HOURLY_RATE`, `ASF_ESTIMATE_CURRENCY`, `MINIAPP_URL`, `CONSOLE_TOKEN`.

Деплой на VPS (существующий сайт сохраняется): [16-VPS-Deploy.md](16-VPS-Deploy.md), секреты [`.github/SECRETS.md`](../../.github/SECRETS.md).
