#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${APP_DIR:-$SCRIPT_DIR}"
ENV_FILE="${ENV_FILE:-$APP_DIR/.env.prod}"
COMPOSE_FILE="${COMPOSE_FILE:-$APP_DIR/docker-compose.prod.yml}"

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing $ENV_FILE" >&2
  exit 2
fi

set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a

export JOBRADAR_ENV_FILE="$ENV_FILE"

cd "$APP_DIR"

echo "Checking JobRadar health..."
curl -fsS "http://127.0.0.1:${APP_PORT:-8000}/health" >/dev/null

echo "Checking Docker Compose services..."
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps

container_ids="$(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps -q app db)"
if [ -z "$container_ids" ]; then
  echo "No app/db containers found" >&2
  exit 1
fi

max_mem_percent="${MAX_MEM_PERCENT:-80}"
failed=0

echo "Checking container memory usage. Max allowed: ${max_mem_percent}%"
while IFS='|' read -r name mem_percent mem_usage; do
  numeric_percent="${mem_percent%\%}"
  echo "$name memory: $mem_usage ($mem_percent)"
  if awk "BEGIN { exit !($numeric_percent > $max_mem_percent) }"; then
    echo "$name is above memory threshold: $mem_percent > ${max_mem_percent}%" >&2
    failed=1
  fi
done < <(docker stats --no-stream --format '{{.Name}}|{{.MemPerc}}|{{.MemUsage}}' $container_ids)

if [ "$failed" -ne 0 ]; then
  exit 1
fi

echo "JobRadar health and memory checks passed."
