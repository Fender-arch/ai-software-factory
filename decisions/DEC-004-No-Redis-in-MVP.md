# DEC-004 — No Redis in MVP

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2026-07-30 |

## Context

ChatGPT plan included Redis early. For first customers, Postgres task statuses are enough.

## Decision

Do not run Redis in MVP. Use PostgreSQL for task queue semantics (`NEW`, `IN_PROGRESS`, `WAITING_USER`, `DONE`, `FAILED`).

## Consequences

- Smaller compose stack
- Redis may be added later without changing domain statuses
