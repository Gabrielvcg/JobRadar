# Full-cohort career alignment audit — 2026-10-22

Production is **0.1.47 / 66ab5992a94da4965fc98b4306caea70f6ce4e94**.
This follows the [coverage delivery](career-coverage-2026-10-22.md), whose
0.1.45 ranking still contained unresolved career-direction errors. No previous
source discovery or security work was repeated.

## Scope and evidence

The live database was captured at 15:23 UTC before the change and again at
16:04 UTC after the scoring deployment, rescoring and a bounded ingestion check.
The final CSV-access patch and preservation fingerprints were checked again
at 16:17 UTC after its deployment. All **595**
candidate-profile records were evaluated, including **15 disabled synthetic
fixtures**. Thus 580 records represent market postings, not 580 distinct live
selection processes. Descriptions and requirements, rather than technology tags
alone, are used. The other profile contains 155 records.

Every record receives A/B/C/D/U advice and an explanation. This is a rule-based
full-cohort review; it is not a claim that every employer was manually contacted
or all 595 pages individually verified. Twenty-two shortlisted employer URLs
were individually checked at 15:57 UTC: **19 public application forms and three
enabled application controls**. A public control is weaker evidence than a
retrieved candidate form. Neither proves that a recruiter will respond. No CV,
application, recruiter message or applicant data was submitted.

Complete descriptions, personal prioritization and review exports stay outside
Git. The authenticated **Export all offers CSV** button now includes stored
history, descriptions, requirements, advice, uncertainty and application proof.
The existing radar export retains its narrower scope. Disabled history is
explicitly marked, and current-profile isolation and user statuses are retained.

## Diagnosis and implementation

- Infrastructure maintenance and wording about a developer platform previously
  counted as building software. MDOTM DevOps scored 88 despite operations duties.
  It now scores **19 / D**, while the knowmad Java Sevilla posting 8525964 moves
  from **59 to 66 / A**. Genuine platform API development remains an eligible
  secondary career path.
- Requirement headings were lost between list items. Mandatory Kotlin, Python,
  frontend and professional cloud gaps were understated. Explicit Java-or-Kotlin
  alternatives remain alternatives; desirable skills and years remain desirable.
  Backend tenure does not establish independent professional DevOps/cloud or
  frontend experience. Five-year and genuinely senior responsibilities move to
  strategic review; copied portal senior tags do not override actual requirements.
- Career alignment, work evidence and application advice are separate fields.
  Existing technical categories and current/strategic/excluded contracts remain
  intact. Existing fit/growth/viability weights are unchanged. Evidence-based
  exclusions and confidence caps prevent operations, unverified access and
  specialist gaps from outranking suitable backend work. Equal scores prefer
  actionable advice over unknown information. The 64 cap deliberately remains
  below the existing 65-point good-match threshold; it is not a hiring estimate.
- The salary parser had accepted community sizes, ISO numbers, working hours
  and annual leave as pay. Salary evidence is recalculated during career rescoring.
  Employee salary ranges remain separate from freelance day rates, and ceilings
  remain ceilings. The preferred salary floor is EUR28k; the change minimum stays
  EUR24k. Unknown salaries remain eligible and never establish a salary floor.
- Explicit Latin America titles and enumerated eligible countries override broad
  worldwide metadata. Existing Spain remote alternatives and Sevilla office
  compatibility remain supported.

## Measured result

| Measure | Before, 0.1.45 | After, 0.1.46–47 |
| --- | ---: | ---: |
| Both profiles, stored records | 750 | 750 |
| Candidate-profile records | 595 | 595 |
| Current, score at least 35 | 92 | 62 |
| Strategic references | 81 | 100 |
| Excluded records | 422 | 433 |
| Verified current application routes | 47 | 35 |
| All active / closed / unverified proof states | 50 / 15 / 530 | 50 / 15 / 530 |
| Exact URL duplicates | 0 | 0 |
| Current source errors | 0 | 0 |

Final advice: **A 6, B 16, C 100, D 433, U 40**. Excluding the 15 fixtures gives
**A 6, B 16, C 100, D 418, U 40** across 580 market records. The reduction in current
and verified-current counts reflects stricter career relevance, not deleted jobs
or inaccessible forms. A is a sensible application, not proof of meeting every
unpublished expectation or the salary minimum.

Applying the final policy to the original top twenty yields A 3/B 8/U 8/D 1.
The deployed top twenty is A 6/B 14/U 0/D 0: **11/20 to 20/20 A-or-B records**.
This is a descriptive career-priority metric assessed by the implementing agent,
not an independent accuracy benchmark or hiring probability. The cohorts differ
because ranking changed. Related Talan advertisements and knowmad title/stack
variants remain in the database; they are grouped for personal application
planning, not counted as proven distinct opportunities or blindly merged.

## Coverage decision and remaining limits

The existing bounded employer feeds are retained. Additional official T-Systems
junior full-stack publications
[744000153445359](https://jobs.smartrecruiters.com/T-SystemsIberia/744000153445359-junior-full-stack-developer-m-f-d-)
and [744000153443540](https://jobs.smartrecruiters.com/T-SystemsIberia/744000153443540-junior-full-stack-developer-m-f-d-)
require Python,
Angular, frontend experience and Kotlin/Java. Their junior titles do not establish
backend suitability, so no new source or advertised opportunity was added for
volume. Other search leads did not establish an additional eligible live backend
opportunity. The previous coverage report retains the wider employer research
and its rejection evidence.

This release adds **zero new market records**. Product-company coverage for
early-career Java with explicit Spain eligibility remains limited. Unknown salary,
unpublished seniority, specialist requirements and potential posting families
remain real limits; 40 records are U rather than being presented as incompatible.
Application proof expires after 24 hours and should be refreshed before use.

## Delivery and preservation

- [Commit 9f72c6a](https://github.com/Gabrielvcg/JobRadar/commit/9f72c6ae3e094b30b4095f4f707c6186ca165f44),
  pushed to `codex/career-radar-release`; no merge.
- A final live anonymous check found the expanded CSV accessible without a
  session. The pre-existing export route had not required authentication.
  [Commit 66ab599](https://github.com/Gabrielvcg/JobRadar/commit/66ab5992a94da4965fc98b4306caea70f6ce4e94),
  release 0.1.47, requires a signed-in user and adds an HTTP rejection assertion.
- [CI 39810047591](https://github.com/Gabrielvcg/JobRadar/actions/runs/39810047591):
  **269 tests passed**, including PostgreSQL; lint, typing (81 files) and Docker
  build passed. Local validation: 266 passed, three PostgreSQL checks skipped.
  Dependency security also passed.
- [Final CI 39812216421](https://github.com/Gabrielvcg/JobRadar/actions/runs/39812216421)
  passed for the exact 0.1.47 revision, with the same 269-test suite and build checks.
- Pre-deploy backup `jobradar_20261022T160031Z.sql.gz` created and gzip integrity
  checked. This is not a claim of a new restore drill. Previous image, environment,
  Compose configuration and runtime configuration target retained for rollback.
  The 0.1.47 rollout repeated backup/integrity checks with
  `jobradar_20261022T161409Z.sql.gz` and retained 0.1.46 as its immediate rollback.
- Git archive SHA256 checked; exact committed source built on the VPS; public and
  private configuration preflights passed. Deployment used the existing ingest
  lock and changed only the application container and its configuration.
- Public health returned exact version/revision; actual user login returned 303,
  dashboard 200 and the complete CSV contained 595 distinct IDs and 36 columns.
  The final 0.1.47 check repeated login/export successfully and confirmed
  anonymous CSV requests return 401. The personal audit file adds four review
  columns to the same 595 rows, including the previous score and planning group.
- Post-deploy official SmartRecruiters ingestion fetched 11, updated 7, created 0,
  rejected 4 by score and returned no error. A normal cycle after 0.1.47 had no
  due sources or errors, respecting existing intervals. Scheduled ingestion remains.
- All 750 IDs and stored statuses, account/password/role fingerprint and user-state
  fingerprint match the fresh baseline. A separate fingerprint confirms all 155
  secondary-profile records, descriptions, scores, reasons and salary values are
  unchanged. No schema migration or other VPS service was changed.

The personal report provides thirteen application groups with employer links,
experience, gaps, pay evidence and exact application-check timestamps. Related
advertisements are alternatives within a group rather than repeated CV targets.
