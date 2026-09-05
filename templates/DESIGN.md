# DESIGN.md — anti-slop starter for an ASF customer MVP

Fill this file **before** writing UI. Tokens come from the approved TZ (`brand_assets`, `design_references`, `design_direction`). Do not leave the placeholders if the TZ already decided.

Companion skill: `.cursor/skills/anti-slop-design/SKILL.md`.

## Product

- Name / public identity:
- Product type: `website` | `telegram_bot` | `rest_service` | `ai_automation` | `mobile_native`
- One-line offer:
- Audience:

## Voice

Describe the character in three adjectives that are **not** “modern, clean, professional”.

- Character:
- Type: pick a distinct pairing (example: newsroom serif + mono labels — **not** Inter + system UI as the brand face)
- Copy tone: short, concrete, no “unlock your potential”

## Tokens

Replace every `CHANGE_ME`. Do **not** use Tailwind defaults `blue-500`, `indigo-500`, `violet-500`, or `gray-800` as the primary look.

```css
:root {
  --bg: CHANGE_ME;       /* page / screen */
  --ink: CHANGE_ME;      /* body text */
  --muted: CHANGE_ME;    /* secondary text */
  --accent: CHANGE_ME;   /* one signature color */
  --accent-ink: CHANGE_ME;
  --danger: CHANGE_ME;
  --line: CHANGE_ME;
  --radius: CHANGE_ME;   /* e.g. 4px or 18px — pick a stance */
  --font-display: CHANGE_ME;
  --font-body: CHANGE_ME;
}
```

## Layout rhythm

- First viewport does **one** job (the TZ primary scenario / CTA).
- No obligatory “3 feature cards + FAQ + logo cloud”.
- Spacing scale: one named rhythm (tight editorial **or** airy poster — not both).

## Motion

- One signature interaction (hover, page enter, Mini App send).
- No decorative gradient loops or generic AI orbs.
- Native: system motion; do not fake a marketing site inside the app.

## Forbidden (primary look)

- Inter / Roboto as brand type
- Purple–blue SaaS gradients
- Glass cards on `gray-800`
- Stock hero illustrations of smiling dashboards
- Lorem / “AI-powered platform” filler

## References

From TZ: URLs + **what to copy** (type, color, motion). If none, stay with tokens above — do not invent a second aesthetic mid-build.

## Acceptance

A stranger can describe the look in one sentence that does not apply to a random Tailwind template.
