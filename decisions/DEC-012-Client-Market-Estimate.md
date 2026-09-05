# DEC-012 — Client market estimate and narrative report

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2026-09-05 |
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
2. After owner `approve` on `WAITING_OWNER`, the orchestrator computes the client estimate and moves the project to `WAITING_CLIENT_ESTIMATE`. Planner / MVP build stay locked.
3. The customer sees the quote and report in the Mini App and either **confirms** → `READY` (Planner may run) or **asks to discuss** → `WAITING_CUSTOMER`.
4. Sources are logged on the payload (`kind`: `config` or `fetched`). Do not invent labels such as “Source: Admin analytics”. Optional HTTP fetch is allowlisted HTTPS only (no customer-supplied URLs).
5. Copy and the report include a **disclaimer**: this is a market orientation for scope agreement, not a legal offer and not an invoice.
6. No Redis, Neo4j, extra microservice, or new table. JSONB on the existing `draft_tz` Artifact is enough.
7. LLM writes the Russian narrative when a provider is configured; stub / failure uses a deterministic template built from the same numbers.

## Consequences

- HITL `approve` no longer jumps straight to `READY`.
- Mini App gains a compact estimate card (confirm / discuss). Owner console shows both estimates side by side.
- Telegram notifies the customer when the quote is ready and the owner when the customer confirms or wants to discuss.
- Full MVP factory / Cursor interventions remain a later stage. Sales/finance agents stay in `backlog/Future.md`.
