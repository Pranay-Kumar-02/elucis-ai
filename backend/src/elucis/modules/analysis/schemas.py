"""API schemas for analysis runs (D09 API-31, API-32)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

RunStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]


class RunIn(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RunOut(BaseModel):
    id: uuid.UUID
    status: RunStatus
    is_current: bool = Field(description="The run the workspace's results come from")
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    job_id: uuid.UUID | None
    step: str | None = Field(description="The step running now, while the run is in progress")
    progress: dict[str, Any] | None
    config: dict[str, Any]
    report: dict[str, Any] | None
    error: str | None


class AnalysisStatusOut(BaseModel):
    """What the dashboard needs to offer a run (UI-05)."""

    analysable_records: int
    records_since_last_run: int
    current_run: RunOut | None
    latest_run: RunOut | None
