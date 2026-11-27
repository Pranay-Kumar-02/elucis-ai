"""The ``ingest`` job (SVC-03, D06 §2): read the stored file in batches, store valid rows as
``feedback_records`` and rejected rows as ``import_row_errors``, then reconcile.

Restartable (DR-39): each batch of 500 rows is one transaction that also saves the cursor,
so a crash resumes at the last committed batch; inserts are keyed by (import, row, segment),
so a repeated batch can never store a row twice (FR-ING-07).

Call chain::

    run_ingest(ctx, settings)
      _start(...)            -> import row 'processing', file bytes, adapter + validator
      _ingest_batch(...)     -> one transaction per 500 rows (validate, insert, checkpoint)
      _finish(...)           -> counts, reconciliation (DR-40), report, final status
"""

from __future__ import annotations

import logging
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from elucis.core.config import Settings
from elucis.db.models import FeedbackRecord, ImportJob, ImportRowError, SourceFile
from elucis.modules.imports.service import load_source
from elucis.modules.ingestion.adapters.base import ColumnMapping, SourceType
from elucis.modules.ingestion.adapters.file_adapter import FileAdapter
from elucis.modules.ingestion.service import open_for_rows
from elucis.modules.ingestion.validation import (
    MetricObservation,
    NormalizedRecord,
    RowError,
    RowValidator,
)
from elucis.workers.runtime import JobContext

logger = logging.getLogger(__name__)

BATCH_SIZE = 500  # D03 SVC-03
FINAL_STATUSES = frozenset({"completed", "completed_with_errors", "failed", "cancelled"})


class ReconciliationError(Exception):
    """received != imported + rejected + duplicates + filtered + failed (DR-40)."""


@dataclass(slots=True)
class IngestState:
    """What the job carries between batches; saved in ``jobs.cursor`` with every batch."""

    position: int = 0
    flags: Counter[str] = field(default_factory=Counter)

    @classmethod
    def from_cursor(cls, cursor: dict[str, Any]) -> IngestState:
        return cls(int(cursor.get("position", 0)), Counter(cursor.get("flags", {})))

    def to_cursor(self) -> dict[str, Any]:
        return {"position": self.position, "flags": dict(self.flags)}


def run_ingest(ctx: JobContext, settings: Settings) -> str:
    """Job handler. Returns the job's final status."""
    import_id = uuid.UUID(str(ctx.job.payload["import_job_id"]))
    try:
        started = _start(ctx, settings, import_id)
        if started is None:  # gone, or already finished: nothing to do
            return "succeeded"
        adapter, validator = started
        state = IngestState.from_cursor(ctx.job.cursor)
        total = adapter.item_count
        while state.position < total:
            _ingest_batch(ctx, import_id, adapter, validator, state, total=total)
        return _finish(ctx, import_id, received=total, flags=state.flags)
    except Exception as exc:
        if ctx.job.attempts >= ctx.job.max_attempts:  # no retry left: say so on the import
            _mark_failed(ctx, import_id, f"Processing stopped: {type(exc).__name__}.")
        raise


# ---------------------------------------------------------------- stages
def _start(
    ctx: JobContext, settings: Settings, import_id: uuid.UUID
) -> tuple[FileAdapter, RowValidator] | None:
    with ctx.step() as (db, _queue):
        imp = _import(db, ctx.job.workspace_id, import_id)
        if imp is None or imp.status in FINAL_STATUSES:
            return None
        db.execute(
            update(ImportJob)
            .where(ImportJob.workspace_id == imp.workspace_id, ImportJob.id == import_id)
            .values(status="processing", started_at=func.coalesce(ImportJob.started_at, func.now()))
        )
        file_row = db.execute(
            select(SourceFile).where(
                SourceFile.workspace_id == imp.workspace_id, SourceFile.id == imp.source_file_id
            )
        ).scalar_one()
        source_type = SourceType(imp.source_type)
        mapping = ColumnMapping.model_validate(imp.column_mapping)
        src = load_source(settings, file_row)
    adapter = open_for_rows(src, source_type, mapping)
    return adapter, RowValidator(adapter, source_type)


def _ingest_batch(
    ctx: JobContext,
    import_id: uuid.UUID,
    adapter: FileAdapter,
    validator: RowValidator,
    state: IngestState,
    *,
    total: int,
) -> None:
    stop = min(state.position + BATCH_SIZE, total)
    ws = ctx.job.workspace_id
    records: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    flags: Counter[str] = Counter()
    for batch, _cursor in adapter.fetch_range(state.position, stop):
        for item in batch:
            result = validator.validate(item)
            if isinstance(result, RowError):
                errors.append(_rejected_row(ws, import_id, result))
            elif isinstance(result, NormalizedRecord):
                flags.update(result.flags)
                records.append(_captured_record(ws, import_id, result))
            elif isinstance(result, MetricObservation):  # refused by API-15; never reached
                raise TypeError("metric rows cannot be imported as feedback")
    with ctx.step() as (db, queue):
        if records:
            db.execute(
                pg_insert(FeedbackRecord)
                .values(records)
                .on_conflict_do_nothing(
                    index_elements=["workspace_id", "import_job_id", "row_number", "segment_index"]
                )
            )
        if errors:
            db.execute(pg_insert(ImportRowError).values(errors))
        next_state = IngestState(stop, state.flags + flags)
        queue.checkpoint(ctx.job, next_state.to_cursor(), {"processed": stop, "total": total})
    state.position, state.flags = next_state.position, next_state.flags


def _finish(ctx: JobContext, import_id: uuid.UUID, *, received: int, flags: Counter[str]) -> str:
    with ctx.step() as (db, _queue):
        report = build_report(db, ctx.job.workspace_id, import_id, received, flags)
        if report["reconciled"]:
            with_errors = report["rejected"] > 0 or report["failed"] > 0
            status = "completed_with_errors" if with_errors else "completed"
        else:
            report["error"] = "Reconciliation error: the counts do not add up to the rows received."
            status = "failed"
        db.execute(
            update(ImportJob)
            .where(ImportJob.workspace_id == ctx.job.workspace_id, ImportJob.id == import_id)
            .values(status=status, report=report, finished_at=func.now())
        )
    logger.info("import finished", extra={"import_job_id": str(import_id), "status": status})
    if status == "failed":
        return "failed"
    return "succeeded_with_errors" if status == "completed_with_errors" else "succeeded"


def _mark_failed(ctx: JobContext, import_id: uuid.UUID, message: str) -> None:
    try:
        with ctx.step() as (db, _queue):
            db.execute(
                update(ImportJob)
                .where(ImportJob.workspace_id == ctx.job.workspace_id, ImportJob.id == import_id)
                .values(status="failed", report={"error": message}, finished_at=func.now())
            )
    except Exception:
        logger.exception("could not mark the import as failed")


# ---------------------------------------------------------------- rows
def _rejected_row(ws: uuid.UUID, import_id: uuid.UUID, error: RowError) -> dict[str, Any]:
    return {
        "workspace_id": ws,
        "import_job_id": import_id,
        "row_number": error.row_number,
        "kind": "rejected",
        "stage": "validation",
        "field": error.field,
        "code": error.code,
        "message": error.message,
    }


def _captured_record(ws: uuid.UUID, import_id: uuid.UUID, rec: NormalizedRecord) -> dict[str, Any]:
    return {
        "workspace_id": ws,
        "import_job_id": import_id,
        "row_number": rec.row_number,
        "segment_index": rec.segment_index,
        "source_type": rec.source_type.value,
        "source_record_id": rec.source_record_id,
        "raw_text": rec.raw_text,
        "occurred_at": rec.occurred_at,
        "occurred_at_missing": rec.occurred_at is None,  # missing or unreadable (DR-08)
        "rating_raw": rec.rating_raw,
        "metadata_": rec.metadata,
        "stage": "captured",
    }


def _import(db: Session, ws: uuid.UUID, import_id: uuid.UUID) -> ImportJob | None:
    return db.execute(
        select(ImportJob).where(ImportJob.workspace_id == ws, ImportJob.id == import_id)
    ).scalar_one_or_none()


# ---------------------------------------------------------------- report (D06 §10.1)
def build_report(
    db: Session, ws: uuid.UUID, import_id: uuid.UUID, received: int, flags: Counter[str]
) -> dict[str, Any]:
    """Counts from the database, never from memory, so the identity proves what was stored."""
    fr = FeedbackRecord
    scope = (fr.workspace_id == ws, fr.import_job_id == import_id)
    failed = _count(db, select(func.count()).where(*scope, fr.stage == "failed"))
    reasons: dict[str | None, int] = {
        reason: int(n)
        for reason, n in db.execute(
            select(fr.exclusion_reason, func.count())
            .where(*scope, fr.stage != "failed")
            .group_by(fr.exclusion_reason)
        ).all()
    }
    rejected = _count(
        db,
        select(func.count()).where(
            ImportRowError.workspace_id == ws,
            ImportRowError.import_job_id == import_id,
            ImportRowError.kind == "rejected",
        ),
    )
    imported = reasons.pop(None, 0)
    duplicates = reasons.pop("duplicate", 0)
    filtered = {"noise": reasons.pop("noise", 0), "pii_failed": reasons.pop("pii_failed", 0)}
    filtered.update({str(k): v for k, v in reasons.items()})  # other reasons still counted
    pii: Counter[str] = Counter()
    for (counts,) in db.execute(select(fr.pii_counts).where(*scope)).all():
        pii.update({k: int(v) for k, v in (counts or {}).items()})
    first, last = db.execute(
        select(func.min(fr.occurred_at), func.max(fr.occurred_at)).where(*scope)
    ).one()
    accounted = imported + rejected + duplicates + sum(filtered.values()) + failed
    return {
        "received": received,
        "imported": imported,
        "rejected": rejected,
        "duplicates": duplicates,
        "filtered": filtered,
        "failed": failed,
        "reconciled": accounted == received,
        "flags": dict(flags),
        "pii_masked": dict(pii),
        "date_range": {"from": _iso(first), "to": _iso(last)},
        "not_checked": ["language", "spam"],  # deferred stages, stated rather than implied
    }


def _count(db: Session, query: Any) -> int:
    return int(db.execute(query).scalar_one())


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None
