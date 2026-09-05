#!/usr/bin/env bash
# Per-boot runtime init for the ASF Cloud Agent environment.
# Starts the PostgreSQL cluster the API depends on and waits until it
# accepts connections. Dependency installation and migrations live in
# scripts/cloud-agent-install.sh, not here.
set -euo pipefail

PG_VERSION=16

echo "==> Starting PostgreSQL cluster"
sudo pg_ctlcluster "${PG_VERSION}" main start 2>/dev/null || true

for _ in $(seq 1 30); do
  if sudo -u postgres pg_isready -q; then
    echo "==> PostgreSQL is ready"
    exit 0
  fi
  sleep 1
done

echo "!! PostgreSQL did not become ready in time" >&2
exit 1
