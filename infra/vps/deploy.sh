#!/usr/bin/env bash
# Update the existing app only; keep runtime configuration, DB and schedules.
set -euo pipefail
umask 077
: "${APP_DIR:?Set confirmed existing APP_DIR}"
: "${APP_IMAGE:?Set immutable repository@sha256 image}"
: "${EXPECTED_REVISION:?Set exact source revision}"
[[ "$EXPECTED_REVISION" =~ ^[a-f0-9]{40}$ ]] || exit 2
[[ "$APP_IMAGE" =~ ^ghcr\.io/[a-z0-9._/-]+@sha256:[a-f0-9]{64}$ ]] || exit 2
cd "$APP_DIR"
ENV_FILE="$APP_DIR/.env.prod"
COMPOSE_FILE="$APP_DIR/docker-compose.prod.yml"
test -f "$ENV_FILE" && test -f "$COMPOSE_FILE"
# Existing ingestion uses this lock; do not modify its cron or run ingestion here.
exec 9>/tmp/jobradar-ingest.lock
flock -w 120 9
compose() { docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"; }
old_container=$(compose ps -q app)
test -n "$old_container"
old_image=$(docker inspect --format '{{.Image}}' "$old_container")
backup_dir="$APP_DIR/backups/release-$EXPECTED_REVISION-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -m 700 "$backup_dir"
cp -p "$ENV_FILE" "$backup_dir/env.before"
cp -p "$COMPOSE_FILE" "$backup_dir/compose.before"
printf '%s\n' "$old_image" > "$backup_dir/image.before"
changed=false
rollback() {
  code=$?
  trap - ERR
  if [ "$changed" = true ]; then
    cp -p "$backup_dir/env.before" "$ENV_FILE"
    APP_IMAGE="$old_image" compose up -d --no-deps app || true
    echo 'Update failed; previous app image requested. Verify rollback health.' >&2
  fi
  exit "$code"
}
trap rollback ERR
# Never start or update db, recalculate scores, ingest, or install cron.
docker pull "$APP_IMAGE"
changed=true
compose up -d --no-deps app
container=$(compose ps -q app)
healthy=false
for attempt in $(seq 1 60); do
  if docker exec "$container" python -c '
import json,sys,urllib.request
with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=3) as response:
    value=json.load(response)
assert value["status"] == "ok" and value["revision"] == sys.argv[1]
' "$EXPECTED_REVISION" >/dev/null 2>&1; then
    healthy=true
    break
  fi
  sleep 3
done
[ "$healthy" = true ]
# Persist only the image pin so the unchanged scheduled ingest uses the same code.
# Every other byte/value is preserved; never regenerate .env from workflow secrets.
python3 - "$ENV_FILE" "$APP_IMAGE" <<'PY'
import os,re,stat,sys,tempfile
path,image=sys.argv[1:]
with open(path,'rb') as source: data=source.read()
pattern=rb'(?m)^APP_IMAGE=[^\r\n]*'
assert len(re.findall(pattern,data))==1, 'Expected exactly one existing image pin'
updated=re.sub(pattern,lambda match:b'APP_IMAGE='+image.encode('ascii'),data)
mode=stat.S_IMODE(os.stat(path).st_mode)
fd,tmp=tempfile.mkstemp(dir=os.path.dirname(path))
try:
    with os.fdopen(fd,'wb') as target: target.write(updated)
    os.chmod(tmp,mode)
    os.replace(tmp,path)
finally:
    if os.path.exists(tmp): os.unlink(tmp)
PY
trap - ERR
echo "App healthy at revision $EXPECTED_REVISION; existing configuration and schedules retained."
