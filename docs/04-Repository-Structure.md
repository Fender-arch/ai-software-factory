# 04 — Repository Structure

| Field | Value |
|-------|-------|
| Status | Accepted |
| Version | 0.1 |
| Updated | 2026-07-30 |
| Owner | ASF Core |

```
ai-software-factory/
├── README.md
├── AGENTS.md             # Agent entrypoint
├── pyproject.toml
├── requirements.txt
├── docker-compose.yml
├── .env.example
├── docs/                 # Foundation (incl. Agent-Toolkit, Dev-Setup)
├── decisions/            # Short ADRs
├── backlog/              # Future / Ideas / Research
├── tasks/                # Epics for delivery
├── prompts/              # Mode prompts
├── schemas/              # JSON schemas
├── templates/            # Product-type hints
├── .cursor/
│   ├── rules/            # Persistent Cursor rules
│   └── skills/asf-mvp/   # Project implementation skill
├── apps/api/             # FastAPI entrypoint
├── core/                 # config, db, models, coordinator
├── knowledge/            # entity/relation repositories
├── discovery/            # Discovery FSM stubs
├── integrations/
│   ├── telegram/
│   └── stt/
├── shared/
├── alembic/
├── tests/
└── docker/
```

## Rules

- Documentation is versioned like code (status, version, date).
- Rejected architecture ideas live in `decisions/` or `backlog/`, not as competing docs.
- Application code stays in package modules; no business logic in Telegram handlers beyond I/O.
