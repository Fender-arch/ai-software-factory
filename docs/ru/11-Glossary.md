# 11 — Глоссарий

> Перевод. Канон: [`docs/11-Glossary.md`](../11-Glossary.md)

| Поле | Значение |
|------|----------|
| Status | Accepted |
| Version | 0.5 |
| Updated | 2026-09-05 |
| Owner | ASF Core |

| Термин | Значение |
|--------|----------|
| ASF | AI Software Factory |
| Orchestrator | Не-LLM процесс, двигающий состояние проекта |
| AI Coordinator | Один AI-worker с переключаемыми режимами |
| Mode | Именованная компетенция (Discovery, Reviewer, …) |
| Knowledge Graph (KG) | Логический SoT сущностей и связей |
| HITL | Human in the loop |
| Owner heuristic | Внутренняя оценка студии на `payload.estimate` (`core/estimate.py`) |
| Client estimate | Рыночная смета заказчику + narrative-отчёт (DEC-012); подтверждение до Planner |
| TZ | Техническое задание / пакет требований |
| STT | Speech-to-text (Whisper в MVP) |
| Product type | Один из: website, telegram_bot, rest_service, ai_automation, mobile_native |
| Telegram Mini App | Полноэкранный UI заказчика внутри Telegram (основной канал) |
| Owner TZ console | Внутренний граф требований ТЗ для владельца/аналитика (`/console/`, DEC-007) |
| Project workspace | UI/лента Mini App, привязанная к одному `project_id` («чат проекта») |
| Implementation feedback | Замечания заказчика после ознакомления с поставленным MVP |
| Foundation | Базовый набор документации |
| Future | Отложенные идеи в `backlog/Future.md` |
| ADR / DEC | Architecture Decision Record в `decisions/` |
| AGENTS.md | Точка входа для Cursor-агентов в репозитории |
| Agent Toolkit | Карта rules/skills/docs для MVP (`docs/12-Agent-Toolkit.md`) |
