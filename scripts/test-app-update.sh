#!/usr/bin/env bash
# Exercise update/rollback with synthetic files and a Docker command substitute.
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
fixture=$(mktemp -d)
trap 'rm -rf "$fixture"' EXIT
mkdir -p "$fixture/bin"
cat > "$fixture/bin/docker" <<'SH'
#!/usr/bin/env bash
set -eu
printf '%s image=%s\n' "$*" "${APP_IMAGE:-}" >> "$CALLS"
case "$1" in
  pull) exit 0 ;;
  inspect) echo sha256:previous-image; exit 0 ;;
  exec) test "${FAIL_HEALTH:-false}" != true; exit $? ;;
  compose)
    case "$*" in
      *'ps -q app'*) echo app-container ;;
      *'up -d --no-deps app'*) ;;
      *) echo 'Unexpected compose operation' >&2; exit 99 ;;
    esac ;;
  *) echo 'Unexpected docker operation' >&2; exit 99 ;;
esac
SH
printf '#!/usr/bin/env bash\nexit 0\n' > "$fixture/bin/sleep"
# Avoid touching the runner's shared lock; exercise only the update procedure.
printf '#!/usr/bin/env bash\nexit 0\n' > "$fixture/bin/flock"
chmod +x "$fixture/bin/"*
export PATH="$fixture/bin:$PATH"
export APP_IMAGE=ghcr.io/example/jobradar@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
export EXPECTED_REVISION=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
for outcome in success failure; do
  export APP_DIR="$fixture/$outcome"
  mkdir -p "$APP_DIR/backups"
  printf 'APP_IMAGE=old-image\r\nCONFIG_DIR=runtime-config\r\nAPP_SECRET_KEY=synthetic-only\r\nPUBLIC_REGISTRATION_ENABLED=false\r\n' > "$APP_DIR/.env.prod"
  chmod 600 "$APP_DIR/.env.prod"
  printf 'synthetic compose fixture\n' > "$APP_DIR/docker-compose.prod.yml"
  cp "$APP_DIR/.env.prod" "$APP_DIR/original"
  export CALLS="$APP_DIR/calls"
  export FAIL_HEALTH=false
  if [ "$outcome" = failure ]; then export FAIL_HEALTH=true; fi
  status=0
  bash "$root/infra/vps/deploy.sh" > "$APP_DIR/output" 2>&1 || status=$?
  if [ "$outcome" = success ]; then
    test "$status" = 0
    python3 - "$APP_DIR/original" "$APP_DIR/.env.prod" "$APP_IMAGE" <<'PY'
import pathlib,sys
before,after,image=sys.argv[1:]
a=pathlib.Path(before).read_bytes();b=pathlib.Path(after).read_bytes()
assert b==a.replace(b'APP_IMAGE=old-image',b'APP_IMAGE='+image.encode())
assert pathlib.Path(after).stat().st_mode & 0o777==0o600
PY
  else
    test "$status" != 0
    cmp "$APP_DIR/original" "$APP_DIR/.env.prod"
    grep -q 'image=sha256:previous-image' "$CALLS"
  fi
  ! grep -Eq 'score-all|ingest|up -d db|install-cron' "$CALLS"
  test "$(find "$APP_DIR/backups" -name env.before | wc -l)" = 1
done
echo 'Synthetic app update and rollback controls passed; no real Docker or production used.'
