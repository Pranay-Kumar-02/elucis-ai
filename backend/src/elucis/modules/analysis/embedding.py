"""Step ``embed`` (SVC-08, DR-26): a vector for every analysable record that has none for
the current model, in batches of 64, L2-normalised, stored with the model ID.

A failing batch is retried twice (DR-38); then its records are embedded one by one, and a
record that still fails is marked ``embedding_failed`` for this run only (D06 §10.2). Only
masked ``processed_text`` is ever sent to the model (DR-29).
"""

from __future__ import annotations

import logging
import math
import uuid
from typing import Any

from sqlalchemy import and_, exists, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from elucis.ai.ollama import InvalidModelOutputError
from elucis.core.errors import ModelUnavailableError
from elucis.db.models import FeedbackRecord, RecordClassification, RecordEmbedding
from elucis.db.models._common import CURRENT_EMBEDDING_MODEL, EMBEDDING_DIMENSION
from elucis.modules.analysis.config import EMBED_BATCH_SIZE, EMBED_RETRIES
from elucis.modules.analysis.context import RunContext
from elucis.modules.analysis.gateway import ModelGateway, log_call
from elucis.workers.runtime import JobContext

logger = logging.getLogger(__name__)

EmbedErrors = (ModelUnavailableError, InvalidModelOutputError)


def normalise(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vector))
    if norm == 0:
        raise InvalidModelOutputError("zero-length embedding")
    return [x / norm for x in vector]


def embed_texts(
    gateway: ModelGateway, texts: list[str], log: Any = None, attempt: int = 1
) -> list[list[float]]:
    """Normalised vectors for texts (also used for request asks in SVC-12)."""
    result = gateway.embed(
        texts, model=CURRENT_EMBEDDING_MODEL, expected_dimension=EMBEDDING_DIMENSION
    )
    if log is not None:
        log(texts, "ok", attempt, result.stats)
    return [normalise(v) for v in result.vectors]


def _pending(ctx: JobContext, run_id: uuid.UUID) -> Any:
    fr, emb, rc = FeedbackRecord, RecordEmbedding, RecordClassification
    return (
        select(fr.id, fr.processed_text)
        .where(
            fr.workspace_id == ctx.job.workspace_id,
            fr.analysable.is_(True),
            ~exists().where(
                and_(
                    emb.workspace_id == fr.workspace_id,
                    emb.record_id == fr.id,
                    emb.model_id == CURRENT_EMBEDDING_MODEL,
                )
            ),
            ~exists().where(
                and_(
                    rc.workspace_id == fr.workspace_id,
                    rc.record_id == fr.id,
                    rc.analysis_run_id == run_id,
                )
            ),
        )
        .order_by(fr.created_at, fr.id)
        .limit(EMBED_BATCH_SIZE)
    )


def embed_step(ctx: JobContext, run: RunContext) -> None:
    run_id, gateway = run.run_id, run.gateway
    done = 0
    while True:
        with ctx.step() as (db, queue):
            batch = db.execute(_pending(ctx, run_id)).all()
            if not batch:
                return
            ids = [r.id for r in batch]
            texts = [r.processed_text or "" for r in batch]

            def log(inputs: list[str], outcome: str, attempt: int, stats: Any = None) -> None:
                log_call(
                    db,
                    workspace_id=ctx.job.workspace_id,
                    job_id=ctx.job.id,
                    call_id="EMBED",
                    model=CURRENT_EMBEDDING_MODEL,
                    inputs=inputs,
                    outcome=outcome,
                    attempt=attempt,
                    stats=stats,
                )

            vectors = _embed_with_fallback(gateway, texts, log)
            stored = [
                {
                    "workspace_id": ctx.job.workspace_id,
                    "record_id": rid,
                    "model_id": CURRENT_EMBEDDING_MODEL,
                    "embedding": vec,
                }
                for rid, vec in zip(ids, vectors, strict=True)
                if vec is not None
            ]
            failed = [rid for rid, vec in zip(ids, vectors, strict=True) if vec is None]
            if stored:
                db.execute(pg_insert(RecordEmbedding).values(stored).on_conflict_do_nothing())
            if failed:
                db.execute(
                    pg_insert(RecordClassification).values(
                        [
                            {
                                "workspace_id": ctx.job.workspace_id,
                                "analysis_run_id": run_id,
                                "record_id": rid,
                                "status": "embedding_failed",
                            }
                            for rid in failed
                        ]
                    )
                )
            done += len(batch)
            queue.checkpoint(ctx.job, {"step": "embed"}, {"step": "embed", "embedded": done})


def _embed_with_fallback(
    gateway: ModelGateway, texts: list[str], log: Any
) -> list[list[float] | None]:
    for attempt in range(1, EMBED_RETRIES + 2):  # first try plus two retries
        try:
            return list(embed_texts(gateway, texts, log, attempt))
        except EmbedErrors as exc:
            log(texts, _outcome(exc), attempt)
            logger.warning("embedding batch failed", extra={"attempt": attempt})
    out: list[list[float] | None] = []
    unavailable = 0
    for text in texts:  # one by one, so one bad record cannot sink the batch
        try:
            out.append(embed_texts(gateway, [text], log)[0])
        except EmbedErrors as exc:
            log([text], _outcome(exc), 1)
            unavailable += isinstance(exc, ModelUnavailableError)
            out.append(None)
    if unavailable == len(texts):
        # The runtime itself is down: fail the step (the job retries later) instead of
        # marking every record as failed.
        raise ModelUnavailableError("The embedding model did not answer.")
    return out


def _outcome(exc: Exception) -> str:
    if isinstance(exc, InvalidModelOutputError):
        return "invalid_output"
    return "timeout" if "timed out" in str(exc) else "error"
