#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/jobradar}"
ENV_FILE="${ENV_FILE:-$APP_DIR/.env.prod}"
COMPOSE_FILE="${COMPOSE_FILE:-$APP_DIR/docker-compose.prod.yml}"

usage() {
  echo "Usage: $0 email [display-name] [--admin]" >&2
}

if [ "$#" -lt 1 ] || [ "$#" -gt 3 ]; then
  usage
  exit 2
fi

email="$1"
if [ "${2:-}" = "--admin" ]; then
  display_name="$email"
  admin_flag="--admin"
else
  display_name="${2:-$email}"
  admin_flag="${3:-}"
fi
admin_args=()

if [ -n "$admin_flag" ]; then
  if [ "$admin_flag" != "--admin" ]; then
    usage
    exit 2
  fi
  admin_args+=(--admin)
fi

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing $ENV_FILE. Create it before adding users." >&2
  exit 2
fi

generate_password() {
  local password
  while true; do
    set +o pipefail
    password="$(
      LC_ALL=C tr -dc 'A-Za-z0-9@%+=:,./_-' < /dev/urandom | head -c 28
    )"
    set -o pipefail
    if [[ "$password" =~ [[:lower:]] ]] \
      && [[ "$password" =~ [[:upper:]] ]] \
      && [[ "$password" =~ [[:digit:]] ]] \
      && [[ "$password" =~ [^[:alnum:]] ]]; then
      printf '%s\n' "$password"
      return
    fi
  done
}

password="$(generate_password)"

export JOBRADAR_ENV_FILE="$ENV_FILE"

printf '%s\n' "$password" | docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" run \
  --rm -T ingest python -m app.cli create-user "$email" --display-name "$display_name" \
  --password-stdin "${admin_args[@]}"

echo "Created user: $email"
echo "Temporary password: $password"
echo "Store this password now. The script does not save it."
