# 16 — VPS deploy (alongside an existing website)

| Field | Value |
|-------|-------|
| Status | Accepted |
| Version | 0.5 |
| Updated | 2026-09-05 |
| Owner | ASF Core |

## Goal

Run ASF on a VPS that **already serves a website**, without replacing that site.

ASF never binds host ports **80**, **443**, or **5432**. The API listens on `127.0.0.1:18000` (override `ASF_HOST_PORT`). New nginx vhosts are added only for the ASF hostnames you provide.

## Layout

| Piece | Role |
|-------|------|
| `docker-compose.yml` | Local development (reload, published 8000/5432) |
| `docker-compose.prod.yml` | VPS: `db` + `api` + `bot`, named project `asf` |
| `deploy/` | Render `.env`, nginx snippets, remote start |
| `.github/workflows/deploy-vps.yml` | SSH/SCP deploy from GitHub Actions |
| `.github/SECRETS.md` | Secret names to fill |

## What is not touched

- Existing nginx `default_server` / current site configs
- Host ports 80/443 (the current reverse proxy keeps them)
- Other Docker Compose projects (ASF uses project name `asf` and network `asf_internal`)
- Postgres is not published on the host

## DNS

Point **A/AAAA** records to the VPS IP **before** expecting HTTPS:

- `DOMAIN_MINIAPP` → Mini App `https://<domain>/miniapp/`
- `DOMAIN_CONSOLE` → Console `https://<domain>/console/` (may be the same hostname)

In @BotFather set the Mini App URL to `https://<DOMAIN_MINIAPP>/miniapp/`. The Mini App itself requests fullscreen on open (`requestFullscreen`); fully close and reopen the WebApp after a deploy so Telegram does not keep a cached HTML/JS bundle.

## GitHub secrets

Create/replace secrets listed in [`.github/SECRETS.md`](../.github/SECRETS.md). Placeholders are `SET_ME`.

**Discovery interview:** set `LLM_PROVIDER=groq` (with `GROQ_API_KEY`). Leaving the default `stub` keeps TZ coverage via the FSM fallback — the customer will not get the DEC-008 conversational path (DEC-014).

The workflow **does nothing** until `VPS_HOST` is a real IP/hostname (not empty / not `SET_ME`). Then:

1. Packs the repo (no `.env`, no `.git`)
2. Copies it to the VPS (`/opt/asf` by default)
3. Writes `.env` from secrets
4. `docker compose -f docker-compose.prod.yml up -d --build`
5. Installs **only** `asf*.conf` nginx sites and runs certbot **for those domains**

Trigger: **Actions → Deploy VPS → Run workflow**, or push to `main` after secrets are filled.

## VPS prerequisites

- Docker Engine + Compose v2
- nginx already serving the current site (typical)
- `certbot` + `python3-certbot-nginx` for HTTPS (optional to install yourself)
- SSH user can run Docker (root, or sudo, or `docker` group)

Do **not** install a second reverse proxy that binds 80/443.

## Manual run (without Actions)

On the VPS, with secrets exported in the shell:

```bash
cd /opt/asf
python3 deploy/write_env.py
docker compose -f docker-compose.prod.yml --env-file .env up -d --build
bash deploy/setup_proxy.sh
```

## Smoke after deploy

1. Existing website still loads on its original domain
2. `curl -sS http://127.0.0.1:18000/health` → `ok`
3. `https://<DOMAIN_MINIAPP>/miniapp/` opens the Russian Mini App
4. `https://<DOMAIN_CONSOLE>/console/` opens the owner console (paste `CONSOLE_TOKEN`)
5. Telegram bot Menu button opens the Mini App (`MINIAPP_URL`)
6. **Same bot:** `TELEGRAM_BOT_TOKEN` is the BotFather bot that has the Mini App URL. `GET /health/telegram` (or bot start logs) shows `bot_username` — it must match the chat that opened the Mini App. `sendDocument` uses this token from the **API container**, not from the WebView.
7. **VPS egress to Bot API** (TZ send fails here if blocked; the user being inside Telegram is irrelevant):

```bash
# from the VPS host
curl -sS -o /dev/null -w '%{http_code}\n' --max-time 8 https://api.telegram.org
# from the API container (this is the sendDocument path)
docker compose -f /opt/asf/docker-compose.prod.yml --env-file /opt/asf/.env exec -T api \
  python -c "from integrations.telegram.notify import diagnose_telegram_bot_api; import json; print(json.dumps(diagnose_telegram_bot_api()))"
curl -sS http://127.0.0.1:18000/health/telegram
```

Expect egress HTTP from `api.telegram.org` and `bot_ok: true` with the Mini App bot username. `401` / `Unauthorized` = wrong or placeholder token. Transport / timeout = firewall, DNS, or IPv6 egress — not the customer’s phone. Logs for `sendDocument` include `http` status + Telegram `description` and never the token.

## Telegram Bot API egress (sendDocument)

`sendDocument` / `getMe` leave the **API container** on Docker network `asf_internal` (bridge) via the host NAT. Incoming Mini App HTTPS is unrelated.

Typical failure (prod `ConnectError`, empty `bot_username`):

| Check | Meaning |
|-------|---------|
| Host `curl -4 https://api.telegram.org` works, container does not | Docker IPv6/AAAA or container DNS. App prefers IPv4 (`ASF_TELEGRAM_IP=auto`/`4`). Optional local override `docker-compose.telegram-egress.yml` (`extra_hosts`, not committed). |
| Host `curl https://example.org` works, Telegram does not | Provider/firewall blocks Telegram. Allow `api.telegram.org:443` **or** set GitHub secret `HTTPS_PROXY` / `TELEGRAM_PROXY` (never commit it) and redeploy. |
| Neither host HTTPS works | Outgoing 443 denied (`ufw` / iptables / panel). Allow OUTPUT 443/tcp. |

Runbook on the VPS (no secrets in the output):

```bash
sudo bash /opt/asf/deploy/diagnose_telegram_egress.sh
# if host IPv4 to Telegram works:
sudo bash /opt/asf/deploy/hotfix_telegram_ipv4.sh
curl -sS http://127.0.0.1:18000/health/telegram
# expect egress_ok=true and a non-empty bot_username
```

GitHub: **Actions → Telegram egress → Run workflow** (uses the same SSH secrets as Deploy VPS; does not print the bot token). Compose also sets container DNS to `8.8.8.8` / `1.1.1.1`. `ASF_TELEGRAM_IP=4` forces IPv4; `6` leaves dual-stack.

## Rollback ASF only

```bash
docker compose -f /opt/asf/docker-compose.prod.yml --env-file /opt/asf/.env down
# optional: rm /etc/nginx/sites-enabled/asf*.conf && nginx -t && nginx -s reload
```

That does not remove the existing website. Docker volumes `asf_pgdata` / `asf_uploads` stay until you `docker volume rm` them on purpose.
