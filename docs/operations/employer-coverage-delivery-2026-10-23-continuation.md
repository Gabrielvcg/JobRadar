# GHCG employer coverage delivery — 23 October 2026

## Result and opportunity

Production runs **0.1.50**, revision
`e601e01601344d80b2abd6e8407b55bb38853fcb`. GHCG is the eighth employer with a
currently classified A/B opportunity. The target of ten employers remains unmet.
Research now covers 81 named employers; see the
[17-employer continuation inventory](../research/employer-coverage-2026-10-23-continuation.md)
and its [machine-readable companion](../research/employer-coverage-2026-10-23-continuation.json).

| Employer | Vacancy | Location / experience | Salary | Result / application evidence |
| --- | --- | --- | --- | --- |
| Global Human Capital Group | [Junior Java / Spring developer](https://globalhumancapitalgroup.zohorecruit.com/jobs/Careers/353577000030011001/Junior-Java-Spring-developer-Remote-Work-in-Spain?source=RSS) | Remote from Spain; one–two years in requirements, one–three in metadata; B2 minimum, C1 desired | Not published | **A80**. Vacancy-specific rendered form checked on 23 October at 16:27 UTC: matching title/ID, email/name, required CV, CAPTCHA and submit button. No application sent. |

The advert was published on **5 January 2026**. It is newly discovered by this run,
not newly posted this month. Availability means the application path was accessible;
it does not establish that an old advert is actively staffed, guarantee recruitment,
or confirm salary. The client is unnamed.

A second GHCG Senior Java/Spring posting was imported as **C59**, without verified
application evidence. Its prose/requirements/structured metadata disagree on years
(three, two–three and four–five). Both original publications and identities are kept.
There is insufficient evidence to assert that they represent separate end-client
projects; no speculative merge or two-project claim was made. No scoring weights,
thresholds or candidate profile were changed.

## Measured changes

Baseline: 16:08 UTC. Final snapshot: 16:35 UTC.

| Metric | Before | After | Attribution |
| --- | ---: | ---: | --- |
| Candidate records, including disabled fixtures | 616 | 618 | Two GHCG postings |
| Market records / distinct canonical posting URLs | 601 | 603 | Two postings; independent hiring-project count unknown |
| Distinct market employer names | 191 | 192 | GHCG |
| A/B records | 27 | 28 | One newly discovered useful vacancy |
| Employers with A/B records | 7 | 8 | GHCG |
| A/B records with fresh application evidence | 25 | 28 | One GHCG browser check plus two scheduled rechecks |
| A/B grade split | A7 / B20 | A8 / B20 | GHCG junior is A80 |
| Top-20 employer names | 7 | 8 | GHCG enters the top 20 |
| knowmad mood postings in top 20 | 11 | 10 | Existing ranking, without an employer penalty |
| Exact duplicate URLs per profile | 0 | 0 | Repeat ingestion created zero records |
| Secondary-profile records | 156 | 156 | Preserved |
| Total records across both profiles | 772 | 774 | Only the two new GHCG records |

The two existing checks were refreshed by the already scheduled 16:30 UTC process:
White Team posting 8559939 at 16:30:12 and knowmad posting 8525964 at 16:30:15.
The controlled finalizer found no remaining expired checks among the original A/B
IDs and therefore did not recheck them. They are not new research discoveries.

After delivery, A/B distribution is knowmad mood 16, eXperience 3, Talan 2,
The White Team 2, Talent Connect 2, T-Systems Iberia 1, SNGULAR 1 and GHCG 1.
The final market grade counts are A8, B20, C112, D419 and U44.

## Implementation and controlled ingestion

The small `zoho_rss` adapter reuses existing RSS discovery and filtering, then reads
complete fields from public server-rendered job data. The observed RSS omitted the
requirements and API-development duties needed to judge the role. The extension
checks the detail's employer origin, title and numeric identity; it never evaluates
JavaScript or calls a private ATS endpoint. Collection is every 12 hours, with at
most five detail pages and a one-second delay. The current collection uses one RSS
request and two vacancy requests.

| Controlled run | Fetched | Created | Updated | Rejected | Error |
| --- | ---: | ---: | ---: | ---: | --- |
| First GHCG run | 2 | 2 | 0 | 0 | None |
| Second GHCG run | 2 | 0 | 2 | 0 | None |

The second run preserved the junior's browser evidence and A80 classification.
Both postings retain source IDs and provenance. New fixtures use only vacancy JSON;
no CSRF tokens, credentials or complete application pages were committed.

## Validation, deployment and preservation

- Feature commit: [e601e01](https://github.com/Gabrielvcg/JobRadar/commit/e601e01601344d80b2abd6e8407b55bb38853fcb).
- Local checks: Ruff and Mypy passed; 285 tests passed, with three PostgreSQL tests
  skipped locally and subsequently exercised in CI.
- [Exact-revision CI](https://github.com/Gabrielvcg/JobRadar/actions/runs/39987256956):
  successful, including **288 tests**, PostgreSQL, Ruff, Mypy and Docker build.
- [Dependency security](https://github.com/Gabrielvcg/JobRadar/actions/runs/39987256969):
  successful on the same revision, before deployment.
- Production backup: `jobradar_20261023T163230Z.sql.gz`; compressed archive integrity
  checked successfully. This was not a restore drill.
- Built from the committed Git archive, SHA-256
  `5f4b804135cc0a2c05d4c8d058329faa7c14151e395b6fd384421eefc667ce3c`,
  excluding unrelated working-tree changes and private configuration.
- Image `jobradar:0.1.50-e601e01`; public and private preflights ran with networking
  disabled. Existing runtime files outside `sources.yml` are byte-identical;
  existing source settings are semantically identical. Only GHCG was added for
  the candidate profile.
- App-only deployment used the existing ingestion lock. Health returned version
  0.1.50 and the exact feature revision. Authentication returned 303, dashboard 200,
  protected full CSV 200 and anonymous CSV 401. Only JobRadar's app was recreated.
- All **772 original record IDs and statuses**, user/password/role fingerprints and
  user job-state fingerprint were preserved. The secondary profile remains at 156
  with the same full-content/score/status SHA-256:
  `80288e0e1ffd6538a8ee9865c8992f0da0a016693832822f2a31529ae15ea046`.
- Final source errors: none. Both profiles remain present. Full CSV contains
  **618 rows and 36 columns**, including GHCG's full requirements and duties.

Rollback material retains image `jobradar:0.1.49-56fb900`, the prior runtime-config
symlink target, and private environment/Compose copies under the 0.1.50 release's
rollback directory. No other VPS application was changed.

## Limits and stopping point

The new A/B source adds one employer, with one currently useful posting. Ten A/B
employers and a five–ten useful-new-postings monthly rate are not established.
Remaining inspected candidates were blocked legitimately, lacked current eligible
roles, had incompatible geography/seniority, or required a bespoke integration
without proven value. Promising manual leads include AD4 and IOON; Veeva's HTML/API
availability contradiction needs confirmation before treating it as open.

GHCG's application is JavaScript-rendered and CAPTCHA-gated. The automatic HTTP
verifier does not claim to validate it. The explicitly recorded browser check
expires after the existing 24-hour lifetime; if it is not renewed, the next normal
rescore can return the vacancy to U. Its unknown salary and old publication date
remain visible. No employer contact, application, CAPTCHA solution, global scoring
relaxation or speculative employer/project identity was used.
