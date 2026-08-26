# Cadence

[![CI](https://github.com/FloatingPegasus/Cadence/actions/workflows/ci.yml/badge.svg)](https://github.com/FloatingPegasus/Cadence/actions/workflows/ci.yml)

Cadence is a private, self-hosted tracker for habits, an hourly log, notes,
and follow-ups.

## Features

- Habit tracking with a month grid, plus daily notes, check-ins, and close/reopen.
- Hourly activity log.
- Focus room with a pomodoro timer and generated lo-fi audio.
- Optional AI daily reviews from hours, habits, and goals.
- Goals in settings, PostgreSQL with pgvector, account export, and backups.
- Email-verified accounts. External summaries stay off until you consent.

## Database and migrations

Cadence is PostgreSQL-only and requires the `vector` and `pg_trgm` extensions. The
`0001_postgresql_baseline` migration creates the current schema in a fresh
database; it is not an in-place conversion from SQLite.

Migration warning: this release does not read legacy SQLite files and does not
automatically copy their data. If you are upgrading from an older SQLite build,
use that build's export feature first and keep the original database until you
have verified the exported records; this release has no SQLite importer. Do not
point the test commands at a production database: they intentionally reset
their dedicated test database.

## Privacy

Records stay in your configured PostgreSQL database. External summaries are off
by default and require both operator configuration and account consent. Account
verification uses the configured Brevo email service.

## Local setup

Requires Docker with Compose for the recommended local setup. A manual setup
requires Python 3.14, Node.js 22.12 or newer, and PostgreSQL with the `vector`
and `pg_trgm` extensions enabled.

```sh
git clone https://github.com/FloatingPegasus/Cadence.git
cd Cadence
cp .env.example .env
python -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Set the generated value as `CADENCE_SECRET_KEY` in `.env`. Configure Brevo for
normal registration, then start PostgreSQL and the backend:

```sh
docker compose up -d --wait db
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install -r cadence/requirements.txt
alembic -c cadence/alembic.ini upgrade head
python -m cadence.main
```

The settings file is loaded from the project root, so a direct launch from the
backend directory is also supported after activating the environment:

```sh
cd cadence
python3 main.py
```

If startup reports `CADENCE_SECRET_KEY`, the value in the project-root `.env`
is missing, a placeholder, or shorter than 32 characters. Generate a fresh
value with the command above and replace only that setting; do not bypass the
check by enabling test mode.

The Compose database init script creates the `cadence_test` database and
enables `vector` on a fresh PostgreSQL volume. If the volume already exists,
run the same idempotent script once:

```sh
docker compose exec -T db psql -U cadence -d postgres \
  < docker/postgres/init/01-create-test-database.sql
```

In another terminal:

```sh
cd front
npm ci
npm run dev
```

Open <http://localhost:3001>.

The interactive API reference is available at
<http://localhost:8000/docs>. See [DIAGRAMS.md](DIAGRAMS.md) for the current
deployment and data-flow overview.

### Developer login

To skip registration and email delivery locally, set:

```dotenv
CADENCE_DEV_MODE=true
CADENCE_DEV_EMAIL=dev@example.com
CADENCE_DEV_PASSWORD=choose-a-local-password
```

Restart and sign in with those credentials. Keep dev mode off outside local
development. `CADENCE_DEV_USERNAMES` is retired.

## Docker

```sh
docker compose up --build
```

Open <http://localhost:8000>. Public deployments must use HTTPS and a trusted
reverse proxy. For multiple workers or instances, set
`CADENCE_AUTH_RATE_LIMIT_BACKEND=redis` and `CADENCE_REDIS_URL`; memory limits
are process-local. The Compose file uses the pinned
`pgvector/pgvector:0.8.0-pg17` image and waits for its health check before
running migrations and serving the API. PostgreSQL is bound to `127.0.0.1`;
set `CADENCE_POSTGRES_DB`, `CADENCE_POSTGRES_USER`, and
`CADENCE_POSTGRES_PASSWORD` in `.env` to change the local defaults. If a
password needs URL escaping, set `CADENCE_COMPOSE_DATABASE_URL`; set
`CADENCE_COMPOSE_MIGRATION_DATABASE_URL` separately only when the migration
endpoint differs. Compose replaces the host-side URLs from `.env` with
container URLs that use the `db` service name; never use `localhost` in either
`CADENCE_COMPOSE_*` value.

### Managed PostgreSQL

Neon’s free tier is a good starting point for a low-cost deployment. Enable the
`vector` and `pg_trgm` extensions in the project, set `CADENCE_DATABASE_URL` to the pooled
runtime connection, and keep `sslmode=require`. For migrations, backups, and
restores, use a separate direct (non-pooled) connection in
`CADENCE_MIGRATION_DATABASE_URL`; poolers can reject administrative commands or
hold connections longer than expected. The same variables work with any
PostgreSQL provider, so Neon is optional. Neon may copy a URL beginning with
`postgresql://`; change it to `postgresql+psycopg://` before assigning it to
Cadence, preserving the host, credentials, database, and query parameters.

Run migrations as a one-shot operation with the direct connection before
starting additional application replicas. The migration runner takes a
PostgreSQL advisory lock, so simultaneous startup commands serialize safely:

```sh
CADENCE_MIGRATION_DATABASE_URL='postgresql+psycopg://user:password@direct-host/db?sslmode=require' \
  alembic -c cadence/alembic.ini upgrade head
```

## Configuration

See [`.env.example`](.env.example) for every setting.

| Variable | Purpose |
| --- | --- |
| `CADENCE_SECRET_KEY` | Random session-signing key of at least 32 characters. |
| `CADENCE_DATABASE_URL` | PostgreSQL URL used by the application runtime. |
| `CADENCE_MIGRATION_DATABASE_URL` | Direct PostgreSQL URL for migrations, maintenance, and embedding backfill. |
| `CADENCE_FRONTEND_BASE_URL` | Frontend URL used in verification links. |
| `CADENCE_CORS_ORIGINS` | Explicit comma-separated frontend origins. |
| `CADENCE_BREVO_API_KEY`, `CADENCE_FROM_EMAIL` | Registration email delivery. |
| `CADENCE_AI_ENABLED`, `CADENCE_EMBEDDING_ENABLED`, `CADENCE_AI_API_KEY` | Consent-gated external summaries and semantic continuity search using NVIDIA. |
| `CADENCE_AUTH_RATE_LIMIT_BACKEND`, `CADENCE_REDIS_URL` | Shared authentication limits. |

Semantic embeddings require `CADENCE_AI_ENABLED=true`,
`CADENCE_EMBEDDING_ENABLED=true`, a valid `CADENCE_AI_API_KEY`, and the user's
AI-processing consent. Keep both feature switches off when no provider is
configured.

Embedding refreshes run synchronously after a source commit so the source write
remains durable even when the provider is unavailable; successful provider
calls can add their network latency to that response.

## Backups

The maintenance commands require the PostgreSQL client utilities `pg_dump` and
`pg_restore`. They create custom-format `.dump` files and retain a safety dump
before every restore. Stop all API replicas and workers before restoring; the
restore command cannot coordinate writes from still-running instances.

```sh
docker compose run --rm --no-deps --entrypoint python app \
  -m cadence.maintenance backup
docker compose run --rm --no-deps --entrypoint python app \
  -m cadence.maintenance verify /app/cadence/data/backups/<backup-file>.dump
docker compose stop app
docker compose run --rm --no-deps --entrypoint python app \
  -m cadence.maintenance restore \
  /app/cadence/data/backups/<backup-file>.dump \
  --confirm RESTORE
docker compose start app
```

The Compose backup volume persists these dumps independently of the application
container. When the runtime uses a pooled URL, pass the direct URL to each
maintenance or migration command:

```sh
docker compose run --rm --no-deps --entrypoint python \
  -e CADENCE_MIGRATION_DATABASE_URL='postgresql+psycopg://user:password@direct-host/db?sslmode=require' \
  app -m cadence.maintenance backup
```

After a provider outage, use the direct migration URL to retry a bounded batch
of missing or stale embeddings; the same command also clears rows for emptied
sources (optionally add `--user-id`):

```sh
CADENCE_MIGRATION_DATABASE_URL='postgresql+psycopg://user:password@direct-host/db?sslmode=require' \
  python -m cadence.maintenance backfill-embeddings --batch-size 50
```

## Tests

```sh
docker compose up -d --wait db
docker compose exec -T db psql -U cadence -d postgres \
  < docker/postgres/init/01-create-test-database.sql
CADENCE_TEST_DATABASE_URL=postgresql+psycopg://cadence:cadence-local-password@localhost:5432/cadence_test \
.venv/bin/python -m unittest discover -s cadence/tests -v
(cd front && npm ci && npm run check)
```

The backend tests apply the Alembic schema once, then truncate application
tables and reseed fixture users before each API test. Use the exact disposable
`cadence_test` database above, never `cadence` or a shared/production database.
The Redis integration tests run only when `CADENCE_TEST_REDIS_URL` is set.

For the live PostgreSQL integration suite, use a PostgreSQL 17/pgvector
database and matching PostgreSQL 17 `pg_dump`/`pg_restore` client tools. Set
`CADENCE_RUN_INTEGRATION=true` and provide
`CADENCE_INTEGRATION_ADMIN_DATABASE_URL` for a database where the test user can
create and drop disposable databases:

```sh
CADENCE_RUN_INTEGRATION=true \
CADENCE_INTEGRATION_ADMIN_DATABASE_URL=postgresql+psycopg://cadence:password@localhost:5432/postgres \
.venv/bin/python -m unittest discover -s cadence/tests/integration -v
```

The regular test command above remains the beginner path; CI runs this live
suite separately.

CI also runs dependency, source, and secret scans.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and the
[Code of Conduct](CODE_OF_CONDUCT.md). Cadence is released under the
[MIT License](LICENSE).

If Cadence is useful to you, [star it on GitHub](https://github.com/FloatingPegasus/Cadence).
