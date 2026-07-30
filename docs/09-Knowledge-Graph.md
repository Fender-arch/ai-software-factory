# 09 — Knowledge Graph

| Field | Value |
|-------|-------|
| Status | Accepted |
| Version | 0.1 |
| Updated | 2026-07-30 |
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

## Entity types (MVP)

`Project` · `Message` · `Requirement` · `Decision` · `Task` · `Artifact` · `Risk` (optional)

Operational tables `projects` / `messages` / `tasks` may mirror hot paths; graph entities keep semantic links.

## Relation types (MVP)

`derived_from` · `decides` · `implements` · `blocks` · `related_to`

## Traceability example

`Message` → `derived_from` → `Requirement` → `decides` → `Decision` → `implements` → `Task` → `Artifact`

## Non-goals

- Graph query languages / GraphDB until Future
- Agents freely scanning the entire DB without a context builder
