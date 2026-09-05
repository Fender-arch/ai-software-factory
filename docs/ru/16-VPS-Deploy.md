# 16 — Деплой на VPS (рядом с существующим сайтом)

> Перевод. Канон: [`docs/16-VPS-Deploy.md`](../16-VPS-Deploy.md)

| Поле | Значение |
|------|----------|
| Status | Accepted |
| Version | 0.3 |
| Updated | 2026-09-05 |
| Owner | ASF Core |

## Цель

Запустить ASF на VPS, который **уже отдаёт сайт**, не подменяя этот сайт.

ASF не занимает порты хоста **80**, **443** и **5432**. API слушает `127.0.0.1:18000` (можно сменить `ASF_HOST_PORT`). Новые vhost nginx добавляются только для указанных вами имён ASF.

## Состав

| Часть | Роль |
|-------|------|
| `docker-compose.yml` | Локальная разработка (reload, порты 8000/5432) |
| `docker-compose.prod.yml` | VPS: `db` + `api` + `bot`, проект `asf` |
| `deploy/` | Рендер `.env`, фрагменты nginx, удалённый старт |
| `.github/workflows/deploy-vps.yml` | Деплой по SSH/SCP из GitHub Actions |
| `.github/SECRETS.md` | Имена секретов, которые нужно заполнить |
| `docker/Dockerfile.egress` | Опциональный SSH-туннель на VPS без geo-ограничений |

## Что не трогается

- Существующий nginx `default_server` / конфиги текущего сайта
- Порты хоста 80/443 (текущий reverse proxy их сохраняет)
- Другие Docker Compose проекты (у ASF имя проекта `asf` и сеть `asf_internal`)
- Postgres не публикуется на хост

## DNS

Записи **A/AAAA** на IP VPS нужны **до** ожидания HTTPS:

- `DOMAIN_MINIAPP` → Mini App `https://<domain>/miniapp/`
- `DOMAIN_CONSOLE` → консоль ТЗ `https://<domain>/console/` (может совпадать с Mini App)

В @BotFather укажите URL Mini App: `https://<DOMAIN_MINIAPP>/miniapp/`. Само Mini App запрашивает полноэкранный режим при открытии (`requestFullscreen`); после деплоя полностью закройте WebApp и откройте снова, чтобы Telegram не держал старый HTML/JS.

## Секреты GitHub

Создайте/замените секреты из [`.github/SECRETS.md`](../../.github/SECRETS.md). Заглушки — `SET_ME`.

Workflow **ничего не делает**, пока `VPS_HOST` не станет реальным IP/именем (не пусто / не `SET_ME`). Затем:

1. Упаковывает репозиторий (без `.env`, без `.git`)
2. Копирует на VPS (по умолчанию `/opt/asf`)
3. Пишет `.env` из секретов
4. `docker compose -f docker-compose.prod.yml up -d --build`
5. Ставит **только** сайты nginx `asf*.conf` и запускает certbot **для этих доменов**

Запуск: **Actions → Deploy VPS → Run workflow** или push в `main` после заполнения секретов.

## Требования к VPS

- Docker Engine + Compose v2
- nginx, который уже отдаёт текущий сайт (типичный случай)
- `certbot` + `python3-certbot-nginx` для HTTPS (можно поставить заранее)
- SSH-пользователь может запускать Docker (root, sudo или группа `docker`)

**Не** ставьте второй reverse proxy на 80/443.

## Ручной запуск (без Actions)

На VPS, с экспортированными секретами в оболочке:

```bash
cd /opt/asf
python3 deploy/write_env.py
docker compose -f docker-compose.prod.yml --env-file .env up -d --build
bash deploy/setup_proxy.sh
```

## Smoke после деплоя

1. Существующий сайт по-прежнему открывается на своём домене
2. `curl -sS http://127.0.0.1:18000/health` → `ok`
3. `https://<DOMAIN_MINIAPP>/miniapp/` открывает Mini App на русском
4. `https://<DOMAIN_CONSOLE>/console/` открывает консоль владельца (вставьте `CONSOLE_TOKEN`)
5. Кнопка меню Telegram-бота открывает Mini App (`MINIAPP_URL`)

## Geo-egress (Groq / OpenAI / Telegram)

Сети российских VPS часто режут `api.groq.com`, `api.openai.com` и иногда `api.telegram.org`. Опциональный профиль compose `egress` держит HTTP-прокси **только на localhost** выходного SSH-хоста и прокидывает его в контейнеры `api` и `bot`.

Цепочка:

1. Выходной VPS: `tinyproxy` на `127.0.0.1:8888` (не в интернет).
2. VPS ASF: постоянный ключ ed25519 в `/opt/asf-secrets/` (вне tarball деплоя).
3. Сервис `egress`: `autossh -L 0.0.0.0:8888:127.0.0.1:8888` в сети Docker `asf_internal`.
4. `HTTPS_PROXY=http://egress:8888` для `api` и `bot`. `NO_PROXY` исключает `db`, localhost и сам `egress`.

Секреты GitHub: `EGRESS_SSH_HOST`, `EGRESS_SSH_USER` (по умолчанию `root`), `EGRESS_SSH_PORT` (по умолчанию `22`). `EGRESS_SSH_PASSWORD` — **только первый деплой** (поставить tinyproxy и pubkey); в `/opt/asf/.env` пароль не пишется. Дальше достаточно ключа. Пустой `EGRESS_SSH_HOST` — прямой исходящий трафик, как раньше.

Smoke на VPS ASF после деплоя:

```bash
docker compose -f /opt/asf/docker-compose.prod.yml --env-file /opt/asf/.env --profile egress exec -T api \
  python -c "import os,httpx; print(os.environ.get('HTTPS_PROXY')); r=httpx.get('https://api.telegram.org'); print(r.status_code)"
```

## Откат только ASF

```bash
docker compose -f /opt/asf/docker-compose.prod.yml --env-file /opt/asf/.env down
# опционально: rm /etc/nginx/sites-enabled/asf*.conf && nginx -t && nginx -s reload
```

Текущий сайт это не удаляет. Тома Docker `asf_pgdata` / `asf_uploads` остаются, пока вы сами не сделаете `docker volume rm`.
