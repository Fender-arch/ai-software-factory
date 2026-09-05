# 02 — Architecture

| Field | Value |
|-------|-------|
| Status | Accepted |
| Version | 0.4 |
| Updated | 2026-09-05 |
| Owner | ASF Core |

## Style

**Modular monolith.** One deployable API process today; clear package boundaries for future extraction. Customer UI is a Telegram Mini App served alongside Bot API integration.

```
Telegram bot DM (RU onboarding | notifications)
        │ Menu / WebApp
        ▼
Telegram Mini App (fullscreen) ── text | voice
        │
   Whisper STT ──┐
                 ▼
            FastAPI (Orchestrator)
                 │
        ┌────────┼────────┐
        ▼        ▼        ▼
 AI Coordinator   KG     Tasks
   (modes)     (Postgres)
        │
   Artifacts (Markdown, derived)
        │
   Owner HITL (bot) → Planner → Cursor → Product MVP
        │
   Owner TZ console (`/console/`) ← KG view (DEC-007)
```

## Components

| Component | Responsibility |
|-----------|----------------|
| Orchestrator | Deterministic workflow, project state, who runs next — **not an LLM** |
| AI Coordinator | Single worker with modes: Discovery, Reviewer, Architect, Planner, Developer, QA |
| Knowledge Graph | Logical SoT: entities + relations in PostgreSQL |
| STT | Voice → text (Whisper); then same path as text messages |
| Telegram Mini App | Primary customer UI: home actions, project workspace; client Experience Layer (DEC-011) |
| Telegram bot | Entry, notifications; owner HITL commands in MVP |
| Owner TZ console | Internal graph of requirements + status/links (DEC-007); not customer UI |
| Artifact generator | Markdown derived from graph (TZ, decisions, backlog export) |
| Cursor executor | External coding agent; ASF prepares context and tasks |

## Agent model

Agents are **modes / skills**, not always-on personas chatting with each other.

Cycle per invocation:

1. Read bounded context (built for the mode)
2. Analyze
3. Write structured result to KG / DB
4. Publish outcome (status / event-like record)
5. Stop

No free-form multi-agent dialogue loops.

## Human in the loop

- Mandatory gate after draft specification
- `HumanDecisionRequired` when confidence is low, contradictions exist, or business choice is required
- Task status `WAITING_USER`

## Language

- Customer channel (Mini App + bot copy): **Russian**
- Canonical storage & agent reasoning: English (Language Normalizer as **infrastructure**, not a workflow agent)
- Localized artifacts may be generated for the customer

## Events

MVP uses **task/project statuses** in PostgreSQL. A richer **server** event bus may appear later without changing the domain model. Conceptual events: `ProjectCreated`, `MessageReceived`, `DiscoveryReady`, `HumanDecisionRequired`, `TaskCompleted`. The Mini App also has a **client-only** UX event bus for the mascot (DEC-011) — not Redis, not event sourcing.

## Package layout

See [04-Repository-Structure.md](04-Repository-Structure.md). Customer UX: [14-Telegram-Customer-UX.md](14-Telegram-Customer-UX.md). Owner TZ console: [15-Owner-TZ-Console.md](15-Owner-TZ-Console.md).
