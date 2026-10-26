# Reviewed delivery and existing-production update

The reviewed correctness changes are delivered on top of d1a85e8. The observed
production revision a09cc2015d1df138689fe32859f148bd6b7eed2a differs from that base
only by a research delivery document. Production PostgreSQL is 16.14 and Alembic
0003_add_job_profiles; this delivery adds no migration. Remote main is older than
that already-running release line. Review the full PR ancestry before merging.

## Gates

CI on the exact source must pass Ruff, Mypy app/tests, the complete suite with no
skipped tests, disposable PostgreSQL integration (including named export cursor
and scheduler beyond 500 with commits after cursor close), upgrade/downgrade/
upgrade on the disposable DB, synthetic update/rollback procedure and Docker build.
The opt-in test URLs must NEVER point at production: existing dedup fixtures drop
tables. No production DB restore/test workload is authorized by these fixtures.

## Existing installation only

The manual Deploy VPS workflow is main-only and checks exact-head quality/security
results before publishing. Image tag is the full source SHA, APP_REVISION is passed
to the build and its OCI revision label is set. Promotion uses the build digest.
An old successful check is insufficient for a different commit.

Confirmed installation: vacaro@62.171.150.163:22, /home/vacaro/jobradar. Existing
runtime .env.prod is owner-only and runtime-config remains mounted. Existing user
cron schedules ingestion and backups. Do not run an installer or replace those
files/schedules as part of this update. Workflow secrets/access and registry pull
permission must be configured/confirmed separately before a manual dispatch.

The workflow copies only deploy.sh, not Compose, Nginx, .env or cron installers.
The script requires the existing app/config and an immutable image plus exact
revision. It shares the existing ingestion lock, pulls the image, saves owner-only
runtime-state backups and updates only app with --no-deps. Startup retains the
existing Alembic upgrade behavior; no new migration is introduced here. It does
not start/recreate the DB, run score-all, ingest or install cron. It waits for
health with the expected source revision, then atomically changes only APP_IMAGE
in the existing .env, preserving every other byte/value and file mode. This image
pin also makes the unchanged scheduled ingest use the updated code on its next
normal run; no ingest is triggered by the rollout.

On an update/health/pin failure it requests the captured previous local image ID
and restores the saved environment. Automatic rollback is an attempt, not a health
success claim: the operator must confirm old revision/health. Retain the old image
until acceptance; never prune or remove volumes. For this schema-compatible app
change rollback is image-only. A database restore is a separate approved recovery
operation, not routine rollback. This procedure does not take a DB backup itself;
confirm a recent restorable backup and compatible migration state before promotion.

Current observed rollback image ID:
sha256:b4dc9e2379465a6cda74363ac15ec5f60570eaefd9e0d2a6e3e6cb203453d175
Current app source a09cc2015d1df138689fe32859f148bd6b7eed2a, version 0.1.51.
These are point-in-time read-only observations, not future rollout evidence.

## Remaining behavior

R04 verified-only SQL still uses cached assessment/textual timestamps and can
disagree with authoritative raw proof. It is a preexisting bug in current production,
not fixed or newly introduced by this delivery; health, export completeness and
scheduler correctness do not establish that filter's correctness. Do not promote
this release as fixing it. The proposed projection needs separate implementation
and PostgreSQL validation before cutover. Streaming scans retain a connection;
row-bounded memory is not constant bytes, and concurrent-write snapshots/timeouts
remain outside these correctness changes.
