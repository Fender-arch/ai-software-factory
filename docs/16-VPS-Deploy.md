# 16 — VPS deploy (alongside an existing website)

| Field | Value |
|-------|-------|
| Status | Accepted |
| Version | 0.9 |
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
| `docker/Dockerfile.egress` | Optional SSH tunnel to a geo-unrestricted exit VPS |

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
| Host `curl https://example.org` works, Telegram does not | **Provider-level Telegram block** (seen on FirstVDS: DNS + IPv4 route OK, `curl -4 https://api.telegram.org` times out, ufw OUTPUT is allow). Do **not** open a FirstVDS ticket if the VPS already has a foreign hop for Groq/OpenAI: reuse that URL as `HTTPS_PROXY` (below). IPv4 extra_hosts cannot fix a filtered path. |
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

## Same proxy as AI (FirstVDS / foreign channel)

There is **no** dedicated `OPENAI_BASE_URL` / WireGuard sidecar in this repo. Groq LLM + Groq/OpenAI STT use vanilla httpx (`trust_env=True`), so they already follow `HTTPS_PROXY` / `HTTP_PROXY` / `ALL_PROXY` when those are in the **container** env. Telegram Bot API now resolves the **same** URL:

`TELEGRAM_PROXY` → `HTTPS_PROXY` → `HTTP_PROXY` → `ALL_PROXY` → `LLM_HTTP_PROXY`

**Do not create a second secret** unless Telegram must use a different hop than Groq.

### Preferred: GitHub Actions secret (survives Deploy VPS)

1. Repo → **Settings → Secrets and variables → Actions**
2. Set **`HTTPS_PROXY`** to the HTTP(S) proxy URL the AI channel already uses (example shape only: `http://user:pass@203.0.113.10:3128` — never commit the real value).
3. Leave `TELEGRAM_PROXY` empty.
4. **Actions → Deploy VPS → Run workflow** (or push to `main`). `write_env.py` writes `/opt/asf/.env`; compose injects the vars into `api` and `bot`.
5. On the VPS:

```bash
curl -sS http://127.0.0.1:18000/health/telegram
# expect egress_ok=true, via_proxy=true, and a non-empty bot_username
```

### If the proxy exists only on the VPS (not in GitHub)

Deploy VPS rewrites `/opt/asf/.env` from secrets. An empty GitHub `HTTPS_PROXY` no longer wipes a proxy that is already in that file. To attach the existing AI hop without a new GitHub secret:

```bash
# on the VPS — paste the same URL AI already uses; do not echo it into chat/logs
# /opt/asf/.env  (add or edit, never commit)
# HTTPS_PROXY=<existing-ai-proxy-url>
# HTTP_PROXY=<existing-ai-proxy-url>
cd /opt/asf
docker compose -f docker-compose.prod.yml --env-file .env up -d --no-build --force-recreate api bot
curl -sS http://127.0.0.1:18000/health/telegram
```

Host-level WireGuard / split-tunnel that is **not** an HTTP proxy is invisible to Docker unless you put an HTTP(S) proxy URL into `HTTPS_PROXY` as above. After a later **Deploy VPS**, either keep the line in `/opt/asf/.env` or copy it into the GitHub secret so the next rewrite stays aligned.

## Geo egress (Groq / OpenAI / Telegram)

Russian VPS networks often block `api.groq.com`, `api.openai.com`, and sometimes `api.telegram.org`. Optional compose profile `egress` keeps a **localhost-only** HTTP proxy on an unrestricted SSH host and forwards it into the `api` and `bot` containers.

Flow:

1. Exit VPS: `tinyproxy` on `127.0.0.1:8888` (not public).
2. ASF VPS: durable ed25519 key in `/opt/asf-secrets/` (outside the deploy tarball).
3. Service `egress`: `autossh -L 0.0.0.0:8888:127.0.0.1:8888` on Docker network `asf_internal`.
4. `HTTPS_PROXY=http://egress:8888` for `api` and `bot`. `NO_PROXY` keeps `db`, localhost, and `egress` itself off the proxy.

GitHub secrets: `EGRESS_SSH_HOST`, `EGRESS_SSH_USER` (default `root`), `EGRESS_SSH_PORT` (default `22`). `EGRESS_SSH_PASSWORD` is **first deploy only** (install tinyproxy + the pubkey); it is not written to `/opt/asf/.env`. After that, key-only SSH is enough. Leave `EGRESS_SSH_HOST` empty to keep today’s direct outbound.

`asf_sudo` runs apt via `env` so `DEBIAN_FRONTEND=noninteractive` is an env prefix, not a command. Exit-node `tinyproxy.conf` must keep `PidFile` / `LogFile` — Ubuntu’s unit is Type=forking and otherwise times out on restart. If first-time install still cannot reach the exit host, add `/opt/asf-secrets/egress_id_ed25519.pub` to that host’s `authorized_keys` and re-run **Deploy VPS** (password can stay empty).

Smoke on the ASF VPS after deploy:

```bash
docker compose -f /opt/asf/docker-compose.prod.yml --env-file /opt/asf/.env --profile egress exec -T api \
  python -c "import os,httpx; print(os.environ.get('HTTPS_PROXY')); r=httpx.get('https://api.telegram.org'); print(r.status_code)"
```

## Rollback ASF only

```bash
docker compose -f /opt/asf/docker-compose.prod.yml --env-file /opt/asf/.env down
# optional: rm /etc/nginx/sites-enabled/asf*.conf && nginx -t && nginx -s reload
```

That does not remove the existing website. Docker volumes `asf_pgdata` / `asf_uploads` stay until you `docker volume rm` them on purpose.
