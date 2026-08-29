#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/jobradar}"
ENV_FILE="${ENV_FILE:-$APP_DIR/.env.prod}"
COMPOSE_FILE="${COMPOSE_FILE:-$APP_DIR/docker-compose.prod.yml}"

mkdir -p "$APP_DIR/backups" "$APP_DIR/logs"
cd "$APP_DIR"

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing $ENV_FILE. Copy .env.prod.example to .env.prod and set APP_IMAGE and POSTGRES_PASSWORD." >&2
  exit 2
fi

export JOBRADAR_ENV_FILE="$ENV_FILE"

if [ "${SKIP_PULL:-false}" != "true" ]; then
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" pull
fi
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d db
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d app
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" run --rm ingest python -m app.cli score-all
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" run --rm ingest
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps

if [ -x "$APP_DIR/check-health.sh" ]; then
  "$APP_DIR/check-health.sh"
fi
