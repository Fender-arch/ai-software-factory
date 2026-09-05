# DEC-011 — Experience Layer: Rive mascot in Mini App MVP

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2026-09-05 |
| Supersedes | Future-only mascot line in [DEC-009](DEC-009-Agent-Toolkit-Reuse.md) and `.cursor/rules/miniapp-ux.mdc` |

## Context

DEC-006 made the Telegram Mini App the customer workspace. DEC-009 treated a Rive / Experience Layer mascot as Future so the toolkit stay would not pull a motion runtime into MVP. Dmitry wants that slice **now**: a calm interview companion that reacts to Discovery beats (listening, thinking, answer, voice, file, draft ready, error) without turning the Mini App into a marketing landing or a second owner console.

A server event bus, Redis, Neo4j, lip-sync, and TTS-driven mouth shapes are still out of scope.

## Decision

1. **Experience Layer is an MVP Mini App slice.** A compact mascot slot may run `@rive-app/canvas` (CDN, progressive) plus a client-only event bus. Discovery / API contracts, HITL, and secrets stay unchanged.
2. **Events (client UX only):** `idle`, `listening` / `thinking`, `got_answer`, `got_voice`, `got_file`, `draft_ready`, `error`. Mapped from existing `apps/miniapp/app.js` actions — not from a backend broker.
3. **Calm path:** `prefers-reduced-motion` freezes or hides the mascot and keeps status text. A Russian **«Спокойный режим»** toggle persists in `localStorage`.
4. **Progressive enhancement:** if the `.riv` asset or runtime is missing (Telegram WebView, offline, CDN fail), a CSS/SVG placeholder keeps the same events. Drop in a branded `mascot.riv` when design is ready.
5. **Not in this slice:** lip-sync / TTS puppet, owner-console mascot, server event sourcing.

Related: [DEC-006](DEC-006-Telegram-Mini-App.md), [docs/14-Telegram-Customer-UX.md](../docs/14-Telegram-Customer-UX.md).

## Consequences

- `.cursor/rules/miniapp-ux.mdc` allows the Rive runtime and the Mini App event bus; compact workspace, RU UI, anti-slop, and 20–25% composer stay mandatory.
- DEC-009’s “Rive = Future” row is superseded for this slice; wholesale vendoring of external Rive *kits* is still rejected.
- Lip-sync / spoken mascot remains `backlog/Future.md`.
