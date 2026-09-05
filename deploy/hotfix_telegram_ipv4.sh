#!/usr/bin/env bash
# If the VPS host can reach api.telegram.org over IPv4, pin that A record
# into a local compose override (not committed) and recreate api/bot.
# Never prints tokens. Telegram IPs are resolved live — not stored in git.
set -euo pipefail
DEPLOY_PATH="${VPS_DEPLOY_PATH:-/opt/asf}"
if [[ "$DEPLOY_PATH" == "SET_ME" || -z "$DEPLOY_PATH" ]]; then
  DEPLOY_PATH="/opt/asf"
fi
OVERRIDE="${DEPLOY_PATH}/docker-compose.telegram-egress.yml"

ipv4="$(getent ahostsv4 api.telegram.org 2>/dev/null | awk '{print $1; exit}')"
if [[ -z "$ipv4" ]]; then
  echo "hotfix: no A record for api.telegram.org"
  exit 1
fi
if ! curl -4 -sS -o /dev/null --max-time 8 "https://api.telegram.org"; then
  echo "hotfix: host IPv4 cannot reach api.telegram.org — skip extra_hosts"
  exit 2
fi

cat > "$OVERRIDE" <<EOF
# Generated on the VPS. Do not commit. Refresh by re-running this script.
services:
  api:
    extra_hosts:
      - "api.telegram.org:${ipv4}"
    dns:
      - 8.8.8.8
      - 1.1.1.1
  bot:
    extra_hosts:
      - "api.telegram.org:${ipv4}"
    dns:
      - 8.8.8.8
      - 1.1.1.1
EOF
echo "hotfix: pinned api.telegram.org -> ${ipv4} in $(basename "$OVERRIDE")"

cd "$DEPLOY_PATH"
if docker compose version >/dev/null 2>&1; then
  compose=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  compose=(docker-compose)
else
  echo "hotfix: docker compose missing"
  exit 1
fi
"${compose[@]}" -f docker-compose.prod.yml -f docker-compose.telegram-egress.yml --env-file .env up -d --no-build --force-recreate api bot
echo "hotfix: api/bot recreated"
