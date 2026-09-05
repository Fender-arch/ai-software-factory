# AGENTS.md — customer MVP router

You are implementing **this** product repo, not the AI Software Factory.

Load **one** matching skill. Do not dump catalogs or factory epics into context.

## Product lock

- Type: `{{product_type}}`  <!-- website | telegram_bot | rest_service | ai_automation | mobile_native -->
- Template ceiling: `templates/{{product_type}}.md` (copied from ASF) or the TZ “Typical MVP”
- Out of scope stays out of scope. Payments / multi-tenant / extra platforms → stop for the owner.

## Source of truth

1. `spec.md` (Spec Kit) + approved TZ excerpts
2. `DESIGN.md` before any UI
3. `plan.md` / `tasks.md`
4. This file’s Learned sections

## Skill router

| When | Skill |
|------|--------|
| Visual UI | `.cursor/skills/anti-slop-design/SKILL.md` |
| Auth, secrets, Telegram, uploads | `.cursor/skills/security-review/SKILL.md` |
| Interviewing an end user | `.cursor/skills/human-interview/SKILL.md` |
| Session-end durable facts | `.cursor/skills/project-memory/SKILL.md` |
| Docs drifted | `.cursor/skills/autodoc/SKILL.md` |

## Hard rules

- Match exported task acceptance criteria; do not expand scope.
- Require `DESIGN.md` before CSS/HTML/SwiftUI/Compose chrome.
- No default Inter + purple/indigo Tailwind look.
- Never commit secrets or write them into Learned sections.
- Prefer small testable slices.

## Definition of done

- Task acceptance criteria pass
- Tests for new behavior
- `DESIGN.md` respected if UI changed
- No silent product-type change

## Learned User Preferences

(none yet)

## Learned Workspace Facts

(none yet)
