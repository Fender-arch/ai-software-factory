# 03 — Tech Stack

| Field | Value |
|-------|-------|
| Status | Accepted |
| Version | 0.1 |
| Updated | 2026-07-30 |
| Owner | ASF Core |

Locked choices for MVP. Alternatives belong in Future, not in endless bake-offs.

| Layer | Choice |
|-------|--------|
| Language | Python 3.11+ |
| API | FastAPI + Uvicorn |
| ORM / migrations | SQLAlchemy 2 + Alembic |
| Database | PostgreSQL 16 (`entity`, `relation`, JSONB) |
| Queue / cache | **None in MVP** (Postgres statuses); Redis = Future |
| Customer UI | Telegram Bot API (aiogram) |
| STT | OpenAI Whisper API (or compatible); `STT_PROVIDER=stub` for local/dev |
| LLM | Pluggable router; stub in skeleton; OpenAI / OpenRouter later |
| Coding executor | Cursor (rules + task export); CLI integration later |
| Containers | Docker + Docker Compose |
| Tests | Pytest |

## Environment variables

See `.env.example`: `DATABASE_URL`, `TELEGRAM_BOT_TOKEN`, `OPENAI_API_KEY`, `STT_PROVIDER`, `LLM_PROVIDER`, `OWNER_TELEGRAM_ID`.
