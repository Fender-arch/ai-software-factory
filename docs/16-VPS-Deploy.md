# 16 — VPS deploy (alongside an existing website)

| Field | Value |
|-------|-------|
| Status | Accepted |
| Version | 0.3 |
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

## Geo egress (Groq / OpenAI / Telegram)

Russian VPS networks often block `api.groq.com`, `api.openai.com`, and sometimes `api.telegram.org`. Optional compose profile `egress` keeps a **localhost-only** HTTP proxy on an unrestricted SSH host and forwards it into the `api` and `bot` containers.

Flow:

1. Exit VPS: `tinyproxy` on `127.0.0.1:8888` (not public).
2. ASF VPS: durable ed25519 key in `/opt/asf-secrets/` (outside the deploy tarball).
3. Service `egress`: `autossh -L 0.0.0.0:8888:127.0.0.1:8888` on Docker network `asf_internal`.
4. `HTTPS_PROXY=http://egress:8888` for `api` and `bot`. `NO_PROXY` keeps `db`, localhost, and `egress` itself off the proxy.

GitHub secrets: `EGRESS_SSH_HOST`, `EGRESS_SSH_USER` (default `root`), `EGRESS_SSH_PORT` (default `22`). `EGRESS_SSH_PASSWORD` is **first deploy only** (install tinyproxy + the pubkey); it is not written to `/opt/asf/.env`. After that, key-only SSH is enough. Leave `EGRESS_SSH_HOST` empty to keep today’s direct outbound.

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
