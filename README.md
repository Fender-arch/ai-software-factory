# AI Software Factory (ASF)

**Version:** Foundation v0.1  
**Status:** Accepted

ASF is an operating system for a small digital IT company: a customer describes an idea in a Telegram **Mini App** (text or voice), the platform runs Discovery, produces a quality specification, waits for human review, breaks work into tasks, and drives delivery of a simple MVP via Cursor.

## What this repository is

- **Foundation docs** — source of truth for architecture and MVP scope
- **Starter code** — modular monolith (FastAPI + PostgreSQL + Telegram + STT); customer UI under `apps/miniapp/` (`/miniapp/`); owner TZ console under `apps/console/` (`/console/`)

Not in this release: real Discovery LLM provider, Cursor CLI automation, Redis, Neo4j, multi-agent runtime.

## Quick start

```bash
cp .env.example .env
docker compose up --build
```

API: http://localhost:8000/health  
Docs: http://localhost:8000/docs

Local (without Docker API, with Postgres only):

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn apps.api.main:app --reload
pytest
```

## Product flow (MVP)

```
Customer (Telegram Mini App text|voice)
  → Whisper STT (voice)
  → Discovery
  → Draft specification
  →    Owner review (HITL, bot) + TZ graph console (`/console/`)
  → Planner / tasks
  → Cursor executor
  → Simple MVP (website | bot | service | automation)
```

Customer home actions: create project · change project · implementation feedback — see [docs/14-Telegram-Customer-UX.md](docs/14-Telegram-Customer-UX.md).
## For Cursor agents

| Entry | Purpose |
|-------|---------|
| [AGENTS.md](AGENTS.md) | How to work in this repo |
| [docs/12-Agent-Toolkit.md](docs/12-Agent-Toolkit.md) | Rules, skills, docs map |
| [docs/13-Dev-Setup.md](docs/13-Dev-Setup.md) | Run / test / env |
| [.cursor/skills/asf-mvp](.cursor/skills/asf-mvp/SKILL.md) | MVP implementation skill |

## Documentation

Start here:

| Doc | Purpose |
|-----|---------|
| [docs/00-Vision.md](docs/00-Vision.md) | Why ASF exists |
| [docs/01-MVP-Scope.md](docs/01-MVP-Scope.md) | In / out of MVP |
| [docs/02-Architecture.md](docs/02-Architecture.md) | Components & flow |
| [docs/03-Tech-Stack.md](docs/03-Tech-Stack.md) | Locked stack |
| [docs/09-Knowledge-Graph.md](docs/09-Knowledge-Graph.md) | Logical KG in Postgres |

Decisions: [decisions/](decisions/) · Roadmap: [docs/05-Roadmap.md](docs/05-Roadmap.md) · Future: [backlog/Future.md](backlog/Future.md)

## Principles

1. Maximum architectural value, minimum engineering complexity
2. Orchestrator is not an LLM; AI Coordinator uses modes, not a swarm of processes
3. Knowledge Graph is logical (`entity` / `relation` in PostgreSQL)
4. Human in control at specification gates
5. New ideas go through the MVP filter or land in `backlog/Future.md`

## License

Proprietary / TBD.
