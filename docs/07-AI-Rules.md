# 07 — AI Rules

| Field | Value |
|-------|-------|
| Status | Accepted |
| Version | 0.1 |
| Updated | 2026-07-30 |
| Owner | ASF Core |

Rules for AI Coordinator modes and for Cursor when working in this repo.

## Hard rules

1. Read Foundation docs and `decisions/` before proposing architecture changes.
2. Do not reintroduce Future items into MVP without an Accepted ADR.
3. Prefer deterministic checks before LLM calls (schemas, coverage checklists).
4. Write structured outputs; never “chat forever” between modes.
5. Canonical English in stored knowledge; customer-facing text may be localized.
6. Stop and raise `HumanDecisionRequired` on blocking ambiguity.
7. Cursor implements tasks; it does not redefine product scope silently.

## Cost pyramid (summary)

| Level | Use |
|-------|-----|
| 0 Deterministic | validation, formatting, status transitions |
| 1 Rules | coverage checklists, product-type templates |
| 2 Lightweight LLM | classification, extraction drafts |
| 3 Standard LLM | interview, writing TZ |
| 4 Premium | contradiction / readiness review |

## Modes

`discovery` | `reviewer` | `architect` | `planner` | `developer` | `qa`

Each mode has a prompt in `prompts/` and a deterministic exit checklist.
