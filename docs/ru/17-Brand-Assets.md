# 17 — Бренд-ассеты Uni 4 IT

> Перевод. Канон: [`docs/17-Brand-Assets.md`](../17-Brand-Assets.md)

| Поле | Значение |
|------|----------|
| Status | Accepted |
| Version | 0.3 |
| Updated | 2026-09-05 |
| Owner | ASF Core |

Хром платформы (Mini App + консоль владельца). Не штамп customer-MVP. Токены: `apps/miniapp/DESIGN.md`.

## Файлы

Канон — `apps/miniapp/brand/` (отдаётся как `/miniapp/brand/…`). Те же SVG скопированы в `apps/console/brand/` для шапки консоли.

| Файл | Назначение |
|------|------------|
| `logo-full.svg` | Знак + «Uni 4 IT» + подпись UNIVERSAL IT SOLUTIONS (тёмные буквы, без подложки) |
| `logo-full-on-dark.svg` | Тот же lockup, светлые буквы для тёмного foundry |
| `logo-wordmark.svg` / `logo-wordmark-on-dark.svg` | Знак + Uni 4 IT без подписи |
| `logo-mark.svg` | Пиксельный знак U+4, градиент cyan→purple (шапка чата) |
| `mascot-bust.png` | Компаньон Experience Layer (весь персонаж, прозрачный фон) |
| `mascot-head.png` | Более плотный кроп головы |

Cyan `#00D2FF` · purple `#9D50BB`. Navy-прямоугольника под логотипом нет — фон приложения уже тёмный. Имена `--tg-theme-*` не перезаписывать — только читать как fallback (`--tg-bg` / `--tg-text`) рядом с `--brand-cyan` / `--brand-purple`.

## Mini App

- Старт: полный lockup на своей строке (на низкой высоте — wordmark); хук — под логотипом
- Шапка workspace: компактный mark по центру между «назад» и спокойным режимом; слот маскота не занимает
- Маскот: единорог Uni 4 IT в худи и VR-visor; CSS-реакции на те же биты DEC-011 (`idle`, `listening`, `thinking`, `got_*`, `draft_ready`, `error`) — дыхание, взгляд, периодический взмах. Слот — фиксированная коробка, анимация не толкает композер. `mascot.riv` по-прежнему опционален. Редактор Rive для этого слайса не нужен.

## Бренд-токены (Mini App)

Канон — `apps/miniapp/DESIGN.md`. Вторую палитру не выдумывать.

| Токен | Значение | Роль |
|-------|----------|------|
| `--bg` | `#07060b` | Тёмный foundry-фон |
| `--text` | `#f4efe6` | Кремовые буквы (как в wordmark) |
| `--muted` | `#a89888` | Тёплый soft gray |
| `--accent` | `#e8c36a` | Foundry gold — основной CTA |
| `--ember` | `#ff6b2c` | Жар / ошибка |
| `--brand-cyan` | `#00d2ff` | Знак Uni 4 IT |
| `--brand-purple` | `#9d50bb` | Знак Uni 4 IT |
| `--brand-grad` | cyan→purple | Знак и тонкая пара к золоту, не SaaS-hero |

Неожиданная пара: gold/ember CTA + знак cyan→purple. Ритм (`--space-*`, `--radius`, `--fs-*`) — только сетка, не новые цвета.

## Консоль

В шапке `/console/` — on-dark wordmark рядом с линейкой ASF. Плотность графа и HITL без изменений.
