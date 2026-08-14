# Security Policy

Security fixes target the latest `main` branch.

## Reporting

Do not open a public issue. Submit a
[private GitHub Security Advisory](https://github.com/FloatingPegasus/Cadence/security/advisories/new)
with the affected commit, reproduction steps, impact, and a safe proof of
concept. Do not include credentials, private records, or database files.

## Deployment

- Set a random `CADENCE_SECRET_KEY` of at least 32 characters.
- Use HTTPS with explicit `CADENCE_FRONTEND_BASE_URL` and
  `CADENCE_CORS_ORIGINS` values.
- Browser sessions use an HttpOnly cookie and signed CSRF validation; the
  frontend does not store bearer tokens.
- Use the Redis rate-limit backend for multiple workers or instances. Redis
  failures stop authentication rather than falling back to local limits.
- Keep `CADENCE_DEV_MODE=false` outside local development.
- Keep `.env`, databases, backups, and API keys out of Git.

An XSS issue could still act as the signed-in user while the page is open.
Keep dependencies updated and retain the response security headers.
