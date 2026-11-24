"""Health endpoints (D09 API-87, AIR-22, NFR-11). Unauthenticated; return no customer data."""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from copilot.api.deps import SettingsDep
from copilot.schemas.health import (
    DatabaseHealthOut,
    HealthOut,
    LivenessOut,
    ModelRuntimeHealthOut,
)
from copilot.services import health as health_service

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthOut, summary="Readiness: database, model runtime, worker")
def health(settings: SettingsDep, response: Response) -> HealthOut:
    result = health_service.overall_health(settings)
    if result.status == "unavailable":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return result


@router.get("/live", response_model=LivenessOut, summary="Liveness: the process is serving")
def live() -> LivenessOut:
    return LivenessOut(status="ok")


@router.get("/database", response_model=DatabaseHealthOut, summary="PostgreSQL and pgvector")
def database(settings: SettingsDep, response: Response) -> DatabaseHealthOut:
    result = health_service.database_health(settings)
    if result.status != "ok":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return result


@router.get("/model-runtime", response_model=ModelRuntimeHealthOut, summary="Ollama and models")
def model_runtime(settings: SettingsDep, response: Response) -> ModelRuntimeHealthOut:
    result = health_service.model_runtime_health(settings)
    if result.status != "ok":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return result
