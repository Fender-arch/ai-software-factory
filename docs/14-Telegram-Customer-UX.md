# 14 — Telegram Customer UX

| Field | Value |
|-------|-------|
| Status | Accepted |
| Version | 0.4 |
| Updated | 2026-08-25 |
| Owner | ASF Core |

ADR: [DEC-006](../decisions/DEC-006-Telegram-Mini-App.md)

## Goal

All customer interaction with ASF happens in a **fullscreen Telegram Mini App** (Russian UI). The bot DM is entry + notifications only.

## Surfaces

| Surface | Role |
|---------|------|
| Bot DM | `/start` onboarding (RU), Menu Button / WebApp button, push notifications |
| Mini App (fullscreen) | Home actions, project list, project workspace (Discovery / change / implementation feedback) |
| Owner HITL (bot) | `/review`, `/approve`, `/changes`, `/reject`, `/plan`, `/export` (MVP) |

## Why not a separate Telegram chat per project

A bot has **one** private chat with a user. Bot API cannot open a second DM “for this project”.

**Project chat** in ASF means: Mini App **project workspace** (thread UI bound to `project_id`). Optional Telegram forum topics / multi-chat layouts are Future.

## Home (after onboarding)

Short explanation: idea → Discovery → draft TZ → owner review → tasks → simple MVP.

Then three actions (Russian labels in product UI):

1. **Создать проект** (Create project)
2. **Изменить проект** (Change project)
3. **Замечания к реализации** (Implementation feedback)

### Create project

1. Create `project` for this Telegram user.
2. Open that project’s workspace in the Mini App.
3. Run Discovery (text, **choice chips**, and/or voice → STT → same ingest as today). Interview covers TZ sections until the customer pauses, hands remaining items to the developer, or confirms «готово» after coverage and wrap-up (extra notes, budget figure, attached brief). The workspace shows a **progress bar** (gray track, green fill) for requirements gathering; `done/total` is recomputed after every answer if the outline grows (extra modules, clarify, wrap-up). After send, the workspace offers a download of the same draft TZ.
4. Bot may notify when owner review is needed or when the customer must answer.

### Change project

1. Show the user’s project list.
2. User picks a project.
3. Open workspace in **change** mode: clarifications and edits → KG update, gap / contradiction checks, possible re-open of Discovery stages or owner escalation.

### Implementation feedback

1. Show projects the user may comment on (after delivery / after they reviewed the MVP).
2. User picks a project and submits feedback (text/voice).
3. System classifies: defect / change request / new requirement.
4. Check against approved TZ / KG; on contradiction or blocking ambiguity → `HumanDecisionRequired` / owner path.
5. Persist as structured entities/relations (not free-form chat loss).

## Language

- Customer UI and bot copy: **Russian**
- Canonical KG storage and agent reasoning: **English** (Language Normalizer as infrastructure)

## Transitional bot commands

Until Mini App ships, customer may still use `/new`, `/use`, text/voice in the bot DM. Those paths must remain compatible with the same `core.services` ingest. Prefer Mini App once available.

## Notifications (bot DM)

Examples: Discovery needs an answer; draft TZ sent to owner; owner requested changes; MVP / export ready. Deep-link or WebApp button should reopen the relevant Mini App project workspace when possible.

## Out of scope here

- Owner portal inside Mini App (later)
- Forum topics / separate Telegram chats per project (`backlog/Future.md`)
- Web Human Review Portal (already Future; owner TZ graph console is DEC-007, not a customer portal)
