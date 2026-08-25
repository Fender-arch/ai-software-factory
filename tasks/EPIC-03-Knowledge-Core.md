# EPIC-03 — Knowledge Core

| Field | Value |
|-------|-------|
| Status | Done |
| Version | 0.1 |

## Goal

Reliable entity/relation CRUD, context builder per mode, basic search/traceability.

## Deliverables

- [x] Repository APIs for entity/relation
- [x] Context builder (no free-range DB reads by modes)
- [x] Trace Message → Requirement → Decision → Task
- [x] Coverage checklist helpers

## Notes

`knowledge/` owns CRUD (`repository`), mode-scoped `ContextBuilder`, spine helpers in `traceability` (`derived_from` → `decides` → `implements`), and Level-1 `coverage` checklists from product templates. Discovery links via `link_derived_from`; coordinator discovery uses bounded context + exit checklist.

Verified: `pytest` covers CRUD/search, trace spine, mode context scoping, coverage, and discovery API coverage payload.
