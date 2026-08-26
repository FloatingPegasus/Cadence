#!/bin/sh
set -eu

python /app/docker/wait_for_database.py
if [ -n "${CADENCE_MIGRATION_DATABASE_URL:-}" ]; then
  CADENCE_DATABASE_URL="$CADENCE_MIGRATION_DATABASE_URL" \
    alembic -c /app/cadence/alembic.ini upgrade head
else
  alembic -c /app/cadence/alembic.ini upgrade head
fi
exec uvicorn cadence.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --proxy-headers \
    --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-127.0.0.1}"
