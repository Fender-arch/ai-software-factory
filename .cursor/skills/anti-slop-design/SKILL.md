---
name: anti-slop-design
description: >-
  Design distinctive UI that avoids Tailwind blue-gray SaaS slop, Inter+purple
  clichés, and generic AI aesthetics. Use when editing CSS, HTML, JS, Mini App,
  owner console, or a customer MVP frontend. Require DESIGN.md before visual work.
---

# Anti-slop / anti-template UI

Vibe-coding defaults to the same landing: Inter, indigo/purple gradient, `gray-800` cards, `blue-500` buttons, hero + 3 feature cards + FAQ. **Forbidden as the primary look.**

## Before any UI

1. Read `DESIGN.md` at the repo root (customer) or `templates/DESIGN.md` (stamp it first).
2. If `DESIGN.md` is missing, draft it from the TZ brand tokens — do not invent a second design system in CSS.
3. Rule: `.cursor/rules/design-anti-slop.mdc`.

## Hard bans (primary look)

- Inter / Roboto / Arial as the **brand** face (system UI for chrome is fine)
- Default Tailwind `blue-500`, `indigo-500`, `violet-500`, `gray-800` as the palette
- Purple-to-blue hero gradients, glassmorphism-for-its-own-sake, generic “AI orb” backgrounds
- Cookie-cutter SaaS sections with stock copy (“Unlock your potential”)
- Centered card-on-gray-canvas dashboards with no typographic voice

## Required

- Distinct **brand tokens** (background, ink, accent, danger, radius, motion) named in `DESIGN.md`
- One unexpected pairing (type, color temperature, or layout rhythm) that a stranger could describe
- Real content hierarchy: type scale and spacing do the work, not more boxes
- Motion with intent (one signature interaction). Mini App: see `.cursor/rules/miniapp-ux.mdc` (mascot / Experience Layer is Future)

## ASF itself

`apps/miniapp` already has a warm dark + gold/cyan voice — extend that, do not “normalize” it to SaaS gray. `apps/console` is an internal tool; keep it dense and graph-first, not a marketing template.

## Customer MVPs

Stamp `templates/DESIGN.md` via `mvp-customer-pack`. Implement the look from that file, not from the model’s default aesthetic.
