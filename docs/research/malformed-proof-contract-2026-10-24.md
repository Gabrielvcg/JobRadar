# Availability metadata boundary

The verification writer produces a dictionary with a textual state, a listing URL
or null, an ISO timestamp, and an optional application URL. Active writer results
have a textual destination; older compatible active proofs may omit it or use null.
The reader keeps those optional-field semantics and accepts historical textual
states without an enum allowlist. It adds no country, evidence, form, host or
scheme requirement.

`current_verification` now returns a controlled textual `unverified` result when
state is missing/nontext, a supplied listing/offer URL is nontext, or URL parsing
raises `ValueError`. An active proof's supplied non-null application URL must also
be text and parse without that error. The invalid application destination is not
exposed. This is structural validation, not a new provenance or URL-scheme policy.

`canonical_url` is unchanged globally. Timestamp grammar/coercion, naive timestamps
as UTC, future rejection and the inclusive 24-hour window are unchanged. The reader
does not modify raw payloads, require optional metadata, normalize arbitrary extras,
or use assessment availability as authority. Non-active unused application metadata
retains its prior behavior.

The declared outer payload remains a dictionary. This change does not promise a
total serializer for invalid offer models: a nontext `JobOffer.url` can independently
violate the DTO's optional-string field. Validation of every arbitrary extra field
is also outside this boundary.

Tests use real reader/serializer functions, synthetic SQLite and authenticated ASGI
list/detail/CSV requests with a damaged offer beside a valid one. They verify complete
CSV output, cursor/session cleanup and raw-payload preservation. Valid R04 controls
and a separate old/new-reader differential retain compatible timestamp/URL behavior.

The SQL verified-only filter and the experimental R18 projection are unchanged.
R18's original reader-oracle counts do not automatically validate this revised
malformed-metadata contract; projection parsing must be aligned and revalidated
before any implementation or backfill. PostgreSQL integration remains a gate.
