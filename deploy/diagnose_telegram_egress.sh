#!/usr/bin/env bash
# Diagnose VPS → api.telegram.org. Never prints tokens, .env, or passwords.
set -u
DEPLOY_PATH="${VPS_DEPLOY_PATH:-/opt/asf}"
if [[ "$DEPLOY_PATH" == "SET_ME" || -z "$DEPLOY_PATH" ]]; then
  DEPLOY_PATH="/opt/asf"
fi

echo "=== ASF Telegram egress diagnose ==="
echo "host=$(hostname) path=${DEPLOY_PATH}"

echo
echo "-- host stack --"
ip -4 route show default 2>/dev/null | head -3 || echo "no ipv4 default"
ip -6 route show default 2>/dev/null | head -3 || echo "no ipv6 default"

echo
echo "-- DNS api.telegram.org --"
if command -v getent >/dev/null 2>&1; then
  getent ahosts api.telegram.org 2>/dev/null | head -8 || true
fi
if command -v python3 >/dev/null 2>&1; then
  python3 - <<'PY'
import socket
for fam, label in ((socket.AF_INET, "A"), (socket.AF_INET6, "AAAA")):
    try:
        infos = socket.getaddrinfo("api.telegram.org", 443, fam, socket.SOCK_STREAM)
        addrs = sorted({item[4][0] for item in infos})
        print(f"{label}: {', '.join(addrs) or '(none)'}")
    except OSError as exc:
        print(f"{label}: fail {type(exc).__name__}")
PY
fi

curl_one() {
  local label="$1"
  shift
  local code
  code="$(curl -sS -o /dev/null -w '%{http_code} err=%{errormsg} ip=%{remote_ip}' --max-time 8 "$@" 2>/dev/null || true)"
  echo "${label}: ${code:-fail}"
}

echo
echo "-- host HTTPS (no token) --"
curl_one "example.org default" https://example.org
curl_one "telegram default" https://api.telegram.org
curl_one "telegram IPv4" -4 https://api.telegram.org
curl_one "telegram IPv6" -6 https://api.telegram.org

echo
echo "-- host firewall (summary) --"
if command -v ufw >/dev/null 2>&1; then
  ufw status verbose 2>/dev/null | head -20 || echo "ufw not readable"
else
  echo "ufw not installed"
fi
if command -v iptables >/dev/null 2>&1; then
  iptables -S OUTPUT 2>/dev/null | head -20 || echo "iptables OUTPUT not readable"
fi

compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
    return
  fi
  if command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
    return
  fi
  return 1
}

echo
echo "-- api container --"
if [[ -f "${DEPLOY_PATH}/docker-compose.prod.yml" ]]; then
  (
    cd "$DEPLOY_PATH" || exit 0
    files=(-f docker-compose.prod.yml)
    if [[ -f docker-compose.telegram-egress.yml ]]; then
      files+=(-f docker-compose.telegram-egress.yml)
    fi
    compose "${files[@]}" --env-file .env exec -T api python - <<'PY' || echo "container diagnose failed"
import json
import socket
import urllib.request
from integrations.telegram.notify import diagnose_telegram_bot_api

print("container ipv4 route probe:", end=" ")
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(1)
    s.connect(("1.1.1.1", 443))
    s.close()
    print("yes")
except OSError as exc:
    print(type(exc).__name__)

for host in ("example.org", "api.telegram.org"):
    try:
        urllib.request.urlopen(f"https://{host}", timeout=8)
        print(f"container urllib {host}: ok")
    except Exception as exc:
        print(f"container urllib {host}: {type(exc).__name__}")

report = diagnose_telegram_bot_api()
print(json.dumps(report, ensure_ascii=False))
PY
  )
else
  echo "compose file missing"
fi

echo
echo "-- verdict --"
python3 - <<'PY'
import subprocess, sys

def run(cmd):
    try:
        return subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL, timeout=12).strip()
    except Exception:
        return ""

def curl(args):
    try:
        out = subprocess.check_output(
            ["curl", "-sS", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", "8", *args],
            text=True, stderr=subprocess.DEVNULL, timeout=12,
        ).strip()
        return out.isdigit() and out != "000"
    except Exception:
        return False

tg4 = curl(["-4", "https://api.telegram.org"])
tg6 = curl(["-6", "https://api.telegram.org"])
tg = curl(["https://api.telegram.org"])
ex = curl(["https://example.org"])
print(f"host_example={ex} host_telegram={tg} host_telegram_v4={tg4} host_telegram_v6={tg6}")
if tg4 or tg:
    print("VERDICT=host_can_reach_telegram")
    print("HINT=If /health/telegram is still down, recreate api/bot with ASF_TELEGRAM_IP=4 and DNS 8.8.8.8")
elif ex and not tg4 and not tg:
    print("VERDICT=telegram_blocked")
    print("HINT=HTTPS works, Telegram TCP/443 times out. Not ufw (if OUTPUT allow) and not Mini App. Reuse the existing AI/foreign-channel URL as HTTPS_PROXY (same hop as Groq) or TELEGRAM_PROXY, then recreate api/bot. Do not open a FirstVDS ticket if that hop already works for AI.")
elif not ex and not tg:
    print("VERDICT=egress_blocked")
    print("HINT=Outgoing 443 looks blocked (ufw/iptables/provider). Allow OUTPUT 443/tcp.")
else:
    print("VERDICT=unknown")
    print("HINT=See DNS and curl lines above.")
PY
