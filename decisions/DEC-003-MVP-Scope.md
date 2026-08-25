# DEC-003 — MVP scope and product types

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2026-07-30 |

## Context

Need a factory that can handle simple commercial specs without building a full AI company org chart.

## Decision

MVP delivers customer Discovery via Telegram Mini App (see [DEC-006](DEC-006-Telegram-Mini-App.md)) → draft TZ → owner HITL → tasks → Cursor-ready export for product types:

- `website`
- `telegram_bot`
- `rest_service`
- `ai_automation`

Complex SaaS / multi-tenant / heavy integrations are out of MVP.

## Consequences

Templates in `templates/` guide Discovery and Architect modes. Over-scoped requests escalate to owner or are narrowed.
