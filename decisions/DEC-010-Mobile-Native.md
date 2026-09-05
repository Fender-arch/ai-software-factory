# DEC-010 — Product type `mobile_native` in scope

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2026-09-05 |
| Supersedes | Product-type list in [DEC-003](DEC-003-MVP-Scope.md) (that ADR’s four types remain; this **adds** one) |

## Context

DEC-003 locked factory output to `website`, `telegram_bot`, `rest_service`, and `ai_automation`. Customers still ask for Android/iOS apps. Discovery already surfaced extra chips when they said “мобильное приложение”, but the type was mapped away or treated as out of factory scope. That produced worse TZs than an honest native slice.

## Decision

`mobile_native` is a first-class MVP product type.

- Discovery template: `templates/mobile_native.md`
- Typical v1: **one platform-first** native or cross-platform binary, one happy path, store listing optional
- Both iOS and Android in v1, payments, Super Apps, and a companion backend-as-a-second-product still escalate
- Agent allowlists (`AGENTS.md`, `asf-mvp`, `asf.mdc`, planner, estimate, schema enum) include the type
- “Mobile-friendly website” remains `website`. “Достаточно бота” remains `telegram_bot`

## Consequences

- Outline modules for platforms and distribution apply when the type is locked.
- Planner emits native slices instead of falling back to a website scaffold.
- Estimate base hours are higher than a brochure site (see `core/estimate.py`).
- Complex native programs (offline-first sync meshes, Wear/TV) stay Future / owner escalate.
