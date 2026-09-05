# 17 — Uni 4 IT brand assets

| Field | Value |
|-------|-------|
| Status | Accepted |
| Version | 0.2 |
| Updated | 2026-09-05 |
| Owner | ASF Core |

Platform chrome (Mini App + owner console). Not a customer-MVP stamp. Tokens: `apps/miniapp/DESIGN.md`.

## Files

Canonical copies live in `apps/miniapp/brand/` (served at `/miniapp/brand/…`). The same SVGs are copied to `apps/console/brand/` for the owner header.

| File | Use |
|------|-----|
| `logo-full.svg` | Mark + wordmark + tagline UNIVERSAL IT SOLUTIONS (navy ink, transparent) |
| `logo-full-on-dark.svg` | Same lockup, cream ink for the dark foundry UI |
| `logo-wordmark.svg` / `logo-wordmark-on-dark.svg` | Mark + Uni 4 IT without tagline |
| `logo-mark.svg` | U+4 pixel mark, cyan→purple (chat chrome) |
| `mascot-bust.png` | Experience Layer companion (full character, transparent) |
| `mascot-head.png` | Tighter crop of the same head |

Cyan `#00D2FF` · purple `#9D50BB`. No navy rectangle behind the lockup — the Mini App background is already dark. Do not overwrite Telegram’s `--tg-theme-*` names — consume them as `--tg-bg` / `--tg-text` fallbacks next to `--brand-cyan` / `--brand-purple`.

## Mini App

- Home header: full lockup (wordmark on short viewports)
- Workspace chrome: compact mark — does not replace the mascot slot
- Mascot: Uni 4 IT unicorn in a hoodie + VR visor; CSS motion on the same DEC-011 beats (`idle`, `listening`, `thinking`, `got_*`, `draft_ready`, `error`) — breathe, glance, periodic wave. Optional `mascot.riv` remains progressive enhancement. No Rive Editor required for this slice.

## Console

`/console/` header shows the on-dark wordmark next to the ASF product line. Graph density and HITL stay unchanged.
