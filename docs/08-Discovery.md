# 08 — Discovery

| Field | Value |
|-------|-------|
| Status | Accepted |
| Version | 0.1 |
| Updated | 2026-07-30 |
| Owner | ASF Core |

## Purpose

Turn a customer idea into a draft specification with enough clarity for architecture and planning — adapted to the customer’s IT literacy.

## Channels

- Telegram text
- Telegram **voice** → Whisper STT → text (same pipeline)

## High-level FSM

```
PROJECT_CREATED
  → UNDERSTANDING_IDEA
  → BUSINESS_CONTEXT
  → USERS
  → FUNCTIONAL
  → NON_FUNCTIONAL
  → INTEGRATIONS
  → RISKS
  → REVIEW
  → READY_FOR_OWNER
```

Transitions may go backward when contradictions or gaps appear.

## Project statuses (runtime)

`NEW` → `INTERVIEW` → `ANALYZING` → `WAITING_CUSTOMER` → `WAITING_OWNER` → `READY` → `ARCHIVED`

## Readiness criteria (draft)

- No critical unknowns for the chosen product type
- MVP scope stated
- Architectural sufficiency (enough to plan simple delivery)
- No blocking contradictions (or escalated to owner)

## Output artifacts

Derived from Knowledge Graph:

- Vision / problem statement
- Requirements list
- Open questions
- Draft MVP scope
- Recommendations for owner review

## HITL

Owner receives draft TZ + gap list. Development planning starts only after approval.
