#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${APP_DIR:-$SCRIPT_DIR}"
ENV_FILE="${ENV_FILE:-$APP_DIR/.env.prod}"
COMPOSE_FILE="${COMPOSE_FILE:-$APP_DIR/docker-compose.prod.yml}"
BACKUP_DIR="${BACKUP_DIR:-$APP_DIR/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing $ENV_FILE" >&2
  exit 2
fi

set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a

mkdir -p "$BACKUP_DIR"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_file="$BACKUP_DIR/jobradar_${timestamp}.sql.gz"

export JOBRADAR_ENV_FILE="$ENV_FILE"

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T db \
  pg_dump -U "${POSTGRES_USER:-jobradar}" "${POSTGRES_DB:-jobradar}" \
  | gzip > "$backup_file"

find "$BACKUP_DIR" -type f -name "jobradar_*.sql.gz" -mtime +"$RETENTION_DAYS" -delete
echo "Created $backup_file"
