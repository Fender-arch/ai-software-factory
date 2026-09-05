# 01 — Объём MVP

> Перевод. Канон: [`docs/01-MVP-Scope.md`](../01-MVP-Scope.md)

| Поле | Значение |
|------|----------|
| Status | Accepted |
| Version | 0.6 |
| Updated | 2026-09-05 |
| Owner | ASF Core |

## Цель MVP

Запустить первый реальный поток заказчика:

1. Заказчик использует Telegram (**Mini App** — основной канал; DM бота — онбординг/уведомления) — текст или **голос**
2. Платформа собирает требования (Discovery) в project workspace Mini App
3. Формируется черновик спецификации
4. Владелец ревьюит и утверждает (HITL)
5. Заказчик видит **рыночную смету + отчёт с обоснованием** и подтверждает (DEC-012)
6. Работа разбивается на задачи
7. Cursor может реализовать **простой** MVP по этим задачам

Home заказчика (UI на русском): **создать проект**, **изменить проект**, **замечания к реализации**. Детали: [14-Telegram-Customer-UX.md](14-Telegram-Customer-UX.md), [DEC-006](../../decisions/DEC-006-Telegram-Mini-App.md).

Definition of done для *платформенного* MVP: Telegram Mini App → качественное ТЗ → HITL → подтверждение клиентской сметы → задачи → Cursor может собрать простой продукт — не «идеальная автономная компания».

## В объёме

| Область | Детали |
|---------|--------|
| Каналы | Telegram Mini App (полноэкранный UI заказчика) + DM бота (онбординг, уведомления); **голос через Whisper STT** |
| UX заказчика | Онбординг на RU; создать / изменить / замечания к реализации; project workspace в Mini App; маскот Experience Layer ([DEC-011](../../decisions/DEC-011-Experience-Layer-Mascot.md)) |
| Discovery | Адаптивные вопросы, черновик ТЗ / артефакты |
| Память | Логический Knowledge Graph в PostgreSQL (`entity`, `relation`, JSONB) |
| AI | Один **AI Coordinator** с режимами (не множество OS-процессов) |
| HITL | Ревью спецификации в боте владельца; `HumanDecisionRequired` на развилках |
| Клиентская смета | Рыночный ориентир + отчёт на русском после approve владельца; подтверждение до Planner ([DEC-012](../../decisions/DEC-012-Client-Market-Estimate.md)) |
| Консоль ТЗ владельца | Внутренний граф требований (`/console/`); [DEC-007](../../decisions/DEC-007-Owner-TZ-Console.md), [15-Owner-TZ-Console.md](15-Owner-TZ-Console.md) |
| Типы продуктов | `website`, `telegram_bot`, `rest_service`, `ai_automation`, `mobile_native` ([DEC-010](../../decisions/DEC-010-Mobile-Native.md)) |
| Поставка | Экспорт задач + правила Cursor; **MVP Factory** BuildJob + Intervention Queue ([DEC-013](../../decisions/DEC-013-MVP-Factory-Interventions.md)); исполнение человеком/Cursor |
| Стек | FastAPI, PostgreSQL, Alembic, Docker Compose, фронтенд Mini App, консоль владельца |
| Переходный режим | Командный бот (`/new`, `/use`, …) до поставки Mini App |

## Вне объёма (ASF Future)

- Redis / отдельные брокеры очередей (в MVP — статусы задач в Postgres)
- Neo4j / GraphDB
- Event sourcing, DSL, Rule Engine, Architecture Compiler
- Полный Knowledge Kernel / Explainability API / Evolution Engine
- Multi-agent runtime (отдельные процессы агентов)
- Sales / finance / C-level оргструктура агентов
- Web Human Review Portal для **заказчика** (Mini App + HITL в боте владельца остаются путями заказчика/HITL; консоль графа ТЗ — DEC-007, не этот портал)
- Второй репозиторий `asf-template` (используем in-repo `templates/`)
- Отдельный Telegram DM / forum topic на проект
- Полный owner-портал внутри Mini App

## Фильтр MVP для новых идей

Перед добавлением чего-либо в MVP ответьте:

1. Это помогает первому заказчику?
2. Это упрощает поставку?
3. Это сохраняет архитектуру простой?

Если нет → `backlog/Future.md`.

## Целевая сложность продукта

MVP-фабрика нацелена на **простые** спецификации: визитки, боты, небольшие API, лёгкие автоматизации, нативные приложения на одной платформе — не multi-tenant SaaS и не сложные распределённые системы.
