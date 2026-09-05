---
name: mvp-customer-pack
description: >-
  Stamp a generated customer MVP repo with slim AGENTS.md, DESIGN.md,
  security-review, anti-slop rules, and Spec Kit stubs. Use when the factory
  exports a product repo or when scaffolding Cursor-ready delivery for
  website, telegram_bot, rest_service, ai_automation, or mobile_native.
---

# Customer MVP agent pack

Audience **B**: the repo Cursor will implement *for the customer*, not ASF itself.

Do not copy the factory’s full `.cursor/skills` tree. Stamp a thin pack.

## Files to stamp

| Destination in customer repo | Source |
|------------------------------|--------|
| `AGENTS.md` | `templates/customer-agents/AGENTS.md` |
| `DESIGN.md` | `templates/DESIGN.md` (fill tokens from TZ) |
| `.cursor/rules/design-anti-slop.mdc` | factory rule (same globs, retarget paths) |
| `.cursor/rules/security-basics.mdc` | factory rule (retarget to customer `app/` if needed) |
| `.cursor/skills/security-review/SKILL.md` | factory skill (drop ASF-only paths) |
| `.cursor/skills/anti-slop-design/SKILL.md` | factory skill |
| `.cursor/skills/human-interview/SKILL.md` | factory skill (optional; if the MVP interviews users) |
| `.cursor/skills/project-memory/SKILL.md` | factory skill |
| `.cursor/skills/autodoc/SKILL.md` | factory skill (optional) |
| `spec.md` `plan.md` `tasks.md` | `templates/speckit/` via `mvp-speckit-export` |

## Fill from ASF KG (do not invent)

- Product type + `templates/<product_type>.md`
- Approved TZ excerpts → `spec.md` and `DESIGN.md` tokens
- Planner tasks → `tasks.md`
- Out of scope / risks → assumption ledger in customer `AGENTS.md`

## Do not stamp

- ASF epic files, DEC-* factory ADRs, Discovery FSM, Telegram owner console
- Redis/Neo4j/multi-agent runtimes
- Always-on mega rules
- Secrets, tokens, customer PII

## After stamp

Customer `AGENTS.md` is the router. Factory `asf-mvp` stays in *this* repo only.
