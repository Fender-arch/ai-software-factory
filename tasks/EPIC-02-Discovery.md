# EPIC-02 — Discovery

| Field | Value |
|-------|-------|
| Status | Done |
| Version | 0.10 |

## Goal

Adaptive Discovery interview in Telegram (text + voice transcripts) producing structured requirements in the KG.

## Deliverables

- [x] Discovery FSM transitions
- [x] Question generation adapted to IT literacy
- [x] Requirement / open-question entities
- [x] Draft TZ artifact generation

## v0.4 — Spec quality (Spec Kit-inspired)

- [x] Vague free text does not close a TZ topic (chip answers still do)
- [x] Quality floor + clarify pass in REVIEW (max 5)
- [x] Recommended chips on safe defaults
- [x] Draft TZ includes FR-###, SC-###, Assumptions, Clarifications, Given–When–Then
- [x] Reviewer scan: vague wording, duplicates, must vs non-goal clashes

## Notes

Since DEC-008 the LLM interviewer drives customer-facing turns when
`DISCOVERY_ENGINE=llm` (default `auto`); the deterministic core keeps KG
writes, the coverage gate, the quality floor, and pause/ready intents, and any
LLM failure falls back to the FSM path. Outline adaptation is heuristic +
optional Groq JSON (`LLM_PROVIDER=groq`).

## v0.11 — LLM-driven interview (DEC-008)

- [ ] `prompts/discovery-interview.md` — interviewer prompt (checklist in, JSON turn out)
- [ ] `discovery/llm_interviewer.py` — context builder, JSON validation, KG writes via existing helpers
- [ ] `DISCOVERY_ENGINE` setting + dispatch in `run_discovery_turn` with FSM fallback
- [ ] Per-turn LLM choice chips with code-side sanitization
- [ ] Tests: scripted fake LLM interview, guard rails, fallback path

v0.3: TZ outline (`discovery/tz_outline.py`) — one topic per turn, pause/resume, choice chips including “discuss with developer”, no early finalize.

v0.4: quality gate in `discovery/quality.py`; do not vendor Spec Kit CLI.

## v0.5 — Adaptive TZ outline

- [x] Per-project outline plan: spine + type/shape modules + capability subsections
- [x] Skip N/A public-presence sections for internal tools
- [x] Structured LLM extras (`custom:…`) when `LLM_PROVIDER=groq`; heuristic fallback on stub
- [x] Contextual next-question preamble from already captured answers

## v0.6 — Estimate drivers

- [x] Promotion / SEO / ads / analytics for public presence
- [x] Legal / 152-FZ / industry constraints on the core spine (affects timeline and cost)

## v0.7 — Implementation content follow-ups

- [x] Do not auto-close public-presence / substance topics from the idea dump
- [x] Re-ask when URLs, service chips, lead destination, or existing host lack implementable detail
- [x] «Discuss with developer» / «I don’t know» still escalates; do not infer those sections
- [x] Mini App asks bot-chat vs Mini App only; short deadline restates 3D/вау trade-off

Verified: `pytest` covers substance gates, infer skip, bare reference URLs, discuss-with-developer handoff.

## v0.8 — Visible task-fit questions and chips

- [x] After the idea is captured, remaining questions, section titles, and choice chips are rewritten from that task (heuristic; Groq may refine)
- [x] Next turn announces added and skipped sections
- [x] Heuristic extras (e.g. who books a slot) without waiting for Groq

## v0.9 — Choice chips follow previous answers

- [x] Remaining chips are retargeted from captured answers (tools/process), not only the task brief
- [x] Irrelevant catalog chips are hidden; extra `ctx:*` chips may echo a previous fact
- [x] Groq JSON (`prompts/discovery-choices.md`) refines the next topic's chips; stub keeps the heuristic

## v0.10 — Requested surfaces on solution-type chips

- [x] If the idea names Android / iOS / a mobile app, those chips are prepended on `product_shape` (heuristic, no Groq required)
