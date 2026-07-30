# 06 — Coding Standards

| Field | Value |
|-------|-------|
| Status | Accepted |
| Version | 0.1 |
| Updated | 2026-07-30 |
| Owner | ASF Core |

## Language & style

- Python 3.11+, type hints on public functions
- Prefer clear modules over clever abstractions
- No microservices in MVP
- Business rules in `core` / `discovery` / `knowledge`, not in transport layers

## API

- FastAPI routers thin; services own transactions
- Pydantic models for request/response
- Explicit HTTP errors; no silent swallow

## Database

- SQLAlchemy 2 mapped classes
- All schema changes via Alembic
- JSONB payloads validated against `schemas/` where practical

## Tests

- Pytest for unit + API smoke
- Prefer in-memory or test DB; STT/LLM always injectable stubs in tests

## Git

- Small commits; messages explain why
- Do not commit `.env`, secrets, or large media
