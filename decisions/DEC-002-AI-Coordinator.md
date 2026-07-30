# DEC-002 — Single AI Coordinator with modes

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2026-07-30 |

## Context

Multi-agent swarms are hard to debug and expensive. Roles still matter.

## Decision

One AI Coordinator process/service with modes: Discovery, Reviewer, Architect, Planner, Developer, QA. Modes may become separate agents later without rewriting orchestration contracts.

## Consequences

- Simpler runtime and logging
- Clear contracts via prompts + schemas
- No agent-to-agent free chat
