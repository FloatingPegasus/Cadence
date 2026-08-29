# Always-on deploy (cadence.kanishq.dev)

Run Cadence on one always-on VM: Postgres+pgvector and the app in Compose,
Caddy for HTTPS. No cold starts. Cost stays $0 on Oracle Always Free, or uses
GitHub Education Pack DigitalOcean credits.

## Architecture

- `compose.yaml` + `compose.prod.yaml`: `db`, `app`, `caddy`
- App serves the built frontend (`CADENCE_SERVE_FRONTEND=true`)
- Caddy terminates TLS for `CADENCE_DOMAIN` and proxies to `app:8000`
- Postgres stays on `127.0.0.1:5432` only

## 1. Create the VM

Pick one:

### DigitalOcean (GitHub Education Pack)

1. Redeem the DigitalOcean offer from [Education Pack](https://education.github.com/pack).
2. Create a Droplet: Ubuntu 24.04, Basic shared CPU, 1 GB+ RAM, add your SSH key.
3. Note the public IPv4 (and IPv6 if enabled).

### Oracle Cloud Always Free

1. Create an Ampere A1 instance (Ubuntu 24.04), shape within the free pool.
2. VCN ingress: TCP 22, 80, 443 (and UDP 443 for HTTP/3).
3. Note the public IP.

## 2. DNS on name.com

For `kanishq.dev`:

| Host | Type | Value |
| --- | --- | --- |
| `cadence` | A | droplet / VM IPv4 |
| `cadence` | AAAA | VM IPv6 (optional) |

Remove any old Vercel / parking records for `cadence`. Wait until
`dig +short cadence.kanishq.dev` returns your VM IP.

## 3. Bootstrap the host

```sh
ssh root@YOUR_VM_IP
git clone https://github.com/FloatingPegasus/Cadence.git /opt/cadence
cd /opt/cadence
sudo ./scripts/bootstrap-host.sh
```

If you SSH as a non-root user with sudo, add that user to the `docker` group
and re-login.

## 4. Configure and start

```sh
cd /opt/cadence
cp .env.production.example .env
# Set CADENCE_SECRET_KEY (or let deploy-prod.sh generate it),
# CADENCE_POSTGRES_PASSWORD, CADENCE_BREVO_API_KEY, CADENCE_FROM_EMAIL.
./scripts/deploy-prod.sh
```

Confirm:

```sh
curl -fsS https://cadence.kanishq.dev/healthz
```

Register once in the browser (Brevo must accept the from-address).

## 5. Backups

```sh
chmod +x /opt/cadence/scripts/backup-cron.sh
(crontab -l 2>/dev/null; echo "15 3 * * 0 /opt/cadence/scripts/backup-cron.sh") | crontab -
```

Dumps land in the Compose backup volume and are copied to
`/opt/cadence/backups/host/`.

## Updates

```sh
cd /opt/cadence
git pull
./scripts/deploy-prod.sh
```

## Scale later

1. Managed Postgres with `vector` and `pg_trgm`; migrate with `pg_dump`.
2. Run the app image on Fly (or similar) with `min_machines_running=1`.
3. Point DNS at the new app; add Redis when you run multiple workers.
