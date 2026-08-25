# EPIC-01 — Infrastructure

| Field | Value |
|-------|-------|
| Status | Done |
| Version | 0.1 |

## Goal

Runnable platform skeleton: Docker Compose, PostgreSQL, Alembic, FastAPI health, Telegram create-project, voice→STT stub path.

## Deliverables

- [x] Repo structure + Foundation docs
- [x] `docker compose up` healthy
- [x] Migrations applied
- [x] `/health`, create project, ingest message APIs
- [x] Telegram bot stub
- [x] STT stub wired for voice messages

## Notes

No Redis. No full Discovery LLM yet.

Verified locally (2026-07-31): compose (db healthy + api), Alembic `0001_initial`, smoke `/health` → create project → text → voice stub; `pytest` 5 passed.
