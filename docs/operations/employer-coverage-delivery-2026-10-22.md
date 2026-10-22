# Employer coverage delivery — 22 October 2026

Production: [JobRadar](https://jobradar.vacaro.es), version **0.1.48**, revision
`22c0b085d781319d3624bd052f1c24487904e031`.

[Research inventory](../research/employer-coverage-2026-10-22.md) and
[structured inventory](../research/employer-coverage-2026-10-22.json) cover 49
employers, including the two accepted integrations. Additional search-only leads
are explicitly separated. No scoring weights, thresholds or personal profile
settings changed.

## Actual new current opportunities

These four rows were absent from the baseline. Each official vacancy and its
candidate form was checked in production on **2026-10-22**, between 20:13 and
20:17 UTC. Evidence is anonymous GET access, not an application submission or
guarantee of headcount, response, hiring, salary offer or contractual eligibility.

| Employer / official vacancy | Location / mode | Experience / technical caveats | Published salary | Application grade / evidence |
| --- | --- | --- | --- | --- |
| [SNGULAR — Java Developer](https://www.sngular.com/es/talento-y-cultura/jobs/77/java-developer-remoto-en-espana-1) | Spain; vacancy metadata says 100% remote. General benefits reserve client-specific partial attendance, so confirm the actual assignment. | Numeric minimum absent. Advanced Java/Spring/Kafka, event-driven and hexagonal design, agents and SDD; advanced proficiency is not established merely by familiarity/certification. | Not published; minimum EUR 24k remains unconfirmed. | A / 73 under the unchanged policy; vacancy-bound email/CV form present. Applicant must complete consent and CAPTCHA; submit is validation-gated. Confirm project level before treating this as an easy application. |
| [eXperience — Backend Developer, Java & banking](https://jobs.experienceis.com/jobs/backend-developer-java-banca-remoto) | Spain, remote; Madrid board location. | Minimum 3 years, APIs/microservices and banking integration; Python knowledge required; B2 English. Ambitious with 14 months professional backend experience. | Not published; compatibility unconfirmed. | B / 64; observed public job-specific candidate and CV form accessible. |
| [eXperience — Backend Developer Java, 100% remote](https://jobs.experienceis.com/jobs/backend-developer-java-100-remoto-5e9910e8-3e19-40d5-87c4-98157281a734) | Spain, 100% remote; Madrid board location. | Minimum 4 years; Java/Spring, professional IBM MQ, PostgreSQL, Kafka and container familiarity; B2+/C1. Frontend adjustments are desirable and occasional. MQ/experience/English are meaningful gaps to discuss. | EUR 30,000–50,000 gross/year; upper limit is not guaranteed. | B / 59; observed public job-specific candidate and CV form accessible. |
| [eXperience — Java and REST APIs, ASO/APX](https://jobs.experienceis.com/jobs/desarrollado-a-java-y-api-rest-aso-apx-remoto) | Spain, 100% remote; Madrid board location. | Minimum 3 years; Java REST services, API security, ASO/APX knowledge or experience. Specialist platform fit must be confirmed. | EUR 32,000–35,000 gross/year, dependent on experience/knowledge. | B / 64; observed public job-specific candidate and CV form accessible. |

Two additional new eXperience records are **C**, not current applications: Oracle
ADF/JDeveloper (five-year requirement) and Senior Backend Java/Blockchain
(five-year requirement). Their application availability was not promoted to
verified current evidence.

## Before / after

Baseline: 19:19 UTC, 0.1.47. Final snapshot: after deployment, both controlled
ingestions and refreshed expired historical verification, 0.1.48.

| Metric | Before | After | Meaning |
| --- | ---: | ---: | --- |
| Candidate profile records, including disabled synthetic data | 595 | 601 | Exactly six inserted records |
| Market records / distinct canonical URLs | 580 | 586 | URL/record uniqueness, not independently audited global headcount uniqueness |
| Distinct market employers | 187 | 189 | Two actually new employer identities |
| A records | 6 | 7 | One new current A |
| B records | 16 | 19 | Three new current B |
| A/B total | 22 | 26 | Four new current advertised roles |
| Employers with A/B | 5 | 7 | Goal of ten not reached |
| Verified A/B application paths | 22 | 26 | All A/B have fresh public path evidence |
| Verified current paths, including U | 35 | 39 | Four added paths |
| Current radar records | 62 | 66 | Four actual new current records |
| Strategic radar records | 100 | 102 | Two additional C references |
| Excluded candidate records, including synthetic data | 433 | 433 | No historical exclusion was counted as a discovery |
| knowmad mood entries in actual current top 20 | 14 | 11 | 70% to 55%, without artificial employer penalties |
| Distinct employers in actual current top 20 | 5 | 7 | SNGULAR and eXperience add diversity |
| Duplicate exact URLs within a profile | 0 | 0 | Both controlled cycles checked |
| Secondary profile records | 156 | 156 | Full content/score/status fingerprint identical |
| All-profile total | 751 | 757 | All original IDs and employment states preserved |

New source records retain six separate canonical URLs and provenance. The three
current eXperience advertisements have different duties and requirements; there
is insufficient evidence to merge their processes. An undisclosed common client
or shared budget cannot be ruled out. No claim is made that all 586 historical
URLs represent independently verified unique headcount positions. No proven
duplicate process was discarded or silently merged in this execution.

The original 595 candidate recommendations match the baseline after checks.
Seven previously closed listings reached their existing 24-hour evidence expiry
during the release; refreshing those seven public checks reconfirmed all seven
closures. They are neither new offers nor employer growth.

## Controlled ingestion and idempotence

| Source | First fetched | Created | Updated | Score rejected | Repeat fetched | Repeat created | Repeat updated | Repeat rejected |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| experience_official | 11 | 5 | 0 | 6 | 11 | 0 | 5 | 6 |
| sngular_official | 1 | 1 | 0 | 0 | 1 | 0 | 1 | 0 |

Neither cycle reported source errors or scope rejects. “Fetched” counts the
adapter's affinity-selected jobs, not every index card or HTTP request. Bizneo
examined five programming index pages and 27 title-selected details; full Java/
Spring affinity retained 11. Score rejection includes contradictory Madrid office,
incompatible fullstack/location or other non-current-fit cases. The second cycle
preserved the four candidate-form proofs and created zero records. The existing
scheduled ingestion can revisit both sources every twelve hours; this is a
collection schedule, not a guarantee of new vacancies.

## Development and release evidence

- Feature commit: [22c0b08](https://github.com/Gabrielvcg/JobRadar/commit/22c0b085d781319d3624bd052f1c24487904e031).
- [CI 39846372959](https://github.com/Gabrielvcg/JobRadar/actions/runs/39846372959): successful Ruff, Mypy, **279 tests with PostgreSQL**, and Docker build.
- [Dependency security 39846372997](https://github.com/Gabrielvcg/JobRadar/actions/runs/39846372997): successful.
- Local checks: Ruff and Mypy pass; 276 tests pass, three PostgreSQL-only tests skipped locally and exercised successfully in CI. Existing Starlette/httpx deprecation warning remains.
- Production image built from the exact committed Git archive, SHA-256 `bc58c1b34a3ebf3f49e4deda6c36431d528f550293e626d030d7b3dc0b0aaf55`; working-tree/private files excluded.
- Before deployment: database backup `jobradar_20261022T201100Z.sql.gz`, approximately 3 MiB; `gzip -t` successful. This was an archive-integrity check, not a restore drill.
- Rollback retained: 0.1.47 image, previous runtime-config symlink target, private environment and Compose copies. Only the JobRadar application container was recreated; database and unrelated VPS applications were not changed.
- Existing profile/search/scoring and source settings retained; only the two new default-profile source entries added. Secondary Bizneo layout behavior remains opt-in/unchanged.
- Post-deploy `/health`: `ok`, version 0.1.48 and exact feature revision. Login returns 303, authenticated dashboard 200; all-offers export contains **601 rows, 36 columns**, UTF-8 BOM, complete job descriptions/requirements/classifications and application evidence. Anonymous export remains 401.
- Both profiles, original 751 offer IDs/statuses, existing account/password-hash/role fingerprint and user-state fingerprint preserved. Secondary 156-record content/score/status fingerprint is identical before/after. No source errors or duplicate URLs in the final snapshot.

Runtime evidence, database snapshots and the authenticated CSV remain private
local/VPS delivery artifacts rather than repository fixtures. The refreshed CSV is
`build/exports/jobradar-ampliacion-empresas-2026-10-22.csv` in the local workspace.
No application or external contact was sent.

## Limits and stopping decision

Seven A/B employers is a meaningful improvement but below the ten-employer goal.
Only four newly discovered current roles are counted; older records and the two
new C references do not contribute. A monthly discovery rate cannot be established
from this run. Neither new source is a product-company hiring board; the researched
product/international examples were mostly too senior, office-restricted, removed,
blocked or lacked explicit Spain eligibility. Their research is retained for future
rechecks rather than converted into optimistic A/B records.

This delivery completed two useful employer integrations. Further checked options
had poor expected current value or required access workarounds/custom maintenance
without a verified eligible vacancy. Robots/access blocks, missing feeds and sparse
duties remain explicit. Manual leads such as TNG, SOLTEL and SlashMobility are
identified in the inventory with their uncertainties; they are not automatically
counted as verified Java applications. Published salary ranges do not guarantee an
offer; certification/project cloud knowledge never becomes paid cloud experience.
