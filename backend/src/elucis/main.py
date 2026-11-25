"""FastAPI application factory and ASGI entry point.

Run for development (factory mode: nothing is configured at import time)::

    uv run uvicorn elucis.main:create_app --factory --reload --port 8000

Middleware order (outermost first): security headers -> CORS -> request context (request ID,
body limits, access log, last-resort error envelope) -> routes.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from elucis import __version__
from elucis.api.v1.router import API_PREFIX, build_router, is_upload_path
from elucis.core.config import Settings, get_settings
from elucis.core.errors import register_exception_handlers
from elucis.core.logging import configure_logging
from elucis.core.middleware import (
    REQUEST_ID_HEADER,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)
from elucis.db.engine import dispose_engines

logger = logging.getLogger("elucis")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.log_format.value)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        logger.info(
            "api starting",
            extra={
                "env": settings.app_env.value,
                "version": __version__,
                "database": settings.dsn_redacted("api") or "not configured",
                "dev_endpoints": settings.enable_dev_endpoints and not settings.is_production,
            },
        )
        yield
        dispose_engines()
        logger.info("api stopped")

    docs = not settings.is_production
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        summary="AI-driven product assistant based on customer feedback",
        openapi_url=f"{API_PREFIX}/openapi.json" if docs else None,
        docs_url=f"{API_PREFIX}/docs" if docs else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    register_exception_handlers(app)

    # add_middleware wraps: the last added runs first (outermost). CORS sits outside the
    # request-context layer so that its 413 and 500 responses also carry CORS headers.
    app.add_middleware(
        RequestContextMiddleware,
        max_body_bytes=settings.api_max_body_bytes,
        upload_max_bytes=settings.upload_max_bytes,
        is_upload_path=is_upload_path,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api_cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-CSRF-Token", "Idempotency-Key", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
        max_age=600,
    )
    app.add_middleware(SecurityHeadersMiddleware, csp_exempt_prefixes=(f"{API_PREFIX}/docs",))

    app.include_router(build_router(settings))
    return app


__all__ = ["REQUEST_ID_HEADER", "create_app"]
