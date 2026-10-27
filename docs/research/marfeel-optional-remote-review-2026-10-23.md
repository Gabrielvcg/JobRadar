# Marfeel optional remote mode — local review

Status: local, uncommitted, unpublished. No source was added, no ingestion ran,
no production or private production data was accessed, and no deployment occurred.

## Checkpoint and source

Worktree: `C:/Users/GabrielVG/Desktop/PROYECTOS/jobradar/build/marfeel-mode-review`

Base: `d1a85e858ca530c43e26f6c3f0eded0abebb23c6` (the completed 0.1.51 delivery).
The primary checkout and its unrelated modifications were preserved. This detached
checkout contains only the local candidate diff and review artifacts.

On October 23, 2026, the official corporate-linked Recruiterflow index still lists
[Java Developer, job 246](https://recruiterflow.com/marfeel/jobs/246). Both index and
detail returned HTTP 200. The index says Barcelona / Remote, with a Remote flag;
the detail's public JobPosting says TELECOMMUTE and leaves addressCountry empty.
This establishes that the live posting still exists, not a new application-form
verification or a guarantee that the employer is accepting suitable candidates.

Exact employer mode clause:

> Option to work full remote, hybrid or office-based (if in BCN area)

The unchanged normalizer previously returned HYBRID because it searched for any
occurrence of hybrid before recognizing an explicit choice of full remote.

## Concrete diff

- `app/scoring/text.py`: twenty-five lines added inside `detect_remote_type`. Mask only
  the complete explicit list of work-mode choices before the existing hybrid
  check. Explicit no-remote and structured onsite/hybrid location retain priority.
  Client-required office attendance and explicit restrictions on full remote
  prevent masking. Other parsing/scoring/geography logic remains unchanged.
- `tests/fixtures/marfeel-remote-choice.json`: short public mode excerpt and
  observed location/country/TELECOMMUTE metadata, with source URL/check timestamp.
  No entire application page, tokens, personal details or private configuration.
- `tests/test_remote_choice.py`: twenty regression cases, including the actual
  fixture through JobNormalizer and independent geography assertions.
- `CHANGELOG.md`: Unreleased fix entry. No release-version bump.

## Before and after

Offline evaluation uses the full re-read public description, the public
`engineering` example profile, and a fixed date of October 23, 2026. It does not
read the private candidate profile or database. No availability proof is invented.

| Field | Before | After |
| --- | --- | --- |
| Mode | hybrid | remote |
| Location | Barcelona, Remote | Barcelona, Remote |
| Country | unset | unset |
| Existing geography classification | incompatible / relocation | incompatible / country_restricted |
| Existing recommendation | D34 / excluded | D34 / excluded |
| Published salary | unknown | unknown |
| Numeric minimum years | unspecified | unspecified |

The mode bug is corrected. The current geography policy still treats the specific
Barcelona location and empty eligible country conservatively; this review does not
prove that Spain is excluded, nor rewrite that policy into U. Blank-country and
Europe-only scenarios remain uncertain when evaluated independently. A remote
label does not establish Spain eligibility, salary fit, seniority fit or A/B.

## Counterexamples retained

| Scenario | Result after fix |
| --- | --- |
| Hybrid Madrid with two remote days (existing regression text) | hybrid |
| Mandatory three office days overriding a remote source (existing regression) | hybrid |
| Remote Europe with onsite interview (existing regression) | remote; Europe eligibility remains separate |
| Fully remote during onboarding, hybrid afterwards | hybrid |
| Choose remote/hybrid, but client requires two days at office | hybrid |
| Actual choice followed by client-required office attendance | hybrid |
| Choice subject to client approval | hybrid |
| Separate sentence requiring client approval (both independent-review reproductions) | hybrid; fictitious Remote Spain still has zero geography points |
| Remote choice limited to Sales department | hybrid; no unrestricted remote assumption |
| Candidate preference for remote in a hybrid position | hybrid |
| Choice followed by explicit no-remote project | onsite |
| Explicit hybrid location metadata | hybrid |
| Full-remote choice with unknown or Europe-only country | remote / uncertain eligibility |

Except for the identified employer clause, these new surrounding-condition cases
are explicitly constructed counterexamples, not quotations from other real jobs.
The first three reuse existing repository regression cases. This is intentionally
a narrow correction, not comprehensive natural-language work-mode parsing.

## Independent-review correction

The first candidate missed client approval expressed in a second sentence. The
independent P2 review reproduced REMOTE where baseline remained HYBRID. The local
revision now retains both exact conditions: `Full remote requires client approval.`
and `Remote work is subject to client approval.` A bounded remote/choice approval
check prevents masking even across sentence boundaries. Both new tests also use
a deliberately fictitious Remote Spain label and confirm zero geography points;
no employer location data is changed. All earlier positive/negative tests pass.
Independent limited revalidation now returns **ACCEPT for the reviewed scope**,
superseding the initial P2/REVISE decision. It rechecked the actual positive, both
separate approval clauses and synthetic geography blockers, and ran the twenty
regression tests successfully. The full suite, Ruff and Mypy were not independently
rerun. The revalidated code, test and fixture hashes match this delivery exactly.

Independent report: `C:/Users/GabrielVG/Documents/Codex/jobradar-remote-mode-review-2026-10-23/review.md`.
Technical acceptance does not authorize publication, merge or deployment.

## Validation and handoff

- Focused tests: 116 passed (new tests plus existing career, employer and text tests).
- Full offline suite: **305 passed, 3 skipped**. Skipped tests require PostgreSQL;
  no database was started or contacted for this review.
- Ruff `app tests`: passed. Mypy `app tests`: passed (87 source files).
- `git diff --check`: passed. Existing Starlette/httpx deprecation warning remains.
- No weights, API, schema, authentication, frontend, sources or private profiles changed.
- No commit, push, merge, production call, ingestion, deployment or employer contact.

The complete review patch includes code, fixture, tests, changelog and this report.
It remains outside the primary checkout under `build/research_marfeel_mode/`.
Independent technical review is accepted within scope. Further delivery remains
unpublished and requires the applicable authorization; this round ends with the
local diff. No suite was repeated to record this documentation-only update.
