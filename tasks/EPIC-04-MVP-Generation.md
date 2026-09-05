# EPIC-04 — MVP Generation

| Field | Value |
|-------|-------|
| Status | Done |
| Version | 0.3 |

## Goal

Owner-approved TZ → Planner tasks → export for Cursor → **MVP Factory** (BuildJob + Intervention Queue) → simple product MVP.

## Deliverables

- [x] HITL approval flow in Telegram
- [x] Planner mode task breakdown
- [x] Task export (Markdown / JSON)
- [x] Cursor rules aligned with product templates
- [x] Smoke delivery for one product type end-to-end
- [x] MVP Factory: Create MVP from approved `in_mvp` / must / scope_in slice
- [x] Spec Kit brief (`templates/speckit`) + task export on the BuildJob
- [x] Cursor executor (Cloud Agent API if env set, otherwise stub + deep-link)
- [x] Intervention Queue (text/secret, TTL, Telegram owner + console; secrets not in KG/TZ)
- [x] Send-to-client review status + notification (feedback loop skeleton)

## v0.2 — Owner cost estimate on draft TZ

- [x] Deterministic delivery estimate when a new `draft_tz` is persisted (`WAITING_OWNER`)
- [x] Estimate stored on Artifact `payload.estimate` (no extra table)
- [x] Owner Telegram DM (RU) with cost, hours, rationale, `/review`
- [x] `/review` shows the estimate; Mini App / API ingest also notifies
- [x] Rate/currency via `ASF_ESTIMATE_HOURLY_RATE` / `ASF_ESTIMATE_CURRENCY` (default 3000 RUB)
- [x] Customer Discovery budget envelope included in the owner rationale (chip is not the quote)

## v0.3 — MVP Factory + Intervention Queue (DEC-013)

- [x] Gate: project `READY` after owner approve; hook waits for `client_estimate.confirmed` only if that artifact exists (PR #5 not required)
- [x] Tables `build_jobs` / `interventions` (Alembic `0003_mvp_factory`)
- [x] Owner bot: `/mvp` `/queue` `/answer` `/secret` `/sendreview` (RU; secrets not echoed)
- [x] Console: «Создать MVP», очередь, «Отправить клиенту на review»
- [x] pytest stubs (no real Cursor API, no real secrets in assertions)

## Notes

Deterministic HITL (`core/hitl.py`) gates on `WAITING_OWNER`; only `approve` → `READY` unlocks Planner **and** the factory. When a new `draft_tz` is first persisted, `core/estimate.py` writes a heuristic cost onto the Artifact payload and `integrations/telegram/notify.py` DMs the owner (Mini App / API ingest included, not only the bot). Planner (`core/planner.py`) writes DB `tasks` + KG Task entities from product-type templates; LLM stub annotates via `/coordinator/planner`. Export: `GET /export/tasks?format=markdown|json`. Telegram owner commands: `/review`, `/approve`, `/changes`, `/reject`, `/plan`, `/export`, `/mvp`, `/queue`, `/answer`, `/secret`, `/sendreview`. Cursor rule: `.cursor/rules/product-templates.mdc`. Factory: `core/factory.py` + `integrations/cursor`.

Verified: `pytest` **138 passed** — HITL approve/changes/reject/owner check, planner idempotency, markdown/JSON export, website end-to-end smoke, estimate math, mocked owner notify on TZ ready, factory gate, `in_mvp` slice, sealed secrets, stub executor, send-to-client.
