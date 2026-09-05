# 03 — Tech Stack

| Field | Value |
|-------|-------|
| Status | Accepted |
| Version | 0.10 |
| Updated | 2026-09-05 |
| Owner | ASF Core |

Locked choices for MVP. Alternatives belong in Future, not in endless bake-offs.

| Layer | Choice |
|-------|--------|
| Language | Python 3.11+ |
| API | FastAPI + Uvicorn |
| ORM / migrations | SQLAlchemy 2 + Alembic |
| Database | PostgreSQL 16 (`entity`, `relation`, JSONB) |
| Queue / cache | **None in MVP** (Postgres statuses); Redis = Future |
| Customer UI | Telegram **Mini App** (fullscreen) + Bot API (aiogram) for entry/notifications/owner HITL; mascot via `@rive-app/canvas` CDN + SVG fallback ([DEC-011](../decisions/DEC-011-Experience-Layer-Mascot.md)) |
| Owner UI | Internal TZ graph console (`apps/console/`, vis-network); [DEC-007](../decisions/DEC-007-Owner-TZ-Console.md) |
| STT | Mini App in Telegram: **Groq Whisper** via recorded audio; Web Speech only outside Telegram. Also `whisper` (OpenAI) / `stub` |
| LLM | Pluggable router; `stub` or **Groq** JSON (`LLM_PROVIDER=groq`) for Discovery interview turns, TZ outline extras, and TZ polish. `stub` = FSM fallback (DEC-008/014) |
| Coding executor | Cursor Cloud Agent if `CURSOR_API_KEY`, else stub + Spec Kit/task export ([DEC-013](../decisions/DEC-013-MVP-Factory-Interventions.md)) |
| Containers | Docker + Docker Compose (local `docker-compose.yml`; VPS `docker-compose.prod.yml`) |
| Tests | Pytest |

## Environment variables

See `.env.example`: `DATABASE_URL`, `TELEGRAM_BOT_TOKEN`, `GROQ_API_KEY`, `OPENAI_API_KEY`, `STT_PROVIDER` (`stub`\|`groq`\|`whisper`), `STT_MODEL`, `LLM_PROVIDER` (`stub`\|`groq`), `LLM_MODEL`, `OWNER_TELEGRAM_ID`, `ASF_ESTIMATE_HOURLY_RATE`, `ASF_ESTIMATE_CURRENCY`, `MINIAPP_URL`, `CONSOLE_TOKEN`, `ASF_INTERVENTION_KEY`, `CURSOR_API_KEY`.

VPS deploy (existing website kept): [16-VPS-Deploy.md](16-VPS-Deploy.md), secrets [`.github/SECRETS.md`](../.github/SECRETS.md).
