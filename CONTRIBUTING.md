# Contributing to Cadence

Thanks for helping improve Cadence. Small, focused changes are easier to
review and maintain.

## Before you start

- Search existing issues before opening a new one.
- For a larger change, open an issue first so the approach can be discussed.
- Do not include personal data, credentials, local databases, or generated
  build output in a change.

## Local setup

From the repository root:

```sh
python3.14 -m venv venv
source venv/bin/activate
python -m pip install -r cadence/requirements.txt
cp .env.example .env
# Generate a real signing key and replace the CADENCE_SECRET_KEY placeholder.
python -c 'import secrets; print(secrets.token_urlsafe(48))'
# Paste that value after CADENCE_SECRET_KEY= in .env before starting Cadence.
alembic -c cadence/alembic.ini upgrade head
```

The value in `.env.example` is intentionally not usable outside test mode;
copying the file alone is not a complete setup. Keep `CADENCE_TEST_MODE=false`
for local development and production-like runs.

Install frontend dependencies separately:

```sh
cd front
npm install
```

## Checks

Run the backend tests and the frontend checks before opening a pull request:

```sh
venv/bin/python -m unittest discover -s cadence/tests -v
cd front && npm run check
```

If a change affects migrations, API behavior, or configuration, include the
relevant test coverage and explain any manual verification in the pull
request.

## Pull requests

Describe what changed, why it changed, and how it was tested. Keep unrelated
cleanup out of feature changes, and update documentation when setup or
behavior changes.
