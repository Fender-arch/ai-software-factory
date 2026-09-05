# DEC-013 — MVP Factory and Intervention Queue

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2026-09-05 |

## Context

After owner HITL approve (and later, if present, client estimate confirm) the studio must turn the approved TZ into a simple product MVP. Secrets and deploy facts cannot be guessed: Telegram bot tokens, DNS, servers, passwords, Apple/Google store access. Putting those in KG `entity.payload` or the draft TZ would leak them into exports and history. A multi-agent swarm to “chase” missing values would fight [DEC-002](DEC-002-AI-Coordinator.md).

Client market estimate ([DEC-012](DEC-012-Client-Market-Estimate.md)) is in `main`. The factory starts only after customer confirm (`READY`). If a draft has `payload.client_estimate` that is not `confirmed`, the job waits.

## Decision

1. **MVP slice.** Factory builds from the approved cut: explicit `payload.in_mvp`, else `scope_in` / `scope=in`, else `priority=must`, else remaining active requirements. The flag is stored on Requirement payload/status — not a new graph type.
2. **BuildJob.** One job per launch (`core` table, not Redis). Statuses: `queued` → `preparing` → `waiting_intervention` → `running` → `ready_for_client` → `sent_to_client` (or `failed` / `cancelled`). Project status stays `READY` so Discovery/HITL are unchanged.
3. **Cursor executor.** `integrations/cursor`: HTTP Cloud Agent when `CURSOR_API_KEY` is set; otherwise stub + export/deep-link. Architecture is ready; no agent swarm.
4. **Intervention Queue.** Anything the factory must not guess is an `Intervention` (text or secret, TTL). Owner answers in the Telegram owner bot or console. **Secrets** are sealed (`core/secrets_box.py`, `ASF_INTERVENTION_KEY`) and never written to KG/TZ/logs/plaintext job payload.
5. **Client review.** When the job is `ready_for_client`, owner sends a status + notification. Full customer feedback loop stays the existing Mini App path (skeleton).
6. **Client confirm gate.** Project must be `READY` (owner approve → `WAITING_CLIENT_ESTIMATE` → customer confirm). If `payload.client_estimate` exists and is not `confirmed`, the factory waits.

**Rejected:** Redis/Neo4j queues, plaintext secrets on entities, guessing tokens/DNS, extra OS agent processes, vendoring Spec Kit (use `templates/speckit` + `mvp-speckit-export`).

## Consequences

- Alembic `0004_mvp_factory` (after `0003_waiting_client_estimate`): `build_jobs`, `interventions`.
- Owner bot: `/mvp`, `/queue`, `/answer`, `/secret`, `/sendreview` (RU copy).
- Console: Create MVP, queue, send-to-client on the project sheet.
- EPIC-04 tracks the factory slice; Discovery contracts stay intact.
