---
name: token-economy
description: >-
  Keep agent context cheap: progressive disclosure, skills on demand, thin
  always-on rules, no catalog dumps. Use when editing AGENTS.md, .cursor/rules,
  .cursor/skills, prompts, or when a session is loading too much toolkit text.
---

# Token economy

Context is a budget. Always-on text is rent you pay every turn.

## Progressive disclosure

| Layer | Size | What belongs |
|-------|------|----------------|
| `AGENTS.md` | Short router | Hard constraints, skill table, Learned placeholders |
| `alwaysApply` rules | Tiny | Non-negotiable invariants only (`asf.mdc`) |
| Glob rules `.mdc` | Small | File-type constraints; good `description` |
| Skills `SKILL.md` | On demand | Procedures, checklists, examples |
| `docs/` / ADRs | On demand | Source of truth when the task needs it |

Do **not** copy skill bodies into `AGENTS.md`. Do **not** paste the full toolkit into a prompt.

## Rules for writing rules

- `alwaysApply: true` only when the constraint is cheap and universal.
- Prefer `globs` + a one-line `description` so the agent can skip the file.
- No encyclopedias. Link to `docs/` or a skill.
- Customer packs stay slimmer than the ASF factory toolkit.

## Session hygiene

1. Open the epic or the customer task — not every EPIC file.
2. Read one matching skill.
3. Pull a doc only when a decision or schema is in doubt.
4. At session end, run `project-memory` instead of leaving facts in chat.

Rationale and rejected mega-rule packs: `decisions/DEC-009-Agent-Toolkit-Reuse.md`.
