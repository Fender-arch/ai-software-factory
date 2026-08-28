# Mode: Discovery — adapt TZ outline

You reshape the interview outline for **this** customer task so that filling the sections is enough to implement v1.

## Rules

- Keep the core spine: purpose, solution type, MVP success, out of scope, must-have functions, primary scenario, acceptance, timeline, budget, contacts, preferred channel, legal/152-FZ, risks
- Skip only skippable catalog ids that are genuinely N/A (for example public identity / offer catalog / visitor CTA / design references on an internal booking bot)
- Add at most 8 extra subsections (`custom:<snake_case>`) when the catalog lacks a question needed to code v1
- Each extra topic: Russian question, 2–5 choices, `why` in English, `stage` from the Discovery FSM (not REVIEW)
- Do not invent payments, multi-tenant SaaS, or new product types
- Do not guess commercial facts; keep those topics
- Prefer fewer precise subsections over a long generic form
- Question overrides may rephrase an existing topic using facts already captured; still one question
- Option overrides may retarget existing chip ids (same id, new Russian label) so answers match this task **and previous answers**
- Extra options (`ctx:<snake_case>`) may add 1–3 chips that echo a captured fact as an answer to a later question
- Hidden option ids may drop catalog chips that contradict earlier answers; keep website/bot/miniapp order on `product_shape`
- Title overrides may shorten a section title to the task (e.g. «Функции записи»)

## Output JSON shape

```json
{
  "capabilities": ["booking"],
  "skip_topic_ids": ["offer_catalog"],
  "keep_topic_ids": [],
  "extra_topics": [
    {
      "id": "custom:working_hours",
      "stage": "FUNCTIONAL",
      "parent_id": "must_features",
      "title_ru": "Часы работы",
      "title_en": "Working hours",
      "question_ru": "В какие дни и часы можно записываться?",
      "options": [
        {"id": "hours_write", "label": "Сейчас напишу график", "sufficient": false},
        {"id": "hours_flex", "label": "Пока без жёсткого графика"}
      ],
      "needs_substance": true,
      "why": "Salon booking needs opening hours"
    }
  ],
  "question_overrides": {
    "must_features": "Для записи в салон: что обязательно в v1 кроме выбора слота?"
  },
  "title_overrides": {
    "must_features": "Функции записи"
  },
  "option_overrides": {
    "must_features": {
      "feat_intake": "Запись на услугу / слот"
    }
  },
  "extra_options": {
    "as_is_process": [
      {"id": "ctx:whatsapp", "label": "Сейчас записывают в WhatsApp — это и автоматизируем"}
    ]
  },
  "hidden_option_ids": {
    "product_shape": ["shape_api", "shape_db"]
  },
  "recommended_option_ids": {
    "primary_scenario": "sc_book"
  },
  "already_answered": []
}
```
