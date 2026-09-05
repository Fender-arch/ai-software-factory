# 12 — Agent Toolkit

| Field | Value |
|-------|-------|
| Status | Accepted |
| Version | 0.5 |
| Updated | 2026-09-05 |
| Owner | ASF Core |

What Cursor needs to implement ASF (audience A) and to stamp customer MVP repos (audience B) without re-deriving architecture from chat history.

ADR: [DEC-009](../decisions/DEC-009-Agent-Toolkit-Reuse.md). Token-economy rules: `.cursor/skills/token-economy/SKILL.md`.

## Already in this repo (required)

| Asset | Why |
|-------|-----|
| `AGENTS.md` | **Router** — hard constraints, skill table, Learned placeholders |
| `docs/00–16` | Vision, scope, architecture, Discovery, KG, Mini App UX, owner TZ console, VPS deploy |
| `docs/13-Dev-Setup.md` | Run / test / env |
| `docs/16-VPS-Deploy.md` | VPS next to an existing website |
| `decisions/` | Locked ADR choices (incl. DEC-009 toolkit, DEC-010 `mobile_native`, DEC-011 Experience Layer) |
| `tasks/EPIC-*` | Delivery slices |
| `prompts/` | Coordinator mode prompts (`discovery-interview.md` is the interviewer) |
| `schemas/` | Structured I/O contracts |
| `templates/` | Product-type Discovery hints + `DESIGN.md` + customer AGENTS + Spec Kit stubs |
| `.cursor/rules/` | Thin always-on + glob rules |
| `.cursor/skills/` | On-demand procedures |

## Token economy (progressive disclosure)

| Layer | Load when |
|-------|-----------|
| `AGENTS.md` + `asf.mdc` | Every ASF session (keep both short) |
| Glob `.mdc` | Matching file types only |
| One skill | The current task matches its `description` |
| A Foundation doc / ADR | A decision or schema is in doubt |

Do not preload every skill. Do not paste this table into prompts.

## Cursor rules in this repo

| Rule | When |
|------|------|
| `asf.mdc` | Always — MVP freeze, packages, product types, no catalog dump |
| `python-backend.mdc` | Python / FastAPI / SQLAlchemy / Alembic |
| `discovery-kg.mdc` | Discovery FSM, entities, relations, artifacts |
| `integrations.mdc` | Telegram + STT / Whisper |
| `product-templates.mdc` | Implementing exported tasks / product templates |
| `docs-ru-sync.mdc` | English `docs/*.md` edits → `docs/ru/` |
| `design-anti-slop.mdc` | Mini App / console CSS/JS/HTML |
| `security-basics.mdc` | `apps/api`, `core`, `integrations` |
| `miniapp-ux.mdc` | Mini App UX; Experience Layer mascot is DEC-011 |

## Project skills (on demand)

| Skill | Use |
|-------|-----|
| `asf-mvp` | Implement the next factory epic |
| `human-interview` | Consultant interview; one question; assumption ledger |
| `anti-slop-design` | Distinct UI; `DESIGN.md` first |
| `token-economy` | Writing routers/rules/skills without bloating context |
| `project-memory` | Append Learned sections; no secrets |
| `autodoc` | Docs + RU mirror after code/ADR change |
| `security-review` | OWASP-oriented pass; Telegram / initData |
| `mvp-customer-pack` | Stamp audience-B repo |
| `mvp-speckit-export` | KG / TZ → `spec.md` `plan.md` `tasks.md` |

### How to use each skill (short)

1. **asf-mvp** — open one epic checkbox; stay in package boundaries; pytest.
2. **human-interview** — acknowledge, one question, literacy adapt; keep Discovery JSON intact.
3. **anti-slop-design** — read `DESIGN.md`; ban Inter+purple and default Tailwind blue/gray as the look.
4. **token-economy** — always-on tiny; skills on demand; no encyclopedia rules.
5. **project-memory** — durable prefs/facts only; optional Cursor continual-learning plugin (do not copy proprietary hooks).
6. **autodoc** — bump English canon, then `docs/ru/` in the same turn.
7. **security-review** — findings + fixes; no exploit PoCs.
8. **mvp-customer-pack** — copy slim AGENTS + DESIGN + security/design skills + Spec Kit stubs.
9. **mvp-speckit-export** — map KG to Spec Kit filenames; do not vendor spec-kit.

## Two audiences

| | A — ASF factory | B — customer MVP |
|--|-----------------|------------------|
| Router | repo `AGENTS.md` | `templates/customer-agents/AGENTS.md` |
| Implementation skill | `asf-mvp` | exported `tasks.md` + product template |
| Memory | KG for customers; Learned sections for the factory repo | Learned sections + stamped spec |
| UI | Mini App / console tokens | `templates/DESIGN.md` |

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

## Cursor continual-learning plugin

Optional. Settings → Plugins → enable **continual-learning** if the team wants automatic harvest into Learned-style memory. Repo-owned fallback: `.cursor/skills/project-memory/SKILL.md`. Do not vendor plugin TypeScript.

## Intentionally not added

| Temptation | Why skip |
|------------|----------|
| Full Architecture Bible / RFC dump | Already rejected for MVP |
| Copy of `gpt.md` into repo | Noise; decisions are distilled |
| Multi-agent runtime skill pack | Contradicts DEC-002 |
| OpenReq (or similar) runtime | Discovery + KG own the contract |
| Always-on mega rules | DEC-009 / token economy |
| Wholesale vendor of external skill repos | Drift + license |
| Spec Kit git subtree | Mapping + stubs only |
| Wholesale Rive kits / lip-sync TTS puppet | Runtime slice is DEC-011; lip-sync stays Future |
| Redis / GraphDB runbooks | Future |

## Minimum session checklist

1. Read `AGENTS.md` (router only)
2. Activate the **one** matching project skill (`asf-mvp` for factory code)
3. Open the current epic under `tasks/` (factory) or `tasks.md` (customer)
4. Touch only allowed packages / the locked product type
5. Run `pytest` (or the customer test command) before finishing
