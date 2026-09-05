# 15 — Owner TZ graph console

| Field | Value |
|-------|-------|
| Status | Accepted |
| Version | 0.7 |
| Updated | 2026-09-05 |
| Owner | ASF Core |

## Purpose

Internal **owner/analyst** UI to inspect collected TZ requirements as a graph. Customer UI stays the Telegram Mini App. HITL approve of draft TZ stays on the owner bot.

ADR: [DEC-007](../decisions/DEC-007-Owner-TZ-Console.md).

## Access

- URL: `/console/` (static), APIs under `/console/api/`
- Header: `X-Console-Token` matching `CONSOLE_TOKEN`
- Empty token is allowed only when `ASF_ENV=local` and `ASF_DEBUG=true`

## Graph view

Projection (not a competing store). Virtual nodes from Discovery stages + `discovery/tz_outline.py` topics; leaves are KG `Requirement` entities.

```
Project → stage → topic → Requirement
Requirement --depends_on--> Requirement
Requirement --conflicts_with--> Requirement
```

| Edge kind | Meaning | Color (UI) |
|-----------|---------|------------|
| `structure` | Outline hierarchy | gray |
| `depends_on` | Requirement depends on another | amber |
| `conflicts_with` | Contradiction between requirements | red |

Stages start collapsed around the project hub. Click a **stage or topic** to expand that branch (one stage at a time) and open its roster card. Click a **leaf** for the requirement card (description, links, status, history). Click empty canvas or × to return to the project overview. Hover dims unrelated nodes. Search jumps to a matching node.

The sheet is a directory: group cards list children; tapping a child focuses it on the map. Leaves are the only nodes with mutations.

Section nodes use a vendored [Lucide](https://lucide.dev/) (ISC) pictogram set in `apps/console/icons/`. The node **is** the pictogram (no extra circle); a soft glow uses the stage colour. Product hub icon follows type (`website` / `telegram_bot` / `rest_service` / `ai_automation` / `mobile_native`). Mapping: `apps/console/icons/map.json`.

The project sheet has **Export full TZ**: Markdown, Word (`docx`), PDF — generated live from the KG (`GET /console/api/projects/{id}/tz-export?format=md|docx|pdf`). Clicking the **project hub** (graph center) also shows **two estimates**: the owner HITL heuristic (`payload.estimate` / live `core/estimate.py`) and, after approve, the **client market estimate** + report (`payload.client_estimate`, DEC-012) with sources and confirmation status. They stay side by side; the heuristic is never the customer price.

The same sheet lists **project files** (customer Mini App attachments and console uploads) with the Discovery stage they were provided on. Analysts can add or delete files; `entity_history` records `created` / `deleted`. Bytes live on disk under `UPLOAD_DIR` (default `data/uploads`); KG `Artifact` rows with `payload.kind=uploaded_file` are the index. Download: `GET /console/api/projects/{id}/files/{file_id}/content`.

`archived` requirements are omitted. Legacy entity status `active` is shown as `new`.

## Requirement statuses

| Code | RU label | Rule |
|------|----------|------|
| `new` | новое | Just captured; NEW badge |
| `processed` | отработано | Accepted into TZ by analyst |
| `needs_clarification` | уточняется | Waiting on an answer |
| `conflict` | конфликт | Has `conflicts_with` and/or explicit mark |
| `rejected` | отклонено | **Reason required** |
| `superseded` | заменено | Replaced (already used in Discovery) |

## Requirement panel

Shows: id, description, created date, author (`payload.author_role` / `author_id`), structural parent, links, status, reject/conflict reason, change history.

Mutations: create a requirement (on a topic/stage sheet); edit text, topic and priority (logged as `updated`); change status; add/remove `depends_on` and `conflicts_with`. Not in v1: HITL approve, LLM auto-detect conflicts.

Adding `conflicts_with` sets both ends to `conflict` unless `rejected` / `superseded`. Removing the last conflict relation restores the previous status from history (fallback `processed`).

## History

Table `entity_history` is an append-only audit log (`created`, `updated`, `deleted`, `status_change`, `relation_add`, `relation_remove`). It is **not** event sourcing. Text edits store before/after snippets in `payload.fields`. File add/remove store filename and stage in `payload`.
