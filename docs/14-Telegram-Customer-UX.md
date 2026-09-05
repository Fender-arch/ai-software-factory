# 14 — Telegram Customer UX

| Field | Value |
|-------|-------|
| Status | Accepted |
| Version | 0.11 |
| Updated | 2026-09-05 |
| Owner | ASF Core |

ADR: [DEC-006](../decisions/DEC-006-Telegram-Mini-App.md), [DEC-011](../decisions/DEC-011-Experience-Layer-Mascot.md)

## Goal

All customer interaction with ASF happens in a **fullscreen Telegram Mini App** (Russian UI). The bot DM is entry + notifications only.

## Surfaces

| Surface | Role |
|---------|------|
| Bot DM | `/start` onboarding (RU), Menu Button / WebApp button, push notifications |
| Mini App (fullscreen) | Home actions, project list, project workspace (Discovery / change / implementation feedback) |
| Owner HITL (bot) | `/review`, `/approve`, `/changes`, `/reject`, `/plan`, `/export` (MVP) |

On phone, the Mini App calls `Telegram.WebApp.expand()` and `requestFullscreen()` (Bot API 8.0) so the UI uses the full screen, with `safeAreaInset` / `contentSafeAreaInset` padding. Layout is compact: one viewport for home actions; workspace is a flex column (thread scrolls, composer is **20–25%** of the workspace with File / Voice / Send inside that box). A compact **Experience Layer** mascot sits in the workspace chrome (not in the composer): Rive when `mascot.riv` is present, otherwise a gold/cyan SVG companion. Answer options open in a **popup** from «Варианты ответа», not as chips in the chat. New projects start with a **welcome popup** («Поехали»); TZ questions appear after that. `expand()` alone only grows the bottom sheet — that is why older builds overflowed.

## Why not a separate Telegram chat per project

A bot has **one** private chat with a user. Bot API cannot open a second DM “for this project”.

**Project chat** in ASF means: Mini App **project workspace** (thread UI bound to `project_id`). Optional Telegram forum topics / multi-chat layouts are Future.

## Home (after onboarding)

Short explanation: idea → Discovery → draft TZ → owner review → **client estimate** → tasks → simple MVP.

Then three actions (Russian labels in product UI):

1. **Создать проект** (Create project)
2. **Изменить проект** (Change project)
3. **Замечания к реализации** (Implementation feedback)

### Create project

1. Create `project` for this Telegram user.
2. Open that project’s workspace in the Mini App.
3. Run Discovery (text, **choice popup**, and/or voice). After create, a popup explains the interview; «Поехали» starts the first TZ question. The next assistant turn is **only the next question** (no “we recorded that” recap; options live in «Варианты ответа», not in the chat). Inside Telegram, voice is **recorded in the Mini App and sent to Groq Whisper** (`POST /stt/transcribe`); Web Speech is not used in the Telegram WebView because it often starts with no transcript. Outside Telegram (browser smoke with `?uid=`), Web Speech may still be used. The transcript is inserted into the composer, then ingest is the same as text. Interview covers TZ sections until the customer pauses, hands remaining items to the developer, or confirms «готово» after coverage and wrap-up (extra notes, budget figure, attached brief). The workspace shows a **progress bar** (gray track, green fill); the label is a **percent** or «ещё пара уточнений», not «N из M» section counts (DEC-014). Under the bar, `ws-meta` is a **human Russian HUD** (`customer_hud`: «ждём ваш ответ», «уточняем идею», «на ревью у владельца») — never raw `ProjectStatus`, workspace mode (`create`), Discovery stage (`NON_FUNCTIONAL`), topic id, product type, or chip id; unknown maps to «в работе». Multi-select sends **chip labels** into the chat (comma / «и»), not indexes (`1, 3`). A chip like «Сейчас напишу» / «напишу сам» / «свой вариант» stays in the draft and focuses the composer; the turn completes only after Send/Enter with labels + typed text. Ordinary chips still send on tap. After the draft is sent, the **TZ download card is a message in the thread** (not a sticky bar over the composer). Format buttons **send the file to the bot chat first** (`POST /projects/{id}/tz-send` → Telegram `sendDocument`); device download / `downloadFile` / `openLink` is only a fallback when chat_id or the Bot API is missing, with an explicit hint. A later owner-corrected TZ uses the same send channel (current KG export). When the customer adds notes after the draft, a **new version card** is appended in the thread.
4. Bot may notify when owner review is needed or when the customer must answer.
5. After the owner approves the draft TZ, the workspace shows a **client estimate card** (market range, “why it costs this”, disclaimer). Buttons: **Подтверждаю** / **Нужно обсудить**, plus **Markdown / Word / PDF** «Получить в чат бота» for the same quote (`POST /projects/{id}/estimate-send` → `sendDocument`; `GET .../estimate-export` only as fallback). Planner starts only after confirm ([DEC-012](../decisions/DEC-012-Client-Market-Estimate.md)). On success the Mini App says «файл отправлен в чат с ботом»; the TZ card stays in the thread.

### Change project

1. Show the user’s project list.
2. User picks a project.
3. Open workspace in **change** mode: clarifications and edits → KG update, gap / contradiction checks, possible re-open of Discovery stages or owner escalation.

### Implementation feedback

1. Show projects the user may comment on (after delivery / after they reviewed the MVP).
2. User picks a project and submits feedback (text/voice).
3. System classifies: defect / change request / new requirement.
4. Check against approved TZ / KG; on contradiction or blocking ambiguity → `HumanDecisionRequired` / owner path.
5. Persist as structured entities/relations (not free-form chat loss).

## Experience Layer (mascot)

Client-only companion for the interview (DEC-011). It does **not** change Discovery or HTTP contracts.

| Beat | When |
|------|------|
| `idle` | Workspace ready; back home |
| `listening` | Voice recording |
| `thinking` | Send / STT / workspace load |
| `got_answer` | Customer text (or choice) accepted |
| `got_voice` | Transcript inserted into the composer |
| `got_file` | File ingest succeeded |
| `draft_ready` | TZ download card is shown in the thread |
| `error` | Failed request / mic / STT |

**Calm:** button **«Спокойный режим»** persists in `localStorage` (`asf-calm-mode`). `prefers-reduced-motion` freezes or hides the mascot and foundry field; status text stays. Replace the placeholder: drop `apps/miniapp/mascot.riv` (state machine `Mascot`, inputs named like the beats). See `apps/miniapp/README.md`. Lip-sync / TTS mouth shapes are Future.

## Language

- Customer UI and bot copy: **Russian**
- Canonical KG storage and agent reasoning: **English** (Language Normalizer as infrastructure)

## Transitional bot commands

Until Mini App ships, customer may still use `/new`, `/use`, text/voice in the bot DM. Those paths must remain compatible with the same `core.services` ingest. Prefer Mini App once available.

## Notifications (bot DM)

Examples: Discovery needs an answer; draft TZ sent to owner; owner requested changes; **client estimate ready / confirmed / discuss**; MVP / export ready. Deep-link or WebApp button should reopen the relevant Mini App project workspace when possible.

## Out of scope here

- Owner portal inside Mini App (later)
- Forum topics / separate Telegram chats per project (`backlog/Future.md`)
- Web Human Review Portal (already Future; owner TZ graph console is DEC-007, not a customer portal)
