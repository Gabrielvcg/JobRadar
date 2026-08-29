from __future__ import annotations

from fastapi import FastAPI

from app.api.routes import router
from app.core.logging import configure_logging

configure_logging()

app = FastAPI(
    title="JobRadar",
    version="0.1.33",
    description="Collect, normalize, score, and track job offers for a backend/cloud career path.",
)
app.include_router(router)
