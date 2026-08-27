#!/usr/bin/env bash
# Install ASF nginx vhosts next to the existing site. Never replaces default_server.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DOMAIN_MINIAPP="${DOMAIN_MINIAPP:-}"
DOMAIN_CONSOLE="${DOMAIN_CONSOLE:-$DOMAIN_MINIAPP}"
ASF_HOST_PORT="${ASF_HOST_PORT:-18000}"
LETSENCRYPT_EMAIL="${LETSENCRYPT_EMAIL:-}"
UPSTREAM="127.0.0.1:${ASF_HOST_PORT}"
ACME_ROOT="/var/www/asf-acme"

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

install_http_sites() {
  local tls_csv="${1:-}"
  local tmp
  tmp="$(mktemp -d)"
  export DOMAIN_MINIAPP DOMAIN_CONSOLE ASF_HOST_PORT
  export ASF_UPSTREAM="$UPSTREAM"
  export ASF_TLS_DOMAINS="$tls_csv"
  python3 "${ROOT}/deploy/render_nginx.py" "$tmp"

  local available="" enabled=""
  if asf_sudo test -d /etc/nginx/sites-available; then
    available="/etc/nginx/sites-available"
    enabled="/etc/nginx/sites-enabled"
  elif asf_sudo test -d /etc/nginx/conf.d; then
    available="/etc/nginx/conf.d"
    enabled=""
  else
    echo "Unknown nginx layout" >&2
    rm -rf "$tmp"
    return 1
  fi

  local src base dest
  for src in "${tmp}"/*.conf; do
    base="$(basename "$src")"
    dest="${available}/${base}"
    asf_sudo cp "$src" "$dest"
    if [[ -n "$enabled" ]]; then
      asf_sudo ln -sfn "$dest" "${enabled}/${base}"
    fi
    echo "installed ${dest}"
  done
  rm -rf "$tmp"

  if ! asf_sudo nginx -t; then
    echo "nginx -t failed; leaving previous config" >&2
    return 1
  fi
  asf_sudo nginx -s reload
  echo "nginx reloaded (existing default site unchanged)"
}

if ! install_http_sites ""; then
  echo "failed to install HTTP vhosts" >&2
  exit 1
fi

asf_sudo mkdir -p "${ACME_ROOT}/.well-known/acme-challenge"

issue_cert() {
  local domain="$1"
  if [[ -z "$LETSENCRYPT_EMAIL" || "$LETSENCRYPT_EMAIL" == "SET_ME" ]]; then
    echo "LETSENCRYPT_EMAIL not set; skip certbot for ${domain}"
    return 1
  fi
  if command -v apt-get >/dev/null 2>&1 || asf_sudo command -v apt-get >/dev/null 2>&1; then
    asf_sudo apt-get update -qq || true
    asf_sudo DEBIAN_FRONTEND=noninteractive apt-get install -y certbot || true
  fi

  local certbot_bin=""
  if command -v certbot >/dev/null 2>&1; then
    certbot_bin="$(command -v certbot)"
  elif asf_sudo command -v certbot >/dev/null 2>&1; then
    certbot_bin="certbot"
  fi
  if [[ -z "$certbot_bin" ]]; then
    echo "certbot not installed; ${domain} is HTTP-only"
    return 1
  fi

  # Webroot does not need the nginx plugin (that plugin was missing on this VPS).
  asf_sudo "$certbot_bin" certonly --webroot -w "$ACME_ROOT" -d "$domain" \
    --non-interactive --agree-tos -m "$LETSENCRYPT_EMAIL" \
    --keep-until-expiring --preferred-challenges http || {
    echo "certbot webroot failed for ${domain}. Check DNS A record and that port 80 reaches this VPS."
    return 1
  }
}

TLS_DOMAINS=()
if issue_cert "$DOMAIN_MINIAPP"; then
  TLS_DOMAINS+=("$DOMAIN_MINIAPP")
fi
if [[ -n "$DOMAIN_CONSOLE" && "$DOMAIN_CONSOLE" != "$DOMAIN_MINIAPP" && "$DOMAIN_CONSOLE" != "SET_ME" ]]; then
  if issue_cert "$DOMAIN_CONSOLE"; then
    TLS_DOMAINS+=("$DOMAIN_CONSOLE")
  fi
fi

if [[ ${#TLS_DOMAINS[@]} -gt 0 ]]; then
  IFS=","
  tls_csv="${TLS_DOMAINS[*]}"
  unset IFS
  if install_http_sites "$tls_csv"; then
    echo "HTTPS enabled for: ${tls_csv}"
  else
    echo "Certificates exist but TLS nginx reload failed; HTTP vhost still proxies ASF."
  fi
else
  echo "No TLS certs issued. Mini App needs HTTPS — HTTP vhost is live on port 80."
fi
