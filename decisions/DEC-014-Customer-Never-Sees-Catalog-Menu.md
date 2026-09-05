# DEC-014 — Customer never sees the TZ catalog as a menu

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2026-09-05 |
| Amends | [DEC-008](DEC-008-LLM-Driven-Discovery.md) |

## Context

DEC-008 made the LLM drive the customer-facing turn while the adapted
outline stayed the coverage checklist. In production the chat still felt
like a fixed questionnaire: `LLM_PROVIDER=stub` (or `DISCOVERY_ENGINE=fsm`)
fell back to the deterministic FSM, which prefixed every turn with
«Раздел ТЗ N/total — {title_ru}» and announced added/skipped headings;
the LLM coverage gate appended «осталось пройти разделы: …»; Mini App
progress showed «N из M». Coverage worked. The consultant tone did not.

## Decision

1. **Outline is internal.** `discovery/tz_outline.py` + `adapt.py` remain
   the coverage mechanism (DEC-008 guarantees unchanged: KG writes in
   code, `ready_for_owner` only when the adapted outline is empty and
   the quality floor passes, invented topic ids dropped, pause/ready
   intents stay deterministic).
2. **Customer never sees a catalog section menu.** Replies, welcome text,
   FSM fallback, and coverage-gate overrides must not list `title_ru`,
   say «раздел N» / «раздел ТЗ», or announce «Добавляю:» / «Не спрашиваю:»
   heading lists. Soft copy: acknowledge, one question, or «давай уточним
   ещё пару вещей для сборки».
3. **Chips are hints for the current question**, not a menu of sections.
4. **FSM fallback** (stub, `DISCOVERY_ENGINE=fsm`, invalid JSON) still
   answers, but uses rephrased human questions without outline announce.
   Log WARNING when the LLM path was enabled and the turn fell back.
5. **Mini App progress** shows a percent or «ещё пара уточнений», not
   «done из total». Owner console graph still uses outline titles.
6. **Flexible interview requires a real LLM.** Default `auto` is LLM
   only when `LLM_PROVIDER != stub`. Production must set
   `LLM_PROVIDER=groq` (or another non-stub provider). `fsm` / stub is
   a safe fallback, not the intended customer UX.

## Consequences

- Coverage and KG guarantees from DEC-008 stay in code.
- Prompt `prompts/discovery-interview.md` forbids catalog menus;
  `discovery/customer_copy.py` sanitizes leaked questionnaire lines.
- Docs: `docs/08-Discovery.md`, deploy/dev setup note on `LLM_PROVIDER`.
