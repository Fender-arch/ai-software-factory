# 01 — MVP Scope

| Field | Value |
|-------|-------|
| Status | Accepted |
| Version | 0.3 |
| Updated | 2026-08-16 |
| Owner | ASF Core |

## Goal of MVP

Get the first real customer flow working:

1. Customer uses Telegram (**Mini App** primary; bot DM for onboarding/notifications) — text or **voice**
2. Platform collects requirements (Discovery) in a per-project Mini App workspace
3. Draft specification is produced
4. Owner reviews and approves (HITL)
5. Work is broken into tasks
6. Cursor can implement a **simple** MVP from those tasks

Customer home (Russian UI): **create project**, **change project**, **implementation feedback**. Details: [14-Telegram-Customer-UX.md](14-Telegram-Customer-UX.md), [DEC-006](../decisions/DEC-006-Telegram-Mini-App.md).

Definition of done for the *platform* MVP: Telegram Mini App → quality TZ → HITL → tasks → Cursor can build a simple product — not “perfect autonomous company”.

## In scope

| Area | Details |
|------|---------|
| Channels | Telegram Mini App (fullscreen customer UI) + bot DM (onboarding, notifications); **voice via Whisper STT** |
| Customer UX | RU onboarding; create / change / implementation-feedback; project workspace in Mini App |
| Discovery | Adaptive questioning, draft TZ / artifacts |
| Memory | Logical Knowledge Graph in PostgreSQL (`entity`, `relation`, JSONB) |
| AI | One **AI Coordinator** with modes (not many OS processes) |
| HITL | Spec review in owner bot path; `HumanDecisionRequired` on forks |
| Owner TZ console | Internal graph of requirements (`/console/`); [DEC-007](../decisions/DEC-007-Owner-TZ-Console.md), [15-Owner-TZ-Console.md](15-Owner-TZ-Console.md) |
| Product types | `website`, `telegram_bot`, `rest_service`, `ai_automation` |
| Delivery | Task export + Cursor rules; human/Cursor execution |
| Stack | FastAPI, PostgreSQL, Alembic, Docker Compose, Mini App frontend, owner console |
| Transitional | Command-bot customer paths (`/new`, `/use`, …) until Mini App ships |

## Out of scope (ASF Future)

- Redis / dedicated queue brokers (use Postgres task statuses in MVP)
- Neo4j / GraphDB
- Event sourcing, DSL, Rule Engine, Architecture Compiler
- Full Knowledge Kernel / Explainability API / Evolution Engine
- Multi-agent runtime (separate agent processes)
- Sales / finance / C-level agent org chart
- Web Human Review Portal for **customers** (Telegram Mini App + owner bot HITL stay the customer/HITL paths; owner TZ graph console is DEC-007, not this portal)
- Second repository `asf-template` (use in-repo `templates/`)
- Separate Telegram DM / forum topic per project
- Full owner portal inside Mini App

## MVP filter for new ideas

Before adding anything to MVP, answer:

1. Does it help the first customer?
2. Does it simplify delivery?
3. Does it keep architecture simple?

If no → `backlog/Future.md`.

## Target product complexity

MVP factory targets **simple** specs: brochure sites, bots, small APIs, light automations — not multi-tenant SaaS or complex distributed systems.
