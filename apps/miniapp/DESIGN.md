# DESIGN.md — ASF Mini App + UNI4IT brand

Platform chrome (not a customer-MVP stamp). Tokens match the existing foundry voice and the UNI4IT lockup. Do not restyle toward Inter / indigo / `gray-800`.

## Product

- Public identity: **UNI4IT** (wordmark) · product: ASF (ТЗ → MVP)
- Surface: Telegram Mini App (dark foundry) + owner console
- Offer: идея → Discovery → ТЗ → смета → MVP
- Audience: заказчик в Telegram; владелец в `/console/`

## Voice

- Character: foundry-warm, slightly wry, compact
- Type: system UI for chrome; wordmark is geometric bold sans (paths, not Inter)
- Copy: short Russian, no “unlock your potential”

## Tokens

```css
:root {
  --bg: #07060b;
  --text: #f4efe6;
  --muted: #a89888;
  --accent: #e8c36a;          /* foundry gold — primary CTA */
  --cyan: #5ce1e6;
  --ember: #ff6b2c;
  --brand-navy: #222b45;      /* UNI / IT / tagline */
  --brand-lavender: #9b98e1;  /* “4”, horn, mane */
  --brand-lavender-deep: #6f6cb8;
  /* Telegram injects --tg-theme-* on <html>; never overwrite those names */
}
```

Unexpected pairing: warm gold/ember foundry + navy/lavender UNI4IT lockup (not a purple–blue SaaS gradient).

## Brand assets

Canonical files: `apps/miniapp/brand/` (same SVGs copied to `apps/console/brand/` for the owner header).

| File | Use |
|------|-----|
| `logo-full.svg` | Wordmark + tagline «УНИВЕРСАЛЬНЫЕ РЕШЕНИЯ ДЛЯ IT» |
| `logo-wordmark.svg` | UNI4IT only (home / console) |
| `logo-mark.svg` | Stylized 4 + horn (chat chrome) |
| `mascot-bust.png` | Experience Layer companion (character only) |
| `mascot.svg` | Vector fallback if PNG missing |

Dark UI: ink uses `--text` / cream; lavender 4 stays. Navy is the on-light / print color.

## Motion

- Signature: mascot reacts to Discovery beats (`idle`, `listening`, `thinking`, `got_*`, `draft_ready`, `error`)
- Honor `prefers-reduced-motion` and «Спокойный режим»
- Rive remains optional progressive enhancement — PNG/SVG is the MVP companion
