# DEC-015 — Discovery starts with acquaintance, then optional brief merge

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2026-09-05 |
| Amends | [DEC-008](DEC-008-LLM-Driven-Discovery.md) |

## Context

Conversational Discovery (DEC-008 / DEC-014) still opened on the product
idea. Owners reported that the factory jumped into technique without
knowing *who* they were talking to. Contacts existed later as TZ topic
`contacts` and already appear in `compose_tz_markdown` шапка, but they
were asked too late. A written brief (ChatGPT paste, file) was only
offered at the closing wrap-up, so attached requirements were easy to
lose or to treat as one more chat turn.

## Decision

1. **Acquaintance first.** New FSM stage `CUSTOMER_INTRO` runs before
   `UNDERSTANDING_IDEA`. Spine topics `customer_intro` then `have_brief`
   are first. The LLM (DEC-008) still drives phrasing — this is not a
   five-field form. Collect, adaptively:
   - name / how to address;
   - contacts (phone / email / Telegram — whatever they give);
   - company for the product **or** explicit “no company name / individual”;
   - industry;
   - role when useful.
2. **KG types `Customer` and `Organization`.** Same `entity` table, no
   new migration. Payloads hold name, contacts, `is_individual` /
   `no_company_name`, industry, role. `Customer related_to Organization`.
   The later `contacts` topic is auto-closed when intro already captured
   a contact. `compose_tz_markdown` reads these entities for the TZ header
   and still falls back to `contacts` / `preferred_contact` requirements.
3. **Then: ready brief?** After intro, ask whether a written TZ / brief
   already exists.
   - No → ordinary flexible Discovery (purpose, shape, …).
   - Yes → invite a file (existing multimodal upload) or a paste.
4. **File / paste → merge.** Reuse `extract_attachment_text` (txt / md /
   docx). `discovery/brief_ingest.py` maps text onto outline topics,
   writes `Requirement`s, and **creates new `custom:` topics** for overflow
   instead of dropping it. Empty leftover topics become the next
   questions. The customer reply is a short recap (what landed / what is
   still needed) — never an echo of the whole file.
5. **Guarantees unchanged.** HITL, project statuses, pause / «готово» /
   «остальное с разработчиком», conversational tone (DEC-014), tz-send
   and Mini App hub stay as they are. Closing wrap-up skips the late
   “have a brief?” question when `have_brief` was already answered.
6. **Humor is not added** as a product requirement.

## Consequences

- First customer-facing question is acquaintance, not the product idea.
- A brief can fill many TZ sections in one turn; leftover gaps stay on
  the coverage checklist.
- Overflow from a rich brief becomes extra outline topics (cap:
  `MAX_CUSTOM_TOPICS + MAX_BRIEF_OVERFLOW_TOPICS`).
- Stub / FSM path uses the same topic order; LLM path gets
  `interview_phase`: `intro` | `brief_gate` | `discovery`.
