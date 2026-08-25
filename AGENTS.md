# AGENTS.md — how Cursor should work in ASF

Read this first in every implementation session.

## Source of truth (in order)

1. `decisions/DEC-*.md` (Accepted ADRs win conflicts)
2. `docs/01-MVP-Scope.md` + `docs/02-Architecture.md`
3. Other `docs/`, `schemas/`, `prompts/`, `templates/`
4. `backlog/Future.md` — do **not** implement unless a new ADR accepts it
5. Raw chat archives (e.g. UNI4IT `Arch/gpt.md`) are **not** truth

## Current delivery target

Implement epics in order:

1. `tasks/EPIC-01-Infrastructure.md`
2. `tasks/EPIC-02-Discovery.md`
3. `tasks/EPIC-03-Knowledge-Core.md`
4. `tasks/EPIC-04-MVP-Generation.md`
5. `tasks/EPIC-05-Telegram-Mini-App.md`
6. `tasks/EPIC-06-Owner-TZ-Console.md`

Before coding: open the epic, list unfinished checkboxes, implement only those.

## Architecture guardrails

- Modular monolith: `apps/` · `core/` · `knowledge/` · `discovery/` · `integrations/`
- One AI Coordinator with **modes**, not a swarm of agent processes
- Knowledge Graph = PostgreSQL `entity` + `relation` (no Neo4j)
- No Redis in MVP
- Telegram + Whisper STT are in MVP
- Product types only: `website` | `telegram_bot` | `rest_service` | `ai_automation`
- HITL gate after draft TZ; escalate instead of guessing

## Project toolkit

| Kind | Path |
|------|------|
| Rules | `.cursor/rules/` |
| Project skill | `.cursor/skills/asf-mvp/SKILL.md` |
| Skill map | `docs/12-Agent-Toolkit.md` |
| Dev setup | `docs/13-Dev-Setup.md` |

## Definition of done (any task)

- Code matches package boundaries
- Alembic migration if schema changed
- Tests for new behavior (`pytest`)
- Docs/ADR updated only if a decision changed
- No Future-scope creep
