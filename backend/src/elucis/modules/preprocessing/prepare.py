"""Preprocess one batch of validated rows into ``feedback_records`` rows (D06 §3).

Order per record: clean -> noise -> standardise -> PII masking -> exact duplicates. The
first exclusion that applies wins (D06 §3.1). Each record ends in exactly one outcome:
analysable (``stage='prepared'``), excluded with one reason, or failed (``stage='failed'``
plus a ``failed`` row error naming the stage). Masking failures fail closed (``pii_failed``,
no processed text), so unmasked text can never reach analysis or a model (DR-29).

Called inside the ingest job's batch transaction::

    rows, failures = prepare_batch(db, ctx, records)
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from elucis.db.models import Customer, FeedbackRecord
from elucis.modules.ingestion.validation import MAX_TEXT_CHARS, NormalizedRecord
from elucis.modules.preprocessing import duplicates
from elucis.modules.preprocessing.clean import clean_text
from elucis.modules.preprocessing.noise import is_noise
from elucis.modules.preprocessing.pii import Masked
from elucis.modules.preprocessing.pii import mask as default_mask
from elucis.modules.preprocessing.standardise import customer_key, product_version, rating_1_to_5

logger = logging.getLogger(__name__)

# Speaker labels that are roles, not people; anything else is masked as a name.
ROLE_SPEAKERS = frozenset(
    {"customer", "user", "agent", "support", "interviewer", "interviewee", "host", "moderator",
     "participant", "pm", "speaker", "caller", "rep", "me", "q", "a"}
)  # fmt: skip


@dataclass(slots=True)
class BatchContext:
    workspace_id: uuid.UUID
    import_job_id: uuid.UUID
    customer_secret: bytes
    rating_scale: float | None
    mask: Callable[[str], Masked] = default_mask


@dataclass(slots=True)
class _Work:
    """One record on its way through the stages."""

    rec: NormalizedRecord
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    stage: str = "captured"
    reason: str | None = None
    processed: str | None = None
    speaker: str | None = None
    pii: dict[str, int] = field(default_factory=dict)
    key: bytes | None = None
    customer_id: uuid.UUID | None = None
    rating: int | None = None
    version: str | None = None
    content_hash: bytes | None = None
    duplicate_of: uuid.UUID | None = None
    failure: tuple[str, str] | None = None  # (stage, message)


def prepare_batch(
    db: Session, ctx: BatchContext, records: list[NormalizedRecord]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Returns (feedback_records rows, failed import_row_errors rows)."""
    work = [_Work(r) for r in records]
    for w in work:
        _per_record(ctx, w)
    _resolve_customers(db, ctx, [w for w in work if w.failure is None])
    _mark_duplicates(db, ctx, work)
    return [_row(ctx, w) for w in work], [_failure_row(ctx, w) for w in work if w.failure]


# ---------------------------------------------------------------- stages per record
def _per_record(ctx: BatchContext, w: _Work) -> None:
    rec = w.rec
    try:
        text = rec.raw_text[:MAX_TEXT_CHARS]  # longer text is analysed in part (SVC-04)
        cleaned = clean_text(text)
        w.stage = "cleaned"
    except Exception as exc:  # deterministic code: a failure is permanent, no retry
        w.failure = ("cleaning", f"Cleaning failed ({type(exc).__name__}).")
        return
    if is_noise(cleaned):
        w.reason = "noise"
    try:
        w.rating = rating_1_to_5(rec.rating_value, rec.rating_out_of, ctx.rating_scale)
        w.version = product_version(rec.product_version_raw)
        w.key = customer_key(ctx.customer_secret, rec.customer_ref)
        w.stage = "standardised"
    except Exception as exc:
        w.failure = ("standardisation", f"Standardisation failed ({type(exc).__name__}).")
        return
    try:
        masked = ctx.mask(cleaned)
        w.processed, w.pii = masked.text, masked.counts
        w.speaker = _speaker(ctx, rec.speaker)
        w.stage = "masked"
    except Exception:
        logger.exception("PII masking failed; record excluded (fail closed)")
        w.processed, w.pii, w.speaker = None, {}, None
        w.reason = w.reason or "pii_failed"
        return
    if w.reason is None:
        w.content_hash = duplicates.content_hash(w.processed)


def _speaker(ctx: BatchContext, label: str | None) -> str | None:
    if not label:
        return None
    if label.strip().casefold() in ROLE_SPEAKERS:
        return label.strip()
    masked = ctx.mask(label)
    return masked.text if masked.counts else "[NAME]"


# ---------------------------------------------------------------- batch stages
def _resolve_customers(db: Session, ctx: BatchContext, work: list[_Work]) -> None:
    """Upsert one ``customers`` row per key (DR-23); first and last seen from the dates."""
    seen: dict[bytes, list[datetime | None]] = {}
    for w in work:
        if w.key is not None:
            seen.setdefault(w.key, []).append(w.rec.occurred_at)
    if not seen:
        return
    values = []
    for key, dates in seen.items():
        known = [d for d in dates if d is not None]
        values.append(
            {
                "workspace_id": ctx.workspace_id,
                "customer_key": key,
                "first_seen_at": min(known) if known else None,
                "last_seen_at": max(known) if known else None,
            }
        )
    insert = pg_insert(Customer).values(values)
    rows = db.execute(
        insert.on_conflict_do_update(
            index_elements=["workspace_id", "customer_key"],
            set_={
                "first_seen_at": func.least(Customer.first_seen_at, insert.excluded.first_seen_at),
                "last_seen_at": func.greatest(Customer.last_seen_at, insert.excluded.last_seen_at),
            },
        ).returning(Customer.customer_key, Customer.id)
    ).all()
    ids = {bytes(k): i for k, i in rows}
    for w in work:
        if w.key is not None:
            w.customer_id = ids[w.key]


def _mark_duplicates(db: Session, ctx: BatchContext, work: list[_Work]) -> None:
    hashes = list({w.content_hash for w in work if w.content_hash is not None})
    if not hashes:
        return
    fr = FeedbackRecord
    earlier = [
        duplicates.Candidate(
            r.id,
            bytes(r.content_hash),
            r.customer_id,
            r.source_type,
            r.occurred_at,
            r.import_job_id,
        )
        for r in db.execute(
            select(
                fr.id,
                fr.content_hash,
                fr.customer_id,
                fr.source_type,
                fr.occurred_at,
                fr.import_job_id,
            )
            .where(
                and_(
                    fr.workspace_id == ctx.workspace_id,
                    fr.content_hash.in_(hashes),
                    fr.exclusion_reason.is_(None),
                    fr.stage != "failed",
                )
            )
            .order_by(fr.created_at, fr.row_number, fr.segment_index)
        ).all()
    ]
    for w in work:  # in file order, so the first copy in this batch is the primary
        if w.content_hash is None or w.failure is not None:
            continue
        candidate = duplicates.Candidate(
            w.id,
            w.content_hash,
            w.customer_id,
            w.rec.source_type.value,
            w.rec.occurred_at,
            ctx.import_job_id,
        )
        primary = duplicates.find_primary(candidate, earlier)
        if primary is not None:
            w.reason, w.duplicate_of = "duplicate", primary
        else:
            earlier.append(candidate)


# ---------------------------------------------------------------- rows
def _row(ctx: BatchContext, w: _Work) -> dict[str, Any]:
    rec = w.rec
    failed = w.failure is not None
    analysable = not failed and w.reason is None
    return {
        "id": w.id,
        "workspace_id": ctx.workspace_id,
        "import_job_id": ctx.import_job_id,
        "row_number": rec.row_number,
        "segment_index": rec.segment_index,
        "source_type": rec.source_type.value,
        "source_record_id": rec.source_record_id,
        "raw_text": rec.raw_text,
        "processed_text": None if failed else w.processed,
        "content_hash": w.content_hash if analysable or w.reason == "duplicate" else None,
        "customer_id": w.customer_id,
        "speaker": w.speaker,
        "occurred_at": rec.occurred_at,
        "occurred_at_missing": rec.occurred_at is None,  # missing or unreadable (DR-08)
        "rating": w.rating,
        "rating_raw": rec.rating_raw,
        "product_version": w.version,
        "stage": "failed" if failed else ("prepared" if analysable else w.stage),
        "analysable": analysable,
        "exclusion_reason": None if failed else w.reason,
        "duplicate_of": w.duplicate_of,
        "pii_counts": w.pii,
        "metadata_": rec.metadata,
    }


def _failure_row(ctx: BatchContext, w: _Work) -> dict[str, Any]:
    assert w.failure is not None  # noqa: S101 - filtered by the caller
    stage, message = w.failure
    return {
        "workspace_id": ctx.workspace_id,
        "import_job_id": ctx.import_job_id,
        "row_number": w.rec.row_number,
        "kind": "failed",
        "stage": stage,
        "field": None,
        "code": f"{stage}_failed",
        "message": message,
    }
