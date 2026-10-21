# Career radar review — 2026-10-21

## Scope and baseline

Local, unpublished changes only. No production requests, database connections,
deployments, commits, pushes, secrets changes, infrastructure changes, or security
audit were performed. Existing local source, deployment, backup, and documentation
work was preserved. The repository already had FastAPI/Jinja, SQLAlchemy/PostgreSQL,
separate Engineering/Operations profiles, normalization, explanation lists, status
tracking, URL/content deduplication, and Greenhouse, Lever, Ashby, Workable,
Recruitee, Pinpoint, and Personio adapters. These were reused.

Initial checks: 127 passed, 1 PostgreSQL test skipped; mypy passed. Repository-wide
Ruff already reported an unsorted import in the pre-existing, untracked
`scripts/verify-deploy-workflow-syntax.py`; it was left unchanged.

The main problems were fixed experience bands using the upper end of a range,
technology accumulation detached from actual duties, static salary thresholds,
overly broad remote eligibility, and senior roles sharing the application ranking.
Descriptions lost list boundaries; escaped HTML could survive as markup. Broad
career-transition rules accepted technical operations without development evidence.

Priority order was ranking precision, automatic career evolution, explainability,
freshness and location, then a small source expansion. No infrastructure or database
schema redesign was needed.

## Implemented behavior

- Professional tenure starts at August 2025, at month precision: 14 months in
  October 2026, 24 in August 2027, 36 in August 2028, 60 in August 2030. The exact
  first employment day was not supplied. Credentials, education, Kubernetes
  familiarity, and personal cloud/IaC projects never add employment time.
- Fit, growth, and viability are each 0–100. The global heuristic weights are
  65%/10%/25%; eliminating conditions and experience-gap caps take precedence.
  These are prioritization rules, not measured hiring/interview probabilities.
- Category A covers the Java/backend application path; B requires evidence of
  development in an adjacent cloud/platform/security role; C holds senior,
  architecture, or clearly advanced duties. Current, strategic, and excluded are
  separate views. Time alone never makes a senior title a demonstrated fit.
- Experience evidence carries its original clause and mandatory/desirable/
  indicative classification. The lower bound of a range is used. Desirable years
  do not exclude candidates. No stated experience remains uncertain. Three years
  is a stretch, not an automatic rejection; larger gaps reduce priority as tenure
  evolves. More than `max(5, professional_years + 2)` becomes strategic.
- Cloud growth requires relevant development/design/automation duties. Java in
  a broad language list does not make unrelated coding work a Java backend job.
  Unknown optional technology does not automatically exclude an offer. Mandatory
  distant stacks and unsupported required languages are explained.
- EUR 24,000 is the change minimum; EUR 26,000–35,000 is preferred, with higher
  realistic salaries welcome. Unknown salary remains eligible. An overlapping
  range requires confirmation. Foreign currencies and hourly/daily rates remain
  published but not comparable for this policy; no unverifiable fixed FX rate or
  market salary estimate is used. No salary estimates are produced in this release.
- Spain remote, Europe remote, worldwide remote, and country-restricted remote
  remain distinct. Europe/worldwide require eligibility confirmation. Mandatory
  presence outside Sevilla is incompatible; no relocation is assumed. Onsite
  interviews do not invalidate a remote job, while real office attendance does.
- Expiration excludes current applications. Old/undated/future publication dates
  carry freshness reductions or uncertainty. The existing ingestion schedule
  refreshes stored Engineering assessments once per day or after config changes,
  including offers no longer returned by a feed. Status is preserved.
- Existing JSON explanation columns store the structured assessment alongside
  `positive`. `career_assessment` is additive in API responses; existing fields
  remain. Filtering occurs in the repository before pagination. The CLI list,
  dashboard, API list, stats and CSV export support radar selection. Operations
  retains its scoring policy. Tracking URL cleanup keeps identity parameters.

## Public source verification

Only bounded public GET reads were used. Six existing adapters responded:
Himalayas 5, Jobicy 0, WWR 0, Remotive 1, RemoteOK 1, Arbeitnow 7 returned records
after their existing adapter filters. Each was limited to one request/page where
applicable; this is not a full ingestion or a source-wide coverage measurement.

Official ATS probes returned Elastic 371, Datadog 437, Cabify 66, Celonis 215,
Binance 17, Swapcard 3, rindus 11 and Pasiona 37 raw records. Together with the
14 portal records, this produced the fixed 1,171-record comparison pool. Cabify,
Celonis, rindus and Pasiona were investigated but not added: this sample provided
no current compatible application under the new policy. Existing sources were
not disabled on the basis of a single sparse sample.

Greenhouse, Lever and Personio already cover these feed types. Their documented
interfaces were checked against [Greenhouse Job Board API](https://docs.greenhouse.io/job-board),
[Lever Postings API](https://github.com/lever/postings-api), and
[Personio open positions](https://developer.personio.de/docs/retrieving-open-job-positions).

One adapter was justified: the documented [SmartRecruiters public Posting API](https://developers.smartrecruiters.com/docs/endpoints).
The added employer is [T-Systems Iberia](https://careers.smartrecruiters.com/T-SystemsIberia).

| Evaluation | Observed result / control |
| --- | --- |
| Java relevance | Java/Spain query returned 10 listings; 7 matched local Java filters |
| Geography | One current backend role explicitly includes Sevilla; two strategic references also include it |
| Data quality | Structured location/mode, publication date, duties and qualifications; salary/years can remain unknown |
| Updates | Published active vacancies and release dates; configured polling every 12 hours, not a measured update guarantee |
| Duplicates | Stable employer/posting IDs; existing ATS variant and repository deduplication reused |
| Reliability | Public endpoints returned HTTP 200 during this check; no uptime claim |
| Complexity | One adapter, one employer, one page, at most 20 details; timeouts, rate limits and bounded retries |
| Access | Documented public GET endpoints, no credentials or applications submitted; no bypass of access restrictions |

A separate SmartRecruiters probe returned 16 Java-filtered records across T-Systems
and Sopra Steria. Only T-Systems is enabled. Sopra's sample mainly required French,
other office locations, or substantially more experience; its additional value was
insufficient for this bounded change. This is a screening decision, not a blanket
judgment about consulting employers.

## Fixed-pool before/after comparison

The comparison is **scoring plus shared search-scope filtering on the same raw
candidate pool**, using a 35-point review gate and 2026-10-21 evaluation date.
Official ATS data was deliberately evaluated before company/adapter affinity and
variant filters. Consequently, these are diagnostic pool counts, **not historical
database, full ingestion, deployment, or production dashboard totals**. In
particular, some old high-scoring sales/architect rows would have been removed by
the existing adapter filters. No hiring probability or recall estimate follows
from this small, geographically biased sample.

| Metric | Before | After |
| --- | ---: | ---: |
| Raw candidate records obtained | 1,171 | Same 1,171 |
| Search scope + score >=35, mixed ranking / current applications | 66 | 2 |
| Strategic references kept separately | No separate view | 9 |
| Outside the old gate / explicitly excluded by new policy | 1,105 | 1,160 |
| Java token present among current-gate records | 53 / 66 | 2 / 2 |
| Stated minimum 0–3 years among current-gate records | 4 | 1 (the other is unstated) |
| Mean score of current-gate records | 56.76 | 73.00 |
| Score buckets of current-gate records: 35–49 / 50–64 / 65–79 / 80–100 | 19 / 37 / 10 / 0 | 0 / 0 / 2 / 0 |
| Exact URL duplicate excess in raw pool | 0 | 0 |
| Normalized content duplicate excess identified in raw pool | 1 | 2 |

Of the 66 old-gate records, the new location assessment labels 52 incompatible,
11 compatible and 3 uncertain. Across the full pool, blocker counts overlap:
role mismatch 1,104, incompatible location 1,134, required unsupported language 72,
mandatory distant stack 5, operations-only 1. No record is added or removed from
the raw pool by this evaluator; duplicate counts describe detection, not database
deletions. Real deduplication/status preservation is checked separately in tests.

The enabled T-Systems addition is outside that fixed-pool comparison: seven
Java-filtered records provide **one additional current application**, two strategic
references and four exclusions. It is not counted as an improvement to the fixed
pool's retrieval volume. The result is three current offers across these limited
probes, not a claim of 30 available or validated jobs.

## Manual review and ranking examples

Reviewed the old top 15 assessments and the current/strategic shortlist against
description evidence. The review found and corrected unrelated AI-task work,
company-age experience, required French, and onsite-interview confusion. Evidence
remains heuristic; publication, eligibility and salary require employer confirmation.

| Example | Before → after | Why it deserves the new treatment |
| --- | --- | --- |
| [Softtek — Software Engineer Fullstack](https://himalayas.app/companies/softtek/jobs/software-engineer-fullstack) | 75 → 77; mixed rank 3 → current rank 1 | Java/Spring/backend duties, Spain remote; explicitly requires 3 years and Angular; salary unknown, so a stretch application |
| [knowmad mood — Java/JSP/Thymeleaf](https://himalayas.app/companies/knowmad-mood/jobs/full-stack-developer-java-jsp-thymeleaf-remoto) | 62 → 69; mixed rank 15 → current rank 2 | Actual Java/Spring/API work and optional office attendance; experience and salary unstated, frontend duties need confirmation |
| Askable — Software Engineer, AI Coding Tasks | 72 → 34, excluded | Paid AI evaluation tasks and a language list do not establish the requested backend career path |
| Celonis — Senior Backend Java, Munich | 68 → 34, excluded | Technical relevance does not establish ability to work from Sevilla |
| T-Systems — Backend Java | New source; 65, current | Sevilla explicitly offered; no candidate-years minimum stated; company longevity is not candidate experience; salary unknown |

The new [T-Systems vacancy](https://jobs.smartrecruiters.com/T-SystemsIberia/744000153460609-desarrollador-a-backend-java-m-f-d-)
is an example to investigate, not a verified salary increase or guaranteed junior role.

## Validation and reproducibility

- Final suite: **172 passed, 1 PostgreSQL-specific integration test skipped**.
- `mypy app tests`: passed, 73 source files.
- `ruff check app tests scripts/evaluate-career-radar.py`: passed.
- Repository-wide Ruff retains the same pre-existing import-order failure noted
  above. TestClient emits one dependency deprecation warning; no new dependency
  was installed to suppress it.
- Portable SQLite tests exercise persistence, JSON filters before pagination,
  daily refresh idempotence, status preservation, cross-source canonical URL
  deduplication, HTTP responses and dashboard rendering. They do not prove
  PostgreSQL JSONB behavior or migration/runtime behavior on the VPS.
- SmartRecruiters transport tests cover query parameters, request bounds,
  structured mapping, inactive-offer filtering and omission of creator metadata.
- No production verification was performed. Docker's local engine and a
  PostgreSQL test URL were unavailable; no service was started or installed.

Read-only offline evaluation:

```powershell
.\.venv\Scripts\python.exe scripts/evaluate-career-radar.py <raw-job-sample.json> --as-of 2026-10-21 --output <local-report.json>
```

The input is a JSON array of `RawJob` fields with ISO dates. The evaluator never
fetches HTTP data or opens a database session. Local snapshots, baseline source/config
copies, public sample, probe results, and comparison JSON are in ignored
`build/radar-review/`. They are local evidence, not files to publish. The
working-tree evaluator and synthetic tests permit future controlled evaluation.

After an explicitly authorized rollout, run `score-all` in the intended environment
or let the ingestion schedule refresh stored Engineering assessments. Until that
refresh, unassessed legacy records are available with `radar=all`. No such rollout
or production command is authorized or executed by this work.

## Limits and next priorities

1. **Benefit high, effort low–medium:** curate more Spain-compatible Java employers
   using the existing ATS adapters; enable each only after proving incremental
   current-role value. The current sample is too small to estimate market coverage.
2. **Benefit high, effort medium:** use a larger reviewed corpus and an authorized
   isolated PostgreSQL snapshot to measure actual ingestion acceptance/rejection,
   pagination, duplicate provenance and ranking quality end to end.
3. **Benefit medium, effort medium:** improve clause/section interpretation and
   explicit requirement evidence, especially language alternatives, part-time/gig
   terms and cross-portal paraphrases. Exact URL/content deduplication does not
   reliably identify every reworded or mirrored vacancy.

Other limits: absent salaries are not estimated; monthly salary annualization
retains the existing 12-payment convention; foreign currencies/rates need a dated,
verifiable conversion source before comparison. Exact employment start day,
formal master's completion, employer hiring eligibility and unstated job
requirements remain unknown. No statistical hiring probability is produced.
