# DEC-001 — Knowledge Graph in PostgreSQL

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2026-07-30 |

## Context

We need durable project memory and traceability without GraphDB operational cost.

## Decision

Implement a **logical** Knowledge Graph using PostgreSQL tables `entity` and `relation` with JSONB payloads. Neo4j/Memgraph deferred to Future.

## Consequences

- Simple ops and migrations
- Enough for MVP queries and context building
- May later migrate to a graph engine without changing conceptual model
