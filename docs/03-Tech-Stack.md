# 03 — Tech Stack

| Field | Value |
|-------|-------|
| Status | Accepted |
| Version | 0.5 |
| Updated | 2026-08-26 |
| Owner | ASF Core |

Locked choices for MVP. Alternatives belong in Future, not in endless bake-offs.

| Layer | Choice |
|-------|--------|
| Language | Python 3.11+ |
| API | FastAPI + Uvicorn |
| ORM / migrations | SQLAlchemy 2 + Alembic |
| Database | PostgreSQL 16 (`entity`, `relation`, JSONB) |
| Queue / cache | **None in MVP** (Postgres statuses); Redis = Future |
| Customer UI | Telegram **Mini App** (fullscreen) + Bot API (aiogram) for entry/notifications/owner HITL |
| Owner UI | Internal TZ graph console (`apps/console/`, vis-network); [DEC-007](../decisions/DEC-007-Owner-TZ-Console.md) |
| STT | Mini App: Web Speech when capable, else **Groq Whisper**; also `whisper` (OpenAI) / `stub` |
| LLM | Pluggable router; `stub` or **Groq** JSON (`LLM_PROVIDER=groq`) to adapt TZ outline / extra subsections |
| Coding executor | Cursor (rules + task export); CLI integration later |
| Containers | Docker + Docker Compose (local `docker-compose.yml`; VPS `docker-compose.prod.yml`) |
| Tests | Pytest |

## Environment variables

See `.env.example`: `DATABASE_URL`, `TELEGRAM_BOT_TOKEN`, `GROQ_API_KEY`, `OPENAI_API_KEY`, `STT_PROVIDER` (`stub`\|`groq`\|`whisper`), `STT_MODEL`, `LLM_PROVIDER` (`stub`\|`groq`), `LLM_MODEL`, `OWNER_TELEGRAM_ID`, `MINIAPP_URL`, `CONSOLE_TOKEN`.

VPS deploy (existing website kept): [16-VPS-Deploy.md](16-VPS-Deploy.md), secrets [`.github/SECRETS.md`](../.github/SECRETS.md).
