# Signicat source delivery — JobRadar 0.1.51

## Result and new opportunity

Production now includes Signicat's official Teamtailor RSS, reusing the existing
collector, provenance, deduplication and job-bound form verifier. Collection runs
every twelve hours. No adapter, dependency, profile, scoring weight, threshold or
classification policy was changed.

| Employer / role | Location | Required experience | Published pay | Result | Verified application |
| --- | --- | --- | --- | --- | --- |
| [Signicat — Java Software Engineer (Identity Proofing), Spain](https://signicat.teamtailor.com/jobs/8342057-java-software-engineer-identity-proofing-spain) | Fully remote, Spain | 3+ years Java 21 / Spring Boot | Unknown | B76, ambitious | [Vacancy-specific email/name/CV form](https://signicat.teamtailor.com/jobs/8342057-java-software-engineer-identity-proofing-spain/applications/new), HTTP 200 at 18:15:30 UTC on 2026-10-23 |

The product role includes development of distributed services, microservices,
SQL/NoSQL, RabbitMQ, code review, security, testability and performance. Main gaps
are the three-plus-year expectation versus fourteen professional months, depth of
messaging/database experience, and explicitly fluent English. The engine currently
reports English as unspecified because it cannot translate that prose into a
standard level; the original requirement is retained and is material to the human
review. There is no AWS requirement: GCP is in the stack and cloud-native familiarity
is desirable. Published salary is unknown, so a raise or minimum offer is not proved.

This is **one newly discovered posting and one new employer**, published September 8,
2026. It is not a posting published today or evidence of a monthly discovery rate.
No application or employer contact was made.

## Measured before / after

Baseline 17:59 UTC; final snapshot 18:15 UTC, October 23, 2026.

| Metric | Before | After |
| --- | ---: | ---: |
| Candidate records, including disabled fixtures | 618 | 619 |
| Market records / distinct canonical posting URLs | 603 | 604 |
| Distinct market employer names | 192 | 193 |
| A/B records | 28 | 29 |
| A/B employer names | 8 | 9 |
| A/B with fresh verified application evidence | 28 | 29 |
| A / B grade split | 8 / 20 | 8 / 21 |
| Employers represented in top 20 | 8 | 9 |
| knowmad mood postings in top 20 | 10 | 9 |
| Exact duplicate URLs per profile | 0 | 0 |
| Secondary-profile records | 156 | 156 |
| Records across both profiles | 774 | 775 |

Final A/B distribution: knowmad mood 16; eXperience 3; Talan, The White Team and
Talent Connect two each; T-Systems Iberia, SNGULAR, GHCG and Signicat one each.
Final market grades: A8, B21, C112, D419, U44. The remaining ten-employer target
is not achieved, and five–ten useful discoveries per month cannot be established
from this snapshot.

| Controlled Signicat run | Fetched | Created | Updated | Rejected | Error |
| --- | ---: | ---: | ---: | ---: | --- |
| First | 1 | 1 | 0 | 0 | None |
| Repeat after verification | 1 | 0 | 1 | 0 | None |

Repeat ingestion preserved B76, the checked form evidence, source identity and
provenance. Seven RSS items were screened; the other countries were filtered out.

## Release, validation and preservation

- Feature commit [a09cc20](https://github.com/Gabrielvcg/JobRadar/commit/a09cc2015d1df138689fe32859f148bd6b7eed2a).
- Local Ruff/Mypy successful; 285 tests passed and three PostgreSQL tests skipped.
- [Exact-revision CI](https://github.com/Gabrielvcg/JobRadar/actions/runs/40001275810)
  successful before deployment: **288 tests**, PostgreSQL, Ruff, Mypy, Docker.
- [Dependency security](https://github.com/Gabrielvcg/JobRadar/actions/runs/40001275805)
  successful on the exact feature revision before deployment.
- Production backup `jobradar_20261023T181237Z.sql.gz` completed; gzip integrity
  verified. No old backup was deleted. This was not a restore drill.
- Built from the committed Git archive, SHA-256
  `99067e9837061435801680e59aaade657a82e8de752a734e6d028d0475942fac`.
  Unrelated local modifications and private configuration were excluded.
- Image `jobradar:0.1.51-a09cc20`. Public/private preflights ran with networking
  disabled. Every private file outside `sources.yml` is byte-identical; existing
  source settings are semantically identical. Only Signicat was added to the
  candidate profile, preserving GHCG and all prior sources.
- App-only deployment under the ingestion lock. Health confirms 0.1.51 and exact
  revision `a09cc2015d1df138689fe32859f148bd6b7eed2a`. Existing DB remained running.
- Authentication 303, dashboard 200, filtered Signicat API 200 with one result,
  full CSV 200, anonymous CSV 401. Dashboard includes Signicat; export has
  **619 rows, 36 columns**, complete descriptions and the B assessment.
- All **774 original IDs and statuses** preserved; user/password/role fingerprints
  and user job-state fingerprint unchanged. Both profiles remain present.
- Secondary profile's 156 records retain full description/requirements/score/status
  SHA-256 `80288e0e1ffd6538a8ee9865c8992f0da0a016693832822f2a31529ae15ea046`.
- Final source errors: none. New app's ten-minute log has zero ERROR, CRITICAL or
  Traceback entries. App and database report healthy.

Rollback retains the prior image `jobradar:0.1.50-e601e01`, runtime-config symlink
target, environment and Compose copies under this release's rollback directory.
Rollback was prepared, not executed. No other VPS application was changed.

## Research, limitations and next useful work

[Research inventory and candidate-preparation checkpoint](../research/employer-coverage-2026-10-23-signicat.md)
records Signicat and twelve additional directly inspected employers, plus the
Nunegal follow-up. Search-only leads are not counted as reviewed companies.
Research continued after Signicat was found: Marfeel's live Java vacancy has a
rendered CV form but needs explicit hiring-country/seniority clarification;
Vermont's current junior/analyst ads have blocked official collection. Rawson,
Altia, Coremain, Izertis and Laberit did not establish another current compatible
A/B vacancy in the inspected interfaces. No custom collector, country injection,
role renaming or global scoring relaxation was used to produce a tenth employer.

A known coverage limitation remains: Marfeel's optional full-remote/hybrid wording
is interpreted as hybrid by the current normalizer, and country eligibility is
not explicit in its structured job data. It is a manual follow-up, not a verified
recommendation or a reason to bypass source acceptance checks. Keapps' integration
role similarly requires careful reconciliation of metadata with its actual
Sevilla option and contradictory salary bands.

The three preparation priorities supported by these vacancies are: tested Spring
APIs with SQL/security; reliable asynchronous integrations with reproducible
failure/recovery; and an AWS deployment explained in English while distinguishing
personal projects from paid experience. These are examples to demonstrate, not
claims that Gabriel has already proved every required competency.

The delivery branch was confirmed publicly **30 commits ahead / zero behind main**
after the feature commit. Exact-commit deployment remains the established route;
Gabriel's intention to keep main behind is not inferred. Recommendation: review a
complete comparison/PR for integration to main, keep unrelated working-tree work
separate, and merge only with explicit authorization. This delivery performs no
PR creation, merge or shared-base push.
