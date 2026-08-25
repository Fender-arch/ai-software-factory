#!/usr/bin/env bash
# Install ASF nginx vhosts next to the existing site. Never replaces default_server.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DOMAIN_MINIAPP="${DOMAIN_MINIAPP:-}"
DOMAIN_CONSOLE="${DOMAIN_CONSOLE:-$DOMAIN_MINIAPP}"
ASF_HOST_PORT="${ASF_HOST_PORT:-18000}"
LETSENCRYPT_EMAIL="${LETSENCRYPT_EMAIL:-}"
UPSTREAM="127.0.0.1:${ASF_HOST_PORT}"

if [[ -z "$DOMAIN_MINIAPP" || "$DOMAIN_MINIAPP" == "SET_ME" ]]; then
  echo "DOMAIN_MINIAPP is not set; skip proxy install" >&2
  exit 0
fi

asf_sudo() {
  if [[ "$(id -u)" -eq 0 ]]; then
    "$@"
  elif sudo -n true 2>/dev/null; then
    sudo "$@"
  elif [[ -n "${VPS_PASSWORD:-}" ]]; then
    printf '%s\n' "$VPS_PASSWORD" | sudo -S -p "" "$@"
  else
    echo "Need root or passwordless sudo to install nginx vhosts" >&2
    return 1
  fi
}

if ! command -v nginx >/dev/null 2>&1 && ! asf_sudo command -v nginx >/dev/null 2>&1; then
  echo "nginx not found. ASF API is on ${UPSTREAM}."
  echo "Add HTTPS vhosts for ${DOMAIN_MINIAPP} and ${DOMAIN_CONSOLE} yourself; do not change the existing default site."
  exit 0
fi

TMP_SITES="$(mktemp -d)"
trap 'rm -rf "$TMP_SITES"' EXIT

export DOMAIN_MINIAPP DOMAIN_CONSOLE ASF_HOST_PORT
export ASF_UPSTREAM="$UPSTREAM"
python3 "${ROOT}/deploy/render_nginx.py" "$TMP_SITES"

AVAILABLE=""
ENABLED=""
if asf_sudo test -d /etc/nginx/sites-available; then
  AVAILABLE="/etc/nginx/sites-available"
  ENABLED="/etc/nginx/sites-enabled"
elif asf_sudo test -d /etc/nginx/conf.d; then
  AVAILABLE="/etc/nginx/conf.d"
  ENABLED=""
else
  echo "Unknown nginx layout; wrote templates under ${TMP_SITES} (not installed)" >&2
  ls -l "$TMP_SITES"
  exit 0
fi

for src in "${TMP_SITES}"/*.conf; do
  base="$(basename "$src")"
  dest="${AVAILABLE}/${base}"
  asf_sudo cp "$src" "$dest"
  if [[ -n "$ENABLED" ]]; then
    asf_sudo ln -sfn "$dest" "${ENABLED}/${base}"
  fi
  echo "installed ${dest}"
done

if ! asf_sudo nginx -t; then
  echo "nginx -t failed; removing ASF vhosts to protect the existing site" >&2
  for src in "${TMP_SITES}"/*.conf; do
    base="$(basename "$src")"
    asf_sudo rm -f "${AVAILABLE}/${base}"
    if [[ -n "$ENABLED" ]]; then
      asf_sudo rm -f "${ENABLED}/${base}"
    fi
  done
  asf_sudo nginx -t
  asf_sudo nginx -s reload || true
  exit 1
fi

asf_sudo nginx -s reload
echo "nginx reloaded (existing default site unchanged)"

issue_cert() {
  local domain="$1"
  if [[ -z "$LETSENCRYPT_EMAIL" || "$LETSENCRYPT_EMAIL" == "SET_ME" ]]; then
    echo "LETSENCRYPT_EMAIL not set; skip certbot for ${domain}"
    return 0
  fi
  if ! command -v certbot >/dev/null 2>&1 && ! asf_sudo command -v certbot >/dev/null 2>&1; then
    echo "certbot not installed; ${domain} is HTTP-only until you run certbot"
    return 0
  fi
  asf_sudo certbot --nginx -d "$domain" --non-interactive --agree-tos \
    -m "$LETSENCRYPT_EMAIL" --redirect || {
    echo "certbot failed for ${domain} (DNS A record must point to this VPS). Mini App needs HTTPS."
    return 0
  }
}

issue_cert "$DOMAIN_MINIAPP"
if [[ -n "$DOMAIN_CONSOLE" && "$DOMAIN_CONSOLE" != "$DOMAIN_MINIAPP" && "$DOMAIN_CONSOLE" != "SET_ME" ]]; then
  issue_cert "$DOMAIN_CONSOLE"
fi
