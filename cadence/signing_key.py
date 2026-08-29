from __future__ import annotations

import os
import secrets
from pathlib import Path

# Keep this module free of cadence.app imports. The Compose entrypoint
# generates a key before Settings can load.
INSECURE_SECRET_KEYS = frozenset(
    {
        "",
        "change-me-in-production",
        "replace-with-a-long-random-value",
        "cadence-test-only-secret-key-32-bytes",
        "cadence-test-suite-secret-key-32-bytes",
    }
)
DEFAULT_SIGNING_KEY_FILE = Path("/app/cadence/data/backups/.signing-key")


def resolve_signing_key(
    current: str | None = None,
    store: Path | None = None,
) -> str:
    """Return a usable signing key, generating a persistent one if needed.

    Compose copies `.env.example`, which still contains a placeholder. A
    generated key is stored next to backups so container restarts keep the
    same sessions.
    """
    candidate = (
        current if current is not None else os.environ.get("CADENCE_SECRET_KEY", "")
    ).strip()
    if candidate and candidate not in INSECURE_SECRET_KEYS and len(candidate) >= 32:
        return candidate

    path = store or Path(
        os.environ.get("CADENCE_SIGNING_KEY_FILE", str(DEFAULT_SIGNING_KEY_FILE))
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        saved = path.read_text(encoding="utf-8").strip()
        if saved and saved not in INSECURE_SECRET_KEYS and len(saved) >= 32:
            return saved

    generated = secrets.token_urlsafe(48)
    path.write_text(generated + "\n", encoding="utf-8")
    path.chmod(0o600)
    return generated
