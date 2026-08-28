# 09 — Knowledge Graph

| Field | Value |
|-------|-------|
| Status | Accepted |
| Version | 0.4 |
| Updated | 2026-08-28 |
| Owner | ASF Core |

## Principle

The Knowledge Graph is the **single source of truth**. Markdown artifacts are generated views, not competing stores.

MVP implementation: **logical graph in PostgreSQL**, not Neo4j.

## Tables

### `entity`

| Column | Notes |
|--------|-------|
| id | UUID |
| project_id | FK |
| type | see types below |
| name | short label |
| payload | JSONB |
| status | lifecycle |
| confidence | 0..1 optional |
| created_at / updated_at | timestamps |

### `relation`

| Column | Notes |
|--------|-------|
| id | UUID |
| project_id | FK |
| from_entity_id | FK |
| to_entity_id | FK |
| type | see relations below |
| payload | JSONB optional |

### `entity_history`

Append-only audit (not an event bus). Used by the owner TZ console.

| Column | Notes |
|--------|-------|
| id | UUID |
| project_id | FK |
| entity_id | FK |
| actor | `discovery` \| `console` \| `system` |
| action | `created` \| `updated` \| `deleted` \| `status_change` \| `relation_add` \| `relation_remove` |
| from_status / to_status | optional |
| reason | required when rejecting a Requirement |
| payload | JSONB optional |
| created_at | timestamp |

## Entity types (MVP)

`Project` · `Message` · `Requirement` · `OpenQuestion` · `Decision` · `Task` · `Artifact` · `Risk` (optional) · `Feedback` (implementation notes)

`Artifact` payload `kind`: `draft_tz` (generated markdown) or `uploaded_file` (customer/console attachment; bytes on disk under `UPLOAD_DIR`, not in JSONB).

A `draft_tz` Artifact also stores `payload.estimate`: deterministic delivery-cost heuristic (`hours`, `cost`, `currency`, `hourly_rate`, `rationale`, requirement/risk counts). No extra table.

Operational tables `projects` / `messages` / `tasks` may mirror hot paths; graph entities keep semantic links.

## Relation types (MVP)

`derived_from` · `decides` · `implements` · `blocks` · `related_to` · `depends_on` · `conflicts_with`

`depends_on` and `conflicts_with` are Requirement↔Requirement (owner console). Distinct from planner task `depends_on` in task payload.

## Requirement statuses (console)

`new` · `processed` · `needs_clarification` · `conflict` · `rejected` · `superseded`

Legacy `active` is treated as `new` in the console projection. `archived` is omitted from the graph.

TZ outline stages/topics are **virtual nodes** in the console view, not persisted entity types. See [15-Owner-TZ-Console.md](15-Owner-TZ-Console.md).

## Traceability example

`Message` → `derived_from` → `Requirement` → `decides` → `Decision` → `implements` → `Task` → `Artifact`

## Non-goals

- Graph query languages / GraphDB until Future
- Agents freely scanning the entire DB without a context builder
