# 02 — Architecture

| Field | Value |
|-------|-------|
| Status | Accepted |
| Version | 0.1 |
| Updated | 2026-07-30 |
| Owner | ASF Core |

## Style

**Modular monolith.** One deployable process today; clear package boundaries for future extraction.

```
Telegram (text | voice)
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
   Owner HITL → Planner → Cursor → Product MVP
```

## Components

| Component | Responsibility |
|-----------|----------------|
| Orchestrator | Deterministic workflow, project state, who runs next — **not an LLM** |
| AI Coordinator | Single worker with modes: Discovery, Reviewer, Architect, Planner, Developer, QA |
| Knowledge Graph | Logical SoT: entities + relations in PostgreSQL |
| STT | Voice → text (Whisper); then same path as text messages |
| Telegram integration | Customer & owner channel |
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

- Customer channel: Russian (and whatever the customer uses)
- Canonical storage & agent reasoning: English (Language Normalizer as **infrastructure**, not a workflow agent)
- Localized artifacts may be generated for the customer

## Events

MVP uses **task/project statuses** in PostgreSQL. A richer event bus may appear later without changing the domain model. Conceptual events: `ProjectCreated`, `MessageReceived`, `DiscoveryReady`, `HumanDecisionRequired`, `TaskCompleted`.

## Package layout

See [04-Repository-Structure.md](04-Repository-Structure.md).
