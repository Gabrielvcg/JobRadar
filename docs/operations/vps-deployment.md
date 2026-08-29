# VPS Deployment

This deployment keeps JobRadar simple and useful:

- FastAPI runs as a Docker container bound to `127.0.0.1:8000`.
- PostgreSQL runs as a Docker container with a persistent Docker volume.
- Nginx terminates public HTTP/HTTPS and proxies to the app.
- Cron runs ingestion every 30 minutes.
- Cron also creates a daily compressed PostgreSQL backup and keeps 14 days.
- Docker memory limits protect small VPS instances from runaway app, ingestion, or database processes.

## VPS Requirements

Install Docker Engine, Docker Compose v2, Nginx, cron, and certbot. Point the domain DNS
`A` or `AAAA` record at the VPS before requesting TLS certificates.

On Ubuntu/Debian, the final deployment directory used by the provided scripts is:

```bash
/opt/jobradar
```

## First Manual Deploy

Copy these files to `/opt/jobradar` on the VPS:

```text
docker-compose.prod.yml
.env.prod.example
deploy.sh
install-cron.sh
install-user-cron.sh
create-user.sh
backup-postgres.sh
check-health.sh
nginx-jobradar.conf
```

Then create the production environment file:

```bash
cd /opt/jobradar
cp .env.prod.example .env.prod
nano .env.prod
```

Set at least:

```bash
APP_IMAGE=ghcr.io/YOUR_GITHUB_USER_OR_ORG/jobradar:latest
POSTGRES_PASSWORD=a-long-random-password
APP_SECRET_KEY=a-long-random-session-secret
SESSION_COOKIE_SECURE=true
PUBLIC_REGISTRATION_ENABLED=false
```

Generate `POSTGRES_PASSWORD` and `APP_SECRET_KEY` with a password manager or:

```bash
openssl rand -base64 48
```

For a small VPS, the default memory limits are:

```bash
APP_MEM_LIMIT=256m
INGEST_MEM_LIMIT=384m
DB_MEM_LIMIT=384m
MAX_MEM_PERCENT=80
```

Raise them only if the VPS has enough RAM and the health check confirms stable usage.

If the image is private, log in to GHCR:

```bash
echo "YOUR_GHCR_TOKEN" | docker login ghcr.io -u YOUR_GITHUB_USER --password-stdin
```

Start the app and run the first ingestion:

```bash
chmod +x deploy.sh install-cron.sh install-user-cron.sh create-user.sh backup-postgres.sh check-health.sh
./deploy.sh
```

`deploy.sh` starts the app, applies Alembic migrations, recalculates stored job scores, and runs one ingestion.

Production disables public registration by default. Create the first users by SSH:

```bash
./create-user.sh you@example.com "Your Name" --admin
./create-user.sh reviewer@example.com "Reviewer"
```

The script generates a strong temporary password, creates the user, and prints the password
once. Store it immediately in a password manager. To allow self-registration temporarily,
set `PUBLIC_REGISTRATION_ENABLED=true`, deploy, create the accounts, then set it back to
`false`.

Install the scheduled ingestion and backups:

```bash
sudo ./install-cron.sh
```

The ingestion cron runs:

```cron
*/30 * * * *
```

If the SSH user does not have passwordless `sudo`, install the same jobs in the user's crontab instead:

```bash
APP_DIR=/home/vacaro/jobradar ./install-user-cron.sh
```

## Nginx

Allow only SSH plus public web traffic at the firewall. For UFW:

```bash
sudo ufw allow OpenSSH
sudo ufw allow "Nginx Full"
sudo ufw enable
```

Copy the Nginx config and replace `jobradar.example.com` with the real domain:

```bash
sudo cp /opt/jobradar/nginx-jobradar.conf /etc/nginx/sites-available/jobradar
sudo nano /etc/nginx/sites-available/jobradar
sudo ln -s /etc/nginx/sites-available/jobradar /etc/nginx/sites-enabled/jobradar
sudo nginx -t
sudo systemctl reload nginx
```

Enable TLS with certbot and force HTTP to HTTPS:

```bash
sudo certbot --nginx -d jobradar.example.com --redirect
```

After TLS is active, keep `SESSION_COOKIE_SECURE=true` so login cookies are sent only over
HTTPS. The application container remains bound to `127.0.0.1:8000`; do not expose port
`8000` publicly.

## Useful Operations

Check services:

```bash
cd /opt/jobradar
docker compose --env-file .env.prod -f docker-compose.prod.yml ps
```

Run ingestion manually:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml run --rm ingest
```

View ingestion logs:

```bash
tail -f /opt/jobradar/logs/ingest.log
```

Create a backup manually:

```bash
/opt/jobradar/backup-postgres.sh
```

Validate health and memory:

```bash
/opt/jobradar/check-health.sh
```

Restore a backup into a fresh database only after stopping the app and confirming the target:

```bash
gunzip -c /opt/jobradar/backups/jobradar_YYYYMMDDTHHMMSSZ.sql.gz \
  | docker compose --env-file .env.prod -f docker-compose.prod.yml exec -T db \
      psql -U jobradar jobradar
```

Stop the app while keeping data:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml down
```

Dangerous: this removes PostgreSQL data:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml down -v
```

## GitHub Actions Deploy

The workflow `.github/workflows/deploy-vps.yml` builds and pushes a GHCR image, copies VPS files, writes `.env.prod` from secrets, deploys, and installs cron.

Required repository secrets:

- `VPS_HOST`
- `VPS_USER`
- `VPS_SSH_KEY`
- `VPS_POSTGRES_PASSWORD`
- `VPS_APP_SECRET_KEY`

Optional repository secrets and variables:

- `VPS_PORT`, default `22`
- `VPS_APP_DIR`, default `/opt/jobradar`
- `VPS_APP_PORT`, default `8000`
- `VPS_PUBLIC_REGISTRATION_ENABLED`, default `false`
- `GHCR_READ_TOKEN`, only needed if the VPS must pull a private package

The workflow does not publish to Docker Hub and does not create cloud resources.
