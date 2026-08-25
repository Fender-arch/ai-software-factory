# DEC-007 — Owner TZ graph console

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2026-08-16 |

## Context

Owners need a graphical view of collected TZ requirements (sections, leaves, statuses, conflicts, dependencies). A full **customer** web review portal remains Future. Customer UI stays the Telegram Mini App (DEC-006).

## Decision

Ship a **narrow owner/analyst web console** (not a customer portal, not inside the Mini App):

- Static UI at `/console/`, APIs under `/console/api/`
- Auth: `CONSOLE_TOKEN` (`X-Console-Token`). Empty token allowed only when `ASF_ENV=local` and `ASF_DEBUG=true`
- Graph is a **view** over the PostgreSQL KG plus TZ outline (`discovery/tz_outline.py`). No Neo4j. No new Section entities
- Requirement lifecycle statuses: `new` | `processed` | `needs_clarification` | `conflict` | `rejected` | `superseded`
- Relation types `depends_on` and `conflicts_with` (Requirement↔Requirement)
- Append-only `entity_history` audit log — **not** event sourcing / event bus
- HITL approve/reject of the draft TZ stays on the owner bot path

## Consequences

- Analysts inspect and triage requirements without expanding Mini App scope
- Full owner portal inside Mini App and customer Web Human Review Portal stay in `backlog/Future.md`
- Skill / MVP filter: this console is allowed; a customer web portal still needs a new ADR
