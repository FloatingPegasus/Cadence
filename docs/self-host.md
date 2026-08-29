# Self-hosting Cadence

Cadence is PostgreSQL-only and needs the `vector` and `pg_trgm` extensions.
The `0001_postgresql_baseline` migration creates the current schema in a fresh
database; it is not an in-place conversion from SQLite.

This release does not read legacy SQLite files. If you are upgrading from an
older SQLite build, use that build's export feature first and keep the original
database until you have verified the exported records. Do not point the test
commands at a production database: they reset their dedicated test database.

## Privacy

Records stay in your configured PostgreSQL database. External summaries are off
by default and require both operator configuration and account consent. Hosted
verification uses Brevo when `CADENCE_BREVO_API_KEY` is set. Local Compose
without mail prints a verification link in the server log.

## Local setup without Docker

Requires Python 3.14, Node.js 22.12 or newer, and PostgreSQL with `vector` and
`pg_trgm`.

```sh
git clone https://github.com/FloatingPegasus/Cadence.git
cd Cadence
cp .env.example .env
python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Set the generated value as `CADENCE_SECRET_KEY` in `.env`. Then:

```sh
docker compose up -d --wait db
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install -r cadence/requirements.txt
alembic -c cadence/alembic.ini upgrade head
python -m cadence.main
```

If startup reports `CADENCE_SECRET_KEY`, the value in the project-root `.env`
is missing, a placeholder, or shorter than 32 characters. Generate a fresh
value and replace only that setting; do not bypass the check by enabling test
mode.

The Compose database init script creates `cadence_test` and enables `vector` on
a fresh PostgreSQL volume. If the volume already exists:

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

Open <http://localhost:3001>. The API is at <http://localhost:8000>. See
[DIAGRAMS.md](../DIAGRAMS.md) for deployment and data flow.

### Developer login

To skip registration locally:

```dotenv
CADENCE_DEV_MODE=true
CADENCE_DEV_EMAIL=dev@example.com
CADENCE_DEV_PASSWORD=choose-a-local-password
```

Keep dev mode off outside local development.

## Docker

`./scripts/quickstart.sh` copies `.env.example` if needed, writes a signing
key, and runs Compose. You can also run `docker compose up --build` after
that `.env` exists. Public deployments must use HTTPS and a trusted reverse
proxy. For the always-on `cadence.kanishq.dev` layout (Caddy + Compose on one
VM), see [deploy.md](deploy.md). For multiple workers, set
`CADENCE_AUTH_RATE_LIMIT_BACKEND=redis` and
`CADENCE_REDIS_URL`. PostgreSQL is bound to `127.0.0.1`.

Compose replaces host-side URLs from `.env` with container URLs that use the
`db` service name. Never use `localhost` in `CADENCE_COMPOSE_*` values.

### Managed PostgreSQL

Neon’s free tier is a starting point. Enable `vector` and `pg_trgm`, set
`CADENCE_DATABASE_URL` to the pooled runtime connection with `sslmode=require`,
and keep a direct URL in `CADENCE_MIGRATION_DATABASE_URL`. Change
`postgresql://` to `postgresql+psycopg://`.

```sh
CADENCE_MIGRATION_DATABASE_URL='postgresql+psycopg://user:password@direct-host/db?sslmode=require' \
  alembic -c cadence/alembic.ini upgrade head
```

## Configuration

See [`.env.example`](../.env.example) for every setting.

| Variable | Purpose |
| --- | --- |
| `CADENCE_SECRET_KEY` | Random session-signing key of at least 32 characters. |
| `CADENCE_DATABASE_URL` | PostgreSQL URL used by the application runtime. |
| `CADENCE_MIGRATION_DATABASE_URL` | Direct PostgreSQL URL for migrations, maintenance, and embedding backfill. |
| `CADENCE_FRONTEND_BASE_URL` | Frontend URL used in verification links. |
| `CADENCE_CORS_ORIGINS` | Explicit comma-separated frontend origins. |
| `CADENCE_BREVO_API_KEY`, `CADENCE_FROM_EMAIL` | Registration email delivery. |
| `CADENCE_AI_ENABLED`, `CADENCE_EMBEDDING_ENABLED`, `CADENCE_AI_API_KEY` | Consent-gated NVIDIA summaries and search. |
| `CADENCE_AUTH_RATE_LIMIT_BACKEND`, `CADENCE_REDIS_URL` | Shared authentication limits. |

## Backups

The maintenance commands require `pg_dump` and `pg_restore`. Stop all API
replicas before restoring.

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

## Tests

```sh
docker compose up -d --wait db
docker compose exec -T db psql -U cadence -d postgres \
  < docker/postgres/init/01-create-test-database.sql
CADENCE_TEST_DATABASE_URL=postgresql+psycopg://cadence:cadence-local-password@localhost:5432/cadence_test \
.venv/bin/python -m unittest discover -s cadence/tests -v
(cd front && npm ci && npm run check)
```

Use the disposable `cadence_test` database, never `cadence`. Redis tests run
only when `CADENCE_TEST_REDIS_URL` is set.

```sh
CADENCE_RUN_INTEGRATION=true \
CADENCE_INTEGRATION_ADMIN_DATABASE_URL=postgresql+psycopg://cadence:password@localhost:5432/postgres \
.venv/bin/python -m unittest discover -s cadence/tests/integration -v
```

CI runs this suite separately, plus dependency, source, and secret scans.
