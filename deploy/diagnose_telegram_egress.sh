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
echo "-- compose services --"
if [[ -f "${DEPLOY_PATH}/docker-compose.prod.yml" ]]; then
  (
    cd "$DEPLOY_PATH" || exit 0
    compose -f docker-compose.prod.yml --env-file .env config --services 2>/dev/null || echo "compose config failed"
    echo -n "api network_mode="
    compose -f docker-compose.prod.yml --env-file .env config 2>/dev/null \
      | awk '/^  api:/{p=1;next} p && /^  [a-z]/{exit} p && /network_mode:/{print $2; found=1; exit} END{if(!found) print "bridge_or_default"}'
  )
else
  echo "compose file missing"
fi

echo
echo "-- container network_mode (names only) --"
if command -v docker >/dev/null 2>&1; then
  docker ps -a --filter "name=asf-" --format '{{.Names}} {{.Status}}' 2>/dev/null || true
  ids="$(docker ps -aq --filter "name=asf-" 2>/dev/null || true)"
  if [[ -n "$ids" ]]; then
    docker inspect $ids --format '{{.Name}} network_mode={{.HostConfig.NetworkMode}}' 2>/dev/null || true
  fi
fi

echo
echo "-- env key presence (NAMES only, never values) --"
_key_state() {
  local file="$1" key="$2"
  if [[ ! -f "$file" ]]; then
    echo "${key}=absent_file"
    return
  fi
  python3 - "$file" "$key" <<'PY'
import sys
from pathlib import Path
path = Path(sys.argv[1])
key = sys.argv[2]
found = False
for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
    line = raw.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    name, _, val = line.partition("=")
    if name.strip() != key:
        continue
    found = True
    text = val.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        text = text[1:-1]
    print(f"{key}={'set' if text and text != 'SET_ME' else 'empty'}")
    break
if not found:
    print(f"{key}=absent")
PY
}
for key in HTTPS_PROXY HTTP_PROXY ALL_PROXY TELEGRAM_PROXY LLM_HTTP_PROXY NO_PROXY \
           LLM_PROVIDER LLM_MODEL GROQ_API_KEY OPENAI_API_KEY PROXY_URL PROXY_HOST PROXY_PORT; do
  _key_state "${DEPLOY_PATH}/.env" "$key"
done

echo
echo "-- container env NAMES (api/bot, filtered) --"
if [[ -f "${DEPLOY_PATH}/docker-compose.prod.yml" ]]; then
  (
    cd "$DEPLOY_PATH" || exit 0
    for svc in api bot; do
      echo "service=${svc}"
      compose -f docker-compose.prod.yml --env-file .env exec -T "$svc" \
        python - <<'PY' 2>/dev/null || echo "  exec failed"
import os
needles = (
    "HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY", "TELEGRAM_PROXY",
    "LLM_HTTP_PROXY", "NO_PROXY", "LLM_", "GROQ_", "OPENAI_", "PROXY_",
)
names = []
for key in os.environ:
    if any(key == n or key.startswith(n) for n in needles):
        val = os.environ.get(key) or ""
        names.append(f"{key}={'set' if val.strip() and val != 'SET_ME' else 'empty'}")
print("  " + (" ".join(sorted(names)) if names else "none"))
PY
    done
  )
fi

echo
echo "-- host VPN / tunnel / proxy listeners (no addresses, no URLs) --"
python3 - <<'PY'
import os
import re
import socket
import subprocess

def run(cmd):
    try:
        return subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL, timeout=8)
    except Exception:
        return ""

links = run(["ip", "-o", "link", "show"])
vpn_ifaces = []
for line in links.splitlines():
    name = line.split(":", 2)[1].strip().split("@", 1)[0] if ":" in line else ""
    low = name.lower()
    if re.search(r"(tun|tap|wg|nordlynx|tailscale|ppp|utun|tun2socks)", low):
        vpn_ifaces.append(name)
print("vpn_ifaces=" + (",".join(vpn_ifaces) if vpn_ifaces else "none"))

tables = []
for line in run(["ip", "rule", "list"]).splitlines():
    if "lookup" in line:
        tables.append(line.rsplit(None, 1)[-1])
print("policy_tables=" + (",".join(sorted(set(tables))) if tables else "none"))

comms = run(["ps", "-eo", "comm="])
wanted = (
    "wg-quick", "wg", "openvpn", "openconnect", "strongswan", "charon",
    "wireguard", "tailscaled", "redsocks", "tun2socks", "badvpn-tun2socks",
    "clash", "clash-meta", "mihomo", "v2ray", "xray", "sing-box", "singbox",
    "ss-local", "ss-redir", "hysteria", "hysteria2", "3x-ui", "x-ui",
    "proxychains", "dante", "tinyproxy", "privoxy", "gost", "brook",
)
running = sorted({c.strip() for c in comms.splitlines() if c.strip() in wanted})
print("vpn_or_proxy_procs=" + (",".join(running) if running else "none"))

units = run(["systemctl", "list-units", "--type=service", "--state=running", "--no-legend", "--no-pager"])
unit_hits = []
for line in units.splitlines():
    name = line.split()[0] if line.split() else ""
    low = name.lower()
    if re.search(r"(wg|wireguard|openvpn|tailscale|clash|xray|v2ray|sing-box|3x-ui|x-ui|redsocks|hysteria)", low):
        unit_hits.append(name)
print("vpn_or_proxy_units=" + (",".join(unit_hits) if unit_hits else "none"))

proxy_ports = (1080, 1086, 1087, 10808, 2080, 3128, 7890, 7891, 8080, 8443, 8888, 9050, 20170, 61111)
listening = []
for port in proxy_ports:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.2)
    try:
        if sock.connect_ex(("127.0.0.1", port)) == 0:
            listening.append(str(port))
    except OSError:
        pass
    finally:
        sock.close()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.2)
    try:
        if sock.connect_ex(("172.17.0.1", port)) == 0:
            listening.append(f"docker0:{port}")
    except OSError:
        pass
    finally:
        sock.close()
print("local_proxy_ports=" + (",".join(listening) if listening else "none"))

sidecars = []
for line in run(["docker", "ps", "--format", "{{.Names}} {{.Image}}"]).splitlines():
    low = line.lower()
    if re.search(r"(clash|xray|v2ray|sing-box|wireguard|wg-easy|gluetun|privoxy|tinyproxy|3x-ui)", low):
        sidecars.append(line.split()[0])
print("proxy_sidecars=" + (",".join(sidecars) if sidecars else "none"))
print("docker_network_host_hint=" + ("yes" if os.path.exists("/opt/asf/docker-compose.prod.yml") else "n/a"))
PY

echo
echo "-- host HTTPS: groq vs telegram (http code only) --"
curl_one "groq default" https://api.groq.com
curl_one "groq IPv4" -4 https://api.groq.com
curl_one "openai default" https://api.openai.com

echo
echo "-- host telegram via vpn ifaces (no IPs) --"
if command -v python3 >/dev/null 2>&1; then
  python3 - <<'PY'
import re
import subprocess

def links():
    try:
        out = subprocess.check_output(["ip", "-o", "link", "show"], text=True, stderr=subprocess.DEVNULL)
    except Exception:
        return []
    names = []
    for line in out.splitlines():
        name = line.split(":", 2)[1].strip().split("@", 1)[0] if ":" in line else ""
        if re.search(r"(tun|tap|wg|nordlynx|tailscale|ppp)", name.lower()):
            names.append(name)
    return names

def curl_iface(iface):
    try:
        return subprocess.check_output(
            ["curl", "-sS", "-o", "/dev/null", "-w", "%{http_code} err=%{errormsg}",
             "--max-time", "8", "--interface", iface, "https://api.telegram.org"],
            text=True, stderr=subprocess.DEVNULL, timeout=12,
        ).strip()
    except Exception:
        return "fail"

found = links()
if not found:
    print("no vpn iface to bind")
else:
    for iface in found:
        print(f"telegram iface {iface}: {curl_iface(iface)}")
PY
fi

echo
echo "-- container groq vs telegram --"
if [[ -f "${DEPLOY_PATH}/docker-compose.prod.yml" ]]; then
  (
    cd "$DEPLOY_PATH" || exit 0
    compose -f docker-compose.prod.yml --env-file .env exec -T api python - <<'PY' || echo "container groq/telegram probe failed"
import json
import urllib.request
from integrations.telegram.notify import diagnose_telegram_bot_api

for host in ("api.groq.com", "api.openai.com", "api.telegram.org"):
    try:
        urllib.request.urlopen(f"https://{host}", timeout=8)
        print(f"container urllib {host}: ok")
    except Exception as exc:
        print(f"container urllib {host}: {type(exc).__name__}")
print(json.dumps(diagnose_telegram_bot_api(), ensure_ascii=False))
PY
  )
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
    print("HINT=Host VPN/default route reaches Telegram. api/bot must use network_mode=host (not Docker bridge).")
elif ex and not tg4 and not tg:
    print("VERDICT=telegram_blocked")
    print("HINT=Default host route cannot reach Telegram. Check vpn_ifaces / local_proxy_ports / groq vs telegram above. Prefer host network for api/bot so they share the VPS VPN. Do not invent HTTPS_PROXY.")
elif not ex and not tg:
    print("VERDICT=egress_blocked")
    print("HINT=Outgoing 443 looks blocked (ufw/iptables/provider). Allow OUTPUT 443/tcp.")
else:
    print("VERDICT=unknown")
    print("HINT=See DNS, vpn_ifaces, and curl lines above.")
PY
