# 16 — Деплой на VPS (рядом с существующим сайтом)

> Перевод. Канон: [`docs/16-VPS-Deploy.md`](../16-VPS-Deploy.md)

| Поле | Значение |
|------|----------|
| Status | Accepted |
| Version | 0.5 |
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
| `curl https://example.org` ок, Telegram нет | **Блок Telegram у хостера** (на FirstVDS: DNS и IPv4-маршрут есть, `curl -4 https://api.telegram.org` таймаут, ufw OUTPUT = allow). Попросите хостера открыть `api.telegram.org:443` (сети Telegram `149.154.160.0/20`, `91.108.4.0/22`) **или** задайте секрет `HTTPS_PROXY` / `TELEGRAM_PROXY` (не коммитить) и задеплойте снова. IPv4 `extra_hosts` такой путь не лечит. |
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

## Откат только ASF

```bash
docker compose -f /opt/asf/docker-compose.prod.yml --env-file /opt/asf/.env down
# опционально: rm /etc/nginx/sites-enabled/asf*.conf && nginx -t && nginx -s reload
```

Текущий сайт это не удаляет. Тома Docker `asf_pgdata` / `asf_uploads` остаются, пока вы сами не сделаете `docker volume rm`.
