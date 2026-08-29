# JobRadar

JobRadar collects job offers from enabled sources, normalizes them, stores them in PostgreSQL, and scores each offer against separate career profiles. The default profile targets backend Java/Spring evolving toward AWS, cloud, DevOps, platform, and AppSec roles.

## Quick Start

```bash
cp .env.example .env
docker compose up --build
```

Open:

- Web UI: http://localhost:8000
- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

Create your first user from the UI at http://localhost:8000/register or with the CLI:

```bash
docker compose exec app python -m app.cli create-user you@example.com --display-name "Your Name"
```

Run the first ingestion:

```bash
docker compose exec app python -m app.cli ingest
```

## Local Development

```bash
python -m venv .venv
.venv\Scripts\activate
make install
make migrate
make ingest
make run
```

Useful commands:

```bash
make lint
make test
make migrate
make ingest
make run
make down
```

CLI examples:

```bash
python -m app.cli ingest
python -m app.cli score-all
python -m app.cli create-user you@example.com --display-name "Your Name"
python -m app.cli list --min-score 70
python -m app.cli export --format csv
```

## Configuration

Configuration lives under `config/`:

- `profile.yml`: salary thresholds and professional profile.
- `profiles.yml`: available profile tabs and their profile-specific config files.
- `scoring.yml`: scoring weights, technologies, role keywords, and penalties.
- `searches.yml`: initial search terms and target geographies.
- `sources.yml`: source enablement and adapter settings.

Additional profile-specific files live under `config/profiles/<profile>/`. The web UI accepts `?profile=<key>`, and the CLI `list` and `export` commands accept `--profile`.

Runtime values use environment variables. Copy `.env.example` to `.env`, set a long random `APP_SECRET_KEY`, and adjust `DATABASE_URL` if needed. Do not put real secrets in the repository.

Set `PUBLIC_REGISTRATION_ENABLED=false` in public deployments and create users with the CLI
or `infra/vps/create-user.sh`. Set `SESSION_COOKIE_SECURE=true` when the app is behind HTTPS.

Set `ADZUNA_APP_ID` and `ADZUNA_APP_KEY` to enable the Adzuna profile-specific API source. Without those values the source is skipped safely.

## Sources

Initial adapters:

- `fixtures`: local JSON data for development, tests, demos, and deterministic deduplication.
- `arbeitnow`: public API from Arbeitnow, with timeout, retries, page limits, and rate limiting.
- `remotive`: public API from Remotive for remote jobs, filtered locally for technical fit and refreshed at most every 6 hours.
- `remoteok`: public API from Remote OK for remote jobs, filtered locally for realistic backend/cloud fit and refreshed at most every 6 hours.
- `weworkremotely`: public RSS feeds from We Work Remotely programming categories, filtered for Java/Spring/JVM fit.
- `jobicy`: public API from Jobicy with Java-tagged remote requests and local Java/Spring/JVM filtering.
- `himalayas`: public API from Himalayas with Java/Spring/Kotlin searches for Spain and worldwide remote roles.
- `fundacion_adecco`: fixed public Fundación Adecco disability IT listing pages for Engineering's Java/backend/cloud/AppSec profile, enriched from public offer pages and filtered to avoid support, sales, and administrative noise.
- `tecnoempleo`: fixed public Tecnoempleo disability/certificate IT search pages for Engineering, enriched from public `JobPosting` detail data and filtered for backend, DevOps, systems, data, and cybersecurity fit.
- `portalento`: public Por Talento/Inserta sitemap plus selected public offer details for Engineering's disability-focused cybersecurity/backend searches.
- `fundacion_randstad`: public Fundación Randstad offers API, filtered hard for technical disability roles and salary/experience metadata.
- `adzuna`: official API from Adzuna, prepared for profile-specific searches in Spain. It requires `ADZUNA_APP_ID` and `ADZUNA_APP_KEY`.
- `infoempleo`: fixed public Infoempleo listing pages for Operations's administrative/accounting searches in Spain, filtered locally for role, location, schedule noise, and source attribution.
- `domestiko`: fixed public Domestiko administration and secretarial category pages for the Operations profile, using structured `JobPosting` data.
- `trabajos`: fixed public Trabajos.com category pages for Operations's accounting and purchasing searches, filtered locally for role, location, language, and noisy warehouse/retail paths.
- `jobtoday`: fixed public JobToday search pages for Operations's administrative/accounting searches, using only internal postings with stable URLs and structured salary/location data.
- `pagepersonnel`: fixed public Page Personnel search pages for Operations's accounting and administrative searches, filtered locally to avoid recommended off-location or senior/responsibility roles.
- `eurofirms`: fixed public Eurofirms listing pages for Operations's administrative and customer-service searches, filtered locally to avoid warehouse, retail, promoter, Portuguese-language, and senior/responsibility roles.
- `talent`: prepared fixed public Talent.com listing pages for Operations's administrative/accounting/customer-service searches, enriched from public job-detail JSON-LD when available and filtered to avoid duplicate aggregators and off-location noise. It is disabled in production while the VPS receives 403 responses.
- `bizneo`: fixed public Bizneo-powered job portals for Faster, IMAN, and Grupo Crit, using native province/subcategory filters for Operations's administrative/accounting searches and strict role/location/language exclusions.

The real-source adapters use public APIs, RSS feeds, or fixed public listing pages with conservative rate limits, and keep source attribution in the UI. Source compliance notes are in `docs/security/source-compliance.md`.

## API

Implemented endpoints:

- `GET /health`
- `GET /login`
- `POST /login`
- `GET /register`
- `POST /register`
- `POST /logout`
- `GET /jobs`
- `GET /jobs/{id}`
- `GET /jobs/stats`
- `POST /jobs/{id}/status`
- `POST /ingestion/run`
- `GET /ingestion/runs`
- `GET /sources`

`GET /jobs` supports filters for score, match level, technology, source, company, salary, published salary/rate, remote type, status, publication date, and free text. When a user is signed in, status filters and status updates are scoped to that user.

## Testing

Unit tests run without external services:

```bash
pytest
```

PostgreSQL integration tests run when `POSTGRES_TEST_URL` is set:

```bash
$env:POSTGRES_TEST_URL="postgresql+psycopg://jobradar:jobradar@localhost:5432/jobradar_test"
pytest -m integration
```

## AWS Preparation

The MVP is local-first. A future AWS deployment can use ECR, ECS/Fargate, EventBridge scheduled tasks for ingestion, RDS PostgreSQL, Secrets Manager or Parameter Store, and CloudWatch Logs. See `docs/operations/aws-deployment.md`.

## VPS Deployment

For a practical VPS deployment, use the files under `infra/vps/`.

The prepared setup runs:

- FastAPI behind Nginx.
- Public HTTPS access through Nginx and Certbot.
- PostgreSQL in Docker with a persistent volume.
- Explicit user creation with generated strong temporary passwords.
- Ingestion every 30 minutes through system cron.
- Daily compressed PostgreSQL backups with 14-day retention.

See `docs/operations/vps-deployment.md`.

## Public repository boundary

The repository is prepared for public inspection of the ingestion, scoring,
deduplication, and deployment patterns. The checked-in profiles and fixtures
are demonstrations, not a personal job-search export. Keep real profiles,
candidate records, database dumps, cookies, API credentials, `.env` files, and
CSV exports outside Git.

See [SECURITY.md](SECURITY.md) for responsible disclosure and
[CONTRIBUTING.md](CONTRIBUTING.md) for privacy and source-compliance guidance.
