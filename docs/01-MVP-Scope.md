# 01 — MVP Scope

| Field | Value |
|-------|-------|
| Status | Accepted |
| Version | 0.1 |
| Updated | 2026-07-30 |
| Owner | ASF Core |

## Goal of MVP

Get the first real customer flow working:

1. Customer creates a project in Telegram (text or **voice**)
2. Platform collects requirements (Discovery)
3. Draft specification is produced
4. Owner reviews and approves (HITL)
5. Work is broken into tasks
6. Cursor can implement a **simple** MVP from those tasks

Definition of done for the *platform* MVP: Telegram → quality TZ → HITL → tasks → Cursor can build a simple product — not “perfect autonomous company”.

## In scope

| Area | Details |
|------|---------|
| Channels | Telegram bot; **voice messages via Whisper STT** |
| Discovery | Adaptive questioning, draft TZ / artifacts |
| Memory | Logical Knowledge Graph in PostgreSQL (`entity`, `relation`, JSONB) |
| AI | One **AI Coordinator** with modes (not many OS processes) |
| HITL | Spec review; `HumanDecisionRequired` on forks |
| Product types | `website`, `telegram_bot`, `rest_service`, `ai_automation` |
| Delivery | Task export + Cursor rules; human/Cursor execution |
| Stack | FastAPI, PostgreSQL, Alembic, Docker Compose |

## Out of scope (ASF Future)

- Redis / dedicated queue brokers (use Postgres task statuses in MVP)
- Neo4j / GraphDB
- Event sourcing, DSL, Rule Engine, Architecture Compiler
- Full Knowledge Kernel / Explainability API / Evolution Engine
- Multi-agent runtime (separate agent processes)
- Sales / finance / C-level agent org chart
- Web Human Review Portal (Telegram + owner path is enough)
- Second repository `asf-template` (use in-repo `templates/`)

## MVP filter for new ideas

Before adding anything to MVP, answer:

1. Does it help the first customer?
2. Does it simplify delivery?
3. Does it keep architecture simple?

If no → `backlog/Future.md`.

## Target product complexity

MVP factory targets **simple** specs: brochure sites, bots, small APIs, light automations — not multi-tenant SaaS or complex distributed systems.
