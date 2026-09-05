# AGENTS.md — ASF agent router

Read this first. Load **only** the skill that matches the current task.
Do not dump skill catalogs, full docs, or template libraries into context.

Two audiences:

| Audience | Start here |
|----------|------------|
| **A — developing ASF** | This file + `.cursor/skills/asf-mvp/SKILL.md` + active `tasks/EPIC-*.md` |
| **B — customer MVP repo** | Stamp `templates/customer-agents/AGENTS.md` via `.cursor/skills/mvp-customer-pack` |

## Source of truth (in order)

1. `decisions/DEC-*.md` (Accepted ADRs win conflicts)
2. `docs/01-MVP-Scope.md` + `docs/02-Architecture.md`
3. Other `docs/`, `schemas/`, `prompts/`, `templates/`
4. `backlog/Future.md` — do **not** implement unless a new ADR accepts it
5. Raw chat archives (e.g. UNI4IT `Arch/gpt.md`) are **not** truth

## Hard constraints

- Modular monolith: `apps/` · `core/` · `knowledge/` · `discovery/` · `integrations/`
- One AI Coordinator with **modes**, not a swarm of agent processes
- Knowledge Graph = PostgreSQL `entity` + `relation` (no Neo4j)
- No Redis in MVP
- Telegram + Whisper STT are in MVP
- Product types: `website` | `telegram_bot` | `rest_service` | `ai_automation` | `mobile_native` (DEC-010)
- HITL gate after draft TZ; escalate instead of guessing
- Token economy: always-on rules stay tiny; details live in skills; no catalog dumps
- Secrets never go in this file’s Learned sections

## Skill router (on demand)

Match the task, then **read that one skill**. Do not preload the rest.

| When | Skill |
|------|--------|
| Implementing ASF epics / platform code | `.cursor/skills/asf-mvp/SKILL.md` |
| Discovery interview tone / one-question consultant | `.cursor/skills/human-interview/SKILL.md` |
| UI / CSS / Mini App / console look | `.cursor/skills/anti-slop-design/SKILL.md` |
| Writing rules, skills, prompts, AGENTS.md | `.cursor/skills/token-economy/SKILL.md` |
| Durable facts / session end memory | `.cursor/skills/project-memory/SKILL.md` |
| Docs drifted after code or ADR change | `.cursor/skills/autodoc/SKILL.md` |
| Auth, API, Telegram, secrets, Mini App initData | `.cursor/skills/security-review/SKILL.md` |
| Stamping a generated customer repo | `.cursor/skills/mvp-customer-pack/SKILL.md` |
| Mapping KG / TZ → Spec Kit files | `.cursor/skills/mvp-speckit-export/SKILL.md` |

Map and rationale: `docs/12-Agent-Toolkit.md`. Adopted / rejected patterns: `decisions/DEC-009-Agent-Toolkit-Reuse.md`.

## Rules

- Always-on (keep thin): `.cursor/rules/asf.mdc`
- Globs only: python-backend, discovery-kg, integrations, product-templates, docs-ru-sync, design-anti-slop, security-basics, miniapp-ux

## Current delivery target (ASF)

Implement unfinished checkboxes in:

1. `tasks/EPIC-01-Infrastructure.md`
2. `tasks/EPIC-02-Discovery.md`
3. `tasks/EPIC-03-Knowledge-Core.md`
4. `tasks/EPIC-04-MVP-Generation.md`
5. `tasks/EPIC-05-Telegram-Mini-App.md`
6. `tasks/EPIC-06-Owner-TZ-Console.md`

## Definition of done (any task)

- Code matches package boundaries
- Alembic migration if schema changed
- Tests for new behavior (`pytest`)
- Docs/ADR updated only if a decision changed (`autodoc` + `docs/ru` mirror)
- No Future-scope creep

## Learned User Preferences

(none yet — `project-memory` appends durable preferences here; never secrets)

## Learned Workspace Facts

(none yet — `project-memory` appends durable repo facts here; never secrets)
