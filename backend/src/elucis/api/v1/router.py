"""Version 1 API router. Domain modules register their routers here as they are built."""

from __future__ import annotations

from fastapi import APIRouter

from elucis.api.v1 import health
from elucis.core.config import Settings
from elucis.modules.ingestion import router as ingestion_dev

API_PREFIX = "/api/v1"


def build_router(settings: Settings) -> APIRouter:
    router = APIRouter(prefix=API_PREFIX)
    router.include_router(health.router)
    if settings.enable_dev_endpoints and not settings.is_production:
        router.include_router(ingestion_dev.router)
    return router


def is_upload_path(path: str) -> bool:
    """Paths allowed the 20 MB upload limit instead of the 1 MB body limit."""
    return path.startswith(ingestion_dev.UPLOAD_PATH_PREFIX)
