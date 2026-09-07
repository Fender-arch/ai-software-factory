# DEC-012 — Client market estimate and narrative report

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2026-09-05 |
| Updated | 2026-09-07 |
| Supersedes | — (does **not** replace the owner heuristic in [EPIC-04](../tasks/EPIC-04-MVP-Generation.md)) |

## Context

After the owner reviews a draft TZ, the customer still needs a **plain-language quote** and a “why it costs this much” report before anyone starts building the MVP. The existing owner aid (`core/estimate.py`, Artifact `payload.estimate`, HITL Telegram DM) is a studio heuristic. It must stay. Treating it as a customer price would mix an internal aid with a commercial conversation.

Public rate bands (RU/CIS freelance, Eastern Europe contractors) and an LLM-written narrative are enough for MVP. A legal offer, live scraping of job boards, or a finance agent are not.

## Decision

Ship a **dual estimate**:

| Layer | Audience | How | Stored on |
|-------|----------|-----|-----------|
| Owner heuristic | Studio HITL | Deterministic hours × `ASF_ESTIMATE_HOURLY_RATE` | `payload.estimate` |
| Client market estimate | Customer | Work package from KG + documented market bands + LLM (or template) narrative | `payload.client_estimate` + `payload.client_estimate_report` |

Rules:

1. Owner heuristic is **not** replaced and is **not** shown as the customer price.
2. After owner `approve` on `WAITING_OWNER`, the orchestrator **computes and stores** the client estimate and moves the project to `WAITING_CLIENT_ESTIMATE`. Planner / MVP build stay locked. The customer is **not** notified yet.
3. The owner sets the customer-facing price in the console: hours × hourly rate × (1 − discount%). Saving rate/discount is the approved quote. The AI market fork stays in the rationale for the studio.
4. The owner sends **TZ + estimate** as one package from the console (`POST /console/api/projects/{id}/send-tz-estimate`): editable caption + two documents. Only then is `quote_status=sent` and the Mini App card visible (`package_visible`).
5. The customer **confirms** → `READY` (Planner may run) or **rejects** with at least one comment on TZ or estimate. Reject stays in `WAITING_CLIENT_ESTIMATE` (negotiation, no Discovery interviewer) rather than bouncing to interview `WAITING_CUSTOMER`.
6. Sources are logged on the payload (`kind`: `config` or `fetched`). Do not invent labels such as “Source: Admin analytics”. Optional HTTP fetch is allowlisted HTTPS only (no customer-supplied URLs).
7. Copy and the report include a **disclaimer**: this is a market orientation for scope agreement, not a legal offer and not an invoice.
8. No Redis, Neo4j, extra microservice, or new table. JSONB on the existing `draft_tz` Artifact is enough (`quote_status`, `package_events`, rate, discount).
9. LLM writes the Russian narrative when a provider is configured; stub / failure uses a deterministic template built from the same numbers.

## Consequences

- HITL `approve` no longer jumps straight to `READY` and no longer auto-DMs the quote to the customer.
- Mini App shows the package card only after console send: confirm / reject + comments on TZ and estimate.
- Telegram notifies the owner when the customer decides; the owner replies from the console without Discovery LLM.
- Sales/finance agents stay in `backlog/Future.md`; this is owner-operated commercial send, not an agent.
