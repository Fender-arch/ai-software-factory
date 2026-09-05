#!/usr/bin/env bash
# One-time on the geo-unrestricted exit VPS: tinyproxy on 127.0.0.1:8888 only.
set -euo pipefail

PUBKEY="${ASF_EGRESS_PUBKEY:-}"

# env so `asf_sudo VAR=value cmd` works as root (`"$@"` would exec VAR=value).
asf_sudo() {
  if [[ "$(id -u)" -eq 0 ]]; then
    env "$@"
  elif sudo -n true 2>/dev/null; then
    sudo env "$@"
  else
    echo "Need root or passwordless sudo to install tinyproxy" >&2
    return 1
  fi
}

if command -v apt-get >/dev/null 2>&1 || asf_sudo command -v apt-get >/dev/null 2>&1; then
  asf_sudo apt-get update -qq
  asf_sudo DEBIAN_FRONTEND=noninteractive apt-get install -y tinyproxy
else
  echo "apt-get not found; install tinyproxy yourself (listen 127.0.0.1:8888)" >&2
  exit 1
fi

CONF=""
for candidate in /etc/tinyproxy/tinyproxy.conf /etc/tinyproxy.conf; do
  if asf_sudo test -f "$candidate"; then
    CONF="$candidate"
    break
  fi
done
if [[ -z "$CONF" ]]; then
  echo "tinyproxy config not found" >&2
  exit 1
fi

# Ubuntu's tinyproxy.service is Type=forking and waits on this PidFile.
# A config without it makes `systemctl restart` sit until TimeoutStartSec (~90s).
asf_sudo mkdir -p /run/tinyproxy /var/log/tinyproxy
asf_sudo chown tinyproxy:tinyproxy /run/tinyproxy /var/log/tinyproxy 2>/dev/null || true
TMP="$(mktemp)"
cat > "$TMP" <<'EOF'
User tinyproxy
Group tinyproxy
Port 8888
Listen 127.0.0.1
Timeout 600
DefaultErrorFile "/usr/share/tinyproxy/default.html"
StatFile "/usr/share/tinyproxy/stats.html"
LogFile "/var/log/tinyproxy/tinyproxy.log"
PidFile "/run/tinyproxy/tinyproxy.pid"
LogLevel Info
MaxClients 100
MinSpareServers 5
MaxSpareServers 20
StartServers 10
MaxRequestsPerChild 0
Allow 127.0.0.1
ViaProxyName "asf-egress"
ConnectPort 443
ConnectPort 563
EOF
asf_sudo cp "$TMP" "$CONF"
rm -f "$TMP"

asf_sudo systemctl enable tinyproxy 2>/dev/null || true
if ! asf_sudo systemctl restart tinyproxy 2>/dev/null; then
  asf_sudo service tinyproxy restart || true
fi
ready=0
for _ in 1 2 3 4 5 6 7 8 9 10; do
  if command -v nc >/dev/null 2>&1 && nc -z 127.0.0.1 8888 2>/dev/null; then
    ready=1
    break
  fi
  if command -v ss >/dev/null 2>&1 && ss -lnt | grep -q ':8888'; then
    ready=1
    break
  fi
  sleep 1
done
if [[ "$ready" -ne 1 ]]; then
  echo "tinyproxy is not listening on 127.0.0.1:8888" >&2
  asf_sudo systemctl status tinyproxy --no-pager -l 2>/dev/null || true
  exit 1
fi

if [[ -n "$PUBKEY" ]]; then
  AUTH_USER="${SUDO_USER:-${USER:-root}}"
  if [[ "$(id -u)" -eq 0 ]]; then
    HOME_DIR="$(getent passwd root | cut -d: -f6)"
  else
    HOME_DIR="$(getent passwd "$AUTH_USER" | cut -d: -f6)"
    HOME_DIR="${HOME_DIR:-$HOME}"
  fi
  SSH_DIR="${HOME_DIR}/.ssh"
  mkdir -p "$SSH_DIR"
  chmod 700 "$SSH_DIR"
  AUTH="${SSH_DIR}/authorized_keys"
  touch "$AUTH"
  chmod 600 "$AUTH"
  if ! grep -qxF "$PUBKEY" "$AUTH"; then
    printf '%s\n' "$PUBKEY" >> "$AUTH"
  fi
fi

echo "tinyproxy listening on 127.0.0.1:8888 (not public)"
