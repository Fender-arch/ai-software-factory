# 04 — Repository Structure

| Field | Value |
|-------|-------|
| Status | Accepted |
| Version | 0.8 |
| Updated | 2026-09-05 |
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
├── templates/            # Product-type hints, DESIGN.md, customer AGENTS, Spec Kit stubs
├── .cursor/
│   ├── rules/            # Thin always-on + glob rules
│   └── skills/           # On-demand skills (asf-mvp + interview/design/security/…)
├── apps/
│   ├── api/              # FastAPI entrypoint
│   ├── miniapp/          # Telegram Mini App frontend (customer UI + brand/)
│   └── console/          # Owner TZ graph console (DEC-007 + brand/)
├── core/                 # config, db, models, coordinator, estimate, client_estimate, factory
├── knowledge/            # entity/relation repositories
├── discovery/            # Discovery FSM, interview, draft TZ
├── integrations/
│   ├── telegram/         # Bot polling, Menu/WebApp hooks, owner HITL + notify
│   ├── cursor/           # Cloud Agent executor (HTTP or stub)
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
