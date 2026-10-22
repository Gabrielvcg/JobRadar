# Career coverage delivery — 2026-10-22

JobRadar now reads bounded official employer feeds, retains employer provenance and
original dates, and exposes freshly checked application routes. Production is
**0.1.45 / c7c0b750b81d56bd731ef8b52aee37e582e7ebad**. The existing dashboard's
[current, verified filter](https://jobradar.vacaro.es/?radar=current&verified_only=true&min_score=35)
is the most direct shortlist. Verification establishes an application route; fit,
experience, geography and pay remain separate assessments.

## Measured outcome

Snapshots: 09:21 UTC before the first deployment; 14:27 UTC after final validation.
Earlier 08:49 counts were identical. All counts below refer to the candidate
profile except the total across both profiles.

| Measure | 0.1.41 | 0.1.45 |
| --- | ---: | ---: |
| Total stored offers, both profiles | 715 | 750 |
| Candidate-profile offers | 560 | 595 |
| Current radar, score >=35 | 77 | 92 |
| Freshly verified current application routes | 3 | 47 |
| Confirmed removed postings, candidate profile | 12 | 15 |
| Exact URL duplicates | 0 | 0 |
| Current source errors | 0 | 0 |

The 47 routes comprise **39 retrieved candidate forms, seven explicitly recorded
application controls and one previously verified legacy control**. There are 67
current records with compatible location evidence, 23 with a published minimum
experience of at most three years, and 46 with unknown minimum experience. Five
current records publish an EUR24k-or-higher salary floor; salary, fit and location
are independent, so this does not prove five fully suitable jobs.

The 35 new rows comprise 20 current, 14 strategic and one excluded record. They
include title/location variants and unproved specialist requirements. Two new
Java/Spring families are conservatively documented as potentially useful:

- [Talent Connect — Java/Spring/AWS](https://jobs.talentconnect.ai/jobs/612354-backend-developer-java-spring-boot-aws-spain-hybrid-remote/applications/new):
  Spain remote outside its listed hybrid cities; three-plus years, B2, salary
  unknown. Professional AWS experience requires confirmation. The original posting
  is 161 days old, but its candidate form was freshly retrieved.
- [Whiteam — Java/Spring/microservices](https://careers.twtspain.com/jobs/8559939-desarrollador-a-backend-java-spring-boot-microservicios/applications/new):
  Spain remote, four years, salary unknown. This is a lower-priority stretch.

Other useful routes now checked include
[Talan Java/Spring](https://jobs.smartrecruiters.com/talan/744000154386250-ssr-java-springboot-developer)
and [knowmad Java backend](https://knowmadmood.teamtailor.com/jobs/8483639-software-developer-java-remoto/applications/new).
Those improve access to already known opportunities rather than counting as new
market discoveries. Whiteam's Java/API-security role publishes EUR30–32k but
explicitly leaves work mode unspecified; it remains geographically uncertain.
Its Java/Python banking role publishes EUR30–33k and requires Python/banking.

**The target of five to ten new useful opportunities per month is not established
by one day of observations.** No quota, salary estimate or interview probability
has been invented. [Sanitized production comparison](../reviews/jobradar-production-comparison-2026-10-22.json)
records the exact counts, limits and preservation checks.

## Ranking review and demonstrated corrections

The [independent original top twenty](../reviews/jobradar-top20-before-2026-10-22.json)
had ten conditionally relevant, four incompatible/removed and six unknown:
**10/14 = 71.4% conditional relevance precision**. Twelve application paths and
eleven actual forms were independently established, including incompatible roles.

The [final twenty-case re-review](../reviews/jobradar-top20-after-2026-10-22.json)
has twelve conditionally relevant, zero demonstrated incompatible/removed and
eight unknown: **12/12 = 100% among assessable cases**, with **40% unresolved**.
Fourteen paths and twelve actual candidate forms are confirmed. Neither sample
proves a EUR24k salary floor in its top twenty. The final re-review was performed
by the implementing agent; the initial review was independent. The cohorts differ
because ranking changed. This is occupational/geographic plausibility including
authorized experience stretches, not complete qualification or hiring probability.

Corrections backed by live examples and regression tests:

- Exact knowmad Java/travel 410 and PandaDoc official-API 404 are closed despite
  stale mirrors or a generic 200 board. A blocked page stays unknown.
- Expert/technical-lead roles move to strategic references; an independent
  two-year frontend requirement is not satisfied by general Java backend tenure.
- Galicia residence remains incompatible even when a city within Galicia is only
  preferred. Spanish three-to-five ranges retain the three-year minimum.
- Explicit remote alternatives outside Spanish hybrid-office cities are retained.
  Employer text leaving work mode unspecified stays uncertain despite metadata.
- OfferUp's remote-in-Colombia vacancy and Zup's internal-only process are excluded.
  Portal registration gates no longer establish a verified application route.
- Employer-linked Teamtailor forms are checked using their actual CV upload widget,
  enabled email and submission controls. No forms or CVs were submitted.
- SBA pay ranges are recognized; annual salary is not multiplied because a nearby
  project duration is in months. Up-to/Max pay remains a ceiling with no known floor.

The general ranking still contains unresolved roles, including MDOTM DevOps at score 88,
Liferay and mandatory frontend/specialty gaps. The verified filter improves access
but does not resolve every qualification. Talan's similar SSR postings and knowmad
Java/Kotlin title variants remain possible job families, not proven distinct jobs.
They are not blindly merged or counted as new relevant families.

## Sources and actual contribution

| Source | Observed contribution and bounded decision |
| --- | --- |
| knowmad / official Teamtailor RSS | Existing adapter; max200, twelve hours. After affinity correction: 56 filtered records, sixteen new, 27 updated, thirteen score-rejected. Many are mirrors, variants or future roles. |
| IRIUM / JazzHR | One new bounded adapter: public board, at most ten title-filtered details, twelve hours and paced requests. Four fetched, two updated, two rejected; no new record. |
| Talan and Scalian / SmartRecruiters | Existing adapter expanded from T-Systems. Eleven fetched, four new, three updated, four rejected on the first pass. Skill/seniority limits remain visible. |
| Whiteam / official RSS | Existing adapter; max200/twelve hours. Thirteen fetched: nine new, three outside search scope and one score-rejected. Pay and work-mode conflicts are retained. |
| Talent Connect / official RSS | Existing adapter; max200/twelve hours. Twelve fetched. Correct remote interpretation admits four records: three current with different stretches and one senior strategic; seven outside scope and one score-rejected. |

The [Teamtailor RSS guide](https://support.teamtailor.com/en/articles/11171756-rss-feed-how-to-guide)
documents the chosen interface. Employer robots permit the selected public paths.
RSS is filtered locally. JazzHR reads fixed employer-host pages, excludes protected
paths and external redirects, and does not store applicant field values. Repeated
controlled passes create **zero** additional rows. Exact variants retain alternate
identities; promotions from portals preserve the existing offer and user state.
Fourteen reviewed existing employer URLs were reconciled once; those are not new
market discoveries. Geography and numeric requirements guard against false merges.

Bounded research also covered Affirm, Trading212, New Relic, Eclipse, Revolut,
Alan, Flywire, Sportradar, lastminute, Teya, Sopra Steria, Inetum, Devoteam,
Metrica, SlashMobility, Accenture/Workday, CloudPay, Babel, Guidewire, INNOCV,
Clarity AI, Marfeel, Semrush, SNGULAR, Azertium and Kapres. Observed rejection
reasons were mandatory distant stacks/languages/offices, seniority, removed exact
postings, unverifiable current identity or disproportionate adapter cost. Accenture's
Java Sevilla R00328303 is a manual three-year lead; one posting and no documented
public discovery interface do not justify a general Workday connector. No blocked
interface was bypassed or source added solely to increase volume.

## Delivery and operation

| Deployed release | Revision | Validation |
| --- | --- | --- |
| 0.1.42 | 75f964e | CI 39754428508, 230 tests; official-source coverage and identity fixes |
| 0.1.43 | e2023d9 | CI 39790307079, 234 tests; real Teamtailor forms and explicit source affinity |
| 0.1.44 | 45c95ee | CI 39792946567, 244 tests; eligibility, account gates and salary context |
| 0.1.45 | c7c0b75 | [CI 39794443083](https://github.com/Gabrielvcg/JobRadar/actions/runs/39794443083), 245 tests; abbreviated salary ceilings |

Final local validation: 242 passed and three PostgreSQL tests skipped locally;
CI ran all 245, plus lint, typing and Docker build. Dependency audit passed.
Public health returns the exact final revision; app and existing database are
healthy. Login303, dashboard200, verified filter200, anonymous redirect303 and
cleanup of the isolated validation account passed after deployment. Assertions
confirm the corrected EUR35k ceiling, no verified registration gates and the
known country/internal exclusions. No schema migration was introduced.

All 715 original offer IDs and statuses, both profiles, existing accounts/passwords/
roles and user-specific states were preserved. Unrelated local work remains
uncommitted. Only the work branch was pushed; no merge was performed. Each rollout
retains prior images, environment/compose rollback copies and gzip-validated SQL
backups, including `jobradar_20261022T141908Z.sql.gz` for the final release. A restore
was not claimed. Other VPS applications/services were not changed.

The existing half-hour scheduled ingestion was checked across the morning and
14:00 cycle; successful runs distinguish zero/new/updated and interval skips.
Twelve-hour official-feed intervals bound employer traffic. Active verification
expires and is rechecked by the existing verification process. Final releases
also passed controlled real ingestions before the last scoring-only patch.

## Next work, ordered by benefit and effort

1. Measure a rolling thirty-day cohort of newly discovered, distinct, relevant
   families with checked paths: high benefit, low implementation effort, requires
   elapsed observation. Do not extrapolate today's 35 rows to a monthly yield.
2. Resolve employer title variants with conflicting identity/state carefully:
   medium benefit and effort; explicit ambiguity must survive until enough
   evidence supports a merge.
3. Refine professional frontend/Kotlin/Python/sector requirements when the candidate
   supplies demonstrable experience: medium benefit, low effort, depends on factual
   profile information. Certifications and projects remain separate from employment.
