# 15 — Консоль графа ТЗ владельца

> Перевод. Канон: [`docs/15-Owner-TZ-Console.md`](../15-Owner-TZ-Console.md)

| Поле | Значение |
|------|----------|
| Status | Accepted |
| Version | 0.11 |
| Updated | 2026-09-05 |
| Owner | ASF Core |

## Назначение

Внутренний UI **владельца / аналитика** для просмотра собранных требований ТЗ в виде графа. UI заказчика остаётся Telegram Mini App. HITL-утверждение черновика ТЗ остаётся в боте владельца.

ADR: [DEC-007](../../decisions/DEC-007-Owner-TZ-Console.md).

## Доступ

- URL: `/console/` (статика), API под `/console/api/`
- Заголовок: `X-Console-Token`, совпадающий с `CONSOLE_TOKEN` (UI также шлёт `Authorization: Bearer …`)
- Пустой токен разрешён только при `ASF_ENV=local` и `ASF_DEBUG=true`
- На проде вставьте **значение** секрета GitHub `CONSOLE_TOKEN` с **последнего успешного деплоя VPS**, затем нажмите **Сохранить**. Смена секрета в GitHub не действует, пока не будет новый деплой.

## Представление графа

Проекция (не конкурирующее хранилище). Виртуальные узлы из этапов Discovery + топиков `discovery/tz_outline.py`; листья — сущности KG `Requirement`.

```
Project → stage → topic → Requirement
Requirement --depends_on--> Requirement
Requirement --conflicts_with--> Requirement
```

| Вид ребра | Смысл | Цвет (UI) |
|-----------|-------|-----------|
| `structure` | Иерархия оглавления | серый |
| `depends_on` | Требование зависит от другого | янтарь |
| `conflicts_with` | Противоречие между требованиями | красный |

Этапы сначала свёрнуты вокруг узла проекта. Клик по **этапу или разделу** раскрывает эту ветку (один этап за раз) и открывает карточку-состав. Клик по **листу** открывает карточку требования (описание, связи, статус, история). Клик по пустому месту или × возвращает к обзору проекта. Наведение затемняет чужие узлы. Поиск переходит к совпадению.

Карточка справа — каталог: у групповых узлов список детей; клик по ребёнку фокусирует его на карте. Мутации только у листьев.

Узлы разделов — пиктограммы [Lucide](https://lucide.dev/) (ISC) в `apps/console/icons/`. Сам узел **и есть** пиктограмма (без дополнительного кружка); мягкое свечение — цвет этапа. Иконка центра зависит от типа продукта. Карта: `apps/console/icons/map.json`.

В карточке проекта — **выгрузка полного ТЗ**: Markdown, Word (`docx`), PDF. Файл собирается из KG: `GET /console/api/projects/{id}/tz-export?format=md|docx|pdf`. Клиентский документ — `core/tz_document.compose_tz_markdown`: заголовок **Техническое задание** + имя проекта, мета (проект + контакты заказчика + контакты студии/владельца), оглавление со ссылками, пронумерованные разделы и коды требований `ТЗ-N.M`. Без Appendix и без заголовка «Draft TZ». Контакты исполнителя: `STUDIO_NAME` / `OWNER_CONTACT_*` или хук в KG `Project.payload.owner_contacts` (`{studio, name, email, phone, telegram, note}`). PDF/DOCX — тот же Markdown (ссылки оглавления становятся обычным нумерованным списком; в PDF заголовки попадают в outline, если экспортёр умеет). Клик по **центру графа** (сам проект) показывает **две оценки**: эвристику HITL владельца (`payload.estimate` / `core/estimate.py`) и, после approve, **рыночную смету клиенту** + отчёт (`payload.client_estimate`, DEC-012) с источниками и статусом подтверждения. Они рядом; эвристика не является ценой заказчику. У клиентской сметы те же кнопки файла (MD / Word / PDF): `GET /console/api/projects/{id}/estimate-export?format=md|docx|pdf` — тот же конвейер Markdown→файл, что у ТЗ (`core/tz_document.export_markdown_file`). Правая панель на широком экране ≈760px (`min(760px, 100% − 28px)`), на узком (<900px) по-прежнему на всю ширину / снизу.

В карточке проекта можно **сменить статус проекта**: выпадающий список с русскими подписями и кнопка **Сохранить статус**. В БД остаются английские значения `ProjectStatus` (`NEW`, `INTERVIEW`, `ANALYZING`, `WAITING_CUSTOMER`, `WAITING_OWNER`, `WAITING_CLIENT_ESTIMATE`, `READY`, `ARCHIVED`). Это явный override владельца (`PATCH /console/api/projects/{id}`, токен консоли). Откат назад (например с `READY`) разрешён после confirm в UI. Аудит: `entity_history` на сущности KG `Project` (`status_change`) и `payload.status` этой сущности. Discovery / фабрика по-прежнему читают `projects.status`.

Там же **MVP Factory** (DEC-013): кнопка **Создать MVP** после approve владельца **и** confirm клиентской сметы (`READY`), ответы Intervention Queue (текст / секрет; секреты не показываются обратно), статус сборки и **Отправить клиенту на review**. API: `GET/POST /console/api/projects/{id}/mvp`, `POST .../mvp/send-to-client`, `GET .../interventions`, `POST /console/api/interventions/{id}/resolve`.

Там же — **файлы проекта** (вложения Mini App заказчика и загрузки из консоли) с этапом Discovery, на котором файл был передан. Аналитик может добавить или удалить файл; `entity_history` пишет `created` / `deleted`. Байты на диске в `UPLOAD_DIR` (по умолчанию `data/uploads`); индекс — сущности KG `Artifact` с `payload.kind=uploaded_file`. Скачивание: `GET /console/api/projects/{id}/files/{file_id}/content`.

Требования со статусом `archived` не показываются. Устаревший статус сущности `active` отображается как `new`.

## Статусы требования

| Код | Подпись RU | Правило |
|-----|------------|---------|
| `new` | новое | Только что снято; бейдж NEW |
| `processed` | отработано | Принято в ТЗ аналитиком |
| `needs_clarification` | уточняется | Ждём ответ |
| `conflict` | конфликт | Есть `conflicts_with` и/или явная пометка |
| `rejected` | отклонено | **Обязательна причина** |
| `superseded` | заменено | Заменено (уже используется в Discovery) |

## Панель требования

Показывает: id, описание, дату создания, автора (`payload.author_role` / `author_id`), структурного родителя, связи, статус, причину отклонения/конфликта, историю изменений.

Мутации: создать требование (в карточке раздела/этапа); править текст, раздел и приоритет (в журнале `updated`); менять статус; добавлять/снимать `depends_on` и `conflicts_with`. Вне v1: HITL-approve, автодетект конфликтов LLM.

Добавление `conflicts_with` ставит обоим концам статус `conflict`, если они не `rejected` / `superseded`. Снятие последней конфликтной связи возвращает предыдущий статус из истории (fallback `processed`).

## История

Таблица `entity_history` — журнал аудита (`created`, `updated`, `deleted`, `status_change`, `relation_add`, `relation_remove`). Это **не** event sourcing. Правки текста кладут сниппеты «было/стало» в `payload.fields`. Добавление/удаление файлов кладут имя и этап в `payload`.
