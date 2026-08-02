# Cadence

A lightweight personal cognitive continuity system — habit tracking, daily reflection, structured check-ins, and conversational logging.

## Tech Stack

- **Backend:** FastAPI + SQLAlchemy + Alembic + SQLite
- **Frontend:** Vite + React + TypeScript + Tailwind CSS v4
- **API:** RESTful JSON

## Getting Started

### Backend

Cadence targets Python 3.14. The repository is a monorepo and `cadence/` is the
backend Python package. The canonical commands run from the repository root so
Python sees the package's parent directory:

```sh
python3.14 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r cadence/requirements.txt
alembic -c cadence/alembic.ini upgrade head
python -m cadence.main
```

Server runs at `http://localhost:8000`.

The `cadence` directory is a Python package. Starting `cadence/main.py` while
the shell is already inside that directory changes Python's import root. The
entry point also supports that workflow explicitly:

```sh
cd cadence
../venv/bin/python main.py
```

### Email verification

Normal local development must use `CADENCE_TEST_MODE=false`. Test mode only
suppresses outbound verification mail for automated tests; it does not bypass
verification enforcement.

Brevo delivery also requires:

- a valid `CADENCE_BREVO_API_KEY`
- an active Brevo sender matching `CADENCE_FROM_EMAIL`
- the machine's current public IP allowed by the Brevo account when authorized
  IP restrictions are enabled

After changing `.env`, restart the API. Existing unverified accounts can use
the **Resend verification email** action on the login page.

The local `.env` and all other dotfiles are intentionally ignored by Git. Set
the values locally or through the deployment environment; do not copy real
provider keys into documentation or source files.

### Frontend

```sh
cd front
npm install
npm run dev
```

App runs at `http://localhost:3001` with API proxy to backend.

## Production deployment

The recommended first deployment is one Fly.io app with one machine, one
mounted persistent volume, and a single origin:

- `https://cadence.kanishq.dev` serves the React application and `/api` from the
  same process.
- SQLite lives at `/data/cadence.db` on the mounted volume. Do not run multiple
  app machines while SQLite is the source of truth.
- The container runs `alembic upgrade head` before starting the API and exposes
  `/healthz` for the platform health check.
- Backups must be copied off the machine on a schedule. A volume is persistence,
  not a complete backup strategy.

The repository includes [Dockerfile](Dockerfile), [fly.toml](fly.toml), and a
manual [production deployment workflow](.github/workflows/deploy-production.yml).
The workflow is deliberately manual and targets the protected `production`
GitHub environment.

Create the Fly app and its volume once, after authenticating with `flyctl`:

```sh
fly auth login
fly apps create cadence-kanishq
fly volumes create cadence_data --region bom --size 10
fly tokens create deploy --app cadence-kanishq
```

Save the deploy token directly in the GitHub `production` environment as
`FLY_API_TOKEN`; do not paste it into the repository or this chat.

If the app name is already taken, choose another globally unique Fly app name
and update `fly.toml`; the public hostname remains `cadence.kanishq.dev`.
After the first deploy, attach the custom hostname and follow Fly's certificate
instructions:

```sh
fly certs add cadence.kanishq.dev --app cadence-kanishq
fly certs show cadence.kanishq.dev --app cadence-kanishq
```

Add the DNS record requested by Fly at the DNS provider for `kanishq.dev`. Keep
the DNS record and certificate managed by one provider path so TLS ownership is
unambiguous.

### GitHub production environment

Create a protected environment named `production`, restrict deployment to
`main`, and require your approval before the deployment job can read its
secrets. GitHub environment variables are non-secret configuration; environment
secrets are credentials only.

Required production variables:

| Type | Name | Value |
| --- | --- | --- |
| variable | `CADENCE_DATABASE_URL` | `sqlite+aiosqlite:////data/cadence.db` |
| variable | `CADENCE_BACKUP_DIR` | `/data/backups` |
| variable | `CADENCE_RUNTIME_LOCK_PATH` | `/data/cadence.lock` |
| variable | `CADENCE_FRONTEND_BASE_URL` | `https://cadence.kanishq.dev` |
| variable | `CADENCE_CORS_ORIGINS` | `https://cadence.kanishq.dev` |
| variable | `CADENCE_SERVE_FRONTEND` | `true` |
| variable | `CADENCE_TEST_MODE` | `false` |
| variable | `CADENCE_DEV_MODE` | `false` |
| variable | `CADENCE_AI_ENABLED` | `true` or `false`, according to the launch decision |
| variable | `CADENCE_AI_PROVIDER` | `nvidia` |
| variable | `CADENCE_AI_BASE_URL` | `https://integrate.api.nvidia.com/v1` |
| variable | `CADENCE_AI_CATALOG_REFRESH_MINUTES` | `360` |
| variable | `CADENCE_AI_REQUEST_TIMEOUT_SECONDS` | `45` |
| variable | `CADENCE_FROM_EMAIL` | `no-reply@kanishq.dev` |
| variable | `CADENCE_FROM_NAME` | `Cadence` |

Required production secrets:

| Name | Purpose |
| --- | --- |
| `FLY_API_TOKEN` | Deploy permission for the Fly app only |
| `CADENCE_SECRET_KEY` | JWT signing key; generate a new long random value |
| `CADENCE_BREVO_API_KEY` | Brevo transactional-email API key |
| `CADENCE_AI_API_KEY` | NVIDIA Build API key; may be blank if AI is disabled |

Never place these values in GitHub repository variables, commits, workflow YAML,
`.env` files that are shared, screenshots, issue comments, or logs. Rotate any
credential that has ever been pasted into a public or shared location.

### Brevo for `@kanishq.dev`

Use `no-reply@kanishq.dev` as the sender. In Brevo, add and authenticate the
`kanishq.dev` sending domain, then publish the exact Brevo code, DKIM, and DMARC
records that Brevo shows for the account. Do not invent or reuse values from
another account. Add the sender only after domain authentication, then generate
a transactional API key and store it as the `CADENCE_BREVO_API_KEY` production
secret. Finally send a verification email to a real test mailbox and inspect
the headers for SPF/DKIM/DMARC pass.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/habits` | List habits |
| POST | `/api/habits` | Create a discipline |
| PATCH | `/api/habits/{id}` | Rename a discipline |
| DELETE | `/api/habits/{id}` | Archive a discipline while preserving history |
| GET | `/api/habits/month?month=YYYY-MM` | Month grid data |
| POST | `/api/habits/toggle` | Toggle habit log |
| GET/PUT | `/api/days/{date}` | Day detail + daily note |
| GET/PUT | `/api/days/{date}/checkin` | Structured check-in (energy, focus, sleep, etc.) |
| GET/POST | `/api/days/{date}/conversation` | Chat-style entries |
| GET | `/api/days/{date}/context` | Previous day context |
| GET/PUT | `/api/days/{date}/summary` | Read or manually edit the daily summary artifact |
| POST | `/api/days/{date}/summary/generate` | Generate a source-traceable summary through AI fallback |
| PATCH | `/api/days/{date}/status` | Close or reopen a day |
| GET/POST | `/api/days/{date}/carry-forward` | List inherited threads or create one |
| PATCH | `/api/days/{date}/carry-forward/{id}` | Complete, release, or reopen a thread |
| GET | `/api/continuity/weeks/{date}` | Reconstruct the date's Monday–Sunday week and open threads |
| GET | `/api/continuity/search?q={term}` | Search one bounded year of user-owned continuity sources |
| GET | `/api/continuity/patterns` | Read bounded, deterministic pattern observations and weekly trend buckets |
| GET/POST | `/api/contexts` | List or create projects, learning contexts, and areas |
| PATCH/DELETE | `/api/contexts/{id}` | Edit or archive a context while preserving history |
| GET/PUT | `/api/days/{date}/contexts` | Read or replace a day's context links |
| GET | `/api/contexts/{id}/continuity` | Read recent days and open threads for one context |
| GET | `/api/account/export` | Download a versioned JSON export of the authenticated user's data |
| GET/PUT | `/api/account/ai-preferences` | Read or update external-AI consent and outbound redaction |
| POST | `/api/auth/verification/resend` | Request a fresh verification message without exposing account existence |

## Database Migrations

From the repository root:

```sh
source venv/bin/activate
alembic -c cadence/alembic.ini revision --autogenerate -m "description"
alembic -c cadence/alembic.ini upgrade head
```

## Local database backups

Backups use SQLite's online backup API, so committed WAL data is included in a
consistent snapshot. Each snapshot is integrity-checked before it receives its
final filename. The default retention policy keeps the ten newest
Cadence-managed backups and does not touch unrelated files.

```sh
python -m cadence.maintenance backup
python -m cadence.maintenance verify cadence/data/backups/<backup-file>.db
```

Configure the directory and retention count with
`CADENCE_BACKUP_DIR` and `CADENCE_BACKUP_RETENTION_COUNT`.

Restore requires an exact schema-version match. Stop the API first, verify the
chosen snapshot, and provide the explicit confirmation:

```sh
python -m cadence.maintenance verify cadence/data/backups/<backup-file>.db
python -m cadence.maintenance restore \
  cadence/data/backups/<backup-file>.db \
  --confirm RESTORE
```

The API holds a runtime lock while serving, so restore refuses to run against a
live process. Before replacement, Cadence creates and verifies a fresh safety
backup of the live database. If post-install verification fails, that safety
backup is restored automatically. Restart the API only after the command
completes.

## Tests

```sh
venv/bin/python -m unittest discover -s cadence/tests -v
cd front && npm run check
```

## NVIDIA AI development

Cadence keeps a persisted, timed model registry and a dated quality ranking.
Copy the relevant values from `.env.example` into `.env`. Developer endpoints
require both a normal authenticated login and `CADENCE_DEV_MODE=true`. If
`CADENCE_DEV_USERNAMES` is set, only those comma-separated usernames may use
them.

External AI is off for each user until they explicitly enable it in
**Settings → AI privacy**. Manual daily summaries and weekly reflections remain
available without AI. When redaction is enabled, Cadence replaces email
addresses and phone-like values in the bounded outbound prompt; the local source
data is unchanged. The settings screen identifies NVIDIA Build API as the
external provider, and no recorded data is sent automatically.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/dev/ai/models` | Return the registry; refresh when stale |
| GET | `/api/dev/ai/models?refresh=true` | Force NVIDIA catalog discovery |
| POST | `/api/dev/ai/models/test` | Probe selected models or every model |
| GET | `/api/dev/ai/fallback/{task}` | Inspect summary/context/extraction fallback order |

Probe selected models:

```json
{"model_ids": ["nvidia/nemotron-3-ultra-550b-a55b", "z-ai/glm-5.2"]}
```

Probe the complete discovered chat catalog explicitly:

```json
{"test_all": true}
```

Bulk probes are sequential but still consume free-tier requests. A `429`
marks a model as rate-limited and the runtime proceeds to the next eligible
model. The dev console's **Test all** action asks for confirmation before
issuing one probe per discovered chat model.

## Project Structure

```
cadence/           # FastAPI backend
  app/
    config.py            # Settings
    extensions.py        # SQLAlchemy engine, session, Base
    persistence/models/  # Habit, HabitLog, Day, DailyCheckin, ConversationEntry
    persistence/migrations/  # Alembic migrations
    web/routes/          # habits.py, days.py
  domains/habits/service.py
  main.py

front/             # React frontend
  src/
    App.tsx
    components/    # Dashboard navigation and focused continuity components
    contexts/      # Auth state and session lifecycle
    styles/        # base.css
```
