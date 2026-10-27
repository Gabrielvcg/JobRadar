"""Bounded CSV generation with a session owned by the stream."""

from __future__ import annotations

import csv
import io
from collections.abc import Callable, Iterator

from sqlalchemy.orm import Session

from app.core.availability import current_verification
from app.formatting import salary_label
from app.repositories.jobs import JobFilters, JobRepository

EXPORT_BATCH_SIZE = 500


def iter_csv_chunks(
    session_factory: Callable[[], Session],
    filters: JobFilters,
    user_id: int,
) -> Iterator[str]:
    repository = JobRepository()
    with session_factory() as session:
        stream = io.StringIO()
        writer = csv.writer(stream)
        writer.writerow(
            [
                "id",
                "score",
                "level",
                "company",
                "title",
                "salary/rate",
                "location",
                "status",
                "url",
                "description",
                "requirements",
                "source",
                "source_enabled",
                "remote_type",
                "experience_min_years",
                "experience_max_years",
                "salary_original_text",
                "salary_currency",
                "salary_period",
                "salary_unknown",
                "radar",
                "recommendation",
                "recommendation_reason",
                "career_alignment",
                "professional_fit",
                "growth",
                "viability",
                "specialist_requirements_to_confirm",
                "uncertainties",
                "blockers",
                "availability_state",
                "availability_checked_at",
                "availability_evidence",
                "application_url",
                "publication_date",
                "expiration_date",
            ]
        )
        yield "\ufeff" + stream.getvalue()
        stream.seek(0)
        stream.truncate(0)
        batches = repository.iter_job_batches(session, filters, batch_size=EXPORT_BATCH_SIZE)
        try:
            for jobs in batches:
                user_statuses = repository.get_user_statuses(session, user_id, jobs)
                for job in jobs:
                    effective_status = user_statuses.get(str(job.id), job.status)
                    assessment = job.match_reasons.get("assessment", {})
                    proof = current_verification(job.raw_payload, job.url)
                    writer.writerow(
                        [
                            str(job.id),
                            job.match_score,
                            job.match_level,
                            job.company.name,
                            job.title,
                            salary_label(
                                job.salary_min,
                                job.salary_max,
                                job.salary_currency,
                                job.salary_unknown,
                            ),
                            job.location or "",
                            effective_status.value,
                            job.url or "",
                            job.description,
                            job.requirements or "",
                            job.source.name,
                            job.source.enabled,
                            job.remote_type.value,
                            job.experience_min_years,
                            job.experience_max_years,
                            job.salary_original_text or "",
                            job.salary_currency or "",
                            job.salary_period or "",
                            job.salary_unknown,
                            assessment.get("radar", ""),
                            assessment.get("recommendation", ""),
                            assessment.get("recommendation_reason", ""),
                            assessment.get("career_alignment", ""),
                            assessment.get("professional_fit", ""),
                            assessment.get("growth", ""),
                            assessment.get("viability", ""),
                            " | ".join(assessment.get("specialist_requirements_to_confirm", [])),
                            " | ".join(assessment.get("uncertainties", [])),
                            " | ".join(assessment.get("blockers", [])),
                            proof["state"],
                            proof.get("checked_at", ""),
                            proof.get("evidence_level", ""),
                            proof.get("application_url", ""),
                            job.publication_date.isoformat() if job.publication_date else "",
                            job.expiration_date.isoformat() if job.expiration_date else "",
                        ]
                    )
                yield stream.getvalue()
                stream.seek(0)
                stream.truncate(0)
                del job, jobs, user_statuses
        finally:
            batches.close()
