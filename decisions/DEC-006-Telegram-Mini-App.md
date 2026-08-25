# DEC-006 — Telegram Mini App as customer UI

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2026-07-31 |

## Context

Command-only Telegram UX (`/new`, `/use`, free-text in one DM) does not match the intended customer journey: Russian onboarding, clear home actions (create / change / implementation feedback), and a dedicated communication space per project. Customers also asked for a fullscreen UI rather than chat commands.

Telegram Bot API does not create a separate private chat per project with the same bot. Treating “project chat” as a second Telegram DM is therefore not feasible.

## Decision

1. **Primary customer UI** is a fullscreen **Telegram Mini App** opened from the main ASF bot (Menu Button / WebApp keyboard).
2. The **bot DM** is for short Russian onboarding, launching the Mini App, and push notifications (need reply, draft TZ ready, MVP ready). It is not the main Discovery workspace.
3. A **project workspace** lives inside the Mini App (message thread + `project_id` context). This is the product equivalent of a “project chat”.
4. **Owner HITL** stays in the bot for MVP (`/review`, `/approve`, …). Moving owner flows into the Mini App is a later step.
5. Command-only customer handlers remain **transitional** until the Mini App ships.

Related: [DEC-003](DEC-003-MVP-Scope.md), [docs/14-Telegram-Customer-UX.md](../docs/14-Telegram-Customer-UX.md).

## Consequences

- Stack: Mini App frontend + Bot API (aiogram) + FastAPI backend.
- Forum topics / separate Telegram chats per project → `backlog/Future.md`.
- Customer-facing copy is Russian; KG and agent reasoning stay English per Architecture.
