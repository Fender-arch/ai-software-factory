# 12 — Agent Toolkit

| Field | Value |
|-------|-------|
| Status | Accepted |
| Version | 0.1 |
| Updated | 2026-07-31 |
| Owner | ASF Core |

What Cursor needs to implement the ASF MVP without re-deriving architecture from chat history.

## Already in this repo (required)

| Asset | Why |
|-------|-----|
| `AGENTS.md` | Session entrypoint + DoD |
| `docs/00–11` | Vision, scope, architecture, Discovery, KG |
| `docs/13-Dev-Setup.md` | Run / test / env |
| `decisions/` | Locked ADR choices |
| `tasks/EPIC-*` | Delivery slices |
| `prompts/` | Coordinator mode prompts |
| `schemas/` | Structured I/O contracts |
| `templates/` | Product-type Discovery hints |
| `.cursor/rules/` | Persistent constraints |
| `.cursor/skills/asf-mvp/` | How to implement the next epic |

## Cursor rules in this repo

| Rule | When |
|------|------|
| `asf.mdc` | Always — MVP freeze & package boundaries |
| `python-backend.mdc` | Python / FastAPI / SQLAlchemy / Alembic |
| `discovery-kg.mdc` | Discovery FSM, entities, relations, artifacts |
| `integrations.mdc` | Telegram + STT / Whisper |

## Personal / global skills (use when relevant)

These live outside the repo (`~/.cursor/skills/`). Activate on demand; do not copy wholesale into ASF.

| Skill | Use for ASF MVP |
|-------|-----------------|
| `project-development` | Pipeline shape, cost, structured stage handoffs |
| `multi-agent-patterns` | Confirm **Coordinator+modes** (not swarm); handoff design |
| `harness-engineering` | HITL gates, locked vs editable surfaces, durable logs |
| `tool-design` | LLM/tool contracts, mode JSON schemas, error recovery |
| `memory-systems` | KG as semantic memory; consolidation rules |
| `context-optimization` | Context builder: what each mode may see |
| `filesystem-context` | Artifact export / file-backed project views |
| `evaluation` | Discovery readiness / quality checklists |
| `long-horizon-prompting` | Hardening Discovery / Reviewer prompts |

**Usually not needed for MVP coding:** design/UI skills, slides, banner, latent-briefing, hosted-agents (unless Cursor CLI hosting is in scope later).

## Intentionally not added

| Temptation | Why skip |
|------------|----------|
| Full Architecture Bible / RFC dump | Already rejected for MVP |
| Copy of `gpt.md` into repo | Noise; decisions are distilled |
| Multi-agent runtime skill pack | Contradicts DEC-002 |
| Redis / GraphDB runbooks | Future |

## Minimum session checklist

1. Read `AGENTS.md`
2. Activate project skill `asf-mvp`
3. Open the current epic under `tasks/`
4. Touch only allowed packages
5. Run `pytest` before finishing
