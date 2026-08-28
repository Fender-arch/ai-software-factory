# EPIC-04 — MVP Generation

| Field | Value |
|-------|-------|
| Status | Done |
| Version | 0.2 |

## Goal

Owner-approved TZ → Planner tasks → export for Cursor → simple product MVP.

## Deliverables

- [x] HITL approval flow in Telegram
- [x] Planner mode task breakdown
- [x] Task export (Markdown / JSON)
- [x] Cursor rules aligned with product templates
- [x] Smoke delivery for one product type end-to-end

## v0.2 — Owner cost estimate on draft TZ

- [x] Deterministic delivery estimate when a new `draft_tz` is persisted (`WAITING_OWNER`)
- [x] Estimate stored on Artifact `payload.estimate` (no extra table)
- [x] Owner Telegram DM (RU) with cost, hours, rationale, `/review`
- [x] `/review` shows the estimate; Mini App / API ingest also notifies
- [x] Rate/currency via `ASF_ESTIMATE_HOURLY_RATE` / `ASF_ESTIMATE_CURRENCY` (default 3000 RUB)

## Notes

Deterministic HITL (`core/hitl.py`) gates on `WAITING_OWNER`; only `approve` → `READY` unlocks Planner. When a new `draft_tz` is first persisted, `core/estimate.py` writes a heuristic cost onto the Artifact payload and `integrations/telegram/notify.py` DMs the owner (Mini App / API ingest included, not only the bot). Planner (`core/planner.py`) writes DB `tasks` + KG Task entities from product-type templates; LLM stub annotates via `/coordinator/planner`. Export: `GET /export/tasks?format=markdown|json`. Telegram owner commands: `/review`, `/approve`, `/changes`, `/reject`, `/plan`, `/export`. Cursor rule: `.cursor/rules/product-templates.mdc`.

Verified: `pytest` covers HITL approve/changes/reject/owner check, planner idempotency, markdown/JSON export, website end-to-end smoke, estimate math, and mocked owner notify on TZ ready.
