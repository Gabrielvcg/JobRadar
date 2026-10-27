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

## Verified release 0.1.40

- Deployed revision `d56c83017d866e623cc995d642dd3fcfab1b8bf5` after
  [201-test CI](https://github.com/Gabrielvcg/JobRadar/actions/runs/39669315266)
  passed, including PostgreSQL and Docker. Public health matched exactly.
- Two real curated-source GET refreshes each returned six records, updated the
  same three stored offers, created zero, and rejected three at the score gate.
  Both completed without errors. The second preserved the verified application
  evidence and offer identity. A full refresh respected polling intervals.
- Verification found the canonical T-Systems Backend Java page active. A temporary
  non-admin user completed public HTTPS login (303), dashboard (200) and the
  verified-only view (200), with that actual application link. The user was removed
  in a finally block. Unauthenticated dashboard access continued to redirect.
- Existing users, password hashes, role flags and application states matched their
  pre-deployment fingerprints. Both private profiles remained; duplicate URL excess
  remained zero. Runtime evidence and backups are private host/local artifacts.

## Final bounded salary correction — 0.1.41

The manual sample also revealed IRIUM's "Salario hasta 33K" had been normalized as
an exact EUR 33,000 salary. The upper limit is published, but it guarantees no lower
limit or increase over the candidate's change minimum. The correction stores no
invented minimum, displays "up to", and treats the minimum as requiring employer
confirmation. Rescoring repairs this explicit ceiling in legacy career records.
Local validation: 203 passed, two PostgreSQL tests awaiting CI; Ruff/mypy passed.
The release is not considered deployed until the following evidence is recorded.

## Final production result — 2026-10-21, 20:27 UTC

Release **0.1.41**, revision `d4ea420191cbb266e1f0007f4c086fa1c7f6d6e5`, is live.
[CI passed 205 tests](https://github.com/Gabrielvcg/JobRadar/actions/runs/39669994964),
including PostgreSQL, type checks, lint and the image build. The dependency workflow
also passed. Local tests passed 203 with the two PostgreSQL cases deferred to CI.
The exact hash-checked source was built on the VPS; public HTTPS health matched
version/revision, both containers were healthy, and the existing database container
was retained. The new compressed backup passed gzip integrity validation. Backups
were not restored into production and this work makes no restore-test claim.

Final HTTPS login, the authenticated dashboard, and verified-only filtering passed
again. The IRIUM API record now has `salary_min=null`, `salary_max=33000`, and
`salary_status=overlapping_minimum`; the dashboard shows "up to 33,000 EUR".
The temporary validation user was removed, and existing account/status fingerprints
still matched. No employer application, CV upload or contact message was sent.

### Like-for-like live comparison

The baseline is the saved 0.1.38 snapshot immediately before 0.1.39; both columns
refer to the same 688 stored offers, including 533 in the candidate profile. This
is distinct from the fixed 1,171-record public diagnostic pool in the initial report.
The original 0.1.33 installation had 684 offers; the existing scheduled 20:00 UTC
ingestion added four during 0.1.38, including the three curated ATS records.

| Measure | 0.1.38 snapshot | Final 0.1.41 |
| --- | ---: | ---: |
| Stored offers, both profiles | 688 | 688 |
| Candidate-profile offers | 533 | 533 |
| Current radar, score >=35 | 92 | 72 |
| Strategic references | 57 | 45 |
| Excluded from the candidate radar | 384 | 416 |
| Current offers with fresh verified application controls | 0 | 1 |
| Listings with confirmed HTTP removal | Not checked | 12 |
| Exact URL duplicate excess | 0 | 0 |
| Private profiles retained | 2 | 2 |

The candidate-profile verification totals are 1 active, 12 removed, and 520
unverified (unchecked, blocked, unsupported, or insufficient evidence). They include
strategic/excluded records, so they must not be confused with the 72 current offers.
No error or blocking response was interpreted as proof of closure.

### Ranking and application examples

| Live example | Before | Final treatment |
| --- | --- | --- |
| Sporty Group, Weekend DevOps Engineer | 87, current | 34, excluded: operations duties do not establish the desired development path |
| Askable, Software Engineer, AI Coding Tasks | 74, current | 34, excluded: task evaluation is not the requested backend career |
| knowmad mood, Java Developer, sector textil | 71 in 0.1.39 | 34, excluded: explicit Galicia residence conflicts with Sevilla |
| IRIUM, Full Stack Developer, Java and Angular | 73 in 0.1.39; three years treated as minimum, EUR 33,000 treated as exact | 78, current: up to three years; salary ceiling only, minimum EUR 24,000 unconfirmed |
| T-Systems Iberia, Backend Java | 65; preview URL blocked | 65, current: canonical listing and application form verified; Sevilla hybrid explicitly available |

The verified [T-Systems application opportunity](https://jobs.smartrecruiters.com/T-SystemsIberia/744000153460609-desarrollador-a-backend-java-m-f-d-)
requires backend Java experience without a numerical minimum. It mentions Git,
collaboration with architecture/QA/DevOps, and learning opportunities. Its salary
is unpublished; neither a EUR 24,000 minimum nor employer acceptance is established.
The browser opened its real form, including CV and hiring-team message fields.

### Refresh evidence and limits

- The existing half-hour cron remained in place. Its 20:00 run during 0.1.38
  fetched six curated records and created three, plus one WWR offer.
- The two deliberate 0.1.40 curated refreshes each fetched six, updated three,
  created zero, and score-rejected three. Stable offer identities, application
  state and verification evidence were preserved.
- Full refreshes in 0.1.39, 0.1.40 and final 0.1.41 all completed without errors
  while respecting source intervals. The final run fetched/created/updated zero
  because no source was due, and checked 20 further pages as uncertain. These runs
  demonstrate interval handling; they are not represented as new feed retrievals.
- Checks expire after 24 hours. A verified control proves an available application
  path at check time, not form submission, an interview, a salary increase, or
  employer responsiveness. Scores are heuristics, never hiring probabilities.
- The present utility is demonstrated but coverage is limited: one current offer
  has verified application availability. The other 71 current results require
  manual confirmation. Portal access blocks and similar employer variants remain.
- Changes were pushed on `codex/career-radar-release`; no merge to the shared base
  branch was performed. Existing unrelated local deployment/backup work was retained.

### Three next priorities

1. **High benefit, medium effort:** add a small number of Spain-compatible Java
   employers through existing official ATS adapters, gated by actual current-role
   and application-path yield rather than raw listing volume.
2. **High benefit, medium effort:** review a larger real shortlist against mandatory
   skills, years, residence and current availability; use the judgments to measure
   ranking precision and requirement ambiguity instead of only synthetic cases.
3. **Medium benefit, medium effort:** detect reworded employer variants and expose
   duplicate provenance so similar portal titles do not crowd out distinct roles.
