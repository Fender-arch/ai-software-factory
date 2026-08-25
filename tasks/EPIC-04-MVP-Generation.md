# EPIC-04 — MVP Generation

| Field | Value |
|-------|-------|
| Status | Done |
| Version | 0.1 |

## Goal

Owner-approved TZ → Planner tasks → export for Cursor → simple product MVP.

## Deliverables

- [x] HITL approval flow in Telegram
- [x] Planner mode task breakdown
- [x] Task export (Markdown / JSON)
- [x] Cursor rules aligned with product templates
- [x] Smoke delivery for one product type end-to-end

## Notes

Deterministic HITL (`core/hitl.py`) gates on `WAITING_OWNER`; only `approve` → `READY` unlocks Planner. Planner (`core/planner.py`) writes DB `tasks` + KG Task entities from product-type templates; LLM stub annotates via `/coordinator/planner`. Export: `GET /export/tasks?format=markdown|json`. Telegram owner commands: `/review`, `/approve`, `/changes`, `/reject`, `/plan`, `/export`. Cursor rule: `.cursor/rules/product-templates.mdc`.

Verified: `pytest` covers HITL approve/changes/reject/owner check, planner idempotency, markdown/JSON export, website end-to-end smoke.
