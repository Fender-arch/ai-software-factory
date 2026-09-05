#!/bin/sh
# SSH local-forward: this container :8888 -> exit-node tinyproxy (127.0.0.1:8888).
set -eu

KEY="${EGRESS_SSH_KEY_FILE:-/run/secrets/egress_id_ed25519}"
HOST="${EGRESS_SSH_HOST:-}"
USER="${EGRESS_SSH_USER:-root}"
PORT="${EGRESS_SSH_PORT:-22}"

if [ -z "$HOST" ] || [ "$HOST" = "SET_ME" ]; then
  echo "EGRESS_SSH_HOST is empty; egress container should not be started" >&2
  exit 1
fi
if [ ! -f "$KEY" ]; then
  echo "missing SSH key at ${KEY}" >&2
  exit 1
fi
chmod 600 "$KEY" 2>/dev/null || true
mkdir -p /root/.ssh
chmod 700 /root/.ssh

export AUTOSSH_GATETIME=0
exec autossh -M 0 -N \
  -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 \
  -o ExitOnForwardFailure=yes \
  -o StrictHostKeyChecking=accept-new \
  -o UserKnownHostsFile=/root/.ssh/known_hosts \
  -o IdentitiesOnly=yes \
  -i "$KEY" \
  -p "$PORT" \
  -L 0.0.0.0:8888:127.0.0.1:8888 \
  "${USER}@${HOST}"
