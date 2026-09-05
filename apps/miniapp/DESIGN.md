# DESIGN.md — ASF Mini App + Uni 4 IT brand

Platform chrome (not a customer-MVP stamp). Tokens match the Uni 4 IT lockup:
cyan `#00D2FF` → purple `#9D50BB`. Do not restyle toward Inter / indigo / `gray-800`.
No yellow / gold / foundry-ember as primary.

## Product

- Public identity: **Uni 4 IT** (wordmark) · product: ASF (ТЗ → MVP)
- Surface: Telegram Mini App (dark foundry) + owner console
- Offer: от идеи до продукта
- Audience: заказчик в Telegram; владелец в `/console/`

## Voice

- Character: compact, slightly wry, digital — not SaaS-indigo, not gold-luxury
- Type: system UI for chrome; wordmark is geometric bold sans
- Copy: short Russian, no “unlock your potential”, no bureaucratic TZ essays
- Home slogan is only **«От идеи до продукта»**. No pipeline chips, no marketing lead.

## Tokens

```css
:root {
  --bg: #07060b;
  --text: #f4efe6;
  --muted: #a89888;
  --accent: #00d2ff;          /* Uni 4 IT cyan — primary */
  --accent-pressed: #12b8e0;
  --accent-text: #061318;
  --cyan: #00d2ff;
  --ember: #ff6b2c;           /* error only, never CTA */
  --brand-cyan: #00d2ff;      /* Uni 4 IT mark */
  --brand-purple: #9d50bb;    /* Uni 4 IT mark */
  --brand-navy: #0b1220;      /* on-light ink only */
  --brand-grad: linear-gradient(135deg, #00d2ff, #9d50bb);
  /* Telegram injects --tg-theme-* on <html>; never overwrite those names */
}
```

Primary CTA is `--brand-grad` (cyan → purple). Do not reintroduce `#e8c36a` / gold.

## Rhythm (layout tokens — not a second palette)

```css
:root {
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 24px;
  --radius-sm: 8px;
  --radius: 12px;
  --radius-lg: 16px;
  --fs-xs: 0.68rem;
  --fs-sm: 0.78rem;
  --fs-md: 0.9rem;
  --fs-lg: 1.05rem;
}
```

Home lockup sits on its own row; the hook line is underneath, not beside the mark.
Workspace uses the **full** lockup in chrome (`logo-v2.png`, `object-fit: contain` —
never crop the cyan-purple mark or the floating pixels). Mascot + «Проект: {name}»
+ status line share one even row. Mascot slot is a reserved box (`contain: layout`,
overflow clipped) so breathe / glance / wave cannot shift the thread or composer.
Progress HUD stays gray track + green fill (DEC-014).

«Спокойный режим» lives on the Settings screen, not in the home or workspace header.

## Brand assets

Canonical files: `apps/miniapp/brand/` (SVGs still copied to `apps/console/brand/`
for the owner header). Mini App chrome uses the raster lockup.

| File | Use |
|------|-----|
| `logo-v2.png` | Canonical Mini App lockup (mark + «Uni 4 IT» + UNIVERSAL IT SOLUTIONS) |
| `logo-full.svg` | Vector source of the same lockup |
| `logo-wordmark.svg` | Mark + «Uni 4 IT» (console / fallback) |
| `logo-mark.svg` | U+4 pixel mark (small chrome if a full lockup does not fit) |
| `mascot-bust.png` | Experience Layer companion (full character, transparent) |
| `mascot-head.png` | Tighter head crop of the same sprite |

`logo-v2.png` already sits on navy. Keep `object-fit: contain` and `overflow: visible`
on the lockup so the left mark and the three pixels above the stem stay fully visible.
The mark always carries the cyan→purple gradient.

## Motion

- Signature: mascot breathes, glances (`rotateY`), and periodically waves; stronger on Discovery beats (`idle`, `listening`, `thinking`, `got_*`, `draft_ready`, `error`)
- Background: muted Matrix rain in brand cyan/purple (not green). No particle field.
- Honor `prefers-reduced-motion` and «Спокойный режим»: rain becomes a static frame (or off)
- Rive remains optional progressive enhancement — PNG is the MVP companion

## Settings

- Current Telegram user (WebApp `initDataUnsafe.user` or `?uid=`)
- Bot `@UNI4ITBot`
- Contacts: Дмитрий Нижебецкий, тел. `8 903 151 7888`
- Owner Telegram: `OWNER_CONTACT_TELEGRAM` if injected; otherwise «не задан»
