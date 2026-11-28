"""Version 1 API router. Domain modules register their routers here as they are built."""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends

from elucis.api.auth import current_principal
from elucis.api.v1 import health
from elucis.core.config import Settings
from elucis.modules.analysis import router as analysis
from elucis.modules.identity import router as identity
from elucis.modules.imports import router as imports
from elucis.modules.ingestion import router as ingestion_dev
from elucis.modules.insights import router as insights

API_PREFIX = "/api/v1"


def build_router(settings: Settings) -> APIRouter:
    router = APIRouter(prefix=API_PREFIX)
    router.include_router(health.router)
    router.include_router(identity.auth)
    router.include_router(identity.workspaces)
    router.include_router(imports.router)
    router.include_router(analysis.router)
    router.include_router(insights.router)
    if settings.enable_dev_endpoints and not settings.is_production:
        # Development-only, but still behind sign-in (FR-AUTH-02, IMP-28).
        router.include_router(ingestion_dev.router, dependencies=[Depends(current_principal)])
    return router


_FILE_UPLOAD = re.compile(r"^/api/v1/workspaces/[0-9a-fA-F-]{36}/files/?$")


def is_upload_path(path: str) -> bool:
    """Paths allowed the 20 MB upload limit instead of the 1 MB body limit."""
    return path.startswith(ingestion_dev.UPLOAD_PATH_PREFIX) or bool(_FILE_UPLOAD.match(path))
