#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/jobradar}"
CRON_FILE="${CRON_FILE:-/etc/cron.d/jobradar}"
DOCKER_BIN="${DOCKER_BIN:-/usr/bin/docker}"
FLOCK_BIN="${FLOCK_BIN:-/usr/bin/flock}"

if [ ! -f "$APP_DIR/docker-compose.prod.yml" ]; then
  echo "Missing $APP_DIR/docker-compose.prod.yml" >&2
  exit 2
fi

if [ ! -f "$APP_DIR/.env.prod" ]; then
  echo "Missing $APP_DIR/.env.prod" >&2
  exit 2
fi

mkdir -p "$APP_DIR/logs" "$APP_DIR/backups"

cat > "$CRON_FILE" <<EOF
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# JobRadar ingestion every 30 minutes. flock prevents overlapping runs.
*/30 * * * * root cd $APP_DIR && $FLOCK_BIN -n /tmp/jobradar-ingest.lock $DOCKER_BIN compose --env-file .env.prod -f docker-compose.prod.yml run --rm ingest >> $APP_DIR/logs/ingest.log 2>&1

# Daily PostgreSQL backup at 04:17, keeping 14 days.
17 4 * * * root cd $APP_DIR && APP_DIR=$APP_DIR $FLOCK_BIN -n /tmp/jobradar-backup.lock ./backup-postgres.sh >> $APP_DIR/logs/backup.log 2>&1
EOF

chmod 0644 "$CRON_FILE"
echo "Installed $CRON_FILE"
