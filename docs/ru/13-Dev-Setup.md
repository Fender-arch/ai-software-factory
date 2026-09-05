# 13 — Настройка окружения разработки

> Перевод. Канон: [`docs/13-Dev-Setup.md`](../13-Dev-Setup.md)

| Поле | Значение |
|------|----------|
| Status | Accepted |
| Version | 0.10 |
| Updated | 2026-09-05 |
| Owner | ASF Core |

## Предварительные требования

- Python 3.11+
- Docker Desktop (Postgres + API)
- Git
- Токен Telegram-бота (для живого бота)
- OpenAI API key (для Whisper при `STT_PROVIDER=whisper`)

## Быстрый старт (Docker)

```bash
cp .env.example .env
# при необходимости отредактируйте TELEGRAM_BOT_TOKEN / OPENAI_API_KEY
docker compose up --build
```

- API: http://localhost:8000/health
- OpenAPI: http://localhost:8000/docs

## Локальный API (venv)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
# Postgres: docker compose up db -d
alembic upgrade head
uvicorn apps.api.main:app --reload
pytest
```

## Окружение

| Переменная | Назначение |
|------------|------------|
| `DATABASE_URL` | URL SQLAlchemy |
| `TELEGRAM_BOT_TOKEN` | Polling бота |
| `GROQ_API_KEY` | Groq Whisper STT (рекомендуемый серверный fallback) |
| `OPENAI_API_KEY` | OpenAI Whisper при `STT_PROVIDER=whisper` (+ будущий LLM) |
| `STT_PROVIDER` | `stub` \| `groq` \| `whisper` |
| `STT_MODEL` | напр. `whisper-large-v3-turbo` (Groq) или `whisper-1` (OpenAI) |
| `LLM_PROVIDER` | `stub` \| `groq` (адаптация каркаса ТЗ и вариантов ответа JSON; ходы заказчика остаются детерминированными) |
| `LLM_MODEL` | Модель Groq chat (по умолчанию `llama-3.3-70b-versatile`; для stub не нужна) |
| `OWNER_TELEGRAM_ID` | Чат владельца для HITL |
| `ASF_ESTIMATE_HOURLY_RATE` | Ставка часа для оценки стоимости ТЗ (по умолчанию `3000`) |
| `ASF_ESTIMATE_CURRENCY` | Валюта этой оценки (по умолчанию `RUB`) |
| `ASF_MARKET_RATES_URL` | Опциональный HTTPS JSON публичных вилок ставок (смета клиенту). Пусто = встроенная таблица |
| `ASF_MARKET_RATES_ALLOWLIST` | Хосты через запятую, которым разрешён этот fetch (защита от SSRF) |
| `MINIAPP_URL` | HTTPS URL Mini App (например `https://host/miniapp/`) для Menu Button / WebApp |
| `CONSOLE_TOKEN` | Консоль ТЗ владельца (`X-Console-Token`). Пустой токен только при `ASF_ENV=local` и `ASF_DEBUG=true` |
| `ASF_INTERVENTION_KEY` | Шифрует секреты Intervention Queue (DEC-013). Пустое → локальный производный ключ |
| `ASF_INTERVENTION_TTL_HOURS` | TTL открытого вмешательства (по умолчанию `72`) |
| `CURSOR_API_KEY` | Опциональный Cursor Cloud Agent. Пустое → stub + deep-link экспорта |
| `CURSOR_CLOUD_API_URL` | База Cursor API (по умолчанию `https://api.cursor.com`) |
| `CURSOR_AGENT_REPO` | Опциональный URL репозитория для Cloud Agent |
| `UPLOAD_DIR` | Вложения проекта (по умолчанию `data/uploads`) |
| `MAX_UPLOAD_BYTES` | Максимальный размер вложения (по умолчанию 20 МиБ) |

## Telegram Mini App

Отдаётся API по адресу http://localhost:8000/miniapp/ (smoke в браузере: `?uid=<telegram_user_id>`).

Для Telegram WebApp нужен HTTPS на API и `MINIAPP_URL` на этот `/miniapp/`, затем перезапуск бота. Mini App запрашивает fullscreen, а внутри Telegram пишет голос и отдаёт его в Groq Whisper (на Android разрешите микрофон приложению Telegram).

## Консоль ТЗ владельца

Отдаётся по адресу http://localhost:8000/console/. Задайте `CONSOLE_TOKEN` в `.env` и вставьте его в шапку консоли (заголовок `X-Console-Token`). В локальном debug пустой токен разрешён.

Детали: [15-Owner-TZ-Console.md](15-Owner-TZ-Console.md).

## Telegram-бот (опциональный процесс)

```bash
python -m integrations.telegram.bot
```

`/start` — онбординг на русском + кнопка WebApp при заданном `MINIAPP_URL`. Переходный режим: `/new`, `/use`, текст или голос.

HITL владельца (после draft TZ): `/review`, `/approve`, `/changes`, `/reject`, затем `/plan`, `/export`.

## Smoke-проверки

1. `GET /health` → `ok`
2. `GET /miniapp/` → home UI на русском
3. `GET /console/` → UI графа ТЗ владельца
4. `POST /projects` → создать
5. `GET /projects?customer_telegram_id=` → список
6. `POST /projects/{id}/messages` → ответ Discovery
7. `GET /projects/{id}/workspace` → лента
8. `POST /projects/{id}/feedback` → классифицированное замечание
9. После полного интервью `GET /projects/{id}/artifacts/draft-tz` → markdown-черновик
10. `POST /projects/{id}/hitl` с `{"action":"approve"}` → статус `READY`
11. `pytest` зелёный

## VPS (существующий сайт)

Production compose **не** заменяет локальный `docker compose`. См. [16-VPS-Deploy.md](16-VPS-Deploy.md): API на `127.0.0.1:18000`, только дополнительные vhost nginx, секреты GitHub в [`.github/SECRETS.md`](../../.github/SECRETS.md).
