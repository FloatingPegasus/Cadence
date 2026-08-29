#!/bin/sh
# Deploy or update Cadence with TLS (Caddy) on this host.
# Usage: ./scripts/deploy-prod.sh
set -eu

root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cd "$root"

if [ ! -f .env ]; then
  if [ -f .env.production.example ]; then
    cp .env.production.example .env
    echo "Created .env from .env.production.example"
    echo "Edit .env (secret key, DB password, Brevo) then re-run." >&2
    exit 1
  fi
  echo "Missing .env" >&2
  exit 1
fi

python3 - <<'PY'
from pathlib import Path
import re
import secrets

path = Path(".env")
text = path.read_text(encoding="utf-8")
match = re.search(r"^CADENCE_SECRET_KEY=(.*)$", text, flags=re.M)
current = match.group(1).strip() if match else ""
placeholders = {
    "",
    "replace-with-a-long-random-value",
    "change-me-in-production",
}
if current in placeholders or len(current) < 32:
    key = secrets.token_urlsafe(48)
    if match:
        text = re.sub(
            r"^CADENCE_SECRET_KEY=.*$",
            f"CADENCE_SECRET_KEY={key}",
            text,
            count=1,
            flags=re.M,
        )
    else:
        text = text.rstrip() + f"\nCADENCE_SECRET_KEY={key}\n"
    path.write_text(text, encoding="utf-8")
    print("Wrote CADENCE_SECRET_KEY to .env")
PY

docker compose -f compose.yaml -f compose.prod.yaml up -d --build --remove-orphans
docker compose -f compose.yaml -f compose.prod.yaml ps
echo "Check https://${CADENCE_DOMAIN:-cadence.kanishq.dev}/healthz after DNS points here."
