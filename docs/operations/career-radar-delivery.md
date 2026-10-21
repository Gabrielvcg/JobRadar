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
