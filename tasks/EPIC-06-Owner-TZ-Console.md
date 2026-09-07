# EPIC-06 — Owner TZ graph console

| Field | Value |
|-------|-------|
| Status | Done |
| Version | 0.1 |

## Goal

Owner/analyst web console: hierarchical TZ graph from the KG, status legend, conflict/dependency edges, requirement side panel with history. Not Mini App. Not a customer portal.

Refs: `decisions/DEC-007-Owner-TZ-Console.md`, `docs/15-Owner-TZ-Console.md`.

## Deliverables

- [x] `DEC-007` Accepted; docs + Future.md distinguish owner console vs customer review portal
- [x] `entity_history` + Requirement statuses + `depends_on` / `conflicts_with`
- [x] Graph projection + console mutations (`knowledge/tz_graph.py`, `core/requirement_console.py`)
- [x] FastAPI `/console/api/*` with `CONSOLE_TOKEN`; static UI `apps/console/` at `/console/`
- [x] Tests: graph shape, auth, status + history, rejected-without-reason, edge kinds

## Notes

Customer channel remains Mini App. HITL TZ gate is owner bot **and** console. After approve, the owner sends TZ+estimate from the console; the customer confirms in Mini App. History is an audit table, not an event bus. Commercial spine is derived (`core/commercial_pipeline.py`), not a second writable enum.

APIs: `GET /console/api/projects`, `GET .../tz-graph`, requirement GET/PATCH, relation POST/DELETE, project files GET/POST/DELETE + download. Static UI at `/console/`. Env: `CONSOLE_TOKEN`, `UPLOAD_DIR`.

Verified: `pytest` 45 passed (incl. `tests/test_console.py`).
