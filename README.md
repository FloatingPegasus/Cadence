# Cadence

Cadence is a personal daily record. It keeps practices, notes, check-ins,
timed entries, summaries, and follow-ups in one small local app.

## Stack

- FastAPI, SQLAlchemy, Alembic, and SQLite
- React, Vite, TypeScript, and Tailwind CSS
- JSON API

## Run locally

### Backend

Cadence targets Python 3.14. Run these commands from the repository root:

```sh
python3.14 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r cadence/requirements.txt
alembic -c cadence/alembic.ini upgrade head
python -m cadence.main
```

The API runs at `http://localhost:8000`.

If the shell is already inside `cadence`, use:

```sh
cd cadence
../venv/bin/python main.py
```

### Frontend

```sh
cd front
npm install
npm run dev
```

The app runs at `http://localhost:3001` and proxies API requests to the
backend.

## Email verification

Normal development uses `CADENCE_TEST_MODE=false`. Test mode only suppresses
email delivery during automated tests. It does not grant access to an
unverified account.

Brevo delivery needs:

- `CADENCE_BREVO_API_KEY`
- an active sender matching `CADENCE_FROM_EMAIL`
- the current public IP allowed by the Brevo account when IP restrictions are
  enabled

Restart the API after changing `.env`. An unverified account can request a new
message from the login page.

All local dotfiles, including `.env`, are ignored by Git. Keep real keys in
local or private runtime configuration.

## Common API routes

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/habits` | List practices |
| POST | `/api/habits` | Add a practice |
| PATCH | `/api/habits/{id}` | Rename a practice |
| DELETE | `/api/habits/{id}` | Archive a practice and keep its history |
| GET | `/api/habits/month?month=YYYY-MM` | Read the month grid |
| POST | `/api/habits/toggle` | Mark a practice for a day |
| GET/PUT | `/api/days/{date}` | Read or save the day note |
| GET/PUT | `/api/days/{date}/checkin` | Read or save check-in fields |
| GET/POST | `/api/days/{date}/conversation` | Read or add timed entries |
| GET/PUT | `/api/days/{date}/summary` | Read or edit a summary |
| POST | `/api/days/{date}/summary/generate` | Create a summary |
| PATCH | `/api/days/{date}/status` | Finish or reopen a day |
| GET/POST | `/api/days/{date}/carry-forward` | Read or add follow-ups |
| PATCH | `/api/days/{date}/carry-forward/{id}` | Complete or reopen a follow-up |
| GET | `/api/continuity/weeks/{date}` | Read a week of recorded days |
| GET | `/api/continuity/search?q={term}` | Search recorded history |
| GET | `/api/continuity/patterns` | Read local activity patterns |
| GET/POST | `/api/contexts` | Read or add areas |
| PATCH/DELETE | `/api/contexts/{id}` | Edit or archive an area |
| GET/PUT | `/api/days/{date}/contexts` | Read or set day areas |
| GET | `/api/account/export` | Download account data |
| GET/PUT | `/api/account/ai-preferences` | Read or save summary settings |
| POST | `/api/auth/verification/resend` | Request a new verification message |

## Database and backups

Run migrations from the repository root:

```sh
source venv/bin/activate
alembic -c cadence/alembic.ini revision --autogenerate -m "description"
alembic -c cadence/alembic.ini upgrade head
```

Backups use SQLite's online backup API and keep the ten newest Cadence-managed
copies by default:

```sh
python -m cadence.maintenance backup
python -m cadence.maintenance verify cadence/data/backups/<backup-file>.db
```

Restore requires the API to be stopped, a verified backup, and explicit
confirmation:

```sh
python -m cadence.maintenance restore \
  cadence/data/backups/<backup-file>.db \
  --confirm RESTORE
```

## Tests

```sh
venv/bin/python -m unittest discover -s cadence/tests -v
cd front && npm run check
```

## Developer model checks

Developer routes require a normal verified login, `CADENCE_DEV_MODE=true`, and
an optional username allowlist in `CADENCE_DEV_USERNAMES`.

```text
GET  /api/dev/ai/models
GET  /api/dev/ai/models?refresh=true
POST /api/dev/ai/models/test
GET  /api/dev/ai/fallback/{task}
```

The test route accepts a list of model IDs or `{ "test_all": true }`. Testing
all discovered models is sequential and may use one request per model.

## Project layout

```text
cadence/                 FastAPI application and database migrations
  app/
    config.py            Settings
    extensions.py        Database engine and sessions
    persistence/models/  Database models
    web/routes/          JSON routes
    domains/             Application services
  main.py                Backend entry point

front/                   React application
  src/
    App.tsx
    components/          Dashboard and daily record components
    contexts/             Login state and session lifecycle
    styles/               Base styles
```
