# Bounded verification scheduling

Verification traverses each eligible career profile in its existing configured
order. The global check budget is shared by profiles. A nonpositive budget returns
before profile lookup, database queries, HTTP client or scoring construction.

For each visited profile, one ordered repository query streams batches of 500.
The reader/cache rules decide which offers need a check. A stable `nsmallest`
selection retains at most the remaining budget and preserves the original key:
portal preference, textual cached-check value, then descending score. Equal keys
retain the repository's score/advice/creation/ID order. Non-object raw proof uses
an empty cached-check value, matching missing proof without modifying stored data.
Historical timestamp sorting is intentionally textual; this is not a temporal
interpretation or SQL-filter change.

Selection exhausts/closes the query before any check, scoring or commit. The
selected bounded list is fixed for that profile even if scoring changes its
ordering or removes checked offers from eligibility. There is no OFFSET traversal,
rescan loop, or duplicate selection caused by those writes. Fresh failed checks
still use the existing cache; force bypasses it. No source/profile/score/country
or availability-reader policy changes are made.

The cost is deliberate: global priority requires scanning all eligible rows of a
visited profile before the first check. Retention is O(batch size + remaining
budget), with temporary ORM batch turnover; selection work is O(N log k) for
k>1, excluding database sorting and IO. It does not reduce database reads or
promise a latency speedup. Large caller budgets can retain correspondingly large
selected sets. A single-row field or driver buffer can still be large.

Synthetic SQLite instrumentation for 2,501 eligible offers and budget 4 observed
one offer query, maximum 500 rows per batch and 1,004 live ORM offers during
turnover; the cursor was closed before fake verification checks. This is an object
count, not a byte measurement. PostgreSQL cursor execution is not established.

A scan is not an application-wide snapshot: external concurrent writes and later
profiles can change between statements. Slow scans hold a connection/read cursor;
query timeouts and transaction-isolation changes are outside this correction.
R04 verified-only SQL semantics and R18 projection gates remain unresolved.
