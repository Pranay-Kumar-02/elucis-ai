"""Version 1 API router. Domain modules register their routers here as they are built."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from elucis.api.auth import current_principal
from elucis.api.v1 import health
from elucis.core.config import Settings
from elucis.modules.identity import router as identity
from elucis.modules.ingestion import router as ingestion_dev

API_PREFIX = "/api/v1"


def build_router(settings: Settings) -> APIRouter:
    router = APIRouter(prefix=API_PREFIX)
    router.include_router(health.router)
    router.include_router(identity.auth)
    router.include_router(identity.workspaces)
    if settings.enable_dev_endpoints and not settings.is_production:
        # Development-only, but still behind sign-in (FR-AUTH-02, IMP-28).
        router.include_router(ingestion_dev.router, dependencies=[Depends(current_principal)])
    return router


def is_upload_path(path: str) -> bool:
    """Paths allowed the 20 MB upload limit instead of the 1 MB body limit."""
    return path.startswith(ingestion_dev.UPLOAD_PATH_PREFIX)
