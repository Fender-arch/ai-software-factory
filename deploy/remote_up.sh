#!/usr/bin/env bash
# Unpack tarball, write .env, start ASF compose without touching other stacks.
set -euo pipefail

DEPLOY_PATH="${VPS_DEPLOY_PATH:-/opt/asf}"
if [[ "$DEPLOY_PATH" == "SET_ME" || -z "$DEPLOY_PATH" ]]; then
  DEPLOY_PATH="/opt/asf"
fi
TARBALL="${ASF_TARBALL:-/tmp/asf-deploy.tgz}"
ASF_HOST_PORT="${ASF_HOST_PORT:-18000}"

asf_sudo() {
  if [[ "$(id -u)" -eq 0 ]]; then
    "$@"
  elif sudo -n true 2>/dev/null; then
    sudo "$@"
  elif [[ -n "${VPS_PASSWORD:-}" ]]; then
    printf '%s\n' "$VPS_PASSWORD" | sudo -S -p "" "$@"
  else
    "$@"
  fi
}

if [[ ! -f "$TARBALL" ]]; then
  echo "missing tarball ${TARBALL}" >&2
  exit 1
fi

asf_sudo mkdir -p "$DEPLOY_PATH"
asf_sudo chown -R "$(id -u):$(id -g)" "$DEPLOY_PATH" 2>/dev/null || true
mkdir -p "$DEPLOY_PATH"
tar -xzf "$TARBALL" -C "$DEPLOY_PATH"

cd "$DEPLOY_PATH"
export PYTHONPATH="$DEPLOY_PATH"
export ASF_ENV_PATH="${DEPLOY_PATH}/.env"
python3 deploy/write_env.py

compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
    return
  fi
  if command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
    return
  fi
  if asf_sudo docker compose version >/dev/null 2>&1; then
    asf_sudo docker compose "$@"
    return
  fi
  echo "Docker Compose is not installed on the VPS" >&2
  exit 1
}

if ! docker info >/dev/null 2>&1 && ! asf_sudo docker info >/dev/null 2>&1; then
  echo "Docker is not running / not installed" >&2
  exit 1
fi

compose -f docker-compose.prod.yml --env-file .env up -d --build

echo "ASF listening on 127.0.0.1:${ASF_HOST_PORT} (not 80/443)"
compose -f docker-compose.prod.yml --env-file .env ps

if [[ -x "${DEPLOY_PATH}/deploy/setup_proxy.sh" ]]; then
  # shellcheck disable=SC1091
  DOMAIN_MINIAPP="${DOMAIN_MINIAPP}" \
  DOMAIN_CONSOLE="${DOMAIN_CONSOLE:-$DOMAIN_MINIAPP}" \
  ASF_HOST_PORT="${ASF_HOST_PORT}" \
  LETSENCRYPT_EMAIL="${LETSENCRYPT_EMAIL:-}" \
  VPS_PASSWORD="${VPS_PASSWORD:-}" \
  bash "${DEPLOY_PATH}/deploy/setup_proxy.sh"
fi

echo "Deploy finished. Existing default website was not modified."
