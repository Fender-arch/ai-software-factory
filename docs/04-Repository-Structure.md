# 04 — Repository Structure

| Field | Value |
|-------|-------|
| Status | Accepted |
| Version | 0.5 |
| Updated | 2026-08-28 |
| Owner | ASF Core |

```
ai-software-factory/
├── README.md
├── AGENTS.md             # Agent entrypoint
├── pyproject.toml
├── requirements.txt
├── docker-compose.yml
├── docker-compose.prod.yml  # VPS: localhost API + bot; see docs/16-VPS-Deploy.md
├── .env.example
├── deploy/               # VPS env/nginx helpers (host-side)
├── .github/              # Actions deploy + SECRETS.md
├── docs/                 # Foundation (incl. Agent-Toolkit, Dev-Setup, Telegram UX)
├── decisions/            # Short ADRs
├── backlog/              # Future / Ideas / Research
├── tasks/                # Epics for delivery
├── prompts/              # Mode prompts
├── schemas/              # JSON schemas
├── templates/            # Product-type hints
├── .cursor/
│   ├── rules/            # Persistent Cursor rules
│   └── skills/asf-mvp/   # Project implementation skill
├── apps/
│   ├── api/              # FastAPI entrypoint
│   ├── miniapp/          # Telegram Mini App frontend (customer UI)
│   └── console/          # Owner TZ graph console (DEC-007)
├── core/                 # config, db, models, coordinator, estimate
├── knowledge/            # entity/relation repositories
├── discovery/            # Discovery FSM, interview, draft TZ
├── integrations/
│   ├── telegram/         # Bot polling, Menu/WebApp hooks, owner HITL + notify
│   └── stt/
├── shared/
├── alembic/
├── tests/
└── docker/
```

## Rules

- Documentation is versioned like code (status, version, date).
- Rejected architecture ideas live in `decisions/` or `backlog/`, not as competing docs.
- Application code stays in package modules; no business logic in Telegram handlers or Mini App UI beyond I/O — call `core.services`.
- Mini App talks to FastAPI; bot remains thin I/O for notifications and owner commands.
- Owner TZ console talks to `/console/api/`; no business logic in the static UI beyond I/O.
