#!/usr/bin/env bash
# If geo-egress is configured but api/bot have empty HTTPS_PROXY, fill
# http://egress:8888 and recreate those services. Never prints URLs or secrets.
set -euo pipefail

DEPLOY_PATH="${VPS_DEPLOY_PATH:-/opt/asf}"
if [[ "$DEPLOY_PATH" == "SET_ME" || -z "$DEPLOY_PATH" ]]; then
  DEPLOY_PATH="/opt/asf"
fi
cd "$DEPLOY_PATH"
export PYTHONPATH="$DEPLOY_PATH"
export ASF_ENV_PATH="${DEPLOY_PATH}/.env"

if [[ ! -f .env ]]; then
  echo "missing ${DEPLOY_PATH}/.env" >&2
  exit 1
fi

python3 - <<'PY'
from pathlib import Path
from core.egress import parse_env_file_values

path = Path(".env")
parsed = parse_env_file_values(path.read_text(encoding="utf-8"))
host = (parsed.get("EGRESS_SSH_HOST") or "").strip()
if not host or host == "SET_ME":
    print("EGRESS_SSH_HOST empty; skip container proxy hotfix")
    raise SystemExit(0)
tunnel = "http://egress:8888"
changed = False
for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "TELEGRAM_PROXY"):
    if not (parsed.get(key) or "").strip():
        parsed[key] = tunnel
        changed = True
no_proxy = (parsed.get("NO_PROXY") or "").strip()
needed = ["localhost", "127.0.0.1", "db", "egress"]
parts = [p.strip() for p in no_proxy.split(",") if p.strip()]
for item in needed:
    if item not in parts:
        parts.append(item)
        changed = True
parsed["NO_PROXY"] = ",".join(parts)
if not changed:
    print("proxy keys already set in .env")
else:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    seen: set[str] = set()
    out = []
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
            out.append(line)
            continue
        key, _, _ = line.partition("=")
        key = key.strip()
        if key in {"HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "TELEGRAM_PROXY", "NO_PROXY"}:
            out.append(f"{key}={parsed[key]}")
            seen.add(key)
            continue
        out.append(line)
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "TELEGRAM_PROXY", "NO_PROXY"):
        if key not in seen:
            out.append(f"{key}={parsed[key]}")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    print("wrote tunnel proxy keys into .env (values not printed)")
PY

set +u
for key in HTTPS_PROXY HTTP_PROXY ALL_PROXY TELEGRAM_PROXY LLM_HTTP_PROXY; do
  val="${!key}"
  if [[ -z "$val" || "$val" == "SET_ME" ]]; then
    unset "$key"
  fi
done
set -u

compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
    return
  fi
  if command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
    return
  fi
  echo "Docker Compose is not installed" >&2
  exit 1
}

files=(-f docker-compose.prod.yml)
if [[ -f docker-compose.telegram-egress.yml ]]; then
  files+=(-f docker-compose.telegram-egress.yml)
fi
profile=(--profile egress)
echo "Recreating api/bot (and egress if needed) so containers pick up .env proxy"
compose "${files[@]}" "${profile[@]}" --env-file .env up -d --no-build egress
ready=0
for _ in $(seq 1 24); do
  if compose "${files[@]}" "${profile[@]}" --env-file .env exec -T egress \
    nc -z 127.0.0.1 8888 2>/dev/null; then
    ready=1
    break
  fi
  sleep 5
done
if [[ "$ready" -ne 1 ]]; then
  echo "egress :8888 not ready; not recreating api/bot" >&2
  compose "${files[@]}" "${profile[@]}" --env-file .env logs --tail 40 egress || true
  exit 1
fi
compose "${files[@]}" "${profile[@]}" --env-file .env up -d --no-build --force-recreate api bot
echo "api/bot recreated"
