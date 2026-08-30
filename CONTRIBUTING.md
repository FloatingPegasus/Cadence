# Contributing to Cadence

Thanks for helping improve Cadence. Small, focused changes are easier to
review and maintain.

## Before you start

- Search existing issues before opening a new one.
- For a larger change, open an issue first so the approach can be discussed.
- Do not include personal data, credentials, local databases, or generated
  build output in a change.
- Cadence uses PostgreSQL with pgvector and pg_trgm. The current baseline starts a fresh
  database; it does not import legacy SQLite files automatically.

## Local setup

The short path is `./scripts/quickstart.sh` from the repository root. That
copies `.env.example` if needed, writes a signing key, and starts Compose.

For a manual environment:

```sh
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install -r cadence/requirements.txt
cp .env.example .env
# Generate a real signing key and replace the CADENCE_SECRET_KEY placeholder.
python -c 'import secrets; print(secrets.token_urlsafe(48))'
# Paste that value after CADENCE_SECRET_KEY= in .env before starting Cadence.
docker compose up -d --wait db
docker compose exec -T db psql -U cadence -d postgres \
  < docker/postgres/init/01-create-test-database.sql
alembic -c cadence/alembic.ini upgrade head
```

The Compose app overrides the host-side URLs from `.env` with URLs that use
the `db` service name. Do not put `localhost` in
`CADENCE_COMPOSE_DATABASE_URL` or `CADENCE_COMPOSE_MIGRATION_DATABASE_URL`.

The value in `.env.example` is intentionally not usable outside test mode;
copying the file alone is not a complete setup. Keep `CADENCE_TEST_MODE=false`
for local development and production-like runs.

Install frontend dependencies separately:

```sh
cd front
npm ci
```

## Checks

Run the backend tests and the frontend checks before opening a pull request:

```sh
CADENCE_TEST_DATABASE_URL=postgresql+psycopg://cadence:cadence-local-password@localhost:5432/cadence_test \
  .venv/bin/python -m unittest discover -s cadence/tests -v
(cd front && npm ci && npm run check)
```

The test suite applies the Alembic schema once, then truncates application
tables and reseeds fixture users before each API test. Use the exact
`cadence_test` database above, never `cadence` or a shared/production database.
The Redis integration tests are opt-in through `CADENCE_TEST_REDIS_URL`.

The live PostgreSQL integration suite is separate. It requires PostgreSQL
17/pgvector and matching PostgreSQL 17 `pg_dump`/`pg_restore` client tools, plus
a PostgreSQL role that can create and drop disposable databases. Run it with:

```sh
CADENCE_RUN_INTEGRATION=true \
CADENCE_INTEGRATION_ADMIN_DATABASE_URL=postgresql+psycopg://cadence:password@localhost:5432/postgres \
.venv/bin/python -m unittest discover -s cadence/tests/integration -v
```

CI runs this suite after the regular tests.

If a change affects migrations, API behavior, or configuration, include the
relevant test coverage and explain any manual verification in the pull
request.

## Branches

Open a pull request against `main`. Name the branch after the change, for
example `fix/habit-checkbox` or `chore/ci`. GitHub Dependabot opens its own
`dependabot/...` branches for package updates; those are not a model for
feature work.

## Pull requests

Describe what changed, why it changed, and how it was tested. Keep unrelated
cleanup out of feature changes, and update documentation when setup or
behavior changes. `main` is protected: changes go through a pull request,
and CI must pass before merge.
