# Career radar delivery

## Authorized scope — 2026-10-21

The user requested: "tienes que hacer push y despliegues y revisiones para generar
versiones sucesivas" and asked to prove that offers refresh and provide real,
active application/contact opportunities. This authorizes the requested JobRadar
release/deployment cycles, not applications to employers or unrelated services.

## Initial live evidence

- Public HTTPS health and job routes returned Nginx 404.
- The existing app and PostgreSQL containers were healthy; internal health returned 200.
- The JobRadar HTTPS site contained an explicit `return 404` before its proxy directive.
- The running release was 0.1.33. Ingestion and backup cron jobs were present.
- Ingestion had completed on the current date. The live database used private/custom
  profile identifiers rather than the public example keys.

No credentials, private candidate profiles, account data or database dumps belong
in this record. Runtime configuration and pre-deployment backups stay on the host.

## Release sequence

1. Release 0.1.38 publishes the reviewed career ranking and preserves private profile
   keys through configuration-based policy selection. It separates runtime profiles
   from image contents, retains existing secrets and account/application state,
   and exposes installed version/revision in health metadata.
2. Follow with an evidence-driven release for live offer verification and contact
   paths if runtime checks show that ingestion freshness alone cannot establish
   whether a vacancy is still accepting applications.

At preparation: 173 local tests passed; two PostgreSQL integration tests await the
isolated CI database. Type checking passed. Release commits and deployment results
must be recorded below only after their actual checks finish.

## Deployment gates

- Push a work branch and require the exact revision's CI, PostgreSQL tests and
  image build to pass.
- Build/deploy the same committed source with explicit image revision labels.
- Preserve the existing environment file, private profile keys, application users,
  database volume and cron ownership. Back up before changing the app image.
- Restore only the JobRadar proxy route after reviewing the site diff, taking a
  backup and passing Nginx configuration validation.
- Verify public health/version, sign-in/dashboard, real current offers, direct
  application availability, repeated refresh behavior and unchanged user state.
- Report failures and uncertainty; a successful build is not a successful deployment
  and a recently fetched portal listing is not proof that an employer is hiring.

## Verified release 0.1.38

- Published work branch: `codex/career-radar-release`, revision
  `2eebad07c06fa4f1de92763b92b00d7dba44ad2d`.
- [CI](https://github.com/Gabrielvcg/JobRadar/actions/runs/39665444696) passed:
  175 tests including PostgreSQL, Ruff, mypy and Docker build. The first candidate
  exposed a SQLAlchemy 2.1 typing change; the corrected release stays on the tested
  2.0 series and passed before deployment.
- A hash-checked archive of that exact commit was built on the existing VPS with
  matching OCI revision/version labels. The environment and Compose file were
  backed up, a compressed database backup passed gzip validation, and an image
  rollback tag was retained. Private profiles moved to a read-only runtime mount.
- Public HTTPS health returned 200 with version 0.1.38 and the exact revision.
  Only the JobRadar proxy's explicit 404 was removed; Nginx validation passed,
  registration remained blocked, and the existing database container was retained.
- All 684 stored offers were rescored. Both private profile identifiers remained.
  The public login page returned 200 and registration returned 403.
- Live ranking review identified legacy flattened requirements inflating fit and
  confirmed that some portal HTML checks receive 403. Those observations justify
  release 0.1.39's description rehydration and explicit availability evidence.

## Release 0.1.39 preparation

The new verification policy distinguishes accessible application controls, explicit
closure, and uncertainty. A blocked request is cached as unverified, never called
closed. Checks are bounded and never send forms, applications, or recruiter messages.
Verified-only filtering expires old evidence even between ingestion runs. Original
HTML is recovered from source payloads where available; unrelated AI evaluation work
and operations-heavy SRE duties receive no backend-career recommendation.

## Verified release 0.1.39 and corrective release 0.1.40

- Revision `43fa81531f1168ab72897040baa7b83546b515ba` passed
  [CI](https://github.com/Gabrielvcg/JobRadar/actions/runs/39667403011):
  196 tests including PostgreSQL, Ruff, mypy and image build.
- Public health confirmed 0.1.39 and that revision after deployment. All 688 offers
  then present were rescored, including four added by the existing schedule after
  the first deployment. The two profiles and the existing database were retained.
- On the same 533 candidate-profile rows, current offers at score >=35 decreased
  from 92 to 82 after legacy description and role corrections. The initial 20 page
  checks found ten removed listings and ten uncertain responses; the next bounded
  batch found two further removed pages. These are page-check counts, not market
  coverage or statistical hiring estimates.
- The full refresh immediately after deployment fetched zero records because the
  configured polling intervals had not elapsed. It completed without errors and
  ran its bounded verification batch. This validates interval handling, not a new
  source fetch; a real curated-source fetch is checked separately below.
- A live SmartRecruiters `applyUrl` containing `oga=true` returned 403, whereas
  `postingUrl` returned 200. The canonical page's empty notification heading and
  JavaScript-bound application anchor also required platform-aware interpretation.
  A browser check opened the actual Backend Java application form with personal
  details, CV and hiring-team message fields. No fields or applications were sent.
- Release 0.1.40 therefore prefers `postingUrl`, matches the nonempty job heading,
  and recognizes only the observed platform-specific JavaScript apply anchor on
  its supported host. It retains the listing URL rather than guessing a form URL.
  Local validation: 196 passed, two PostgreSQL tests pending CI; Ruff/mypy passed.
  Publication, deployment and subsequent live results are recorded only once done.
- Review of the live top 20 also exposed an explicit Galicia residence condition
  hidden by a broad Spain-remote label, and a role allowing up to three years
  interpreted as requiring three. The same 0.1.40 candidate corrects both cases.
