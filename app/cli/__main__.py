from __future__ import annotations

import asyncio
import csv
import json
import sys
from typing import Annotated

import typer

from app.core.logging import configure_logging
from app.core.profiles import resolve_profile_key, uses_career_radar
from app.db.session import new_session
from app.repositories.jobs import JobFilters, JobRepository
from app.repositories.users import UserAlreadyExistsError, UserRepository
from app.security.auth import validate_password_strength
from app.services.ingestion import IngestionService

app = typer.Typer(help="JobRadar command line interface.")


@app.command("verify-offers")
def verify_offers(
    limit: Annotated[int, typer.Option("--limit", min=1, max=100)] = 20,
    profile: Annotated[str | None, typer.Option("--profile")] = None,
    force: Annotated[bool, typer.Option("--force")] = False,
) -> None:
    """Check listing/application availability without sending applications."""
    from app.services.verification import OfferVerificationService

    with new_session() as session:
        result = asyncio.run(
            OfferVerificationService().run(
                session,
                limit=limit,
                profile_key=resolve_profile_key(profile),
                force=force,
            )
        )
    typer.echo(json.dumps(result))


@app.command()
def ingest() -> None:
    """Run ingestion for all enabled sources."""
    configure_logging()
    with new_session() as session:
        summary = asyncio.run(IngestionService().run_enabled_sources(session))
    typer.echo(
        f"Ingestion finished: fetched={summary.jobs_fetched} "
        f"created={summary.jobs_created} updated={summary.jobs_updated} "
        f"errors={len(summary.errors)}"
    )
    for error in summary.errors:
        typer.echo(f"Error: {error}", err=True)


@app.command("score-all")
def score_all() -> None:
    """Recalculate scores for all stored jobs."""
    configure_logging()
    with new_session() as session:
        count = IngestionService().score_all_jobs(session)
    typer.echo(f"Rescored {count} jobs")


@app.command("list")
def list_jobs(
    min_score: Annotated[int, typer.Option("--min-score", min=0, max=100)] = 0,
    limit: Annotated[int, typer.Option("--limit", min=1, max=200)] = 25,
    profile: Annotated[str | None, typer.Option("--profile")] = None,
    radar: Annotated[
        str, typer.Option("--radar", help="current, strategic, excluded or all")
    ] = "current",
) -> None:
    """List jobs ordered by score."""
    repository = JobRepository()
    profile_key = resolve_profile_key(profile)
    if radar not in {"current", "strategic", "excluded", "all"}:
        raise typer.BadParameter("radar must be current, strategic, excluded or all")
    with new_session() as session:
        jobs = repository.list_jobs(
            session,
            JobFilters(
                profile_key=profile_key,
                min_score=min_score,
                limit=limit,
                radar=radar if uses_career_radar(profile_key) else None,
            ),
        )
        for job in jobs:
            typer.echo(
                f"{job.match_score:3d} {job.match_level:10s} "
                f"{job.company.name} - {job.title} [{job.status.value}] {job.url or ''}"
            )


@app.command("create-user")
def create_user(
    email: Annotated[str, typer.Argument(help="User email address.")],
    display_name: Annotated[str, typer.Option("--display-name")] = "",
    password: Annotated[
        str | None,
        typer.Option(
            "--password",
            help="User password. Omit to type it safely.",
        ),
    ] = None,
    password_stdin: Annotated[
        bool,
        typer.Option("--password-stdin", help="Read the user password from standard input."),
    ] = False,
    admin: Annotated[bool, typer.Option("--admin/--no-admin")] = False,
) -> None:
    """Create an application user."""
    if password_stdin:
        password = sys.stdin.readline().rstrip("\r\n")
    elif password is None:
        password = typer.prompt("Password", hide_input=True, confirmation_prompt=True)

    password_error = validate_password_strength(password)
    if password_error is not None:
        typer.echo(password_error, err=True)
        raise typer.Exit(code=2)
    repository = UserRepository()
    with new_session() as session:
        try:
            user = repository.create_user(
                session,
                email=email,
                display_name=display_name,
                password=password,
                is_admin=admin,
            )
        except UserAlreadyExistsError:
            typer.echo("User already exists", err=True)
            raise typer.Exit(code=1) from None
        session.commit()
    typer.echo(f"Created user {user.email}")


@app.command()
def export(
    format: Annotated[
        str, typer.Option("--format", help="Only csv is supported in the MVP.")
    ] = "csv",
    min_score: Annotated[int, typer.Option("--min-score", min=0, max=100)] = 0,
    profile: Annotated[str | None, typer.Option("--profile")] = None,
) -> None:
    """Export jobs to stdout."""
    if format != "csv":
        typer.echo("Only csv export is supported", err=True)
        raise typer.Exit(code=2)
    repository = JobRepository()
    profile_key = resolve_profile_key(profile)
    writer = csv.writer(sys.stdout)
    writer.writerow(["id", "score", "level", "company", "title", "location", "status", "url"])
    with new_session() as session:
        jobs = repository.list_jobs(
            session,
            JobFilters(profile_key=profile_key, min_score=min_score, limit=10_000),
        )
        for job in jobs:
            writer.writerow(
                [
                    str(job.id),
                    job.match_score,
                    job.match_level,
                    job.company.name,
                    job.title,
                    job.location or "",
                    job.status.value,
                    job.url or "",
                ]
            )


if __name__ == "__main__":
    app()
