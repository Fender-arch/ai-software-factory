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
- Motion with intent (one signature interaction). Mini App: see `.cursor/rules/miniapp-ux.mdc` (Experience Layer mascot is DEC-011; keep cyan/purple, honor calm / reduced motion)

## ASF itself

`apps/miniapp` already has a warm dark + cyan/purple voice — extend that, do not “normalize” it to SaaS gray. `apps/console` is an internal tool; keep it dense and graph-first, not a marketing template.

## Customer MVPs

Stamp `templates/DESIGN.md` via `mvp-customer-pack`. Implement the look from that file, not from the model’s default aesthetic.

## Component anti-pattern checklist

For component-level correctness (states, a11y, touch targets), use `.cursor/skills/ui-design-brain` (`components.md`). Distilled from the free rules of [studioalexwolf/cursor-design-rules](https://github.com/studioalexwolf/cursor-design-rules):

- **One primary CTA per screen** (filled). Others outlined / ghost. Vary hierarchy by *style*, not by extra colors.
- **One accent color for actions**; semantic red/green only for system states (error/success).
- **Circular buttons** are fixed `width === height`, `border-radius: 50%` — never hug/auto-sized.
- **Consistent padding** across same-type cards; **≤ 2 border-radius values + pill** site-wide.
- **Type:** body ≥ 16 px (14 px absolute floor), weight ≥ 400 below 18 px, contrast ≥ 4.5:1.
- **Labels verb + noun** ("Создать проект", not "OK"/"Отправить"); one h1 per page; 3+ text sizes for hierarchy.
- **Touch targets ≥ 44 px** (mini app incl. icon buttons); loading feedback < 100 ms, skeleton after ~400 ms.
- **Modals: ≥ 2 ways to close** (X + overlay/Escape); no modal-in-modal; focus trapped + returned.
- **Dark mode elevation:** surface lighter than background, elevated lighter still — don't flatten.
- **Never blame the user** in copy; describe the fix instead of the error.
