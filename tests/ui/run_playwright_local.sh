#!/usr/bin/env bash
set -euo pipefail

# Usage: ./tests/ui/run_playwright_local.sh [<spec>]
# Starts a local Postgres via docker-compose, launches the Flask app in development
# mode with AUTO_CREATE_TABLES enabled, runs the requested Playwright spec (or all UI tests),
# then tears down the DB container.

SPEC=${1:-tests/ui/pod-remove.spec.js}
COMPOSE_FILE="$(dirname "$0")/docker-compose.postgres.yml"

export POSTGRES_USER=playuser
export POSTGRES_PASSWORD=playpass
export POSTGRES_DB=playdb

echo "Bringing up Postgres..."
docker compose -f "$COMPOSE_FILE" up -d

echo "Waiting for Postgres to be healthy..."
docker compose -f "$COMPOSE_FILE" wait --timeout 60 db || true

export DATABASE_URL="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@127.0.0.1:5432/${POSTGRES_DB}"
export ADMIN_E2E_PASSWORD=${ADMIN_E2E_PASSWORD:-admin-pass}
export ADMIN_USERNAME=${ADMIN_USERNAME:-admin}
export ADMIN_PASSWORD_HASH=$(python - <<'PY'
from werkzeug.security import generate_password_hash
print(generate_password_hash("${ADMIN_E2E_PASSWORD}"))
PY
)
export FLASK_ENV=development
export PORT=5000
export AUTO_CREATE_TABLES=true

echo "Starting Flask app (background)..."
python run.py &
APP_PID=$!

trap 'echo "Stopping app and tearing down Postgres..."; kill $APP_PID 2>/dev/null || true; docker compose -f "$COMPOSE_FILE" down' EXIT

echo "Waiting for app /health..."
for i in {1..30}; do
  if curl -sS --fail http://127.0.0.1:${PORT}/health >/dev/null 2>&1; then
    echo "App healthy"
    break
  fi
  sleep 1
done

echo "Installing Playwright browsers (if needed)..."
npx playwright install --with-deps

echo "Running Playwright spec: $SPEC"
npx playwright test "$SPEC" --project=chromium-desktop --reporter=list

echo "Playwright finished"
