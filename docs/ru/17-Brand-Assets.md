# 17 — Бренд-ассеты Uni 4 IT

> Перевод. Канон: [`docs/17-Brand-Assets.md`](../17-Brand-Assets.md)

| Поле | Значение |
|------|----------|
| Status | Accepted |
| Version | 0.4 |
| Updated | 2026-09-06 |
| Owner | ASF Core |

Хром платформы (Mini App + консоль владельца). Не штамп customer-MVP. Токены: `apps/miniapp/DESIGN.md`.

## Файлы

Канон — `apps/miniapp/brand/` (отдаётся как `/miniapp/brand/…`). Те же SVG скопированы в `apps/console/brand/` для шапки консоли.

| Файл | Назначение |
|------|------------|
| `logo-v2.png` | Канон Mini App: знак + «Uni 4 IT» + UNIVERSAL IT SOLUTIONS |
| `logo-full.svg` | Векторный lockup (тёмные буквы, без подложки) |
| `logo-full-on-dark.svg` | Тот же lockup, светлые буквы |
| `logo-wordmark.svg` / `logo-wordmark-on-dark.svg` | Знак + Uni 4 IT без подписи |
| `logo-mark.svg` | Пиксельный знак U+4, градиент cyan→purple |
| `mascot-bust.png` | Компаньон Experience Layer (весь персонаж, прозрачный фон) |
| `mascot-head.png` | Более плотный кроп головы |

Cyan `#00D2FF` · purple `#9D50BB`. Navy-прямоугольника под логотипом нет — фон приложения уже тёмный. Имена `--tg-theme-*` не перезаписывать — только читать как fallback (`--tg-bg` / `--tg-text`) рядом с `--brand-cyan` / `--brand-purple`.

## Mini App

- Старт: полный `logo-v2.png` (`object-fit: contain`, знак не обрезать); слоган только «От идеи до продукта»
- Шапка workspace: тот же полный lockup; маскот + «Проект: {name}» + статус — одна ровная строка
- Спокойный режим — в Настройках, не в шапке home/workspace
- Фон: приглушённый Matrix-дождь cyan/purple, не зелёные частицы
- Маскот: единорог Uni 4 IT в худи и VR-visor; CSS-реакции на те же биты DEC-011 (`idle`, `listening`, `thinking`, `got_*`, `draft_ready`, `error`) — дыхание, взгляд, периодический взмах. Слот — фиксированная коробка, анимация не толкает композер. `mascot.riv` по-прежнему опционален. Редактор Rive для этого слайса не нужен.

## Бренд-токены (Mini App)

Канон — `apps/miniapp/DESIGN.md`. Вторую палитру не выдумывать.

| Токен | Значение | Роль |
|-------|----------|------|
| `--bg` | `#07060b` | Тёмный foundry-фон |
| `--text` | `#f4efe6` | Кремовые буквы (как в wordmark) |
| `--muted` | `#a89888` | Тёплый soft gray |
| `--accent` | `#00d2ff` | Cyan Uni 4 IT — основной |
| `--ember` | `#ff6b2c` | Только ошибка, не CTA |
| `--brand-cyan` | `#00d2ff` | Знак Uni 4 IT |
| `--brand-purple` | `#9d50bb` | Знак Uni 4 IT |
| `--brand-grad` | cyan→purple | Основной CTA + знак |

Жёлтый/золото убраны. Основной акцент — cyan→purple. Ритм (`--space-*`, `--radius`, `--fs-*`) — только сетка.

## Консоль

В шапке `/console/` — on-dark wordmark рядом с линейкой ASF. Плотность графа и HITL без изменений.
