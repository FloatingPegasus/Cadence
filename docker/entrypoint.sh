#!/bin/sh
set -eu

alembic -c /app/cadence/alembic.ini upgrade head
exec uvicorn cadence.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers
