"""Step ``classify`` (SVC-09 Stage B, CP-02): category and sentiment for every embedded,
analysable record, in batches of 10 with stable keys ``r1..r10`` (ADR-07).

Cold start (D03 SVC-09): there is no labelled training split yet, so the calibrated
classifier (Stage A) and confidence calibration are not used; every label comes from CP-02
with ``method='llm'`` and no confidence (IMP-33). A batch whose reply is invalid after
retries is classified record by record; a record that still fails is ``unclassified``.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import and_, exists, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from elucis.ai.prompts import CP02, Cp02Out, render_records
from elucis.db.models import FeedbackRecord, RecordClassification, RecordEmbedding
from elucis.db.models._common import CURRENT_EMBEDDING_MODEL
from elucis.modules.analysis.context import RunContext
from elucis.modules.analysis.tasks import (
    OutputRuleError,
    TaskContext,
    flush_calls,
    register_prompts,
    run_task,
)
from elucis.workers.runtime import JobContext

BATCH = 10  # D04 CP-02


def keys_exactly(expected: list[str]) -> Any:
    """CP-02 rule: every key exactly once (AIR-01); enums are checked by the schema."""

    def check(out: Cp02Out) -> None:
        got = [i.key for i in out.items]
        if sorted(got) != sorted(expected):
            raise OutputRuleError(f"expected the keys {expected} exactly once, got {got}")

    return check


def _pending(ws: uuid.UUID, run_id: uuid.UUID) -> Any:
    fr, emb, rc = FeedbackRecord, RecordEmbedding, RecordClassification
    return (
        select(fr.id, fr.processed_text)
        .join(
            emb,
            and_(
                emb.workspace_id == fr.workspace_id,
                emb.record_id == fr.id,
                emb.model_id == CURRENT_EMBEDDING_MODEL,
            ),
        )
        .where(
            fr.workspace_id == ws,
            fr.analysable.is_(True),
            ~exists().where(
                and_(
                    rc.workspace_id == fr.workspace_id,
                    rc.record_id == fr.id,
                    rc.analysis_run_id == run_id,
                )
            ),
        )
        .order_by(fr.created_at, fr.row_number, fr.segment_index, fr.id)
        .limit(BATCH)
    )


def classify_batch(tc: TaskContext, texts: list[str]) -> list[tuple[str, str] | None]:
    """[(category, sentiment)] per text, ``None`` where the model gave no valid label."""
    keys = [f"r{i + 1}" for i in range(len(texts))]
    out = run_task(
        tc, CP02, render_records(list(zip(keys, texts, strict=True))), Cp02Out, keys_exactly(keys)
    )
    if out is not None:
        by_key = {i.key: (i.category, i.sentiment) for i in out.items}
        return [by_key[k] for k in keys]
    if len(texts) == 1:
        return [None]
    return [classify_batch(tc, [t])[0] for t in texts]  # one by one (D04 CP-02 fallback)


def classify_step(ctx: JobContext, run: RunContext) -> None:
    """Per batch: read (short transaction) -> CP-02 (no transaction open) -> write the labels,
    the call records and the checkpoint together."""
    ws, run_id = ctx.job.workspace_id, run.run_id
    with ctx.step() as (db, _queue):
        prompt_ids = register_prompts(db, CP02)
    done = 0
    while True:
        with ctx.step() as (db, _queue):
            batch = db.execute(_pending(ws, run_id)).all()
        if not batch:
            return
        tc = TaskContext(
            run.gateway,
            ws,
            ctx.job.id,
            run.chat_model,
            prompt_ids,
            fallback=run.fallback,
            fallback_model=run.fallback_model,
        )
        labels = classify_batch(tc, [r.processed_text or "" for r in batch])
        rows = []
        for record, label in zip(batch, labels, strict=True):
            row: dict[str, Any] = {
                "workspace_id": ws,
                "analysis_run_id": run_id,
                "record_id": record.id,
                "status": "unclassified",
                "category": None,
                "sentiment": None,
                "method": None,
            }
            if label is not None:
                row.update(status="classified", category=label[0], sentiment=label[1], method="llm")
            rows.append(row)
        with ctx.step() as (db, queue):
            db.execute(pg_insert(RecordClassification).values(rows).on_conflict_do_nothing())
            flush_calls(db, tc)
            done += len(batch)
            queue.checkpoint(
                ctx.job, {"step": "classify"}, {"step": "classify", "classified": done}
            )
