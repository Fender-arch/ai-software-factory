# DEC-007 — Owner TZ graph console

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2026-08-16 |
| Updated | 2026-09-08 |

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
- HITL approve of the draft TZ is available on the owner bot **and** from the console (`POST /console/api/projects/{id}/hitl`)
- Commercial actions live in the console (not a customer portal): rate/discount on the client quote, send TZ+estimate package, human reply, archive. Discovery `ProjectStatus` remains the FSM; the sheet shows a **derived** spine (unique gates left-to-right, versioned agreement/MVP rows stacked in columns)
- Owner may **view TZ snapshots** by clicking spine gates and **force** previous/next (or any `ProjectStatus`) for recovery and testing. Snapshots live on `Project.payload.commercial.tz_snapshots`

## Consequences

- Analysts inspect, price, and send packages without expanding Mini App into an owner portal
- Full owner portal inside Mini App and customer Web Human Review Portal stay in `backlog/Future.md`
- Console commercial send is allowed; a customer web review portal still needs a new ADR
