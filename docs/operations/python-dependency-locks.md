# Python delivery dependency locks

The files in `requirements/` target Linux CPython 3.12, the CI and production
image platform. They pin all resolved runtime and development dependencies and
allow only published wheel SHA-256 hashes. They do not claim reproducibility of
the operating-system base image or Debian packages.

Runtime (41 packages) and development (76 packages) versions reproduce the
successful installation logs of GitHub Actions run `40537146556`, revision
`c99ebd567c232c803798cdb37a00db0f7dc67008` (595 tests, Docker build).
Runtime versions are identical in both files. Hashes come from the official
PyPI JSON records for those exact releases; source distributions are excluded.
Multiple platform wheel hashes permit the wheel selector to choose a compatible
artifact without permitting a different version. This is integrity pinning,
not an assertion that the dependencies contain no vulnerabilities.

`build.txt` pins pip 26.2.2, already used by that Docker build. The previous
isolated build did not report its setuptools version. The backend is now fixed
explicitly at 84.2.1, published on PyPI on 20 October 2026, before that CI run.
This is a newly explicit build-tool selection, not a claim that the hidden
previous build version was established. The current CI and vulnerability audit
must validate it. Runtime versions are not upgraded by this change.

CI, dependency audit, and Docker first install the hash-checked build tools and
dependencies. The editable local package then uses `--no-index --no-deps
--no-build-isolation`, preventing a second remote resolution or hidden backend
download. The audit examines this installed environment rather than resolving
the project's broad version ranges again. CI also runs `pip check`.

To update dependencies, deliberately select versions in a disposable Linux
Python 3.12 CI environment, record the complete resolved runtime/development
sets and their published wheel hashes, review the diff, and rerun tests,
migrations, Docker and the installed-environment vulnerability audit. Do not
silently regenerate locks from current latest releases during a build. A new
dependency absent from the locks fails installation or `pip check` and requires
an explicit reviewed lock update.
