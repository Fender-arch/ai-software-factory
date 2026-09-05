# 05 — Roadmap

| Field | Value |
|-------|-------|
| Status | Accepted |
| Version | 0.4 |
| Updated | 2026-09-05 |
| Owner | ASF Core |

## Now — Foundation

- Documentation set Accepted (incl. Telegram Mini App UX / DEC-006)
- Runnable skeleton: API + Postgres + Telegram bot stub + STT
- Migrations for projects, messages, entities, relations, tasks
- Epics 01–06 delivered (infra → Discovery → KG → HITL/planner/export/factory → Mini App → owner TZ console)

## Week-oriented MVP delivery

| Week | Focus | Epic |
|------|-------|------|
| 1 | Infra, Docker, Postgres, Telegram create-project, voice→STT path | EPIC-01 |
| 2 | Discovery loop, messages, requirements extraction | EPIC-02 |
| 3 | Knowledge Core: entity/relation, context builder, search | EPIC-03 |
| 4 | Spec generation, HITL review, task breakdown, export, MVP Factory + Intervention Queue | EPIC-04 |
| 5 | Telegram Mini App: RU home (create / change / implementation feedback), project workspace | EPIC-05 |
| 6 | Owner TZ graph console (requirements graph, statuses, conflicts/deps) | EPIC-06 |

## Later (ASF Future)

See [backlog/Future.md](../backlog/Future.md): Redis, GraphDB, event sourcing, multi-agent runtime, **customer** review portal, Cursor CLI automation, forum topics per project, owner Mini App portal, etc.
