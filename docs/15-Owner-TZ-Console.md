# 15 — Owner TZ graph console

| Field | Value |
|-------|-------|
| Status | Accepted |
| Version | 0.15 |
| Updated | 2026-09-08 |
| Owner | ASF Core |

## Purpose

Internal **owner/analyst** UI to inspect collected TZ requirements as a graph and run the commercial TZ/quote cycle. Customer UI stays the Telegram Mini App. HITL approve is on the owner bot **and** the console. Header lockup: Uni 4 IT wordmark (`apps/console/brand/`, see `docs/17-Brand-Assets.md`).

ADR: [DEC-007](../decisions/DEC-007-Owner-TZ-Console.md).

## Access

- URL: `/console/` (static), APIs under `/console/api/`
- Header: `X-Console-Token` matching `CONSOLE_TOKEN` (the UI also sends `Authorization: Bearer …`)
- Empty token is allowed only when `ASF_ENV=local` and `ASF_DEBUG=true`
- Production: paste the **value** of GitHub secret `CONSOLE_TOKEN` from the **last successful VPS deploy**, then click **Сохранить**. Changing the GitHub secret does nothing until you redeploy.

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

The project sheet has **Export full TZ**: Markdown, Word (`docx`), PDF — generated live from the KG (`GET /console/api/projects/{id}/tz-export?format=md|docx|pdf`). The client document is `core/tz_document.compose_tz_markdown`: title **Техническое задание** + project name, meta (project + customer contacts + studio/owner contacts), a linked table of contents, numbered sections, and visible requirement codes `ТЗ-N.M`. No Appendix and no “Draft TZ” heading. Owner/studio lines come from `STUDIO_NAME` / `OWNER_CONTACT_*` or a per-project KG hook `Project.payload.owner_contacts` (`{studio, name, email, phone, telegram, note}`). PDF/DOCX reuse the same Markdown (TOC links become plain numbered lines; PDF headings are added to the outline when the exporter supports it).

Clicking the **project hub** opens a sectioned sheet: **Общее** (name + customer line from stakeholders, timeline/budget from KG, derived pipeline), **ТЗ**, **Смета**, **MVP**, **Требования**, **Замечания**. The pipeline spine is seven unique gates left-to-right (`new_project` → `tz_review` → `tz_approved` → `agreement` → `mvp` → `accepted` → `archived`). Versioned events stack **in columns** under Согласование and MVP so the workflow does not grow sideways. Discovery `ProjectStatus` stays the FSM; the spine is derived (`core/commercial_pipeline.py`). Clicking a spine cell loads a **TZ snapshot** for that gate (`GET .../tz-preview`) and a requirement diff vs current. Owner can force previous/next or jump (`POST .../pipeline`) and may `PATCH` any `ProjectStatus` (testing/recovery). Snapshots are JSONB on `Project.payload.commercial.tz_snapshots`.

The sheet lists **two estimates**: studio heuristic (`payload.estimate`, not the customer price) and, after HITL approve, the **client quote** (`payload.client_estimate`). Owner sets hourly rate and discount %; the sent price is `hours × rate × (1 − discount%)`. Export (`GET .../estimate-export`) uses the stored quote only (no live preview-as-file). **Утвердить ТЗ** calls the same HITL service. **Отправить ТЗ и смету** sends two Telegram documents plus thread cards (`POST .../send-tz-estimate`); both files must succeed. Owner **human reply** (`POST .../replies`) skips Discovery. Unread from the customer is a dot on the project list and the remarks block (`GET /console/api/projects` includes `unread_from_customer`). Requirement chips show the legend snapshot plus a **delta since last package send**.

The right-hand sheet defaults to ~760px (`min(760px, 100% − 28px)`), is resizable (drag handle, `localStorage`), and stacks under 900px.

The same sheet has **MVP Factory** (DEC-013): **Создать MVP** after owner approve **and** client estimate confirm (`READY`), Intervention Queue answers (text / secret; secrets are not shown back), build status, and **Отправить клиенту на review**. APIs: `GET/POST /console/api/projects/{id}/mvp`, `POST .../mvp/send-to-client`, `GET .../interventions`, `POST /console/api/interventions/{id}/resolve`.

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

Shows: id, **current** description in the editor, created date, author (`payload.author_role` / `author_id`), structural parent, links, status, reject/conflict reason, change history. Text edits store the **previous full text** in `entity_history` (`payload.fields.description.from`); the sheet shows that old wording under История and the new wording in the main textarea.

Mutations: create a requirement (on a topic/stage sheet); edit text, topic and priority (logged as `updated`); change status; add/remove `depends_on` and `conflicts_with`. Not in v1: HITL approve, LLM auto-detect conflicts.

Adding `conflicts_with` sets both ends to `conflict` unless `rejected` / `superseded`. Removing the last conflict relation restores the previous status from history (fallback `processed`).

## History

Table `entity_history` is an append-only audit log (`created`, `updated`, `deleted`, `status_change`, `relation_add`, `relation_remove`). It is **not** event sourcing. Text edits store before/after in `payload.fields` (full previous description, not a truncated snippet). File add/remove store filename and stage in `payload`.
