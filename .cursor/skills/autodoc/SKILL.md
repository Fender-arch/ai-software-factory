---
name: autodoc
description: >-
  Update Foundation docs and docs/ru mirrors after code or ADR changes. Use when
  behavior, package layout, product types, or agent toolkit files changed, or
  when a reviewer notes docs drift. Does not invent new architecture.
---

# Autodoc

Docs are executable constraints (`docs/10-Project-Principles.md`). After a behavior or decision change, update the English canon in the same turn.

## When to run

- New or amended Accepted ADR
- Product-type allowlist change
- New rule, skill, prompt, schema, or template
- Package boundary or API contract change
- Discovery / HITL / export flow change

Skip: typo-only code, tests that lock existing behavior, comments.

## Order

1. Identify the **smallest** English doc that is now wrong (`docs/*.md`, `AGENTS.md`, `decisions/`).
2. Match existing frontmatter (`Status`, `Version`, `Updated`, `Owner`). Bump `Version` / `Updated`.
3. Sync `docs/ru/<same-name>.md` in the same turn (`.cursor/rules/docs-ru-sync.mdc`, hook `.cursor/hooks/docs_ru_sync.py`).
4. Keep the RU banner: `> Перевод. Канон: [\`docs/<file>\`](../<file>)`
5. Do not treat RU as source of truth.
6. Customer UX copy stays Russian and is **not** this skill’s job unless `docs/14` changed.

## Do not

- Rewrite Vision/Architecture because a skill was added — patch `docs/12-Agent-Toolkit.md` instead
- Copy raw chat or giant external READMEs into `docs/`
- Implement `backlog/Future.md` items under the guise of documentation
