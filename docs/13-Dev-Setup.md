# 13 — Dev Setup

| Field | Value |
|-------|-------|
| Status | Accepted |
| Version | 0.1 |
| Updated | 2026-07-31 |
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
| `OPENAI_API_KEY` | Whisper (+ future LLM) |
| `STT_PROVIDER` | `stub` \| `whisper` |
| `LLM_PROVIDER` | `stub` (real providers later) |
| `OWNER_TELEGRAM_ID` | HITL owner chat |

## Telegram bot (optional process)

```bash
python -m integrations.telegram.bot
```

Commands: `/start`, `/new <name>`, `/use <project_id>`, then text or voice.

## Smoke checks

1. `GET /health` → `ok`
2. `POST /projects` → create
3. `POST /projects/{id}/messages` → text saved, status → `INTERVIEW`
4. `POST /projects/{id}/messages/voice` → stub/Whisper transcript
5. `pytest` green
