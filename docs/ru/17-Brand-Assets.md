# 17 — Бренд-ассеты UNI4IT

> Перевод. Канон: [`docs/17-Brand-Assets.md`](../17-Brand-Assets.md)

| Поле | Значение |
|------|----------|
| Status | Accepted |
| Version | 0.1 |
| Updated | 2026-09-05 |
| Owner | ASF Core |

Хром платформы (Mini App + консоль владельца). Не штамп customer-MVP. Токены: `apps/miniapp/DESIGN.md`.

## Файлы

Канон — `apps/miniapp/brand/` (отдаётся как `/miniapp/brand/…`). Те же SVG скопированы в `apps/console/brand/` для шапки консоли.

| Файл | Назначение |
|------|------------|
| `logo-full.svg` | Слово + подпись «УНИВЕРСАЛЬНЫЕ РЕШЕНИЯ ДЛЯ IT» (navy) |
| `logo-full-on-dark.svg` | Тот же lockup, светлые буквы для тёмного foundry |
| `logo-wordmark.svg` / `logo-wordmark-on-dark.svg` | UNI4IT без подписи |
| `logo-mark.svg` | Лавандовая **4** + спиральный рог (шапка чата) |
| `mascot-bust.png` | Компаньон Experience Layer (только персонаж, прозрачный фон) |
| `mascot-head.png` | Более плотный кроп того же бюста |

Navy `#222B45` · lavender `#9B98E1`. На тёмном фоне буквы кремовые; **4** и рог остаются лавандовыми. Имена `--tg-theme-*` не перезаписывать — только читать как fallback (`--tg-bg` / `--tg-text`) рядом с `--brand-navy` / `--brand-lavender`.

## Mini App

- Старт: полный lockup (на низкой высоте — wordmark)
- Шапка workspace: компактный mark, слот маскота не занимает
- Маскот: робот-единорог UNI4IT (PNG); CSS-реакции на те же биты DEC-011 (`idle`, `listening`, `thinking`, `got_*`, `draft_ready`, `error`). `mascot.riv` по-прежнему опционален. Редактор Rive для этого слайса не нужен.

## Консоль

В шапке `/console/` — on-dark wordmark рядом с линейкой ASF. Плотность графа и HITL без изменений.
