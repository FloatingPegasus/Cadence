# Always-on deploy runbook (cadence.kanishq.dev)

Goal: `https://cadence.kanishq.dev` stays up with no cold starts.

**Now:** one Ubuntu VM running Compose (`db` + `app` + `caddy`).  
**Later:** managed Postgres + Fly (or similar) under the same hostname.  
Student / Education Pack credits are optional cash only, not the architecture.

---

## 0. What you need before starting

- [ ] GitHub repo access: `FloatingPegasus/Cadence` (already on `main`)
- [ ] Domain: `kanishq.dev` on name.com
- [ ] Brevo account (or create one) for verification email
- [ ] SSH public key on your laptop (`~/.ssh/id_ed25519.pub` or similar)
- [ ] Choice of host: **Oracle Always Free** (preferred $0) **or** a cheap always-on VPS (Hetzner CX22, etc.)

Do **not** use Neon free (DB cold start) or Vercel for the app.

---

## 1. Create the VM (Oracle Always Free)

### 1.1 Account and compartment

1. Open [cloud.oracle.com](https://cloud.oracle.com) and sign in (or create a free tier account).
2. Complete account verification if prompted (card may be required for free tier; Always Free resources should still bill $0 if you stay in free shapes).
3. Note your **home region** (example: `ap-mumbai-1`). Use that region for everything below.

### 1.2 Network security (critical on Oracle)

Oracle blocks 80/443 until you open them in **two** places: the subnet NSG / Security List **and** `iptables`/`firewalld` on the VM. The Cadence bootstrap script opens UFW on the VM; you must open the cloud firewall first.

1. Console → **Networking** → **Virtual Cloud Networks** → open the default VCN (or create one).
2. Open the **public subnet** → **Security Lists** → default security list → **Add Ingress Rules**:

| Source CIDR | IP Protocol | Destination port | Description |
| --- | --- | --- | --- |
| `0.0.0.0/0` | TCP | 22 | SSH |
| `0.0.0.0/0` | TCP | 80 | HTTP (Caddy / ACME) |
| `0.0.0.0/0` | TCP | 443 | HTTPS |
| `0.0.0.0/0` | UDP | 443 | HTTP/3 (optional) |

3. If you use a **Network Security Group** on the instance instead of (or in addition to) the security list, add the same four rules there.

### 1.3 Compute instance

1. Console → **Compute** → **Instances** → **Create instance**.
2. Name: `cadence` (any name).
3. Placement: your home region / any AD.
4. Image: **Canonical Ubuntu 24.04** (not Oracle Linux if you want the scripts as written).
5. Shape: **Change shape** → **Ampere** → **VM.Standard.A1.Flex**.
   - OCPUs: `1` (or up to what your free pool allows; free tier shares 4 OCPU / 24 GB across the tenancy).
   - Memory: `6` GB is comfortable; `4` GB is usually enough for Cadence.
6. Networking:
   - Public subnet.
   - **Assign a public IPv4 address** = Yes.
7. SSH keys: paste your laptop public key contents (`cat ~/.ssh/id_ed25519.pub`).
8. Create the instance. Wait until state is **Running**.
9. Copy the **Public IP address**. Call it `VM_IP` below.

### 1.4 First SSH login (Oracle Ubuntu)

Oracle Ubuntu images usually use user `ubuntu`:

```sh
ssh -i ~/.ssh/id_ed25519 ubuntu@VM_IP
```

If the key was added correctly you should get a shell. If connection times out, the security list / NSG is still blocking port 22.

### 1.5 Fallback: Hetzner (or any VPS)

If Oracle signup fails or Ampere capacity is empty:

1. Create an Ubuntu 24.04 cloud VPS (example: Hetzner CX22).
2. Attach your SSH key.
3. In the provider firewall / cloud firewall, allow TCP 22, 80, 443 (UDP 443 optional).
4. SSH as `root` (Hetzner) or the user they give you.
5. Continue from section 3 with that IP.

---

## 2. DNS on name.com

`cadence.kanishq.dev` previously pointed at Vercel parking. It must point at your VM before Caddy can get a certificate.

1. Log in at [name.com](https://www.name.com) → **My Domains** → **kanishq.dev** → **DNS records** (or Manage DNS).
2. Find every record whose host is `cadence` (or `cadence.kanishq.dev`, depending on UI). Delete A / CNAME / AAAA records that point at Vercel or unrelated IPs.
3. Add:

| Type | Host | Answer / value | TTL |
| --- | --- | --- | --- |
| A | `cadence` | `VM_IP` | 300 (or default) |
| AAAA | `cadence` | your VM IPv6 (only if the VM has one) | 300 |

4. Leave the apex `kanishq.dev` alone unless you intend to move it.
5. From your laptop, wait and check:

```sh
dig +short cadence.kanishq.dev A
# must print VM_IP

dig +short cadence.kanishq.dev AAAA
# empty, or your VM IPv6
```

6. Do **not** start `deploy-prod.sh` until the A record matches. Caddy’s Let’s Encrypt challenge will fail otherwise.

Propagation is often minutes with TTL 300; can be up to an hour if old records were cached.

---

## 3. Brevo (email verification)

Hosted signup needs real mail. Local Compose can log the link; production should not.

1. Open [Brevo](https://www.brevo.com/) → sign in or create an account.
2. **Senders & IPs** (or SMTP & API → Senders): add and verify  
   `no-reply@kanishq.dev`.  
   The From address must be on a Brevo-authenticated domain. `cadence.kanishq.dev` is the website host, not the mail domain, unless you also authenticate that subdomain.
3. If Brevo asks for domain authentication, add the DNS records they show (SPF / DKIM) on name.com for `kanishq.dev`, then wait for verification.
4. **SMTP & API** → **API keys** → create a key with send permission.
5. Keep the key ready for `.env` (`CADENCE_BREVO_API_KEY`). Never commit it.

---

## 4. Bootstrap Docker on the VM

On your laptop:

```sh
ssh ubuntu@VM_IP
```

On the VM:

```sh
sudo mkdir -p /opt
sudo git clone https://github.com/FloatingPegasus/Cadence.git /opt/cadence
cd /opt/cadence
sudo git checkout main
sudo ./scripts/bootstrap-host.sh
```

What that script does:

- Installs Docker Engine + Compose plugin
- Enables UFW: SSH, 80/tcp, 443/tcp, 443/udp
- Starts Docker

Then put your user in the docker group (Oracle `ubuntu` user):

```sh
sudo usermod -aG docker ubuntu
# log out and SSH back in so docker works without sudo
exit
ssh ubuntu@VM_IP
docker version
docker compose version
```

---

## 5. Create and edit production `.env`

Still on the VM:

```sh
cd /opt/cadence
cp .env.production.example .env
chmod 600 .env
nano .env   # or vim
```

### 5.1 Generate a DB password (on the VM)

```sh
python3 -c 'import secrets; print(secrets.token_urlsafe(24))'
```

### 5.2 Fill every required field

| Variable | What to set |
| --- | --- |
| `CADENCE_DOMAIN` | `cadence.kanishq.dev` |
| `CADENCE_SECRET_KEY` | leave placeholder; `deploy-prod.sh` replaces it if still short/placeholder |
| `CADENCE_POSTGRES_PASSWORD` | the strong password you generated |
| `CADENCE_DATABASE_URL` | same password in the URL: `postgresql+psycopg://cadence:THAT_PASSWORD@localhost:5432/cadence` |
| `CADENCE_BREVO_API_KEY` | Brevo API key |
| `CADENCE_FROM_EMAIL` | verified sender on the authenticated domain, `no-reply@kanishq.dev` |
| `CADENCE_FROM_NAME` | `Cadence` |
| `CADENCE_FRONTEND_BASE_URL` | `https://cadence.kanishq.dev` |
| `CADENCE_CORS_ORIGINS` | `https://cadence.kanishq.dev` |
| `CADENCE_SERVE_FRONTEND` | `true` |
| `CADENCE_DEV_MODE` | `false` |
| `CADENCE_TEST_MODE` | `false` |
| `CADENCE_AI_ENABLED` | `false` unless you intentionally enable AI later |

Important: `CADENCE_POSTGRES_PASSWORD` and the password inside `CADENCE_DATABASE_URL` must match. If the password contains `@`, `:`, `/`, or `%`, URL-encode it in `CADENCE_DATABASE_URL` or pick a URL-safe password (`token_urlsafe` is fine).

Compose overrides the app’s DB host to the internal `db` service; the localhost URL is for host-side tools. You do not need to invent `CADENCE_COMPOSE_*` URLs unless you change credentials.

Save and exit the editor.

---

## 6. Deploy (build + start Caddy + app + Postgres)

Confirm DNS one more time from your laptop, then on the VM:

```sh
cd /opt/cadence
./scripts/deploy-prod.sh
```

First run can take several minutes (frontend image build). Expected end state:

```sh
docker compose -f compose.yaml -f compose.prod.yaml ps
```

All of `db`, `app`, `caddy` should be **healthy** / **running**.

If `app` restarts in a loop:

```sh
docker compose -f compose.yaml -f compose.prod.yaml logs app --tail 100
```

Common causes: placeholder Brevo not needed for boot, but bad `CADENCE_SECRET_KEY` length, or Postgres password mismatch.

If Caddy cannot get a cert:

```sh
docker compose -f compose.yaml -f compose.prod.yaml logs caddy --tail 100
```

Usually DNS still points elsewhere, or Oracle security list still blocks 80/443.

---

## 7. Verify end-to-end

### 7.1 Health

From your laptop:

```sh
curl -fsS https://cadence.kanishq.dev/healthz
# expect: {"status":"ok"}
```

### 7.2 Browser

1. Open `https://cadence.kanishq.dev`
2. Confirm the padlock (valid cert).
3. Register a real email you can read.
4. Open the verification email from Brevo (check spam).
5. Log in → Today: add a habit, tick it, write a day note.
6. Hours: write one slot.
7. Focus: confirm the scene loads and the timer starts.
8. Log out and log back in.

### 7.3 If mail never arrives

On the VM:

```sh
docker compose -f compose.yaml -f compose.prod.yaml logs app --tail 50
```

Check Brevo dashboard → transactional logs. Fix sender/domain auth, then:

```sh
# after editing .env
cd /opt/cadence
./scripts/deploy-prod.sh
```

Use **Resend verification email** on the login page.

---

## 8. Weekly backups

On the VM, as the user that can run docker:

```sh
cd /opt/cadence
chmod +x scripts/backup-cron.sh
mkdir -p backups/host
(crontab -l 2>/dev/null; echo "15 3 * * 0 /opt/cadence/scripts/backup-cron.sh >> /opt/cadence/backups/cron.log 2>&1") | crontab -
crontab -l
```

Manual test:

```sh
/opt/cadence/scripts/backup-cron.sh
ls -la /opt/cadence/backups/host/
```

Copy dumps off the box occasionally (laptop `scp`, object storage, etc.). Restores are documented in [self-host.md](self-host.md).

---

## 9. Later updates

```sh
ssh ubuntu@VM_IP
cd /opt/cadence
git pull origin main
./scripts/deploy-prod.sh
```

---

## 10. When you outgrow one VM (scale path)

Keep the hostname. Change only infrastructure:

1. Create managed Postgres with `vector` + `pg_trgm` (Neon always-on or equivalent).
2. `pg_dump` from the VM → restore to managed DB.
3. Point `CADENCE_DATABASE_URL` / `CADENCE_MIGRATION_DATABASE_URL` at managed (pooled + direct).
4. Run the same app image on Fly (or similar) with `min_machines_running=1`.
5. Point `cadence` DNS at the new app; drop on-box `db`.
6. Add Redis when you run multiple workers:
   `CADENCE_AUTH_RATE_LIMIT_BACKEND=redis` and `CADENCE_REDIS_URL`.

---

## Checklist (print this)

- [ ] Oracle (or VPS) Ubuntu 24.04 running with public IP
- [ ] Cloud firewall: 22, 80, 443 open
- [ ] SSH works: `ssh ubuntu@VM_IP`
- [ ] name.com: `cadence` A → `VM_IP`; old Vercel records gone
- [ ] `dig +short cadence.kanishq.dev` → `VM_IP`
- [ ] Brevo sender verified + API key created
- [ ] `/opt/cadence` cloned on `main`
- [ ] `bootstrap-host.sh` ran; docker works for your user
- [ ] `.env` filled (DB password, Brevo, HTTPS URLs, `DEV_MODE=false`)
- [ ] `deploy-prod.sh` succeeded; containers healthy
- [ ] `https://cadence.kanishq.dev/healthz` → `{"status":"ok"}`
- [ ] Register → verify email → habit/note/Focus smoke
- [ ] Weekly backup cron installed and tested once

When the VM exists, send **public IP** and **SSH user** (`ubuntu` / `opc` / `root`) if you want the SSH bootstrap and deploy steps run for you.
