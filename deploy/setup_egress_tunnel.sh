#!/usr/bin/env bash
# On the ASF VPS: durable SSH key + optional first-time install on the exit node.
set -euo pipefail

HOST="${EGRESS_SSH_HOST:-}"
USER="${EGRESS_SSH_USER:-root}"
PORT="${EGRESS_SSH_PORT:-22}"
SECRET_DIR="${ASF_EGRESS_KEY_DIR:-/opt/asf-secrets}"
KEY="${SECRET_DIR}/egress_id_ed25519"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [[ -z "$HOST" || "$HOST" == "SET_ME" ]]; then
  echo "EGRESS_SSH_HOST not set; skip egress tunnel" >&2
  exit 0
fi
if [[ "$PORT" == "SET_ME" || ! "$PORT" =~ ^[0-9]+$ ]]; then
  PORT=22
fi
if [[ -z "$USER" || "$USER" == "SET_ME" ]]; then
  USER=root
fi

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

asf_sudo mkdir -p "$SECRET_DIR"
asf_sudo chown -R "$(id -u):$(id -g)" "$SECRET_DIR" 2>/dev/null || true
mkdir -p "$SECRET_DIR"
chmod 700 "$SECRET_DIR"

if ! command -v ssh-keygen >/dev/null 2>&1; then
  if command -v apt-get >/dev/null 2>&1 || asf_sudo command -v apt-get >/dev/null 2>&1; then
    asf_sudo apt-get update -qq || true
    asf_sudo DEBIAN_FRONTEND=noninteractive apt-get install -y openssh-client
  fi
fi
if ! command -v ssh-keygen >/dev/null 2>&1; then
  echo "ssh-keygen is required on the ASF VPS" >&2
  exit 1
fi

if [[ ! -f "$KEY" ]]; then
  ssh-keygen -t ed25519 -N "" -f "$KEY" -C "asf-egress@$(hostname -s 2>/dev/null || echo asf)"
fi
chmod 600 "$KEY"
chmod 644 "${KEY}.pub"
PUBKEY="$(cat "${KEY}.pub")"

if [[ -n "${EGRESS_SSH_PASSWORD:-}" && "${EGRESS_SSH_PASSWORD}" != "SET_ME" ]]; then
  if ! command -v sshpass >/dev/null 2>&1; then
    if command -v apt-get >/dev/null 2>&1 || asf_sudo command -v apt-get >/dev/null 2>&1; then
      asf_sudo apt-get update -qq || true
      asf_sudo DEBIAN_FRONTEND=noninteractive apt-get install -y sshpass || true
    fi
  fi
  if ! command -v sshpass >/dev/null 2>&1; then
    echo "sshpass missing; cannot push key to ${HOST}. Add this pubkey to authorized_keys:" >&2
    echo "$PUBKEY" >&2
    exit 1
  fi
  export SSHPASS="${EGRESS_SSH_PASSWORD}"
  SSH_OPTS=(-o StrictHostKeyChecking=accept-new -o UserKnownHostsFile="${SECRET_DIR}/known_hosts")
  echo "Installing tinyproxy + SSH key on ${USER}@${HOST}"
  sshpass -e scp "${SSH_OPTS[@]}" -P "$PORT" \
    "${KEY}.pub" \
    "${ROOT}/deploy/setup_egress_exit.sh" \
    "${USER}@${HOST}:/tmp/"
  sshpass -e ssh "${SSH_OPTS[@]}" -p "$PORT" "${USER}@${HOST}" \
    'ASF_EGRESS_PUBKEY="$(cat /tmp/egress_id_ed25519.pub)" bash /tmp/setup_egress_exit.sh'
  unset SSHPASS
  unset EGRESS_SSH_PASSWORD
else
  echo "EGRESS_SSH_PASSWORD empty — assuming key is already on ${HOST}"
  echo "Public key (add to authorized_keys if the tunnel fails):"
  echo "$PUBKEY"
fi

echo "ASF_EGRESS_KEY_PATH=${KEY}"
