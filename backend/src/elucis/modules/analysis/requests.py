"""Step ``requests`` (SVC-12, CP-04(a)): feature-request detection and grouping.

1. **Candidates** (D03 SVC-12): records CP-02 labelled ``feature_request``, plus classified
   records with a request cue ("please add", "would be great if", "I wish", "can you add").
2. **Canonical ask**: CP-04 rewrites each candidate as one ask of at most 12 words, in
   batches of 10 with keys ``r1..r10``. When the call fails even record by record, the
   cleaned text cut to 12 words is used and the membership is marked ``low_confidence``.
3. **Grouping**: the asks are embedded (not stored) and grouped by agglomerative
   clustering, cosine distance, average linkage, ``distance_threshold = 0.25``. The group's
   title is the ask closest to the group's centroid.

Deferred (IMP-34): the CP-04(b) same-or-different check for borderline pairs, request
identity across runs, renames. Every run makes new request groups; earlier ones are
archived on activation.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sqlalchemy import and_, delete, select, update

from elucis.ai.prompts import CP04, Cp04Out, render_records
from elucis.db.models import (
    AggregatedRequest,
    FeedbackRecord,
    RecordClassification,
    RequestMembership,
)
from elucis.db.models._common import CURRENT_EMBEDDING_MODEL
from elucis.modules.analysis.context import RunContext
from elucis.modules.analysis.embedding import embed_texts
from elucis.modules.analysis.tasks import (
    OutputRuleError,
    TaskContext,
    flush_calls,
    register_prompts,
    run_task,
)
from elucis.workers.runtime import JobContext

BATCH = 10
MAX_ASK_WORDS = 12  # D07 CHECK on request_memberships.canonical_ask
DISTANCE_THRESHOLD = 0.25  # D03 SVC-12, tuned on labelled pairs later (step 8)
REQUEST_CUES = re.compile(
    r"\b(please add|would be (?:great|nice) if|i wish|can you (?:please )?add|could you add|"
    r"it would be (?:great|nice) to|please (?:make|support|let|allow)|would love)\b",
    re.IGNORECASE,
)


def is_candidate(category: str | None, text: str) -> bool:
    return category == "feature_request" or bool(REQUEST_CUES.search(text))


def cut_words(text: str, limit: int = MAX_ASK_WORDS) -> str:
    return " ".join(text.split()[:limit])


def ask_rules(keys: list[str]) -> Any:
    def check(out: Cp04Out) -> None:
        got = [i.key for i in out.items]
        if sorted(got) != sorted(keys):
            raise OutputRuleError(f"expected the keys {keys} exactly once, got {got}")
        long = [i.key for i in out.items if len(i.ask.split()) > MAX_ASK_WORDS]
        if long:
            raise OutputRuleError(f"asks for {long} have more than {MAX_ASK_WORDS} words")

    return check


def canonical_asks(tc: TaskContext, texts: list[str]) -> list[str | None]:
    keys = [f"r{i + 1}" for i in range(len(texts))]
    out = run_task(
        tc, CP04, render_records(list(zip(keys, texts, strict=True))), Cp04Out, ask_rules(keys)
    )
    if out is not None:
        by_key = {i.key: i.ask.strip().rstrip(".") for i in out.items}
        return [by_key[k] for k in keys]
    if len(texts) == 1:
        return [None]
    return [canonical_asks(tc, [t])[0] for t in texts]


def group_asks(vectors: np.ndarray) -> np.ndarray:
    """Cluster labels for L2-normalised ask vectors (every ask gets a group)."""
    if len(vectors) == 1:
        return np.zeros(1, dtype=int)
    model = AgglomerativeClustering(
        n_clusters=None, metric="cosine", linkage="average", distance_threshold=DISTANCE_THRESHOLD
    )
    return np.asarray(model.fit_predict(vectors))


def requests_step(ctx: JobContext, run: RunContext) -> None:
    """Read the candidates (short transaction) -> CP-04 asks and their embeddings (no
    transaction open) -> write the groups, memberships and call records together."""
    ws, run_id = ctx.job.workspace_id, run.run_id
    fr, rc = FeedbackRecord, RecordClassification
    with ctx.step() as (db, _queue):
        prompt_ids = register_prompts(db, CP04)
        rows = db.execute(
            select(fr.id, fr.processed_text, rc.category)
            .join(rc, and_(rc.workspace_id == fr.workspace_id, rc.record_id == fr.id))
            .where(rc.workspace_id == ws, rc.analysis_run_id == run_id, rc.status == "classified")
            .order_by(fr.created_at, fr.row_number, fr.segment_index, fr.id)
        ).all()
    candidates = [
        (r.id, r.processed_text or "")
        for r in rows
        if is_candidate(r.category, r.processed_text or "")
    ]
    tc = TaskContext(run.gateway, ws, ctx.job.id, run.chat_model, prompt_ids)
    asks: list[str] = []
    low: list[bool] = []
    groups: list[tuple[str, list[int]]] = []
    if candidates:
        for start in range(0, len(candidates), BATCH):
            texts = [t for _, t in candidates[start : start + BATCH]]
            for text, ask in zip(texts, canonical_asks(tc, texts), strict=True):
                asks.append(cut_words(ask) if ask else cut_words(text))
                low.append(ask is None)

        def log(inputs: list[str], outcome: str, attempt: int, stats: Any = None) -> None:
            tc.pending.append(
                {
                    "workspace_id": ws,
                    "job_id": ctx.job.id,
                    "call_id": "EMBED",
                    "model": CURRENT_EMBEDDING_MODEL,
                    "inputs": inputs,
                    "outcome": outcome,
                    "attempt": attempt,
                    "stats": stats,
                }
            )

        vectors = np.array(
            [
                v
                for start in range(0, len(asks), 64)
                for v in embed_texts(run.gateway, asks[start : start + 64], log)
            ]
        )
        labels = group_asks(vectors)
        for label in sorted(set(labels.tolist())):
            members = np.flatnonzero(labels == label)
            centroid = vectors[members].mean(axis=0)
            title = asks[int(members[np.argmax(vectors[members] @ centroid)])]
            groups.append((title, [int(i) for i in members]))
    with ctx.step() as (db, queue):
        # Idempotent: a retried step replaces this run's request groups.
        db.execute(
            delete(RequestMembership).where(
                RequestMembership.workspace_id == ws, RequestMembership.analysis_run_id == run_id
            )
        )
        db.execute(
            delete(AggregatedRequest).where(
                AggregatedRequest.workspace_id == ws, AggregatedRequest.first_run_id == run_id
            )
        )
        for title, indexes in groups:
            request_id = uuid.uuid4()
            db.add(
                AggregatedRequest(
                    id=request_id,
                    workspace_id=ws,
                    title=title,
                    first_run_id=run_id,
                    last_run_id=run_id,
                )
            )
            db.flush()
            db.add_all(
                RequestMembership(
                    workspace_id=ws,
                    analysis_run_id=run_id,
                    request_id=request_id,
                    record_id=candidates[i][0],
                    canonical_ask=asks[i],
                    low_confidence=low[i],
                )
                for i in indexes
            )
        flush_calls(db, tc)
        queue.checkpoint(
            ctx.job, {"step": "requests"}, {"step": "requests", "candidates": len(candidates)}
        )


def archive_earlier_requests(db: Any, ws: uuid.UUID, run_id: uuid.UUID) -> None:
    db.execute(
        update(AggregatedRequest)
        .where(
            AggregatedRequest.workspace_id == ws,
            AggregatedRequest.last_run_id != run_id,
            AggregatedRequest.status == "active",
        )
        .values(status="archived")
    )
