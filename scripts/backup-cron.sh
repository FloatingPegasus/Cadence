#!/bin/sh
# Weekly DB backup via the app container. Install with:
#   (crontab -l 2>/dev/null; echo "15 3 * * 0 /opt/cadence/scripts/backup-cron.sh") | crontab -
set -eu

root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cd "$root"

mkdir -p "$root/backups/host"
docker compose -f compose.yaml -f compose.prod.yaml run --rm --no-deps \
  --entrypoint python app -m cadence.maintenance backup

# Copy newest dump out of the named volume onto the host tree for off-box copy.
cid=$(docker compose -f compose.yaml -f compose.prod.yaml ps -q app)
if [ -n "$cid" ]; then
  latest=$(docker exec "$cid" sh -c 'ls -1t /app/cadence/data/backups/cadence-backup-*.dump 2>/dev/null | head -1' || true)
  if [ -n "$latest" ]; then
    docker cp "$cid:$latest" "$root/backups/host/"
    echo "Copied $(basename "$latest") to $root/backups/host/"
  fi
fi
