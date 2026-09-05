# DESIGN.md — ASF Mini App + Uni 4 IT brand

Platform chrome (not a customer-MVP stamp). Tokens match the foundry voice and the Uni 4 IT lockup. Do not restyle toward Inter / indigo / `gray-800`.

## Product

- Public identity: **Uni 4 IT** (wordmark) · product: ASF (ТЗ → MVP)
- Surface: Telegram Mini App (dark foundry) + owner console
- Offer: идея → Discovery → ТЗ → смета → MVP
- Audience: заказчик в Telegram; владелец в `/console/`

## Voice

- Character: foundry-warm, slightly wry, compact
- Type: system UI for chrome; wordmark is geometric bold sans
- Copy: short Russian, no “unlock your potential”, no bureaucratic TZ essays

## Tokens

```css
:root {
  --bg: #07060b;
  --text: #f4efe6;
  --muted: #a89888;
  --accent: #e8c36a;          /* foundry gold — primary CTA */
  --cyan: #5ce1e6;
  --ember: #ff6b2c;
  --brand-cyan: #00d2ff;      /* Uni 4 IT mark */
  --brand-purple: #9d50bb;    /* Uni 4 IT mark */
  --brand-navy: #0b1220;      /* on-light ink only */
  --brand-grad: linear-gradient(135deg, #00d2ff, #9d50bb);
  /* Telegram injects --tg-theme-* on <html>; never overwrite those names */
}
```

Unexpected pairing: warm gold/ember foundry + cyan→purple Uni 4 IT mark (pixel U+4, not a SaaS indigo hero).

## Brand assets

Canonical files: `apps/miniapp/brand/` (same SVGs copied to `apps/console/brand/` for the owner header).

| File | Use |
|------|-----|
| `logo-full.svg` | Mark + «Uni 4 IT» + tagline UNIVERSAL IT SOLUTIONS |
| `logo-wordmark.svg` | Mark + «Uni 4 IT» (home / console) |
| `logo-mark.svg` | U+4 pixel mark (chat chrome) |
| `mascot-bust.png` | Experience Layer companion (full character, transparent) |
| `mascot-head.png` | Tighter head crop of the same sprite |

Dark UI uses `*-on-dark.svg` (cream ink, transparent — no navy plate). On-light SVGs use `--brand-navy` ink. The mark always carries the cyan→purple gradient.

## Motion

- Signature: mascot breathes, glances (`rotateY`), and periodically waves; stronger on Discovery beats (`idle`, `listening`, `thinking`, `got_*`, `draft_ready`, `error`)
- Honor `prefers-reduced-motion` and «Спокойный режим»
- Rive remains optional progressive enhancement — PNG is the MVP companion
