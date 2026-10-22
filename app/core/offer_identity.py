"""Provenance for employer listings and their portal mirrors."""

from __future__ import annotations

from urllib.parse import urlsplit

ORIGINS_KEY = "_jobradar_origins"
TEAMTAILOR_HOSTS = {"careers.twtspain.com", "jobs.talentconnect.ai"}
EMPLOYER_HOSTS = {
    "jobs.experienceis.com",
    "www.sngular.com",
    "jobs.smartrecruiters.com",
    "jobs.lever.co",
    "jobs.eu.lever.co",
    "boards.greenhouse.io",
    "job-boards.greenhouse.io",
    "apply.workable.com",
    "jobs.ashbyhq.com",
} | TEAMTAILOR_HOSTS
EMPLOYER_SUFFIXES = (
    ".teamtailor.com",
    ".applytojob.com",
    ".jobs.personio.de",
    ".jobs.personio.com",
    ".recruitee.com",
    ".pinpointhq.com",
)
PORTAL_HOSTS = {
    "himalayas.app",
    "remotive.com",
    "remoteok.com",
    "weworkremotely.com",
    "jobicy.com",
    "www.arbeitnow.com",
}


def is_employer_listing(url: str | None) -> bool:
    host = urlsplit(url or "").hostname or ""
    return host in EMPLOYER_HOSTS or host.endswith(EMPLOYER_SUFFIXES)


def is_portal_listing(url: str | None) -> bool:
    return urlsplit(url or "").hostname in PORTAL_HOSTS
