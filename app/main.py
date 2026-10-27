from __future__ import annotations

from importlib.metadata import version

from fastapi import FastAPI

from app.api.routes import router
from app.core.logging import configure_logging

configure_logging()

app = FastAPI(
    title="JobRadar",
    version=version("jobradar"),
    description="Collect, normalize, score, and track job offers for a backend/cloud career path.",
)
app.include_router(router)
