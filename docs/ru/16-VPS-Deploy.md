# 16 — Деплой на VPS (рядом с существующим сайтом)

> Перевод. Канон: [`docs/16-VPS-Deploy.md`](../16-VPS-Deploy.md)

| Поле | Значение |
|------|----------|
| Status | Accepted |
| Version | 0.8 |
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

**Интервью Discovery:** задайте `LLM_PROVIDER=groq` (и `GROQ_API_KEY`). Дефолтный `stub` оставляет покрытие ТЗ через FSM-запасной путь — заказчик не получит разговорный режим DEC-008 (DEC-014).

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
6. **Тот же бот:** `TELEGRAM_BOT_TOKEN` — бот BotFather, у которого URL Mini App. `GET /health/telegram` (или лог старта бота) показывает `bot_username` — он должен совпадать с чатом, откуда открыли Mini App. `sendDocument` идёт с этим токеном из **контейнера API**, не из WebView.
7. **Исходящий доступ VPS к Bot API** (выгрузка ТЗ падает здесь, если egress закрыт; пользователь уже в Telegram — не аргумент):

```bash
# с хоста VPS
curl -sS -o /dev/null -w '%{http_code}\n' --max-time 8 https://api.telegram.org
# из контейнера API (это путь sendDocument)
docker compose -f /opt/asf/docker-compose.prod.yml --env-file /opt/asf/.env exec -T api \
  python -c "from integrations.telegram.notify import diagnose_telegram_bot_api; import json; print(json.dumps(diagnose_telegram_bot_api()))"
curl -sS http://127.0.0.1:18000/health/telegram
```

Ожидается HTTP до `api.telegram.org` и `bot_ok: true` с username бота Mini App. `401` / `Unauthorized` — неверный или placeholder-токен. Transport / timeout — файрвол, DNS или IPv6 egress, не телефон заказчика. В логах `sendDocument` есть `http` status + `description` Telegram, токена нет.

## Исходящий доступ к Telegram Bot API (sendDocument)

`sendDocument` / `getMe` идут из **контейнера API** (сеть Docker `asf_internal`, bridge) через NAT хоста. Входящий HTTPS Mini App здесь ни при чём.

Типичный сбой (на проде `ConnectError`, пустой `bot_username`):

| Проверка | Смысл |
|----------|--------|
| С хоста `curl -4 https://api.telegram.org` ок, из контейнера нет | IPv6/AAAA в Docker или DNS контейнера. Приложение предпочитает IPv4 (`ASF_TELEGRAM_IP=auto`/`4`). Локальный override `docker-compose.telegram-egress.yml` (`extra_hosts`, не в git). |
| `curl https://example.org` ок, Telegram нет | **Блок Telegram у хостера** (на FirstVDS: DNS и IPv4-маршрут есть, `curl -4 https://api.telegram.org` таймаут, ufw OUTPUT = allow). **Не** открывайте тикет FirstVDS, если на VPS уже есть зарубежный канал для Groq/OpenAI: тот же URL задайте как `HTTPS_PROXY` (ниже). IPv4 `extra_hosts` такой путь не лечит. |
| Нет исходящего HTTPS вообще | Закрыт OUTPUT 443 (`ufw` / iptables / панель). Разрешите 443/tcp наружу. |

На VPS (в выводе нет секретов):

```bash
sudo bash /opt/asf/deploy/diagnose_telegram_egress.sh
# если с хоста IPv4 до Telegram живой:
sudo bash /opt/asf/deploy/hotfix_telegram_ipv4.sh
curl -sS http://127.0.0.1:18000/health/telegram
# ждать egress_ok=true и непустой bot_username
```

GitHub: **Actions → Telegram egress → Run workflow** (те же SSH-секреты, что у Deploy VPS; токен бота не печатается). В compose DNS контейнеров — `8.8.8.8` / `1.1.1.1`. `ASF_TELEGRAM_IP=4` принудительно IPv4; `6` — dual-stack.

## Тот же прокси, что у AI (FirstVDS / зарубежный канал)

В репозитории **нет** отдельного `OPENAI_BASE_URL` и WireGuard-sidecar. Groq LLM и Groq/OpenAI STT ходят обычным httpx (`trust_env=True`) и уже читают `HTTPS_PROXY` / `HTTP_PROXY` / `ALL_PROXY`, если они есть **в контейнере**. Telegram Bot API берёт **тот же** URL:

`TELEGRAM_PROXY` → `HTTPS_PROXY` → `HTTP_PROXY` → `ALL_PROXY` → `LLM_HTTP_PROXY`

**Не создавайте второй секрет**, если Telegram может идти тем же хопом, что Groq.

### Предпочтительно: секрет GitHub Actions (переживает Deploy VPS)

1. Репозиторий → **Settings → Secrets and variables → Actions**
2. Задайте **`HTTPS_PROXY`** — HTTP(S) URL того же канала, которым уже ходит AI (формат, не реальный адрес: `http://user:pass@203.0.113.10:3128`). В git не коммитить.
3. `TELEGRAM_PROXY` оставьте пустым.
4. **Actions → Deploy VPS → Run workflow** (или push в `main`). `write_env.py` пишет `/opt/asf/.env`; compose прокидывает переменные в `api` и `bot`.
5. На VPS:

```bash
curl -sS http://127.0.0.1:18000/health/telegram
# ждать egress_ok=true, via_proxy=true и непустой bot_username
```

### Если прокси только на сервере (не в GitHub)

Deploy VPS переписывает `/opt/asf/.env` из секретов. Пустой GitHub `HTTPS_PROXY` больше не затирает прокси, который уже лежит в этом файле. Подключить существующий AI-канал без нового секрета:

```bash
# на VPS — тот же URL, что уже использует AI; не печатайте его в чат/логи
# /opt/asf/.env  (добавить или поправить, не коммитить)
# HTTPS_PROXY=<существующий-ai-прокси>
# HTTP_PROXY=<существующий-ai-прокси>
cd /opt/asf
docker compose -f docker-compose.prod.yml --env-file .env up -d --no-build --force-recreate api bot
curl -sS http://127.0.0.1:18000/health/telegram
```

Host-level WireGuard / split-tunnel **без** HTTP-прокси контейнеру не виден: нужен HTTP(S) URL в `HTTPS_PROXY`, как выше. После следующего **Deploy VPS** либо оставьте строку в `/opt/asf/.env`, либо скопируйте её в секрет GitHub, чтобы перезапись не разъехалась.

## Geo-egress (Groq / OpenAI / Telegram)

Сети российских VPS часто режут `api.groq.com`, `api.openai.com` и иногда `api.telegram.org`. Опциональный профиль compose `egress` держит HTTP-прокси **только на localhost** выходного SSH-хоста и прокидывает его в контейнеры `api` и `bot`.

Цепочка:

1. Выходной VPS: `tinyproxy` на `127.0.0.1:8888` (не в интернет).
2. VPS ASF: постоянный ключ ed25519 в `/opt/asf-secrets/` (вне tarball деплоя).
3. Сервис `egress`: `autossh -L 0.0.0.0:8888:127.0.0.1:8888` в сети Docker `asf_internal`.
4. `HTTPS_PROXY=http://egress:8888` для `api` и `bot`. `NO_PROXY` исключает `db`, localhost и сам `egress`.

Секреты GitHub: `EGRESS_SSH_HOST`, `EGRESS_SSH_USER` (по умолчанию `root`), `EGRESS_SSH_PORT` (по умолчанию `22`). `EGRESS_SSH_PASSWORD` — **только первый деплой** (поставить tinyproxy и pubkey); в `/opt/asf/.env` пароль не пишется. Дальше достаточно ключа. Пустой `EGRESS_SSH_HOST` — прямой исходящий трафик, как раньше.

`asf_sudo` вызывает apt через `env`, чтобы `DEBIAN_FRONTEND=noninteractive` был префиксом окружения, а не командой. Если первый заход на выходной хост всё равно не выходит, добавьте `/opt/asf-secrets/egress_id_ed25519.pub` в `authorized_keys` того хоста и перезапустите **Deploy VPS** (пароль можно оставить пустым).

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
