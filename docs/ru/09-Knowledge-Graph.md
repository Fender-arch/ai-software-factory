# 09 — Knowledge Graph

> Перевод. Канон: [`docs/09-Knowledge-Graph.md`](../09-Knowledge-Graph.md)

| Поле | Значение |
|------|----------|
| Status | Accepted |
| Version | 0.5 |
| Updated | 2026-09-05 |
| Owner | ASF Core |

## Принцип

Knowledge Graph — это **единственный источник истины**. Markdown-артефакты — сгенерированные представления, а не конкурирующие хранилища.

Реализация MVP: **логический граф в PostgreSQL**, не Neo4j.

## Таблицы

### `entity`

| Колонка | Примечания |
|---------|------------|
| id | UUID |
| project_id | FK |
| type | см. типы ниже |
| name | короткая метка |
| payload | JSONB |
| status | жизненный цикл |
| confidence | 0..1 опционально |
| created_at / updated_at | временные метки |

### `relation`

| Колонка | Примечания |
|---------|------------|
| id | UUID |
| project_id | FK |
| from_entity_id | FK |
| to_entity_id | FK |
| type | см. связи ниже |
| payload | JSONB опционально |

### `entity_history`

Журнал аудита (не event bus). Используется консолью ТЗ владельца.

| Колонка | Примечания |
|---------|------------|
| id | UUID |
| project_id | FK |
| entity_id | FK |
| actor | `discovery` \| `console` \| `system` |
| action | `created` \| `updated` \| `deleted` \| `status_change` \| `relation_add` \| `relation_remove` |
| from_status / to_status | опционально |
| reason | обязательно при отклонении Requirement |
| payload | JSONB опционально |
| created_at | временная метка |

## Типы сущностей (MVP)

`Project` · `Message` · `Requirement` · `OpenQuestion` · `Decision` · `Task` · `Artifact` · `Risk` (опционально) · `Feedback` (замечания к реализации)

`Artifact` payload `kind`: `draft_tz` (сгенерированный markdown), `uploaded_file` (вложение заказчика/консоли; байты на диске в `UPLOAD_DIR`, не в JSONB) или `cursor_brief` (файлы Spec Kit + экспорт задач для BuildJob).

У `draft_tz` также хранится `payload.estimate`: детерминированная **owner**-эвристика стоимости поставки (`hours`, `cost`, `currency`, `hourly_rate`, `rationale`, счётчики требований/рисков). После approve владельца туда же пишутся `payload.client_estimate` + `payload.client_estimate_report`: рыночная смета, источники и русский отчёт (DEC-012). Отдельная таблица не нужна. Два ключа специально — эвристику владельца не затираем.

`payload.in_mvp` у Requirement помечает утверждённый срез MVP для фабрики (DEC-013). Запасной путь: `scope_in` / `scope=in`, затем `priority=must`. **Секреты не пишутся в payload сущности.**

Операционные таблицы `projects` / `messages` / `tasks` / `build_jobs` / `interventions` могут зеркалить горячие пути; сущности графа хранят семантические связи. Секретные ответы Intervention живут только в зашифрованном `interventions.answer_ciphertext`.

## Типы связей (MVP)

`derived_from` · `decides` · `implements` · `blocks` · `related_to` · `depends_on` · `conflicts_with`

`depends_on` и `conflicts_with` — Requirement↔Requirement (консоль владельца). Отличаются от `depends_on` в payload задачи планировщика.

## Статусы требования (консоль)

`new` · `processed` · `needs_clarification` · `conflict` · `rejected` · `superseded`

Устаревший `active` в проекции консоли читается как `new`. `archived` в граф не попадает.

Этапы/топики оглавления ТЗ — **виртуальные узлы** вида консоли, не отдельные типы сущностей. См. [15-Owner-TZ-Console.md](15-Owner-TZ-Console.md).

## Пример трассируемости

`Message` → `derived_from` → `Requirement` → `decides` → `Decision` → `implements` → `Task` → `Artifact`

## Не-цели

- Языки запросов к графу / GraphDB до Future
- Свободный скан всей БД агентами без context builder
