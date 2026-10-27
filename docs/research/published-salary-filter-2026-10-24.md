# Published salary filtering

A salary is published when `salary_unknown` is false and at least one of
`salary_min` or `salary_max` is non-null. A supplied upper bound is published
compensation evidence even when it does not guarantee a minimum. Numeric zero is
a supplied bound; filtering tests use nullness, not truthiness.

Repository `JobFilters.salary_known=True` selects published salaries. False selects
the complementary set: the unknown flag is true, or both bounds are absent. The
model requires a non-null flag; null is rejected by its database constraint.

The API and dashboard retain their existing boolean contract: `salary_known=true`
applies the published-salary restriction, while false omits that restriction. They
do not expose the repository's unknown-only mode through that parameter. Existing
API stats and CSV export do not accept a salary-known filter; their scope remains
unchanged. Dashboard counters reflect its filtered visible offers.

`salary_min` filtering continues to compare the stored minimum only. A maximum-only
salary never supplies a guaranteed minimum, including for a zero threshold. No
conversion, currency, annualization, scoring, profile or eligibility policy changes.

Regression tests cover the supported bound/flag combinations, extracted salary
ceilings, forbidden null flags, authenticated list/dashboard backend data, composed
filters, owner states, unchanged unfiltered stats/export, and persistent state.
SQLite/ASGI checks do not establish PostgreSQL execution; this predicate uses the
same portable boolean/null comparison constructs as the existing query.
