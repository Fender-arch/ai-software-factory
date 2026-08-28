# 13 — Dev Setup

| Field | Value |
|-------|-------|
| Status | Accepted |
| Version | 0.9 |
| Updated | 2026-08-28 |
| Owner | ASF Core |

## Prerequisites

- Python 3.11+
- Docker Desktop (Postgres + API)
- Git
- Telegram bot token (for live bot)
- OpenAI API key (for Whisper when `STT_PROVIDER=whisper`)

## Quick start (Docker)

```bash
cp .env.example .env
# edit TELEGRAM_BOT_TOKEN / OPENAI_API_KEY as needed
docker compose up --build
```

- API: http://localhost:8000/health
- OpenAPI: http://localhost:8000/docs

## Local API (venv)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
# start Postgres via: docker compose up db -d
alembic upgrade head
uvicorn apps.api.main:app --reload
pytest
```

## Environment

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | SQLAlchemy URL |
| `TELEGRAM_BOT_TOKEN` | Bot polling |
| `GROQ_API_KEY` | Groq Whisper STT (recommended server fallback) |
| `OPENAI_API_KEY` | OpenAI Whisper if `STT_PROVIDER=whisper` (+ future LLM) |
| `STT_PROVIDER` | `stub` \| `groq` \| `whisper` |
| `STT_MODEL` | e.g. `whisper-large-v3-turbo` (Groq) or `whisper-1` (OpenAI) |
| `LLM_PROVIDER` | `stub` \| `groq` (JSON outline, LLM interview turns, TZ polish) |
| `LLM_MODEL` | Groq chat model (default `llama-3.3-70b-versatile`; ignored for stub) |
| `DISCOVERY_ENGINE` | `auto` \| `llm` \| `fsm` — DEC-008. `auto` = LLM-driven turns when `LLM_PROVIDER` is not `stub`; `fsm` forces the deterministic path |
| `OWNER_TELEGRAM_ID` | HITL owner chat |
| `ASF_ESTIMATE_HOURLY_RATE` | Hourly rate for owner TZ cost estimate (default `3000`) |
| `ASF_ESTIMATE_CURRENCY` | Currency code for that estimate (default `RUB`) |
| `MINIAPP_URL` | HTTPS URL of Mini App (e.g. `https://host/miniapp/`) for Menu Button / WebApp |
| `CONSOLE_TOKEN` | Owner TZ console (`X-Console-Token`). Empty allowed only if `ASF_ENV=local` and `ASF_DEBUG=true` |
| `UPLOAD_DIR` | Project file attachments (default `data/uploads`) |
| `MAX_UPLOAD_BYTES` | Max attachment size (default 20 MiB) |

## Telegram Mini App

Served by the API at http://localhost:8000/miniapp/ (browser smoke: add `?uid=<telegram_user_id>`).

For Telegram WebApp, expose the API with HTTPS and set `MINIAPP_URL` to that `/miniapp/` URL, then restart the bot. The Mini App requests fullscreen and, inside Telegram, records voice for Groq Whisper (allow the Telegram app microphone permission on Android).

## Owner TZ console

Served at http://localhost:8000/console/. Set `CONSOLE_TOKEN` in `.env` and paste it in the console header (sent as `X-Console-Token`). Local debug with an empty token is allowed.

Details: [15-Owner-TZ-Console.md](15-Owner-TZ-Console.md).

## Telegram bot (optional process)

```bash
python -m integrations.telegram.bot
```

`/start` — Russian onboarding + WebApp button when `MINIAPP_URL` is set. Transitional: `/new`, `/use`, text or voice.

Owner HITL (after draft TZ): `/review`, `/approve`, `/changes`, `/reject`, then `/plan`, `/export`.

## Smoke checks

1. `GET /health` → `ok`
2. `GET /miniapp/` → Russian home UI
3. `GET /console/` → owner TZ graph UI
4. `POST /projects` → create
5. `GET /projects?customer_telegram_id=` → list
6. `POST /projects/{id}/messages` → Discovery reply
7. `GET /projects/{id}/workspace` → thread
8. `POST /projects/{id}/feedback` → classified note
9. After a full interview, `GET /projects/{id}/artifacts/draft-tz` → markdown draft
10. `POST /projects/{id}/hitl` with `{"action":"approve"}` → status `READY`
11. `pytest` green

## VPS (existing website)

Production compose does **not** replace local `docker compose`. See [16-VPS-Deploy.md](16-VPS-Deploy.md): API on `127.0.0.1:18000`, extra nginx vhosts only, GitHub secrets in [`.github/SECRETS.md`](../.github/SECRETS.md).
