# Cadence

[![CI](https://github.com/FloatingPegasus/Cadence/actions/workflows/ci.yml/badge.svg)](https://github.com/FloatingPegasus/Cadence/actions/workflows/ci.yml)

Cadence is a self-hosted daily record for practices, notes, check-ins, and
follow-ups.

## Features

- Daily notes, check-ins, timed entries, summaries, and close/reopen controls.
- Practice tracking, month views, contexts, weekly reflections, and search.
- Local SQLite storage, account export, and backup tools.
- Email-verified accounts and optional external summaries.

## Privacy

Records stay in local SQLite storage. External summaries are off by default and
require both operator configuration and account consent. Account verification
uses the configured Brevo email service.

## Local setup

Requires Python 3.14 and Node.js 22.12 or newer.

```sh
git clone https://github.com/FloatingPegasus/Cadence.git
cd Cadence
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install -r cadence/requirements.txt
cp .env.example .env
python -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Set the generated value as `CADENCE_SECRET_KEY` in `.env`. Configure Brevo for
normal registration, then start the backend:

```sh
alembic -c cadence/alembic.ini upgrade head
python -m cadence.main
```

In another terminal:

```sh
cd front
npm ci
npm run dev
```

Open <http://localhost:3001>.

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
docker build -t cadence:local .
docker volume create cadence-data
docker run --name cadence --rm \
  --publish 8000:8000 \
  --volume cadence-data:/app/cadence/data \
  --env-file .env \
  --env CADENCE_SERVE_FRONTEND=true \
  --env CADENCE_FRONTEND_BASE_URL=http://localhost:8000 \
  --env CADENCE_CORS_ORIGINS=http://localhost:8000 \
  cadence:local
```

Open <http://localhost:8000>. Public deployments must use HTTPS and a trusted
reverse proxy. For multiple workers or instances, set
`CADENCE_AUTH_RATE_LIMIT_BACKEND=redis` and `CADENCE_REDIS_URL`; memory limits
are process-local.

## Configuration

See [`.env.example`](.env.example) for every setting.

| Variable | Purpose |
| --- | --- |
| `CADENCE_SECRET_KEY` | Random session-signing key of at least 32 characters. |
| `CADENCE_DATABASE_URL` | Database URL; defaults to local SQLite. |
| `CADENCE_FRONTEND_BASE_URL` | Frontend URL used in verification links. |
| `CADENCE_CORS_ORIGINS` | Explicit comma-separated frontend origins. |
| `CADENCE_BREVO_API_KEY`, `CADENCE_FROM_EMAIL` | Registration email delivery. |
| `CADENCE_AI_ENABLED`, `CADENCE_AI_API_KEY` | Optional external summaries. |
| `CADENCE_AUTH_RATE_LIMIT_BACKEND`, `CADENCE_REDIS_URL` | Shared authentication limits. |

## Backups

```sh
python -m cadence.maintenance backup
python -m cadence.maintenance verify cadence/data/backups/<backup-file>.db
python -m cadence.maintenance restore \
  cadence/data/backups/<backup-file>.db \
  --confirm RESTORE
```

Stop the backend before restoring.

## Tests

```sh
python -m unittest discover -s cadence/tests -v
(cd front && npm run check)
```

CI also runs dependency, source, and secret scans.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and the
[Code of Conduct](CODE_OF_CONDUCT.md). Cadence is released under the
[MIT License](LICENSE).

If Cadence is useful to you, [star it on GitHub](https://github.com/FloatingPegasus/Cadence).
