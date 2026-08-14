"""Explicit, shared bootstrap for all test modules.

The application validates production configuration while it is imported.  Test
modules call :func:`configure_test_environment` before importing ``cadence.app``
so both unittest discovery and direct module execution stay independent of a
developer's ignored ``.env`` file.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def configure_test_environment() -> None:
    """Install deterministic, test-only settings before app imports."""

    os.environ.update(
        {
            "CADENCE_TEST_MODE": "true",
            "CADENCE_SECRET_KEY": "cadence-test-suite-secret-key-32-bytes",
            "CADENCE_ALGORITHM": "HS256",
            "CADENCE_DEV_MODE": "false",
            "CADENCE_DEV_EMAIL": "",
            "CADENCE_DEV_PASSWORD": "",
            "CADENCE_FRONTEND_BASE_URL": "http://localhost:3001",
            "CADENCE_CORS_ORIGINS": "http://localhost:3001",
            "CADENCE_ACCESS_TOKEN_EXPIRE_MINUTES": "10080",
            "CADENCE_VERIFICATION_TOKEN_EXPIRE_HOURS": "24",
            "CADENCE_AUTH_RATE_LIMIT_WINDOW_SECONDS": "60",
            "CADENCE_AUTH_REGISTER_RATE_LIMIT": "5",
            "CADENCE_AUTH_LOGIN_RATE_LIMIT": "10",
            "CADENCE_AUTH_VERIFICATION_RATE_LIMIT": "20",
            "CADENCE_AUTH_VERIFICATION_RESEND_RATE_LIMIT": "5",
            "CADENCE_AUTH_RATE_LIMIT_BACKEND": "memory",
            "CADENCE_REDIS_URL": "",
            "CADENCE_REDIS_KEY_PREFIX": "cadence:rate-limit",
            "CADENCE_REDIS_CONNECT_TIMEOUT_SECONDS": "5",
            "CADENCE_REDIS_SOCKET_TIMEOUT_SECONDS": "5",
            "CADENCE_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
            "CADENCE_RUNTIME_LOCK_PATH": (
                f"/tmp/cadence-test-suite-{os.getpid()}.lock"
            ),
            "CADENCE_BACKUP_DIR": (
                f"/tmp/cadence-test-suite-{os.getpid()}-backups"
            ),
        }
    )
