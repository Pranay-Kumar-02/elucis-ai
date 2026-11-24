"""Health service: probes the database, the model runtime and the worker.

Overall status follows AIR-22 / NFR-11: the database is required (``unavailable`` -> HTTP 503);
a missing model runtime only degrades the product, because non-AI features keep working.
Version details are returned only when diagnostics are enabled (never by default in production).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from copilot import __version__
from copilot.ai.ollama import OllamaClient
from copilot.core.config import Settings
from copilot.core.errors import AppError
from copilot.db.engine import get_engine
from copilot.repositories.system import DatabaseInfo, SystemRepository, pgvector_ok
from copilot.schemas.health import (
    CheckOut,
    DatabaseHealthOut,
    HealthOut,
    ModelRuntimeHealthOut,
    OverallStatus,
)

logger = logging.getLogger(__name__)
MODEL_PROBE_TIMEOUT_S = 2.0


@dataclass(frozen=True, slots=True)
class DbProbe:
    ok: bool
    latency_ms: float | None
    info: DatabaseInfo | None
    reason: str | None


def _elapsed(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 1)


def probe_database(settings: Settings) -> DbProbe:
    started = time.perf_counter()
    try:
        with get_engine("api", settings).connect() as conn:
            info = SystemRepository(conn).info()
    except AppError as exc:  # not configured
        return DbProbe(False, None, None, exc.message)
    except Exception as exc:
        logger.warning("database probe failed", extra={"error": type(exc).__name__})
        return DbProbe(False, _elapsed(started), None, "connection failed")
    if not pgvector_ok(info.pgvector_installed):
        return DbProbe(
            False, _elapsed(started), info, "pgvector extension missing or older than 0.8"
        )
    return DbProbe(True, _elapsed(started), info, None)


def database_health(settings: Settings) -> DatabaseHealthOut:
    probe = probe_database(settings)
    show = settings.diagnostics_enabled
    info = probe.info
    return DatabaseHealthOut(
        status="ok" if probe.ok else "unavailable",
        latency_ms=probe.latency_ms,
        server_version=info.server_version if (show and info) else None,
        pgvector_version=info.pgvector_installed if (show and info) else None,
        database=info.database if (show and info) else None,
        role=info.current_user if (show and info) else None,
        detail=probe.reason,
    )


def model_runtime_health(settings: Settings) -> ModelRuntimeHealthOut:
    started = time.perf_counter()
    try:
        with OllamaClient(settings, timeout_s=MODEL_PROBE_TIMEOUT_S) as client:
            version = client.version()
            names = {m.get("name") for m in client.list_models()}
    except Exception as exc:
        logger.info("model runtime probe failed", extra={"error": type(exc).__name__})
        return ModelRuntimeHealthOut(
            status="unavailable", latency_ms=_elapsed(started), detail="not reachable"
        )
    models = {
        settings.ollama_chat_model: settings.ollama_chat_model in names,
        settings.ollama_embed_model: settings.ollama_embed_model in names,
    }
    missing = [name for name, present in models.items() if not present]
    show = settings.diagnostics_enabled
    return ModelRuntimeHealthOut(
        status="ok" if not missing else "unavailable",
        latency_ms=_elapsed(started),
        ollama_version=version if show else None,
        models=models if show else None,
        detail=f"model not pulled: {', '.join(missing)}" if missing else None,
    )


def overall_health(settings: Settings) -> HealthOut:
    db = database_health(settings)
    model = model_runtime_health(settings)
    worker = CheckOut(
        status="not_configured",
        detail="worker heartbeat is read from the jobs table, created in the schema task",
    )
    status: OverallStatus = "ok"
    if db.status != "ok":
        status = "unavailable"
    elif model.status != "ok":
        status = "degraded"
    return HealthOut(
        status=status,
        service="copilot-api",
        version=__version__,
        checks={
            "database": CheckOut(status=db.status, latency_ms=db.latency_ms, detail=db.detail),
            "model_runtime": CheckOut(
                status=model.status, latency_ms=model.latency_ms, detail=model.detail
            ),
            "worker": worker,
        },
    )
