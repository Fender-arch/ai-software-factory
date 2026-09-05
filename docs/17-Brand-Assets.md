# 17 — UNI4IT brand assets

| Field | Value |
|-------|-------|
| Status | Accepted |
| Version | 0.1 |
| Updated | 2026-09-05 |
| Owner | ASF Core |

Platform chrome (Mini App + owner console). Not a customer-MVP stamp. Tokens: `apps/miniapp/DESIGN.md`.

## Files

Canonical copies live in `apps/miniapp/brand/` (served at `/miniapp/brand/…`). The same SVGs are copied to `apps/console/brand/` for the owner header.

| File | Use |
|------|-----|
| `logo-full.svg` | Wordmark + tagline «УНИВЕРСАЛЬНЫЕ РЕШЕНИЯ ДЛЯ IT» (navy ink) |
| `logo-full-on-dark.svg` | Same lockup, cream ink for the dark foundry UI |
| `logo-wordmark.svg` / `logo-wordmark-on-dark.svg` | UNI4IT without tagline |
| `logo-mark.svg` | Lavender **4** + spiral horn (chat chrome) |
| `mascot-bust.png` | Experience Layer companion (character only, transparent) |
| `mascot-head.png` | Tighter crop of the same bust |

Navy `#222B45` · lavender `#9B98E1`. Dark surfaces use cream ink; the **4** and horn stay lavender. Do not overwrite Telegram’s `--tg-theme-*` names — consume them as `--tg-bg` / `--tg-text` fallbacks next to `--brand-navy` / `--brand-lavender`.

## Mini App

- Home header: full lockup (wordmark on short viewports)
- Workspace chrome: compact mark — does not replace the mascot slot
- Mascot: UNI4IT unicorn-robot PNG; CSS motion on the same DEC-011 beats (`idle`, `listening`, `thinking`, `got_*`, `draft_ready`, `error`). Optional `mascot.riv` remains progressive enhancement. No Rive Editor required for this slice.

## Console

`/console/` header shows the on-dark wordmark next to the ASF product line. Graph density and HITL stay unchanged.
