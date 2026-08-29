#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cd "$root"

if [ ! -f .env ]; then
  cp .env.example .env
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

exec docker compose up --build "$@"
