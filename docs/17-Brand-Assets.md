# 17 — Uni 4 IT brand assets

| Field | Value |
|-------|-------|
| Status | Accepted |
| Version | 0.4 |
| Updated | 2026-09-06 |
| Owner | ASF Core |

Platform chrome (Mini App + owner console). Not a customer-MVP stamp. Tokens: `apps/miniapp/DESIGN.md`.

## Files

Canonical copies live in `apps/miniapp/brand/` (served at `/miniapp/brand/…`). The same SVGs are copied to `apps/console/brand/` for the owner header.

| File | Use |
|------|-----|
| `logo-v2.png` | Canonical Mini App lockup (mark + Uni 4 IT + UNIVERSAL IT SOLUTIONS) |
| `logo-full.svg` | Vector lockup (navy ink, transparent) |
| `logo-full-on-dark.svg` | Same lockup, cream ink |
| `logo-wordmark.svg` / `logo-wordmark-on-dark.svg` | Mark + Uni 4 IT without tagline |
| `logo-mark.svg` | U+4 pixel mark, cyan→purple |
| `mascot-bust.png` | Experience Layer companion (full character, transparent) |
| `mascot-head.png` | Tighter crop of the same head |

Cyan `#00D2FF` · purple `#9D50BB`. No navy rectangle behind the lockup — the Mini App background is already dark. Do not overwrite Telegram’s `--tg-theme-*` names — consume them as `--tg-bg` / `--tg-text` fallbacks next to `--brand-cyan` / `--brand-purple`.

## Mini App

- Home header: full `logo-v2.png` lockup (`object-fit: contain`, never crop the mark); slogan only «От идеи до продукта»
- Workspace chrome: the same full lockup; mascot + «Проект: {name}» + status share one even row
- Calm mode lives on Settings, not in the home/workspace header
- Background: muted cyan/purple Matrix rain (not green particles)
- Mascot: Uni 4 IT unicorn in a hoodie + VR visor; CSS motion on the same DEC-011 beats (`idle`, `listening`, `thinking`, `got_*`, `draft_ready`, `error`) — breathe, glance, periodic wave. Slot is a reserved box so motion does not shove the composer. Optional `mascot.riv` remains progressive enhancement. No Rive Editor required for this slice.

## Brand tokens (Mini App)

Canonical values live in `apps/miniapp/DESIGN.md`. Do not invent a second palette.

| Token | Value | Role |
|-------|-------|------|
| `--bg` | `#07060b` | Deep foundry ground |
| `--text` | `#f4efe6` | Cream ink (wordmark) |
| `--muted` | `#a89888` | Soft warm gray |
| `--accent` | `#00d2ff` | Uni 4 IT cyan — primary |
| `--ember` | `#ff6b2c` | Error only, never CTA |
| `--brand-cyan` | `#00d2ff` | Uni 4 IT mark |
| `--brand-purple` | `#9d50bb` | Uni 4 IT mark |
| `--brand-grad` | cyan→purple | Primary CTA + mark |

No yellow/gold. Primary is cyan→purple. Layout rhythm (`--space-*`, `--radius`, `--fs-*`) is spacing only.

## Console

`/console/` header shows the on-dark wordmark next to the ASF product line. Graph density and HITL stay unchanged.
