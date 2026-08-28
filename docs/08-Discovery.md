# 08 — Discovery

| Field | Value |
|-------|-------|
| Status | Accepted |
| Version | 0.17 |
| Updated | 2026-08-28 |
| Owner | ASF Core |

## Purpose

Turn a customer idea into a draft specification with enough clarity for architecture and planning — adapted to the customer’s IT literacy.

The interview must **cover every applicable TZ section** before owner review, unless the customer **pauses** or explicitly hands remaining sections to the developer.

**Applicable** is not a fixed form: after the idea and solution type are known, Discovery **adapts the outline to this task** — core spine always, type/shape modules when they apply, extra subsections when the task needs them to be implementable, and skippable modules dropped when they are N/A (for example a public offer catalog on an internal booking bot).

Quality ideas (clarify pass, `[NEEDS CLARIFICATION]` instead of guessing, checklists as “unit tests for English”) are adapted from [GitHub Spec Kit](https://github.com/github/spec-kit) (MIT). Spec Kit itself is a coding-agent toolkit — ASF does **not** vendor its CLI. The TZ outline interview remains the customer path.

## Channels

- Telegram **Mini App** project workspace (primary) — text + **«Варианты ответа» popup**. New project: welcome popup then questions. The chat shows a **progress bar** (gray track, green fill); `done/total` is recomputed after every answer from the current adapted outline (extra modules, clarify items, wrap-up). The assistant message is the next question only.
- Telegram **voice** (Mini App or bot) → Whisper STT → text (same pipeline)
- Bot DM: transitional until Mini App; then notifications + deep links

UX requirements: [14-Telegram-Customer-UX.md](14-Telegram-Customer-UX.md).

## Customer modes (entry)

| Mode | When | Outcome |
|------|------|---------|
| Create | New project | Full Discovery FSM → draft TZ → owner |
| Change | Existing project | Clarifications/edits → KG update, gap/contradiction checks; may revisit stages or escalate |
| Implementation feedback | After customer reviewed delivered MVP | Classify feedback; check vs approved TZ/KG; escalate contradictions |

## High-level FSM

```
PROJECT_CREATED
  → UNDERSTANDING_IDEA
  → BUSINESS_CONTEXT
  → USERS
  → FUNCTIONAL
  → DATA
  → NON_FUNCTIONAL
  → INTEGRATIONS
  → ACCEPTANCE
  → RISKS
  → REVIEW
  → READY_FOR_OWNER
```

Each stage contains **one or more TZ topics**. The agent advances **one topic per answer**, not one stage per message. Transitions may go backward when contradictions or gaps appear. Change / implementation-feedback modes may re-enter relevant stages without resetting the whole project.

`REVIEW` also runs a **clarify pass** (max 5 high-impact questions, one at a time, with a recommended option). Remaining gaps after the quota become `OpenQuestion`s or Assumptions in the draft TZ. This is not a new FSM stage.

After clarify, a short **closing wrap-up** (still `REVIEW`) asks: anything else to add; a specific budget figure if the customer wants one; and whether they already have a brief (file or paste from ChatGPT / another LLM). Attached text/markdown/docx is extracted into the TZ. «готово» skips leftover wrap-up and emits the draft.

When the draft is sent, the customer can **download the same TZ** (Markdown, Word, PDF) in the Mini App.

## TZ outline (start-of-build minimum)

Catalog: `discovery/tz_outline.py`. Tailored from GOST 34.602-2020, ISO/IEC/IEEE 29148, and practical PRDs for **simple** ASF MVPs (not a full government TZ).

The catalog is a **library**, not the interview script. `discovery/adapt.py` builds a per-project plan:

1. **Spine** (never skipped): purpose, solution type, MVP success, out of scope, must-have functions, primary scenario, acceptance, timeline, budget, contacts, preferred channel, **legal / 152-FZ**, risks
2. **Type / shape modules** — pages/CTA, bot vs Mini App, API resources, AI trigger, and so on
3. **Capability modules** — booking rules, notifications, API consumers, voice, failure path — only when the captured idea needs them
4. **Dynamic subsections** (`custom:…`) — heuristics add a few task-specific extras (for example who books a slot); Groq may add up to 8 when `LLM_PROVIDER=groq`
5. **Skips** — public identity / offer / visitor CTA / brand / pages / **promotion (SEO, ads)** / **design references and direction** when there is no public presence; Mini App already chosen → skip “bot vs Mini App”
6. **Wording** — after the idea is captured, remaining **questions, section titles, and choice chips** are rewritten from that task **and from later answers**. If the customer asked for an Android or iOS app, those chips appear on the solution-type question (even though native mobile is outside factory product types — website / bot / API / AI). Catalog chip ids stay; labels are retargeted, irrelevant chips are hidden, and extra `ctx:*` chips may echo a fact already given (heuristic always; Groq refines when `LLM_PROVIDER=groq`). The next turn announces added and skipped sections.

FSM stages stay the same. The agent still advances **one topic per answer**. Owner console virtual nodes follow the adapted outline (no new Section entity type).

| Section | What we must know to start coding |
|---------|-----------------------------------|
| Purpose and problem | What pain this solves |
| Solution type | website / bot / API / AI agent / automation / data admin / integration |
| Current process | How it is done today (object of automation) |
| MVP success | How v1 is judged |
| Out of scope | Explicit non-goals |
| Implementation timeline | Required vs expected date |
| Budget | Whether a budget exists and the order of magnitude |
| Contact details | Name, phone, email, Telegram; decision-maker if different |
| Preferred contact channel | Call, Telegram, email, messenger |
| Promotion / SEO | In v1: search, ads, analytics — or not part of development (affects estimate) |
| Users and roles | Who acts |
| Access | Public vs staff vs login vs API key |
| Must-have functions | v1 capabilities |
| Primary scenario | One happy path |
| Type-specific | Pages/CTA, bot vs Mini App, resources, or AI trigger/I/O |
| Public identity / offer / visitor CTA / brand / references / design | Only when the task has a public presence. Ask for examples they like and *what* to reuse; direction: calm/laconic vs modern motion vs loud 3D (affects estimate) |
| Capability subsections | Booking rules, notifications, API consumers, voice, failure path — only if the idea needs them |
| Dynamic subsections | Extra questions proposed for *this* task when the catalog is not enough |
| Data and records | What is stored / edited |
| Locale / UX | Language, device, brand (skippable when already implied) |
| Hosting / constraints | Where it runs, modest volume, PII |
| Legal / personal data | 152-FZ consent/policy, cookies, ads labelling, industry rules (affects estimate) |
| Integrations | Email, sheets, CRM, none |
| Acceptance | How the customer will check “done” |
| Operator | Who runs it after delivery |
| Risks | Blockers / unknowns |

Product types remain DEC-003: `website` | `telegram_bot` | `rest_service` | `ai_automation`. Customer shapes map onto those types:

| Customer asks for | Locked type |
|-------------------|-------------|
| Site / landing / brochure | `website` |
| Telegram bot | `telegram_bot` |
| REST API | `rest_service` |
| Database + admin tool | `rest_service` (`task_shape=database_tool`) |
| Integration between systems | `rest_service` (`task_shape=integration`) |
| AI agent or process automation | `ai_automation` |

Out of MVP even if asked: payments/SaaS, multi-tenant, unrestricted tool-using agents — escalate.

## When the customer does not know

Every topic offers **choices**. Those choices **follow previous answers**: if the customer said they book in WhatsApp, later chips mention WhatsApp instead of a generic “messengers”. Safe defaults may be marked **recommended** (for example “no payments in v1”, “greenfield”). Do **not** recommend goal, budget, or contacts. Topics like out-of-scope, roles, and integrations allow **several options in one answer**. Exclusive actions (pause, discuss with developer, ready) still submit immediately.

A **choice chip** is enough to close a section **unless** the topic needs implementation content (public name, service list, visitor contact, brand colors, **what they like in a reference**, lead destination, existing host/domain). Those sections close only with written details or an explicit stub chip («пока заглушки», «референсов нет»). **Vague free text** (`удобно`, `быстро`, `как обычно`, and similarly empty phrases) does **not** close the section: the same topic is re-asked once, then escalated to the developer.

Do **not** auto-close public-presence / `needs_substance` topics from the idea dump (keyword hits in earlier answers). Ask the section now. If the customer says they don’t know or «обсудить с разработчиком», escalate that section and **do not fill it by inference**.

URLs without “what to copy”, service-type chips without copy or a stub, “заявки в канал” without `@канал`, and “рядом с существующим сервером” without a host/domain are not enough — re-ask immediately. A short deadline plus loud 3D/вау restates the trade-off on `design_direction` (and in the clarify pass if it still slipped through).

The customer may:

- **«пауза»** — stop without sending a draft TZ
- **«продолжить»** — resume the current topic
- **«остальное с разработчиком»** — escalate uncovered required sections (and leftover clarifications), then emit draft TZ
- **«готово»** — emit draft TZ **only if** all applicable sections are captured or escalated **and** the quality floor holds (or leftover quality gaps are escalated); otherwise the agent lists what is still missing

Short messages and a single idea sentence must **not** finalize Discovery.

## Quality floor (unit tests for the TZ)

Deterministic checks in `discovery/quality.py` and `knowledge/coverage.py` (not implementation tests):

- At least one testable requirement (concrete object/outcome)
- Measurable MVP success (`success_mvp` captured or escalated)
- Scope bounded (`out_of_scope` captured or escalated)
- Optional: primary journey, testable acceptance, no unresolved blocking clarifications

Keyword section-coverage ≥ 0.4 does **not** replace this floor.

## Project statuses (runtime)

`NEW` → `INTERVIEW` → `ANALYZING` → `WAITING_CUSTOMER` → `WAITING_OWNER` → `READY` → `ARCHIVED`

## Readiness criteria (draft)

- Applicable TZ topics captured or escalated to developer
- Quality floor met or leftover quality items escalated
- MVP scope and non-goals stated
- Architectural sufficiency (enough to plan simple delivery)
- No blocking contradictions (or escalated to owner)

## Output artifacts

Derived from Knowledge Graph:

- Vision / problem statement
- User stories with Given–When–Then for the primary path
- TZ sections (from the **adapted** outline for this task)
- `FR-###` / `SC-###` lists
- Assumptions and Clarifications (clarify-pass answers)
- Open questions (including developer handoffs)
- Draft MVP scope
- Recommendations for owner review (gaps / contradictions from the reviewer scan)

## HITL

Owner receives draft TZ + gap list (bot path in MVP). Development planning starts only after approval. Implementation feedback that contradicts the approved TZ raises `HumanDecisionRequired`.

While the draft is with the owner (`WAITING_OWNER`), the customer may still send additions. Those messages are always recorded as requirements and merged into the draft TZ; they do not skip the owner gate or start planning. The Mini App offers a download of the same TZ (Markdown / Word / PDF) that went to the owner.

If applicable TZ sections are still missing (for example the outline gained content topics after a draft was sent), Discovery **resumes those questions**. Opening the Mini App workspace or sending a message asks the next missing section; the project returns to `WAITING_CUSTOMER` until the gaps are captured or escalated, then the draft is refreshed for the owner.
