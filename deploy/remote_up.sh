#!/usr/bin/env bash
# Unpack tarball, write .env, start ASF compose without touching other stacks.
set -euo pipefail

DEPLOY_PATH="${VPS_DEPLOY_PATH:-/opt/asf}"
if [[ "$DEPLOY_PATH" == "SET_ME" || -z "$DEPLOY_PATH" ]]; then
  DEPLOY_PATH="/opt/asf"
fi
TARBALL="${ASF_TARBALL:-/tmp/asf-deploy.tgz}"
if [[ -z "${ASF_HOST_PORT:-}" || "${ASF_HOST_PORT}" == "SET_ME" || ! "${ASF_HOST_PORT}" =~ ^[0-9]+$ ]]; then
  ASF_HOST_PORT="18000"
fi
export ASF_HOST_PORT

# env so `asf_sudo VAR=value cmd` works as root (`"$@"` would exec VAR=value).
asf_sudo() {
  if [[ "$(id -u)" -eq 0 ]]; then
    env "$@"
  elif sudo -n true 2>/dev/null; then
    sudo env "$@"
  elif [[ -n "${VPS_PASSWORD:-}" ]]; then
    printf '%s\n' "$VPS_PASSWORD" | sudo -S -p "" env "$@"
  else
    env "$@"
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
chmod +x "${DEPLOY_PATH}/deploy/"*.sh 2>/dev/null || true

cd "$DEPLOY_PATH"
export PYTHONPATH="$DEPLOY_PATH"
export ASF_ENV_PATH="${DEPLOY_PATH}/.env"
python3 deploy/write_env.py
# Empty GitHub HTTPS_PROXY= wins over --env-file .env interpolation and
# wipes http://egress:8888 from api/bot (via_proxy=false, sendDocument ConnectError).
set +u
for key in HTTPS_PROXY HTTP_PROXY ALL_PROXY TELEGRAM_PROXY LLM_HTTP_PROXY; do
  val="${!key}"
  if [[ -z "$val" || "$val" == "SET_ME" ]]; then
    unset "$key"
  fi
done
set -u
chmod +x "${DEPLOY_PATH}/deploy/"*.sh "${DEPLOY_PATH}/docker/"*.sh 2>/dev/null || true
if [[ -n "${EGRESS_SSH_HOST:-}" && "${EGRESS_SSH_HOST}" != "SET_ME" ]]; then
  export EGRESS_SSH_HOST
  export EGRESS_SSH_USER="${EGRESS_SSH_USER:-root}"
  export EGRESS_SSH_PORT="${EGRESS_SSH_PORT:-22}"
  export EGRESS_SSH_PASSWORD="${EGRESS_SSH_PASSWORD:-}"
  bash "${DEPLOY_PATH}/deploy/setup_egress_tunnel.sh"
  export ASF_EGRESS_KEY_PATH="${ASF_EGRESS_KEY_DIR:-/opt/asf-secrets}/egress_id_ed25519"
  export COMPOSE_PROFILES="${COMPOSE_PROFILES:+$COMPOSE_PROFILES,}egress"
fi
# Compose interpolates ${ASF_HOST_PORT} from the process env first.
# GitHub placeholder SET_ME is non-empty, so ${ASF_HOST_PORT:-18000} would not apply.
if [[ -z "${ASF_HOST_PORT:-}" || "${ASF_HOST_PORT}" == "SET_ME" || ! "${ASF_HOST_PORT}" =~ ^[0-9]+$ ]]; then
  ASF_HOST_PORT="$(python3 -c "from pathlib import Path
for line in Path('.env').read_text().splitlines():
    if line.startswith('ASF_HOST_PORT='):
        print(line.split('=',1)[1].strip().strip(chr(34))); break
")"
fi
if [[ -z "${ASF_HOST_PORT:-}" || "${ASF_HOST_PORT}" == "SET_ME" || ! "${ASF_HOST_PORT}" =~ ^[0-9]+$ ]]; then
  ASF_HOST_PORT="18000"
fi
export ASF_HOST_PORT

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

COMPOSE_FILES=(-f docker-compose.prod.yml)
if [[ -f docker-compose.telegram-egress.yml ]]; then
  COMPOSE_FILES+=(-f docker-compose.telegram-egress.yml)
  echo "Using local telegram egress override (IPv4 extra_hosts)"
fi
PROFILE_ARGS=()
if [[ "${COMPOSE_PROFILES:-}" == *egress* ]]; then
  PROFILE_ARGS=(--profile egress)
fi

if [[ "${COMPOSE_PROFILES:-}" == *egress* ]]; then
  compose "${COMPOSE_FILES[@]}" "${PROFILE_ARGS[@]}" --env-file .env up -d --build egress
  echo "Waiting for egress tunnel on :8888"
  ready=0
  for _ in $(seq 1 36); do
    if compose "${COMPOSE_FILES[@]}" "${PROFILE_ARGS[@]}" --env-file .env exec -T egress \
      nc -z 127.0.0.1 8888 2>/dev/null; then
      ready=1
      break
    fi
    sleep 5
  done
  if [[ "$ready" -ne 1 ]]; then
    echo "egress tunnel did not become ready; API/Telegram may fail geo checks" >&2
    compose "${COMPOSE_FILES[@]}" "${PROFILE_ARGS[@]}" --env-file .env logs --tail 50 egress || true
  fi
fi
compose "${COMPOSE_FILES[@]}" "${PROFILE_ARGS[@]}" --env-file .env up -d --build

echo "ASF listening on 127.0.0.1:${ASF_HOST_PORT} (not 80/443)"
compose "${COMPOSE_FILES[@]}" "${PROFILE_ARGS[@]}" --env-file .env ps

chmod +x "${DEPLOY_PATH}/deploy/"*.sh 2>/dev/null || true
DOMAIN_MINIAPP="${DOMAIN_MINIAPP}" \
DOMAIN_CONSOLE="${DOMAIN_CONSOLE:-$DOMAIN_MINIAPP}" \
ASF_HOST_PORT="${ASF_HOST_PORT}" \
LETSENCRYPT_EMAIL="${LETSENCRYPT_EMAIL:-}" \
VPS_PASSWORD="${VPS_PASSWORD:-}" \
bash "${DEPLOY_PATH}/deploy/setup_proxy.sh"

echo "Probing VPS → https://api.telegram.org (sendDocument goes from this host, not from Mini App)..."
bash "${DEPLOY_PATH}/deploy/diagnose_telegram_egress.sh" || true
echo "TELEGRAM_BOT_TOKEN must be the same BotFather bot that opens the Mini App."
echo "Deploy finished. Existing default website was not modified."
