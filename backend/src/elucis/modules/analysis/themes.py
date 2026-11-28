"""Steps ``cluster`` and ``name`` (SVC-11, SVC-10 step 7, CP-03): themes and pain points.

``cluster``: the vectors of every classified record in the run -> PCA to at most 50
components (``random_state=42``) -> HDBSCAN (``min_cluster_size = max(5, n / 200)``,
``eom``). Each cluster becomes a theme of this run; HDBSCAN's noise is the "Unassigned"
group (FR-THM-07). Same input, same themes (AIR-04).

``name``: CP-03 names each theme from its 5 most central and 3 boundary records (masked)
and must cite record IDs it was given. When the call fails, the theme stays "Unnamed theme
<n>" and the dashboard shows its most central records as evidence instead.

Simplified for milestone 2 (IMP-33): every run makes new themes (no identity matching across
runs, no overrides, no second pass for small themes); themes of earlier runs are archived
when a run is activated.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

import numpy as np
from sklearn.cluster import HDBSCAN
from sklearn.decomposition import PCA
from sqlalchemy import and_, delete, select, update

from elucis.ai.prompts import CP03, Cp03Out, render_records
from elucis.db.models import (
    FeedbackRecord,
    RecordClassification,
    RecordEmbedding,
    Theme,
    ThemeMembership,
    ThemeRunStats,
)
from elucis.db.models._common import CURRENT_EMBEDDING_MODEL
from elucis.modules.analysis.context import RunContext
from elucis.modules.analysis.tasks import (
    OutputRuleError,
    TaskContext,
    flush_calls,
    register_prompts,
    run_task,
)
from elucis.modules.insights.stats import theme_stats
from elucis.workers.runtime import JobContext

PCA_COMPONENTS = 50
MIN_RECORDS = 10  # below this, clustering is not meaningful: everything stays unassigned
CENTRAL, BOUNDARY = 5, 3
UNNAMED = "Unnamed theme"
_DIGIT = re.compile(r"\d")


def min_cluster_size(n: int) -> int:
    return max(5, n // 200)


def cluster_vectors(vectors: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Labels (-1 = noise) and membership strengths for L2-normalised vectors."""
    n = len(vectors)
    if n < MIN_RECORDS:
        return np.full(n, -1), np.zeros(n)
    components = min(PCA_COMPONENTS, n - 1, vectors.shape[1])
    reduced = PCA(n_components=components, random_state=42).fit_transform(vectors)
    model = HDBSCAN(min_cluster_size=min_cluster_size(n), cluster_selection_method="eom", copy=True)
    labels = model.fit_predict(reduced)
    return labels, model.probabilities_


def _unit(v: np.ndarray) -> list[float]:
    norm = float(np.linalg.norm(v))
    unit = v / norm if norm else v
    return [float(x) for x in unit]


# ---------------------------------------------------------------- cluster
def cluster_step(ctx: JobContext, run: RunContext) -> None:
    ws, run_id = ctx.job.workspace_id, run.run_id
    rc, emb = RecordClassification, RecordEmbedding
    with ctx.step() as (db, queue):
        # Idempotent: a retried step replaces this run's themes.
        db.execute(
            delete(ThemeRunStats).where(
                ThemeRunStats.workspace_id == ws, ThemeRunStats.analysis_run_id == run_id
            )
        )
        db.execute(
            delete(ThemeMembership).where(
                ThemeMembership.workspace_id == ws, ThemeMembership.analysis_run_id == run_id
            )
        )
        db.execute(delete(Theme).where(Theme.workspace_id == ws, Theme.first_run_id == run_id))
        rows = db.execute(
            select(rc.record_id, emb.embedding)
            .join(
                emb,
                and_(
                    emb.workspace_id == rc.workspace_id,
                    emb.record_id == rc.record_id,
                    emb.model_id == CURRENT_EMBEDDING_MODEL,
                ),
            )
            .where(rc.workspace_id == ws, rc.analysis_run_id == run_id, rc.status == "classified")
            .order_by(rc.record_id)  # a fixed order, so the same records give the same themes
        ).all()
        if rows:
            ids = [r.record_id for r in rows]
            vectors = np.array([np.asarray(r.embedding, dtype=float) for r in rows])
            labels, strengths = cluster_vectors(vectors)
            # Theme numbers follow cluster size, largest first.
            order = sorted(
                {int(x) for x in labels if x >= 0}, key=lambda c: (-int((labels == c).sum()), c)
            )
            for number, label in enumerate(order, start=1):
                members = np.flatnonzero(labels == label)
                theme_id = uuid.uuid4()
                db.add(
                    Theme(
                        id=theme_id,
                        workspace_id=ws,
                        name=f"{UNNAMED} {number}",
                        description=None,  # NULL = not named yet (step "name")
                        centroid=_unit(vectors[members].mean(axis=0)),
                        first_run_id=run_id,
                        last_run_id=run_id,
                    )
                )
                db.flush()
                db.add_all(
                    ThemeMembership(
                        workspace_id=ws,
                        analysis_run_id=run_id,
                        theme_id=theme_id,
                        record_id=ids[i],
                        probability=float(strengths[i]),
                    )
                    for i in members
                )
        queue.checkpoint(ctx.job, {"step": "cluster"}, {"step": "cluster", "records": len(rows)})


# ---------------------------------------------------------------- name (CP-03)
def evidence_for(
    db: Any, ws: uuid.UUID, run_id: uuid.UUID, theme: Theme
) -> list[tuple[uuid.UUID, str]]:
    """The theme's most central records, then its boundary records (cosine to the centroid)."""
    fr, tm, emb = FeedbackRecord, ThemeMembership, RecordEmbedding
    distance = emb.embedding.cosine_distance(theme.centroid)
    base = (
        select(fr.id, fr.processed_text)
        .join(tm, and_(tm.workspace_id == fr.workspace_id, tm.record_id == fr.id))
        .join(
            emb,
            and_(
                emb.workspace_id == fr.workspace_id,
                emb.record_id == fr.id,
                emb.model_id == CURRENT_EMBEDDING_MODEL,
            ),
        )
        .where(tm.workspace_id == ws, tm.analysis_run_id == run_id, tm.theme_id == theme.id)
    )
    central = db.execute(base.order_by(distance, fr.id).limit(CENTRAL)).all()
    seen = {r.id for r in central}
    boundary = [
        r
        for r in db.execute(base.order_by(distance.desc(), fr.id).limit(BOUNDARY)).all()
        if r.id not in seen
    ]
    return [(r.id, r.processed_text or "") for r in [*central, *boundary]]


def naming_rules(keys: list[str]) -> Any:
    def check(out: Cp03Out) -> None:
        if _DIGIT.search(out.name):
            raise OutputRuleError("the name must not contain numbers")
        unknown = [c for c in out.cited_ids if c not in keys]
        if unknown:
            raise OutputRuleError(f"cited ids {unknown} were not given; use only {keys}")

    return check


def name_step(ctx: JobContext, run: RunContext) -> None:
    """Per theme: read its evidence (short transaction) -> CP-03 (no transaction open) ->
    write the name, the citations and the call records together."""
    ws, run_id = ctx.job.workspace_id, run.run_id
    with ctx.step() as (db, _queue):
        prompt_ids = register_prompts(db, CP03)
    while True:
        with ctx.step() as (db, _queue):
            theme = db.execute(
                select(Theme)
                .where(
                    Theme.workspace_id == ws,
                    Theme.first_run_id == run_id,
                    Theme.description.is_(None),
                )
                .order_by(Theme.name)
                .limit(1)
            ).scalar_one_or_none()
            if theme is None:
                return
            theme_id = theme.id
            evidence = evidence_for(db, ws, run_id, theme)
            taken = list(
                db.execute(
                    select(Theme.name).where(
                        Theme.workspace_id == ws,
                        Theme.first_run_id == run_id,
                        Theme.description.is_not(None),
                    )
                ).scalars()
            )
        keys = [f"E{i + 1}" for i in range(len(evidence))]
        lines = [f"Product: {run.product}"] if run.product else []
        if taken:
            lines.append(f"Names already used for other themes (do not repeat): {', '.join(taken)}")
        lines += [
            "Records:",
            render_records(list(zip(keys, [t for _, t in evidence], strict=True))),
        ]
        content = "\n".join(lines)
        tc = TaskContext(
            run.gateway,
            ws,
            ctx.job.id,
            run.chat_model,
            prompt_ids,
            fallback=run.fallback,
            fallback_model=run.fallback_model,
        )
        out = run_task(tc, CP03, content, Cp03Out, naming_rules(keys)) if evidence else None
        cited: list[uuid.UUID] = []
        if out is not None:
            by_key = dict(zip(keys, [rid for rid, _ in evidence], strict=True))
            cited = list(dict.fromkeys(by_key[k] for k in out.cited_ids))
            values = {"name": out.name.strip().strip('"'), "description": out.description.strip()}
        else:
            values = {"description": ""}  # keeps "Unnamed theme <n>" (D04 CP-03 fallback)
        with ctx.step() as (db, queue):
            db.execute(
                update(Theme).where(Theme.workspace_id == ws, Theme.id == theme_id).values(**values)
            )
            db.execute(
                update(ThemeRunStats)
                .where(
                    ThemeRunStats.workspace_id == ws,
                    ThemeRunStats.analysis_run_id == run_id,
                    ThemeRunStats.theme_id == theme_id,
                )
                .values(cited_record_ids=cited)
            )
            flush_calls(db, tc)
            queue.checkpoint(ctx.job, {"step": "name"}, {"step": "name"})


def stats_step(ctx: JobContext, run: RunContext) -> None:
    """``theme_run_stats`` for every theme of the run (unfiltered snapshot)."""
    ws, run_id = ctx.job.workspace_id, run.run_id
    with ctx.step() as (db, queue):
        db.execute(
            delete(ThemeRunStats).where(
                ThemeRunStats.workspace_id == ws, ThemeRunStats.analysis_run_id == run_id
            )
        )
        for theme_id, s in theme_stats(db, ws, run_id).items():
            db.add(
                ThemeRunStats(
                    workspace_id=ws,
                    analysis_run_id=run_id,
                    theme_id=theme_id,
                    record_count=s.record_count,
                    known_customers=s.known_customers,
                    unknown_identity_records=s.unknown_identity_records,
                    identity_coverage=s.identity_coverage,
                    share=s.share,
                    sentiment=s.sentiment,
                    weekly=s.weekly,
                    trend=s.trend,
                    top_customer_share=s.top_customer_share,
                    vocal_flag=s.vocal_flag,
                )
            )
        queue.checkpoint(ctx.job, {"step": "stats"}, {"step": "stats"})


def archive_earlier_themes(db: Any, ws: uuid.UUID, run_id: uuid.UUID) -> None:
    """On activation: themes of earlier runs are no longer current (status ``archived``)."""
    db.execute(
        update(Theme)
        .where(Theme.workspace_id == ws, Theme.last_run_id != run_id, Theme.status == "active")
        .values(status="archived")
    )
