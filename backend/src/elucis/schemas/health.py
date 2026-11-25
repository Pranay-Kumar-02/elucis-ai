"""Health-check response schemas (D09 API-87 ``{status, checks}``)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

CheckStatus = Literal["ok", "unavailable", "not_configured"]
OverallStatus = Literal["ok", "degraded", "unavailable"]


class CheckOut(BaseModel):
    status: CheckStatus
    latency_ms: float | None = None
    detail: str | None = None


class HealthOut(BaseModel):
    status: OverallStatus
    service: str
    version: str
    checks: dict[str, CheckOut]


class LivenessOut(BaseModel):
    status: Literal["ok"]


class DatabaseHealthOut(BaseModel):
    status: CheckStatus
    latency_ms: float | None = None
    server_version: str | None = None
    pgvector_version: str | None = None
    database: str | None = None
    role: str | None = None
    detail: str | None = None


class ModelRuntimeHealthOut(BaseModel):
    status: CheckStatus
    latency_ms: float | None = None
    ollama_version: str | None = None
    models: dict[str, bool] | None = None
    detail: str | None = None
