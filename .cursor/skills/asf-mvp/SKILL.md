---
name: asf-mvp
description: >-
  Implement AI Software Factory (ASF) MVP epics in this repo: Telegram Discovery,
  Whisper STT, PostgreSQL knowledge graph, AI Coordinator modes, HITL TZ gate,
  Cursor task export, Telegram Mini App, and owner TZ console. Use when coding
  ASF features, advancing EPIC-01..06, or deciding MVP vs Future scope.
---

# ASF MVP Implementation Skill

## When to use

- Implementing or reviewing work against `tasks/EPIC-*.md`
- Changing Discovery, KG, Telegram, STT, Coordinator, planner export, Mini App, console
- Unsure whether a feature belongs in MVP or `backlog/Future.md`

## Mandatory reads (short)

1. `AGENTS.md` (router — do not paste other skills here)
2. Active epic in `tasks/`
3. `docs/01-MVP-Scope.md`, `docs/02-Architecture.md`
4. Relevant ADR in `decisions/`

## Implementation loop

1. **Pick one epic checkbox** — smallest vertical slice that ends in a test.
2. **Respect boundaries**
   - HTTP: `apps/api`
   - Domain/services: `core`
   - Graph: `knowledge`
   - Interview FSM: `discovery`
   - Telegram/STT: `integrations/*`
3. **Providers stay swappable** — STT/LLM behind interfaces; default stub in tests.
4. **Schema change** → Alembic revision + update `schemas/` if contract changed.
5. **Structured AI I/O** → align with `prompts/` + `schemas/`; Discovery turns are LLM-driven per DEC-008, but KG writes, coverage, and quality gates stay in code.
6. **HITL** — draft TZ and hard forks stop for owner; do not auto-approve.
7. **Verify** — `pytest`; manual smoke from `docs/13-Dev-Setup.md` when touching I/O.

## MVP allow / deny

**Allow:** Telegram text+voice, Whisper STT, Coordinator modes, entity/relation KG, draft TZ artifacts, owner review, task breakdown/export, MVP Factory + Intervention Queue (DEC-013), product templates (`website`, `telegram_bot`, `rest_service`, `ai_automation`, `mobile_native`), owner TZ graph console (DEC-007).

**Deny without new ADR:** Redis, Neo4j, event sourcing, multi-agent OS processes, customer web review portal, sales/finance agents, second template repo, vendoring Spec Kit or giant external agent packs.

## Companion skills (load only if needed)

| Need | Skill |
|------|--------|
| Interview tone | `human-interview` |
| UI look | `anti-slop-design` |
| Context budget | `token-economy` |
| Learned sections | `project-memory` |
| Docs/RU sync | `autodoc` |
| Auth / Telegram / secrets | `security-review` |
| Customer repo stamp | `mvp-customer-pack` |
| Spec Kit files | `mvp-speckit-export` |

## Mode map (Coordinator)

| Mode | Package focus | Prompt |
|------|---------------|--------|
| discovery | `discovery/`, messages | `prompts/discovery-interview.md` |
| reviewer | gaps / contradictions | `prompts/reviewer.md` |
| architect | sufficient simple design | `prompts/architect.md` |
| planner | tasks export | `prompts/planner.md` |
| developer / qa | later via Cursor export | rules + tasks |

## Definition of done

- Epic checkbox can be marked done
- Tests cover happy path + one failure/edge
- No contradiction with Accepted ADRs
- Future ideas filed in `backlog/`, not coded
