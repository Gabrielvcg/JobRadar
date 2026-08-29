# Architecture Overview

JobRadar is split into five main concerns:

- Sources: adapters fetch raw jobs from allowed public APIs or local fixtures.
- Normalization: HTML is cleaned, titles are normalized, technologies, remote type, experience, salary, language, and content hash are extracted.
- Scoring: deterministic configurable rules assign a 0-100 score and explain positive and negative reasons.
- Persistence: SQLAlchemy stores sources, companies, offers, and ingestion runs in PostgreSQL.
- Interfaces: FastAPI exposes REST endpoints, Jinja2 renders a minimal web UI, and Typer provides CLI commands.

Controllers stay thin and delegate ingestion, scoring, filtering, and persistence to services and repositories.

