# Career opportunity coverage — 2026-10-22

## Authorized outcome and current-state baseline

The user explicitly authorized continued public-source research, scoped development,
tests, commits, work-branch pushes, successive JobRadar VPS deployments and controlled
ingestion. Applications, uploads and employer messages remain out of scope.
Existing unrelated local deployment/backup changes are preserved.

At 08:49 UTC the public service was healthy on 0.1.41 / `d4ea420`.
The real baseline is 715 offers across two profiles, 560 in the candidate profile,
77 current at score >=35 and three freshly verified application controls. Only
one of those three is a direct Java/backend opportunity; the others are adjacent
platform/SRE roles. The previous evening's 688/72/one figures are historical.
There were no exact URL duplicates or current source errors.

The unchanged half-hour cron had completed real 08:30 ingestion: 19 fetched,
zero created, five updated, no errors. Its SmartRecruiters portion fetched six
and updated three. This is refresh evidence, not discovery of six new jobs.
Private runtime source settings, account/status fingerprints and full snapshots
remain outside Git. No unrelated VPS services are changed.

## Independent review of the original top 20

[The individual 20-row evidence](../reviews/jobradar-top20-before-2026-10-22.json)
records duties, years, geography, mandatory skills, salary, dates and application
availability for every selected offer, including primary URLs when identified.

- Ten conditionally relevant, four incompatible or removed, six unknown.
- Conditional relevance precision: **10 / 14 = 71.4%**. Unknowns are outside the
  denominator. This measures occupational/geographic plausibility including the
  authorized two-to-three-year stretch, not complete qualification or hiring odds.
- Twelve open application controls, including eleven retrieved candidate forms.
  Availability and suitability are separate: open incompatible roles are included
  in this availability coverage of 12/20, not in the relevance numerator.
- Eleven explicitly Spain-remote. No offer proves a published EUR 24,000 floor.
  Missing salaries remain unknown and ceilings are not treated as guarantees.
- The exact knowmad Java/English/travel page returns 410; the PandaDoc AppSec
  posting is absent with official API 404 despite redirecting to a 200 job board.
- Demonstrated scoring defects include independent two-year frontend requirements,
  explicit expert/technical-lead seniority, Galicia residence with a preferred city,
  and a Spanish "between three and five" range misread as a five-year minimum.

## Sources investigated and selection

| Source / employer | Observed contribution | Decision |
| --- | --- | --- |
| knowmad mood / Teamtailor | Documented full-description RSS, employer dates, locations, remote status and verified candidate forms. Many portal mirrors and location variants. | Integrate one bounded 200-record feed, filter locally and group exact variants only. |
| IRIUM / JazzHR | Current board and real Java/Angular form; up to three years, Spain remote, salary ceiling EUR 33k. Bounded probe returns four Java-related records, including senior and QA noise. | Integrate one board, at most ten title-filtered details every twelve hours; score each, do not claim four current opportunities. |
| Scalian / SmartRecruiters | Two public postings: remote Java/Angular with substantial frontend duties; remote backend with four years/senior evidence. | Reuse existing adapter; retain skill uncertainty and strategic separation. |
| Talan / SmartRecruiters | Six Java/Spain postings; an exact current SSR Java/Spring role explicitly permits 100% remote. | Reuse existing adapter and employer evidence; no new ATS architecture. |
| Sopra Steria, Inetum, Devoteam, Métrica | Reviewed examples require French, other-office attendance, leadership or operations work. | No expansion justified by this sample. |
| Affirm | Three real entry/intermediate Spain-remote backend forms, but explicit proficiency in Python/Kotlin and no stated Java substitute. | Do not relax the Java filter to count them. |
| Trading212, New Relic, Eclipse, Revolut, Alan, Flywire | Senior-only Java, removed exact postings, distant mandatory stack or actual non-Sevilla office requirements. | No useful direct-Java expansion proved. |
| Sportradar, lastminute, Teya | Fresh public feeds supply no suitable Java/Spain role in this bounded sample. | No additional integration. |
| SlashMobility / TalentClue | Junior Java page/form accessible, but stale company metadata and no current employer job board independently established. Another junior role is Barcelona hybrid. | Keep uncertain; do not add a general connector or label the job closed from metadata alone. |
| Accenture / Workday | Official Java Sevilla role R00328303 requires three years, degree and unspecified salary; public Workday JSON-LD and application link agree. | Useful manual stretch lead. One confirmed role and no documented public discovery interface do not justify a general Workday connector. |
| CloudPay, Babel, Guidewire / Workday | Two indexed leads cannot be verified from current HTML; Guidewire's actual role requires Ireland. | Unknown or incompatible, not counted as available opportunities. |

The [Teamtailor RSS guide](https://support.teamtailor.com/en/articles/11171756-rss-feed-how-to-guide)
documents descriptions, dates, locations, remote status and the `per_page` parameter.
The employer RSS and JazzHR robots files permit the selected public paths. JazzHR
reads only fixed employer-board links and excludes `/cb`, external hosts, applicant
forms and hidden values from stored job data. No protection mechanism is bypassed.
All raw research snapshots are ignored local evidence; source counts are dated
observations, never market coverage or an uptime promise.

## First delivery candidate — 0.1.42

The candidate reuses RSS and SmartRecruiters, adds only the bounded JazzHR adapter,
and preserves official dates/locations. Exact RSS variants retain alternate URLs.
Matching portal mirrors can be promoted only with consistent geography/mode,
matching company/title, equivalent descriptions and identical requirement numbers.
Original source identities remain aliases; existing user/application state remains
on the same offer. Later stale portal fetches cannot overwrite employer evidence.

Verification distinguishes `active`, `listing_only`, `unverified` and `closed`.
Teamtailor paths require a retrieved candidate form; a listing-only 200 or blocked
form does not become verified active. Greenhouse board redirects require independent
official API removal evidence before closure. Existing JSON columns are reused;
there is no schema migration. The original scoring policy remains for the other
private profile.

Independent review reproduced and corrected two identity risks before deployment:
office/remote roles must not share state merely because descriptions match, and
RSS grouping must not erase different numeric requirements. PostgreSQL integration
coverage includes original and alternate source aliases.

Deployment and measured after-results are recorded only after their checks finish.
