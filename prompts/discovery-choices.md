# Mode: Discovery — adapt choice chips for the next question

Rewrite the **answer options** for this one TZ topic so they fit the customer's task and what they already said. Deterministic Discovery still owns stage advances.

## Rules

- Keep existing catalog option ids unless you hide one
- Russian labels, max 180 characters, concrete and selectable
- Use facts from `previous_answers` (tools, current process, who acts). Do not invent commercial facts (budget, contacts, dates)
- You may hide catalog ids that contradict earlier answers
- You may add at most 3 extra options with ids `ctx:<snake_case>` that echo a previous fact as a real answer to **this** question
- If this topic is `product_shape` and `previous_answers` mention Android, iOS, or a mobile app, extra_options **must** include «Приложение для Android» and «Приложение для iOS» (`ctx:shape_android`, `ctx:shape_ios`)
- Do not hide `discuss_with_developer`
- Leave at least two catalog options visible
- Do not change the question text here

## Output JSON shape

```json
{
  "option_overrides": {
    "asis_chat": "Сейчас записывают в WhatsApp, как вы сказали"
  },
  "hidden_option_ids": ["asis_system"],
  "extra_options": [
    {"id": "ctx:notebook", "label": "Тетрадка остаётся, бот только слоты"}
  ],
  "recommended_option_id": "asis_chat"
}
```
