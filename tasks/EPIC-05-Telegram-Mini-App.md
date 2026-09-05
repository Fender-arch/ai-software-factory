# EPIC-05 — Telegram Mini App

| Field | Value |
|-------|-------|
| Status | Done |
| Version | 0.2 |

## Goal

Fullscreen Russian Mini App as primary customer UI: onboarding, create / change / implementation feedback, project workspace. Bot DM = entry + notifications + owner HITL.

Refs: `docs/14-Telegram-Customer-UX.md`, `decisions/DEC-006-Telegram-Mini-App.md`.

## Deliverables

- [x] `apps/miniapp/` static Mini App (RU home + project workspace)
- [x] Serve Mini App from API (`/miniapp/`)
- [x] Customer APIs: list projects, workspace messages, implementation feedback
- [x] Bot `/start` onboarding in Russian + WebApp / Menu Button when `MINIAPP_URL` set
- [x] Tests for list / workspace / feedback paths

## Notes

Project “chat” = Mini App workspace bound to `project_id` (not a second Telegram DM). Owner HITL stays on bot commands. Transitional `/new` `/use` remain.

APIs: `GET /projects?customer_telegram_id=`, `GET /projects/{id}/workspace`, `POST /projects/{id}/feedback`. KG type `Feedback`. Static UI at `/miniapp/`. Env: `MINIAPP_URL` for Telegram WebApp (HTTPS).

## v0.2 — Discovery progress bar

- [x] Workspace API returns live `discovery_progress` (done/total recomputed from the adapted outline)
- [x] Mini App chat: gray track + green fill; bar rescales when more TZ sections appear

Verified: `pytest` covers workspace progress growth after Mini App outline adapt.

## v0.5 — Home buttons by project state

- [x] Hub shows **Создать проект** only when the customer has no projects
- [x] **Изменить проект** after the first project (Discovery resume, not a new interview)
- [x] **Замечания к реализации** only after MVP was sent to the client (`sent_to_client` / `/sendreview`), not merely `READY`
- [x] `GET /projects` exposes `mvp_review_sent`; tests cover the 0 / has-project / review matrix

## v0.4 — TZ card in thread + sendDocument

- [x] Draft TZ download UI is a thread message, not a sticky dock bar
- [x] Format buttons send the file to the bot chat first (`tz-send` / `estimate-send` → `sendDocument`); device download is fallback only

## v0.3 — Experience Layer mascot (DEC-011)

- [x] Client event bus + mascot slot in Mini App workspace (Rive CDN progressive, SVG fallback)
- [x] «Спокойный режим» + `prefers-reduced-motion`; Discovery/API contracts unchanged
- [x] Docs: DEC-011, `docs/14`, `miniapp-ux.mdc`; smoke tests for slot / calm flag
