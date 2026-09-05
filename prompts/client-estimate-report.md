# Client market estimate report

Write a short Russian narrative for the **customer** (not the studio owner).

You receive a work package from the Knowledge Graph, market rate bands with logged sources, and the customer's Discovery budget hint if any.

## Rules

- Explain the composition of work, why the hours and money look like this, residual risks, and what is **not** in the quote.
- Compare to the customer's stated budget envelope when one exists. The Discovery chip is context, not a quote.
- Do not invent rates, sources, or "Admin analytics". Only use sources from the payload.
- Do not present this as a legal offer or invoice.
- Do not mention the owner's internal heuristic rate.
- Keep it concrete: 4–8 short paragraphs or a compact markdown structure.

## Output JSON shape

```json
{
  "title": "Почему столько стоит",
  "body": "Русский текст отчёта (markdown)."
}
```
