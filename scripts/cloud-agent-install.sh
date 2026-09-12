#!/usr/bin/env bash
# Idempotent Cloud Agent bootstrap for the ASF modular monolith.
# Installs system deps (PostgreSQL 16 + Python venv), the Python
# dependencies, prepares the local database, and applies migrations.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PG_VERSION=16
DB_NAME=asf
DB_USER=asf
DB_PASSWORD=asf

echo "==> Installing system packages (PostgreSQL ${PG_VERSION}, python venv)"
if ! command -v pg_ctlcluster >/dev/null 2>&1 || ! python3 -m venv --help >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    "postgresql-${PG_VERSION}" postgresql-contrib \
    python3-venv python3-pip
fi

echo "==> Ensuring PostgreSQL cluster is running"
sudo pg_ctlcluster "${PG_VERSION}" main start 2>/dev/null || true
# Wait for the socket to accept connections before touching roles.
for _ in $(seq 1 30); do
  if sudo -u postgres pg_isready -q; then break; fi
  sleep 1
done

echo "==> Ensuring database role and database exist"
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'" | grep -q 1 \
  || sudo -u postgres psql -c "CREATE ROLE ${DB_USER} WITH LOGIN PASSWORD '${DB_PASSWORD}';"
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1 \
  || sudo -u postgres psql -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};" >/dev/null

echo "==> Preparing Python virtual environment"
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
. .venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt

echo "==> Ensuring local .env exists"
if [ ! -f .env ]; then
  cp .env.example .env
  # Default to the offline stub providers so the app runs without API keys.
  sed -i 's/^STT_PROVIDER=.*/STT_PROVIDER=stub/' .env
fi

echo "==> Applying database migrations"
alembic upgrade head

echo "==> Install complete"
