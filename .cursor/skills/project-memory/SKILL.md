---
name: project-memory
description: >-
  Mine durable project facts into AGENTS.md Learned sections (preferences and
  workspace facts). No secrets. Use at session end, after a lasting preference
  is stated, or when the same correction keeps recurring. Not a substitute for
  the ASF Knowledge Graph.
---

# Project memory (lightweight)

ASF’s semantic memory for **customer projects** is the PostgreSQL KG (`entity` / `relation`). This skill is **repo memory for agents**: facts that should survive chats.

## Where to write

In the active repo’s `AGENTS.md`:

- `## Learned User Preferences` — how humans want work done
- `## Learned Workspace Facts` — stable truths about *this* tree

Keep bullets short. Date them (`YYYY-MM-DD`). Prefer one fact per line.

## What to keep

- Tooling pins, test commands that differ from docs, package-boundary reminders
- Recurring review comments (“don’t expand product types ad hoc”)
- Owner taste that is not already an ADR
- Customer-MVP: brand tokens already decided, host, locale

## What never to keep

- Tokens, API keys, `.env` values, initData, phone numbers, personal data
- One-off task state, PR review chatter, ephemeral errors
- Secrets in any encoding. If unsure, omit.

## How to mine a session

1. Scan corrections that happened **more than once** or were stated as lasting.
2. Deduplicate against existing Learned bullets and Accepted ADRs.
3. Append only net-new durable facts. Do not rewrite history.
4. If an ADR already covers it, do not duplicate — link the DEC.

## Cursor continual-learning plugin (optional)

Cursor ships a **continual-learning** plugin that can maintain Learned-style memory in some setups.

- Enable it from Cursor Settings → Plugins if the team wants automatic harvest.
- Do **not** vendor or copy proprietary plugin hook TypeScript into this repo.
- This skill remains the repo-owned, license-clear fallback.
- Factory customer packs may mention the plugin; they still ship this skill.

DEC-009 records the “ideas yes, proprietary hooks no” choice.
