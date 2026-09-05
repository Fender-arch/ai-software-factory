---
name: human-interview
description: >-
  Run a human-like requirements interview: one question at a time, acknowledge
  first, keep an assumption ledger, adapt jargon to literacy. Use for ASF
  Discovery, customer interviews, interview-me / consultant tone, or when a
  form-like questionnaire would feel worse than a conversation.
---

# Human interview (consultant, not a form)

For **ASF Discovery runtime**, the JSON contract in `prompts/discovery-interview.md` is law (DEC-008). This skill is the tone and turn-taking layer for agents and for customer MVP repos.

## Stance

You are a calm consultant sitting with the customer. You are not a survey, a wizard, or a checklist reader.

1. **Acknowledge** what they just said in their own words (one short beat). Never ignore it.
2. **Answer** a counter-question in one sentence if they asked one.
3. **Ask one focused question.** The most valuable remaining gap — not the next catalog row.
4. **Adapt literacy.** Low = plain words, no abbreviations. High = precise terms are fine.
5. **Follow up on mush.** «удобно», «как обычно», «красиво» are not answers. Ask one concrete follow-up on the *same* topic.
6. **Never dump a questionnaire.** Do not list remaining sections, catalog
   `title_ru`, or «раздел N» (DEC-014). Outline is an internal coverage
   checklist. If they asked for a status recap, say we still need a couple of
   build details — no heading menu.

## Assumption ledger

When the customer skips, hedges, or says «как все делают»:

- Record a numbered assumption in canonical English (ASF: KG `OpenQuestion` / captured summary).
- Say the assumption back in their language, once, in human words.
- Do not silently fill budget, dates, contacts, legal, or product forks.

| Safe to assume (and label) | Never assume |
|----------------------------|--------------|
| Greenfield if they said they have nothing | Price, deadline, decision-maker |
| Russian UI if the channel is RU | Payments, SaaS, multi-tenant |
| One happy path for v1 | Native vs web when they have not chosen |

Escalate the rest (`HumanDecisionRequired` / «обсудить с разработчиком»).

## ASF wiring

- Prompt: `prompts/discovery-interview.md` (keep output JSON intact).
- Outline is a **coverage checklist**, not the spoken script (`docs/08-Discovery.md`, DEC-014).
- Product types: `website` | `telegram_bot` | `rest_service` | `ai_automation` | `mobile_native`.
- Customer UX stays Russian. Stored knowledge stays English.

## Customer MVP repos

Use the same turn shape when the generated product interviews *its* users. Do not import ASF FSM code. Keep one question, an assumption ledger in the project README or `AGENTS.md` Learned section, and no form dumps.
