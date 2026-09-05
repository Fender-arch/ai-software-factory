---
name: mvp-speckit-export
description: >-
  Map ASF Knowledge Graph and draft TZ artifacts to GitHub Spec Kit files
  (spec.md, plan.md, tasks.md). Use when exporting a customer MVP for Cursor
  or Spec Kit workflows. Do not vendor the spec-kit repository.
---

# Spec Kit export mapping

[GitHub Spec Kit](https://github.com/github/spec-kit) is a *customer-repo* convention (`spec.md`, `plan.md`, `tasks.md`). ASF does **not** vendor that toolkit. The factory **emits compatible stubs** from the KG.

## Mapping (ASF → Spec Kit)

| Spec Kit file | ASF source | How to fill |
|---------------|------------|-------------|
| `spec.md` | Draft TZ artifact + Requirement entities | Problem, users, in/out of scope, acceptance, risks. Canonical English; optional RU customer appendix. |
| `plan.md` | Architect notes + product template + `DESIGN.md` tokens | Sufficient-simple design, stack, HITL leftovers. One product type. |
| `tasks.md` | Planner export (`GET /projects/{id}/export/tasks`) | Numbered slices with requirement IDs and acceptance criteria. |

Stubs: `templates/speckit/spec.md`, `plan.md`, `tasks.md`.

## Rules

- KG is SoT. Markdown is derived. If they disagree, re-export; do not “fix” only the Spec Kit file.
- Keep product type locked: `website` \| `telegram_bot` \| `rest_service` \| `ai_automation` \| `mobile_native`.
- Escalated topics stay explicit assumptions — do not resolve them in `spec.md`.
- Do not clone or submodule spec-kit into ASF or the customer repo unless the owner asks later (Future).

## Factory emission (when implementing export)

Prefer writing the three files next to the existing markdown/JSON task export. Do not add a second planner. Reuse `core/planner.py` task rows.
