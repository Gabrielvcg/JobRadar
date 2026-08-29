# JobRadar MVP Plan

1. Scaffold a Python 3.12 FastAPI project with PostgreSQL, SQLAlchemy 2, Alembic, Typer CLI, pytest, Ruff, mypy, Docker, and Docker Compose.
2. Implement the core job pipeline: source adapters, raw job normalization, salary and text extraction, deterministic scoring, deduplication, persistence, and status tracking.
3. Provide two initial sources: local JSON fixtures for reproducible development and the public Arbeitnow API with conservative timeouts, retries, rate limiting, and attribution.
4. Expose the required REST API, a minimal server-rendered web interface, and CLI commands for ingestion, rescoring, listing, and export.
5. Add fixtures, tests, documentation, CI, and AWS deployment notes, then verify locally with linting, tests, migrations, and Docker Compose.

Assumptions:

- The MVP should be fully usable without paid external APIs or credentials.
- Arbeitnow is used only through its public API, not by scraping HTML pages.
- Salaries are normalized only when explicit salary text is present.
- Integration tests require a PostgreSQL URL through `POSTGRES_TEST_URL`; unit tests run without a database.

