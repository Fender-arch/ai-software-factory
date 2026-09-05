# 02 — Архитектура

> Перевод. Канон: [`docs/02-Architecture.md`](../02-Architecture.md)

| Поле | Значение |
|------|----------|
| Status | Accepted |
| Version | 0.4 |
| Updated | 2026-09-05 |
| Owner | ASF Core |

## Стиль

**Modular monolith.** Один деплойный API-процесс сегодня; чёткие границы пакетов для будущего выделения. UI заказчика — Telegram Mini App рядом с интеграцией Bot API.

```
Telegram bot DM (RU онбординг | уведомления)
        │ Menu / WebApp
        ▼
Telegram Mini App (fullscreen) ── text | voice
        │
   Whisper STT ──┐
                 ▼
            FastAPI (Orchestrator)
                 │
        ┌────────┼────────┐
        ▼        ▼        ▼
 AI Coordinator   KG     Tasks
   (modes)     (Postgres)
        │
   Artifacts (Markdown, derived)
        │
   Owner HITL (бот) → смета клиенту (Mini App) → Planner → Cursor → Product MVP
        │
   Консоль ТЗ владельца (`/console/`) ← вид KG (DEC-007)
```

## Компоненты

| Компонент | Ответственность |
|-----------|-----------------|
| Orchestrator | Детерминированный workflow, состояние проекта, кто следующий — **не LLM** |
| AI Coordinator | Один worker с режимами: Discovery, Reviewer, Architect, Planner, Developer, QA |
| Knowledge Graph | Логический SoT: entities + relations в PostgreSQL |
| STT | Голос → текст (Whisper); далее тот же путь, что у текста |
| Telegram Mini App | Основной UI заказчика: home-действия, project workspace |
| Telegram-бот | Вход, уведомления; команды owner HITL в MVP |
| Консоль ТЗ владельца | Внутренний граф требований + статусы/связи (DEC-007); не UI заказчика |
| Artifact generator | Markdown из графа (ТЗ, решения, экспорт backlog) |
| Cursor executor | Внешний coding-агент; ASF готовит контекст и задачи |

## Модель агентов

Агенты — это **режимы / skills**, а не постоянно живые персоны, переписывающиеся друг с другом.

Цикл на одно обращение:

1. Прочитать ограниченный контекст (для режима)
2. Проанализировать
3. Записать структурированный результат в KG / DB
4. Опубликовать исход (статус / event-подобная запись)
5. Остановиться

Без свободных multi-agent диалоговых циклов.

## Human in the loop

- Обязательный гейт после черновика спецификации
- `HumanDecisionRequired` при низкой уверенности, противоречиях или необходимости бизнес-выбора
- Статус задачи `WAITING_USER`

## Язык

- Канал заказчика (Mini App + тексты бота): **русский**
- Каноничное хранение и рассуждения агентов: английский (Language Normalizer — **инфраструктура**, не workflow-агент)
- Локализованные артефакты могут генерироваться для заказчика

## События

В MVP — **статусы задач/проектов** в PostgreSQL. Более богатая event bus может появиться позже без смены доменной модели. Концептуальные события: `ProjectCreated`, `MessageReceived`, `DiscoveryReady`, `HumanDecisionRequired`, `TaskCompleted`.

## Раскладка пакетов

См. [04-Repository-Structure.md](04-Repository-Structure.md). UX заказчика: [14-Telegram-Customer-UX.md](14-Telegram-Customer-UX.md). Консоль ТЗ владельца: [15-Owner-TZ-Console.md](15-Owner-TZ-Console.md).
