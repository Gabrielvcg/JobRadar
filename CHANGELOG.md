# Changelog

## 0.1.34 - 2026-08-10

- Repaired corrupted UTF-8 text in source filters, scoring expressions, and public documentation so accented Spanish and Portuguese terms match correctly and render professionally.

## 0.1.33 - 2026-07-04

- Added disability-focused Engineering sources for Tecnoempleo, Page Personnel, Por Talento/Inserta, and Fundacion Randstad, with strict technical filters for backend, DevOps, systems, data, and cybersecurity roles.
- Normalized abbreviated Page Personnel annual salary ranges such as `EUR28 - EUR40 por año` into realistic thousand-based EUR ranges before scoring and display.
- Expanded Engineering scoring signals for Spanish cybersecurity, SIEM/SOAR/WAF/EDR, infrastructure, systems, and data roles so disability-focused technical offers are not rejected as non-backend noise.

## 0.1.32 - 2026-07-04

- Added a Fundación Adecco disability IT source for Engineering's Java/backend/cloud/AppSec profile, with detail enrichment and strict filters that reject support, sales, and administrative disability offers.
- Added disability-focused Engineering search terms and a visible positive scoring reason for technical offers aimed at people with a disability certificate.

## 0.1.31 - 2026-07-04

- Hardened Operations's unsupported-language scoring penalty to catch mojibake or accent variants of French/German requirements that were still visible after rescoring.

## 0.1.30 - 2026-07-03

- Added a strong Operations scoring penalty for unsupported French/German language requirements and disability-certificate requirements, so older stored offers with those constraints drop out of the normal visible view after rescoring.

## 0.1.29 - 2026-07-03

- Disabled Operations's Talent.com source in production configuration after the VPS returned repeated 403 responses, keeping the adapter and compliance notes available for future reactivation.

## 0.1.28 - 2026-07-03

- Added Talent.com and Bizneo-powered Faster, IMAN, and Grupo Crit sources for Operations's administrative/accounting/customer-support searches in Sevilla and Almeria, using fixed public listing pages with strict role, language, duplicate-aggregator, and location filters.
- Expanded Operations's JobToday coverage with additional administrative, customer-service, and receptionist pages that respond with structured public data.
- Documented source compliance for Talent.com and Bizneo-powered portals, and left Manpower disabled because its robots policy blocks generic crawling.

## 0.1.27 - 2026-07-03

- Added a Eurofirms source for Operations's Sevilla and Almeria administrative/customer-service searches, using fixed public listing pages with strict filters for location, language, and role quality.
- Documented Eurofirms source compliance and added parser/filter tests for the new adapter.

## 0.1.26 - 2026-07-03

- Added a curated JobToday source for Operations's administrative/accounting searches in Sevilla and Almeria, limited to internal JobToday postings with stable URLs and structured salary/location data.
- Added a Page Personnel source for Operations's Sevilla accounting and administrative searches, ignoring recommended off-location cards and filtering out senior/responsibility roles.
- Documented JobToday and Page Personnel source compliance and added parser/filter tests for both adapters.

## 0.1.25 - 2026-07-03

- Added a fixed public Trabajos.com source for Operations's accounting and purchasing searches in Sevilla and Almeria, after checking that the selected category pages provide a few high-signal administrative offers without broad noisy search paths.
- Added a strong Operations penalty and source exclusions for Portuguese-language requirements and Portuguese job text, keeping visible offers limited to Spanish or English language expectations.
- Added tests for Trabajos.com parsing/filtering and the Operations Portuguese-language rejection path.

## 0.1.24 - 2026-07-03

- Raised the Operations Infoempleo ingestion threshold and strengthened the penalty for offers requiring more than five years of experience, so high-experience administrative roles no longer appear in the normal review view.

## 0.1.23 - 2026-07-03

- Added a public Domestiko source for Operations's administration and secretarial searches in Sevilla and Almeria, using structured `JobPosting` data from public offer pages.
- Expanded Operations's Infoempleo coverage with receptionist pages after testing that they add compatible office/reception offers without broad noisy search paths.
- Kept Randstad, Adecco, Eurofirms, and Empleate out of automated ingestion for now after checks showed blocking, unreliable filtering, non-indexable entry pages, or insufficient parseable offer data.

## 0.1.22 - 2026-07-03

- Added a fixed public Infoempleo source for Operations's Sevilla and Almeria administrative/accounting searches, so the profile has real visible offers even when Adzuna credentials are not configured.
- Added local filtering for Infoempleo role fit, target locations, course/opposition noise, and night-shift noise while preserving source offer links.
- Improved coverage for Spanish experience text such as `2 años` so required experience remains visible on job cards.

## 0.1.21 - 2026-07-02

- Added profile tabs with `profile_key` separation for sources and offers, so new career profiles do not pollute the default backend/AppSec profile.
- Added an Operations administrative/accounting profile for Sevilla and Almeria with dedicated search terms, scoring messages, salary thresholds, and fixture coverage.
- Added an official Adzuna API adapter for profile-specific searches, including safe no-credentials behavior and VPS environment wiring.
- Added API, CLI, export, source listing, and stats filtering by profile.

## 0.1.20 - 2026-07-02

- Deduplicated curated ATS multi-location variants when the same company publishes the same title with highly similar descriptions across separate job IDs.
- Preferred broader compatible locations such as Spain, Europe, EMEA, or worldwide remote when collapsing duplicated ATS variants.
- Added source tests covering PandaDoc-style multi-location duplicates while preserving same-title jobs with genuinely different descriptions.

## 0.1.19 - 2026-07-02

- Expanded curated Greenhouse, Lever, and Ashby company feeds with higher-signal Java/AppSec/DevSecOps candidates such as PandaDoc, Nebius, Swapcard, Oneleet, and Owkin.
- Improved salary extraction and scoring for PLN, CZK, SEK, DKK, NOK, CHF, ILS, RSD, and HUF by converting comparable salaries to EUR before applying salary thresholds.
- Reduced false salary matches from funding amounts, small monthly allowances, URL paths, dates, benefit day counts, and non-salary `k` counters.
- Treated AppSec, DevSecOps, product security, and cloud security as valid profile variations while keeping generic OWASP-only backend roles, QA automation, and risk-management roles from ranking too highly.
- Added precise `US/EU Remote` location matching for compatible remote jobs without broad `UK` or `EU` substring matching.

## 0.1.18 - 2026-07-01

- Added a curated Personio XML source for selected Java/Spring/Kotlin company feeds in Spain, Europe, and compatible remote locations.
- Added Personio source attribution and compliance notes for the documented public XML integration.
- Rechecked Comeet/Spark Hire Recruit, Breezy, JazzHR, and Workday; skipped them for now because they either require credentials/tokens, expose only non-curated global feeds, or lack an official public third-party job API.

## 0.1.17 - 2026-07-01

- Added curated Recruitee and Pinpoint public ATS sources for selected Java/Spring/Kotlin roles in Spain, Europe, and compatible remote locations.
- Made requested years of experience visible as a first-class job-card field while keeping experience-related scoring reasons in the explanations.
- Improved experience range parsing for typographic dashes such as `3–5 years`.
- Reduced false salary and role penalties from location text such as `Europe`, postal codes, recruiter boilerplate, production support, and level words outside job titles.

## 0.1.16 - 2026-07-01

- Added curated Ashby and Workable public ATS sources with strict Java/Spring/Kotlin and Spain/Europe/remote filtering.
- Added Ashby and Workable source attribution links and compliance notes.
- Kept Greenhouse candidate expansion out of configuration after testing showed no additional jobs clearing the current quality threshold.

## 0.1.15 - 2026-06-30

- Hid original salary text in the web UI when it is equivalent to the normalized range despite source-specific notation such as dotted `K` amounts.

## 0.1.14 - 2026-06-30

- Fixed salary extraction for dotted `K` amounts and mixed ranges such as `25.000K - 33.000 EUR` and `30 - 35k EUR` so they no longer become millions or partial ranges.

## 0.1.13 - 2026-06-30

- Added curated Greenhouse and Lever ATS sources for selected technology companies with official public job APIs and local Java/Spain/Europe filters.
- Improved salary display so annual ranges use grouped numbers and duplicate original salary text is hidden when it repeats the normalized value.
- Documented Greenhouse and Lever source compliance.

## 0.1.12 - 2026-06-30

- Added ingestion diagnostics for source-level scope and score rejections so production logs explain why public sources produce few stored jobs.
- Rechecked additional public job feeds and skipped sources whose filters or feeds cannot reliably target Java roles available from Spain or Europe.

## 0.1.11 - 2026-06-30

- Normalized long Himalayas European location restrictions to `Europe` in the country field so production ingestion cannot exceed database country length limits.

## 0.1.10 - 2026-06-30

- Added Himalayas public API ingestion with Java/Spring/Kotlin searches for Spain and worldwide remote roles.
- Added Himalayas source tests covering salary, location, publication dates, and trainer exclusions.
- Documented Himalayas source compliance and attribution.

## 0.1.9 - 2026-06-30

- Penalized non-Java backend/cloud roles unless they have a clear AppSec/security focus, so legacy .NET/Go-style matches no longer dominate the default dashboard.
- Kept Java/Spring/JVM and AppSec exceptions explicit in scoring configuration.
- Fixed VPS cron backup installation so `APP_DIR` is exported before `flock` executes the backup script.

## 0.1.8 - 2026-06-27

- Refocused real-source ingestion on Java/Spring/JVM matches so generic backend, cloud, or JavaScript roles no longer count as Java.
- Added Java-tagged Jobicy requests and extra We Work Remotely RSS feeds for full-stack, back-end, and DevOps categories.
- Parsed We Work Remotely RSS skills and country metadata to improve technology and location matching.
- Split senior scoring from lead/manager scoring so senior Java roles remain visible but penalized.

## 0.1.7 - 2026-06-27

- Added Jobicy API and We Work Remotely RSS ingestion for remote programming, DevOps, cloud, and AppSec candidates.
- Improved remote scope filtering so worldwide and EU-country remote offers are accepted while non-remote EU offers stay out.
- Lowered the default dashboard threshold to 35 points while keeping a 50+ quick filter for stronger matches.
- Added source tests covering Jobicy/RSS mapping, region handling, and senior/manager/business-development exclusions.

## 0.1.6 - 2026-06-27

- Tightened ingestion quality gates with language, target-location, and minimum-score filters so German/local and non-technical offers are not stored.
- Expanded source scanning limits while keeping low-quality public API results out of the database.
- Reworked the web UI from a wide table into responsive offer cards and changed dashboard stats to reflect visible filtered offers.

## 0.1.5 - 2026-06-27

- Hardened public VPS deployment with required session secrets, secure cookies over HTTPS, and public registration disabled by default.
- Added a VPS user creation script that generates strong temporary passwords without committing secrets.
- Strengthened password validation for UI and CLI account creation and documented the SSL/user setup flow.

## 0.1.4 - 2026-06-27

- Added Remote OK as a remote-job API source with strict source-level filtering for realistic backend/cloud matches.
- Added Remote OK attribution in the web UI and source compliance notes.
- Added tests covering Remote OK salary mapping and senior/location filtering.

## 0.1.3 - 2026-06-27

- Added Remotive as a remote-job API source, stricter source-level affinity filters, and source refresh intervals.
- Updated the web UI to default to viable matches and provide quick links to show all offers and source attribution.
- Improved salary extraction so USD, GBP, and EUR ranges keep their original currency labels.

## 0.1.2 - 2026-06-27

- Added email/password users with signed session cookies and per-user job statuses.
- Added published salary/rate filtering and CSV status export scoped to the signed-in user.
- Tightened scoring so senior, lead, and high-experience roles are penalized more realistically for a junior Java/React profile.
- Disabled fixture ingestion in production so the VPS focuses on configured real sources.

## 0.1.1 - 2026-06-27

- Added VPS deployment artifacts with production Docker Compose, Nginx config, cron-based ingestion every 30 minutes, daily PostgreSQL backups, and a GitHub Actions deploy workflow.
- Added production memory limits and a VPS health check script that validates API health, Compose service state, and container memory usage.
- Added user-level cron installation and a no-pull deploy mode for VPS users without passwordless sudo or a remote container registry.
- Documented first deploy, GHCR image usage, required secrets, cron operations, and backup/restore commands.

## 0.1.0 - 2026-06-27

- Added the first JobRadar MVP with FastAPI, PostgreSQL, Alembic, Typer CLI, Docker Compose, and CI.
- Implemented job ingestion from local fixtures and the public Arbeitnow API.
- Added deterministic scoring, salary normalization, technology detection, deduplication, status tracking, REST endpoints, and a minimal web UI.
- Documented local setup, source compliance, AWS deployment preparation, and operational commands.
## 0.1.35 - 2026-08-29

- Prepared the repository for public release with generic profile names,
  sanitized demonstration values, repository security guidance, and a license.
- Added ignore rules for runtime environment files, certificates, and private
  key material.
