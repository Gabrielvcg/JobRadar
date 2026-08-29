from __future__ import annotations

from enum import StrEnum


class RemoteType(StrEnum):
    ONSITE = "onsite"
    HYBRID = "hybrid"
    REMOTE = "remote"
    UNKNOWN = "unknown"


class JobStatus(StrEnum):
    NEW = "new"
    REVIEWED = "reviewed"
    INTERESTED = "interested"
    APPLIED = "applied"
    REJECTED = "rejected"
    EXPIRED = "expired"
