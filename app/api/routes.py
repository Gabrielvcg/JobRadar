from __future__ import annotations

import csv
import io
import uuid
from collections import Counter
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.profiles import get_profile, load_profiles, resolve_profile_key
from app.db.session import get_session
from app.formatting import experience_label, salary_label, salary_original_detail
from app.models.enums import JobStatus, RemoteType
from app.models.job import User
from app.repositories.jobs import JobFilters, JobRepository
from app.repositories.users import UserAlreadyExistsError, UserRepository
from app.schemas.jobs import (
    IngestionRunRead,
    IngestionSummary,
    JobOfferRead,
    JobsResponse,
    JobStats,
    JobStatusUpdate,
    SourceRead,
    job_offer_to_read,
)
from app.security.auth import (
    clear_session_cookie,
    get_current_user,
    set_session_cookie,
    validate_password_strength,
)
from app.services.ingestion import IngestionService

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
repository = JobRepository()
user_repository = UserRepository()


@router.get("/health")
def health(session: Annotated[Session, Depends(get_session)]) -> dict[str, str]:
    session.execute(text("SELECT 1"))
    return {"status": "ok"}


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request) -> Response:
    return _render_auth(request, mode="login")


@router.post("/login", response_class=HTMLResponse)
def login(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
) -> Response:
    user = user_repository.authenticate(session, email=email, password=password)
    if user is None:
        return _render_auth(
            request,
            mode="login",
            error="Invalid email or password.",
            email=email,
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    user_repository.touch_login(session, user)
    session.commit()
    response = RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    set_session_cookie(response, user.id)
    return response


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request) -> Response:
    if not get_settings().public_registration_enabled:
        return _render_auth(
            request,
            mode="login",
            error="Registration is disabled. Ask an administrator to create your account.",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    return _render_auth(request, mode="register")


@router.post("/register", response_class=HTMLResponse)
def register(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    display_name: Annotated[str, Form()] = "",
) -> Response:
    if not get_settings().public_registration_enabled:
        return _render_auth(
            request,
            mode="login",
            error="Registration is disabled. Ask an administrator to create your account.",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    if "@" not in email:
        return _render_auth(
            request,
            mode="register",
            error="Enter a valid email address.",
            email=email,
            display_name=display_name,
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    password_error = validate_password_strength(password)
    if password_error is not None:
        return _render_auth(
            request,
            mode="register",
            error=password_error,
            email=email,
            display_name=display_name,
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    try:
        user = user_repository.create_user(
            session, email=email, display_name=display_name, password=password
        )
    except UserAlreadyExistsError:
        session.rollback()
        return _render_auth(
            request,
            mode="register",
            error="That email is already registered.",
            email=email,
            display_name=display_name,
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    user_repository.touch_login(session, user)
    session.commit()
    response = RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    set_session_cookie(response, user.id)
    return response


@router.post("/logout")
def logout() -> RedirectResponse:
    response = RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)
    clear_session_cookie(response)
    return response


@router.get("/", response_class=HTMLResponse)
def web_index(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    min_score: int | None = Query(default=35, ge=0, le=100),
    match_level: str | None = None,
    technology: str | None = None,
    remote_type: RemoteType | None = None,
    status_filter: Annotated[JobStatus | None, Query(alias="status")] = None,
    salary_known: bool = Query(default=False),
    q: str | None = None,
    profile: str | None = None,
    sort: str = Query(default="score", pattern="^(score|date)$"),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
) -> Response:
    current_user = get_current_user(request, session)
    if current_user is None:
        return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)
    active_profile_key = resolve_profile_key(profile)
    filters = JobFilters(
        profile_key=active_profile_key,
        min_score=min_score,
        match_level=match_level,
        technology=technology,
        remote_type=remote_type,
        status=status_filter,
        salary_known=True if salary_known else None,
        user_id=current_user.id,
        q=q,
        sort=sort,
        order=order,
        limit=200,
    )
    jobs = repository.list_jobs(session, filters)
    sources = repository.list_sources(session, profile_key=active_profile_key)
    user_statuses = repository.get_user_statuses(session, current_user.id, jobs)
    stats = _visible_stats(jobs, user_statuses)
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "request": request,
            "jobs": jobs,
            "stats": stats,
            "sources": sources,
            "filters": filters,
            "user_statuses": user_statuses,
            "current_user": current_user,
            "profiles": list(load_profiles().values()),
            "active_profile": get_profile(active_profile_key),
            "active_profile_key": active_profile_key,
            "statuses": list(JobStatus),
            "remote_types": list(RemoteType),
            "experience_label": experience_label,
            "salary_label": salary_label,
            "salary_original_detail": salary_original_detail,
        },
    )


@router.post("/web/jobs/{job_id}/status", response_class=HTMLResponse)
def web_update_status(
    request: Request,
    job_id: uuid.UUID,
    session: Annotated[Session, Depends(get_session)],
    status_update: Annotated[JobStatus, Form(alias="status")],
) -> RedirectResponse:
    current_user = _require_user(request, session)
    offer = repository.update_user_status(
        session, user_id=current_user.id, job_id=job_id, status=status_update
    )
    if offer is None:
        raise HTTPException(status_code=404, detail="Job not found")
    session.commit()
    referer = request.headers.get("referer", "/")
    return RedirectResponse(referer, status_code=status.HTTP_303_SEE_OTHER)


@router.post("/web/ingestion/run")
async def web_run_ingestion(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    profile: Annotated[str | None, Form()] = None,
) -> RedirectResponse:
    _require_user(request, session)
    service = IngestionService()
    await service.run_enabled_sources(session)
    active_profile_key = resolve_profile_key(profile)
    return RedirectResponse(
        f"/?profile={active_profile_key}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.get("/jobs/stats", response_model=JobStats)
def job_stats(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    profile: str | None = None,
) -> JobStats:
    current_user = get_current_user(request, session)
    active_profile_key = resolve_profile_key(profile)
    return JobStats.model_validate(
        repository.stats(
            session,
            user_id=current_user.id if current_user else None,
            profile_key=active_profile_key,
        )
    )


@router.get("/jobs", response_model=JobsResponse)
def list_jobs(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    min_score: int | None = Query(default=None, ge=0, le=100),
    match_level: str | None = None,
    technology: str | None = None,
    source: str | None = None,
    company: str | None = None,
    salary_min: int | None = Query(default=None, ge=0),
    salary_known: bool = Query(default=False),
    remote_type: RemoteType | None = None,
    status_filter: Annotated[JobStatus | None, Query(alias="status")] = None,
    published_after: datetime | None = None,
    q: str | None = None,
    profile: str | None = None,
    sort: str = Query(default="score", pattern="^(score|date)$"),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> JobsResponse:
    current_user = get_current_user(request, session)
    active_profile_key = resolve_profile_key(profile)
    filters = JobFilters(
        profile_key=active_profile_key,
        min_score=min_score,
        match_level=match_level,
        technology=technology,
        source=source,
        company=company,
        salary_min=salary_min,
        salary_known=True if salary_known else None,
        remote_type=remote_type,
        status=status_filter,
        user_id=current_user.id if current_user else None,
        published_after=published_after,
        q=q,
        sort=sort,
        order=order,
        limit=limit,
        offset=offset,
    )
    jobs = repository.list_jobs(session, filters)
    user_statuses = (
        repository.get_user_statuses(session, current_user.id, jobs) if current_user else {}
    )
    items = [job_offer_to_read(job, status_override=user_statuses.get(str(job.id))) for job in jobs]
    return JobsResponse(items=items, limit=limit, offset=offset)


@router.get("/jobs/export")
def export_jobs(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    min_score: int | None = Query(default=None, ge=0, le=100),
    profile: str | None = None,
) -> StreamingResponse:
    current_user = get_current_user(request, session)
    active_profile_key = resolve_profile_key(profile)
    filters = JobFilters(
        profile_key=active_profile_key,
        min_score=min_score,
        user_id=current_user.id if current_user else None,
        limit=10_000,
    )
    jobs = repository.list_jobs(session, filters)
    user_statuses = (
        repository.get_user_statuses(session, current_user.id, jobs) if current_user else {}
    )
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(
        ["id", "score", "level", "company", "title", "salary/rate", "location", "status", "url"]
    )
    for job in jobs:
        effective_status = user_statuses.get(str(job.id), job.status)
        writer.writerow(
            [
                str(job.id),
                job.match_score,
                job.match_level,
                job.company.name,
                job.title,
                _salary_label(
                    job.salary_min, job.salary_max, job.salary_currency, job.salary_unknown
                ),
                job.location or "",
                effective_status.value,
                job.url or "",
            ]
        )
    stream.seek(0)
    filename = f"jobradar_{active_profile_key}_jobs.csv"
    headers = {"Content-Disposition": f"attachment; filename={filename}"}
    return StreamingResponse(iter([stream.getvalue()]), media_type="text/csv", headers=headers)


@router.get("/jobs/{job_id}", response_model=JobOfferRead)
def get_job(
    request: Request,
    job_id: uuid.UUID,
    session: Annotated[Session, Depends(get_session)],
) -> JobOfferRead:
    current_user = get_current_user(request, session)
    job = repository.get_job(session, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if current_user is None:
        return job_offer_to_read(job)
    user_status = repository.get_user_statuses(session, current_user.id, [job]).get(str(job.id))
    return job_offer_to_read(job, status_override=user_status)


@router.post("/jobs/{job_id}/status", response_model=JobOfferRead)
def update_job_status(
    request: Request,
    job_id: uuid.UUID,
    payload: JobStatusUpdate,
    session: Annotated[Session, Depends(get_session)],
) -> JobOfferRead:
    current_user = _require_user(request, session)
    job = repository.update_user_status(
        session, user_id=current_user.id, job_id=job_id, status=payload.status
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    session.commit()
    return job_offer_to_read(job, status_override=payload.status)


@router.post("/ingestion/run", response_model=IngestionSummary)
async def run_ingestion(
    request: Request, session: Annotated[Session, Depends(get_session)]
) -> IngestionSummary:
    _require_user(request, session)
    service = IngestionService()
    return await service.run_enabled_sources(session)


@router.get("/ingestion/runs", response_model=list[IngestionRunRead])
def ingestion_runs(
    session: Annotated[Session, Depends(get_session)],
    limit: int = Query(default=50, ge=1, le=200),
) -> list[IngestionRunRead]:
    return [
        IngestionRunRead.model_validate(run)
        for run in repository.list_ingestion_runs(session, limit)
    ]


@router.get("/sources", response_model=list[SourceRead])
def sources(
    session: Annotated[Session, Depends(get_session)],
    profile: str | None = None,
) -> list[SourceRead]:
    IngestionService().sync_configured_sources(session)
    active_profile_key = resolve_profile_key(profile)
    return [
        SourceRead.model_validate(source)
        for source in repository.list_sources(session, profile_key=active_profile_key)
    ]


def _require_user(request: Request, session: Session) -> User:
    current_user = get_current_user(request, session)
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Login required")
    return current_user


def _render_auth(
    request: Request,
    *,
    mode: str,
    error: str | None = None,
    email: str = "",
    display_name: str = "",
    status_code: int = status.HTTP_200_OK,
) -> Response:
    return templates.TemplateResponse(
        request=request,
        name="auth.html",
        status_code=status_code,
        context={
            "request": request,
            "mode": mode,
            "error": error,
            "email": email,
            "display_name": display_name,
            "public_registration_enabled": get_settings().public_registration_enabled,
        },
    )


def _visible_stats(jobs: list[Any], user_statuses: dict[str, JobStatus]) -> dict[str, Any]:
    if not jobs:
        return {
            "total": 0,
            "average_score": 0.0,
            "by_status": {},
            "by_match_level": {},
        }
    statuses = [
        str(user_statuses.get(str(job.id), job.status).value)
        for job in jobs
    ]
    return {
        "total": len(jobs),
        "average_score": round(sum(job.match_score for job in jobs) / len(jobs), 1),
        "by_status": dict(Counter(statuses)),
        "by_match_level": dict(Counter(job.match_level for job in jobs)),
    }


def _salary_label(
    salary_min: int | None,
    salary_max: int | None,
    currency: str | None,
    salary_unknown: bool,
) -> str:
    return salary_label(salary_min, salary_max, currency, salary_unknown)
