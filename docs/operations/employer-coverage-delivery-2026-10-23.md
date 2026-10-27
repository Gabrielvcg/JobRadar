# Employer coverage continuation delivery — 23 October 2026

Production [JobRadar](https://jobradar.vacaro.es) now runs **0.1.49**, revision
`56fb9005d154c260e47398e510d3ef78b06f1278`.

The [new research report](../research/employer-coverage-2026-10-23.md) and
[structured inventory](../research/employer-coverage-2026-10-23.json) add fifteen
named employers and one employer-unconfirmed portal to the investigation. Together
with the previous report, 64 named employers have been researched. None of the
newly reviewed boards established an additional current, verified A/B employer.
No source or private profile settings were added or modified during this round.

## Results, with scheduled activity separated

| Metric | Start, 0.1.48 at 13:58 UTC | Immediately before deploy, 0.1.48 | Final, 0.1.49 at 15:09 UTC |
| --- | ---: | ---: | ---: |
| Candidate records, including 15 disabled synthetic records | 609 | 616 | 616 |
| Market records / distinct canonical URLs | 594 | 601 | 601 |
| Distinct market employer names | 191 | 191 | 191 |
| A/B records | 26 | 28 | 27 |
| Verified A/B application paths | 26 | 28 | 27 |
| Employers with current A/B | 7 | 7 | 7 |
| knowmad mood entries in current top 20 | 11 | 11 | 11 |
| Duplicate exact URLs within a profile | 0 | 0 | 0 |
| Secondary profile records | 156 | 156 | 156 |
| All-profile records | 765 | 772 | 772 |

Eight records had already arrived through scheduled ingestion since the preceding
601-record delivery and before this continuation started. Another seven arrived
through the existing scheduled collector during this research round, all under
knowmad mood: three C references, two U records, one B, and one initially incorrect
A. These are attributed to the existing scheduler, not to newly integrated boards.
The net current A/B gain is one B, without employer diversification.

Record/URL uniqueness does not prove distinct headcount or unique underlying
client projects. No unsupported cross-agency/process merge was performed. Original
URLs and provenance remain intact. Neither the ten-employer goal nor a monthly
discovery rate has been established.

## New current lead and corrected false positive

Both application paths below were freshly checked against the official pages on
**2026-10-23 at 15:07 UTC**. Both have an accessible job-specific candidate upload
form. No form was submitted and no employer was contacted.

| Official advertisement | Experience / conditions | Final result |
| --- | --- | --- |
| [knowmad mood — Software Developer Java, AWS, Terraform](https://knowmadmood.teamtailor.com/jobs/8608918-software-developer-java-aws-terraform-remoto) | Remote Spain; numeric minimum and salary not published. Java/Spring microservices, actual AWS deployments, Terraform, SQL/NoSQL, messaging and CI/CD. AWS/Terraform professional practice needs confirmation; certification/projects are not paid cloud employment. | **B / 64**, verified public upload form. Ambitious lead, not a guarantee that specialist experience or salary requirements are met. |
| [knowmad mood — Application Support Engineer, Java](https://knowmadmood.teamtailor.com/jobs/8594415-ingeniero-a-de-soporte-de-aplicaciones-java-remoto) | Remote Spain; explicitly primarily operations and support, production monitoring/incidents and small corrective Java changes. Numeric minimum and salary absent. | Corrected **A / 72 → D / 19**, blocker `career_direction_mismatch`, despite an accessible upload form. |

The focused correction recognizes an explicit declaration of primarily operational
work before incidental Java fixes determine work focus. It retains evidence of
both kinds of work. Existing alignment points, weights, grade thresholds, salary,
geography and paid-cloud rules remain unchanged. A regression is grounded in this
new advertisement, with controls for negated operational focus and backend work
with occasional support. This is not a general scoring redesign.

After refreshing expired verification evidence, the original 616 candidate
recommendations immediately before deployment differ in exactly this one A-to-D
record. Three older closed-listing proofs had expired and temporarily became U
during full rescoring; fresh checks reconfirmed all three closures. They were not
counted as discoveries or promotions. All original job IDs/employment statuses and
user/account state fingerprints were preserved.

## Manual leads and exclusions

- [cleversoft Java Engineer](https://www.clever-soft.com/careers/java-engineer-2/): RegTech product work with Seville listed. Indexed corporate text says 1–5 years, while another employer publication asks five years. Direct automated access returns 403. Salary and current application form remain unverified. This is a manual lead, not an A/B increment.
- [Grupo Data Java Backend & AI](https://grupo-data.careers-page.com/jobs/69874257-e39b-4d09-80ab-7bac8bec852b): live body explicitly allows PT or ESP and asks three years; Node.js/JavaScript also appear in requirements. Structured country metadata says Portugal. The job-specific application route returns 200 but its input fields are JavaScript-rendered and were not independently confirmed. Salary/contract/specialist fit remain uncertain. Keep U/manual status outside the verified A/B totals.
- The Bizneo tenant branded Plexus explicitly describes a blind application in its observed privacy notice. An upload form does not prove an identified Plexus Tech employer; no allowlist or source was added.
- Clarity AI's promising junior Java URL is removed. SCI's current 14-record Teamtailor feed has no Java vacancy despite old search results. Imatia's index says A Coruña/hybrid; generic telework benefits do not establish remote Spain. Full findings and access/interface limitations are in the research report.

The remaining checked sources did not justify another scheduled connector: removed
vacancies, access restrictions, uncertain employer identity or Spain eligibility,
seniority, or insufficient role evidence. No access block or CAPTCHA was bypassed.
No new dependencies, architecture, frontend redesign or artificial records were
introduced to reach a target count.

## Release and runtime evidence

- Feature commit [56fb900](https://github.com/Gabrielvcg/JobRadar/commit/56fb9005d154c260e47398e510d3ef78b06f1278).
- [CI 39974922760](https://github.com/Gabrielvcg/JobRadar/actions/runs/39974922760): successful Ruff, Mypy, **283 tests with PostgreSQL**, and Docker build. Local checks passed with 280 tests and three PostgreSQL-only tests skipped; those ran in CI.
- [Dependency security 39974922810](https://github.com/Gabrielvcg/JobRadar/actions/runs/39974922810): successful.
- Production image built from the committed Git archive, SHA-256 `0ae80da651dab8478280eb625a339900f602a79b30078d4ec43a38e926ab546b`; unrelated working-tree changes and private files excluded.
- Backup before deployment: `jobradar_20261023T150410Z.sql.gz`, approximately 3.1 MiB; `gzip -t` successful. This was an archive-integrity check, not a restore drill.
- Rollback retained the 0.1.48 image, previous runtime-config symlink target, environment and Compose copies. Only the JobRadar application container was recreated.
- Every runtime profile, scoring, search and source config file was checked byte-for-byte identical across the 0.1.48 and 0.1.49 release directories.
- Health confirms `ok`, exact version/revision; login 303, authenticated dashboard 200 and anonymous CSV export 401. The refreshed all-offers CSV contains **616 rows and 36 columns**, including stored descriptions, requirements, classifications and application evidence.
- Two controlled `knowmad_official` ingestion cycles each fetched 62 affinity-selected jobs, updated 49, rejected 13 by score, created **zero**, and reported no errors. The corrected D recommendation remained D after both cycles. No duplicate exact URLs appeared.
- Both profiles preserved. Secondary profile: 156 records with identical content/score/status fingerprint before/after. Original 772 IDs/statuses, account/password-hash/role and user-state fingerprints preserved. Final enabled sources report no errors.

Private runtime evidence and the CSV remain outside the repository. The user export
is `build/exports/jobradar-todas-ofertas-2026-10-23.csv` in the local workspace.
