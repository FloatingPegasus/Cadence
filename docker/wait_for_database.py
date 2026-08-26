from __future__ import annotations

import os
from math import ceil, isfinite
import sys
import time

import psycopg
from sqlalchemy.engine import make_url


def _libpq_url(raw_url: str) -> str:
    try:
        url = make_url(raw_url.strip())
    except Exception as error:
        raise ValueError("CADENCE_DATABASE_URL is not a valid database URL") from error
    if url.get_backend_name() != "postgresql" or not url.host:
        raise ValueError("CADENCE_DATABASE_URL must be a PostgreSQL URL")
    return url.set(drivername="postgresql").render_as_string(
        hide_password=False
    )


def _wait_timeout(raw_timeout: str) -> float:
    try:
        timeout = float(raw_timeout)
    except (TypeError, ValueError) as error:
        raise ValueError(
            "CADENCE_DATABASE_WAIT_SECONDS must be a finite positive number"
        ) from error
    if not isfinite(timeout) or timeout <= 0:
        raise ValueError(
            "CADENCE_DATABASE_WAIT_SECONDS must be a finite positive number"
        )
    return timeout


def main() -> int:
    raw_url = (
        os.environ.get("CADENCE_MIGRATION_DATABASE_URL", "").strip()
        or os.environ.get("CADENCE_DATABASE_URL", "").strip()
    )
    if not raw_url:
        print("CADENCE_DATABASE_URL is required", file=sys.stderr)
        return 1

    try:
        libpq_url = _libpq_url(raw_url)
        timeout = _wait_timeout(
            os.environ.get("CADENCE_DATABASE_WAIT_SECONDS", "60")
        )
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        try:
            with psycopg.connect(
                libpq_url,
                connect_timeout=max(1, min(5, ceil(remaining))),
            ) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    if cursor.fetchone() != (1,):
                        raise psycopg.Error("database readiness query failed")
                return 0
        except psycopg.Error:
            time.sleep(min(0.5, max(0, remaining)))

    print("Database did not become ready before the timeout", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
