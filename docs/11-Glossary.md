# 11 — Glossary

| Field | Value |
|-------|-------|
| Status | Accepted |
| Version | 0.5 |
| Updated | 2026-09-05 |
| Owner | ASF Core |

| Term | Meaning |
|------|---------|
| ASF | AI Software Factory |
| Orchestrator | Non-LLM process that advances project state |
| AI Coordinator | Single AI worker with switchable modes |
| Mode | Named competence (Discovery, Reviewer, …) |
| Knowledge Graph (KG) | Logical SoT of entities and relations |
| HITL | Human in the loop |
| Owner heuristic | Studio-only delivery-cost aid on `payload.estimate` (`core/estimate.py`) |
| Client estimate | Market-band customer quote + narrative report (DEC-012); confirm before Planner |
| TZ | Technical specification / requirements pack |
| STT | Speech-to-text (Whisper in MVP) |
| Product type | One of website, telegram_bot, rest_service, ai_automation, mobile_native |
| Telegram Mini App | Fullscreen customer UI inside Telegram (primary channel) |
| Owner TZ console | Internal owner/analyst graph of TZ requirements (`/console/`, DEC-007) |
| Project workspace | Mini App thread/UI bound to one `project_id` (“project chat”) |
| Implementation feedback | Customer notes after reviewing a delivered MVP |
| BuildJob | Factory record of one MVP build (Cursor or stub) |
| Intervention Queue | Owner questions the factory must not guess (tokens, DNS, store access); secrets stay sealed |
| Foundation | Documentation baseline |
| Future | Deferred ideas in `backlog/Future.md` |
| ADR / DEC | Architecture Decision Record in `decisions/` |
| AGENTS.md | Entrypoint for Cursor agents working in the repo |
| Agent Toolkit | Map of rules/skills/docs for MVP work (`docs/12-Agent-Toolkit.md`) |
