"""Accuracy evaluation of a workspace's current analysis against human labels (step 8).

Reads a labels CSV in the labelling-sheet format (docs/evaluation/LABELLING_GUIDE.md) and
the current analysis run of one workspace, joins them on the record ID from the source file
(``feedback_records.source_record_id``), and writes ``docs/evaluation/ACCURACY_REPORT.md``:

* issue detection: truth ``is_issue``; predicted = CP-02 category is bug, usability or
  performance;
* feature-request detection: truth ``is_feature_request``; predicted = the record is in a
  request group;
* per-category precision and recall where ``category`` is labelled;
* feature grouping: pairwise precision, recall, F1 and purity where ``request_group`` is
  labelled.

A measure without labels is reported as "not measured", never estimated. Unlabelled rows
are only described (how the model labelled them). Usage (from backend/)::

    uv run python scripts/evaluate.py --workspace "Evaluation" \
        --labels ../data/evaluation/zenodo-15852840/test-labels.csv --source zenodo
"""

from __future__ import annotations

import argparse
import csv
import uuid
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import and_, create_engine, select, text
from sqlalchemy.engine import Connection

from elucis.ai.prompts import CATEGORIES, ISSUE_CATEGORIES
from elucis.core.config import REPO_ROOT, get_settings
from elucis.db.engine import normalise_url
from elucis.db.models import (
    AnalysisRun,
    FeedbackRecord,
    RecordClassification,
    RequestMembership,
    Workspace,
)
from elucis.modules.evaluation.metrics import Scores, binary_scores, pairwise_scores, purity

REPORT = REPO_ROOT / "docs" / "evaluation" / "ACCURACY_REPORT.md"
SOURCES = {
    "zenodo": (
        "Farah, L., Kabir, M. R., Ahmed, S. (2025). *Annotated Dataset for User Review "
        "Classification in the Privacy Domain for Social Media Applications* (v1). Zenodo. "
        "https://doi.org/10.5281/zenodo.15852840. Licence CC BY 4.0. Labels by the dataset "
        "authors (two annotators, Cohen's kappa 0.87 as published)."
    ),
    "team": "Labels by the Elucis AI team, using docs/evaluation/LABELLING_GUIDE.md.",
}
CAVEATS = {
    "zenodo": (
        "Scope of these labels (F-09): only privacy-related bug reports and feature requests are "
        "labelled; the scores use the records labelled one of those two, where the label is "
        "definite. The texts are lower-cased by the authors, some read as machine-written, and "
        "the set has no customer IDs or dates. Treat the figures as an indicative public "
        "benchmark, not as accuracy on our customers' feedback."
    ),
    "team": "",
}


def yes_no(value: str) -> bool | None:
    v = value.strip().lower()
    return True if v == "yes" else False if v == "no" else None


def load_labels(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [row for row in csv.DictReader(handle) if row.get("record_id", "").strip()]


def load_outputs(
    conn: Connection, workspace: str
) -> tuple[uuid.UUID, AnalysisRun, dict[str, dict[str, Any]]]:
    ws = conn.execute(
        select(Workspace.id, Workspace.current_analysis_run_id).where(Workspace.name == workspace)
    ).one_or_none()
    if ws is None or ws.current_analysis_run_id is None:
        raise SystemExit(f"workspace {workspace!r} not found or has no successful analysis run")
    conn.execute(text("SELECT set_config('app.workspace_id', :ws, true)"), {"ws": str(ws.id)})
    run = conn.execute(
        select(AnalysisRun).where(AnalysisRun.id == ws.current_analysis_run_id)
    ).one()
    fr, rc, rm = FeedbackRecord, RecordClassification, RequestMembership
    rows = conn.execute(
        select(
            fr.source_record_id,
            fr.analysable,
            fr.exclusion_reason,
            rc.status,
            rc.category,
            rm.request_id,
        )
        .outerjoin(
            rc,
            and_(
                rc.workspace_id == fr.workspace_id,
                rc.record_id == fr.id,
                rc.analysis_run_id == ws.current_analysis_run_id,
            ),
        )
        .outerjoin(
            rm,
            and_(
                rm.workspace_id == fr.workspace_id,
                rm.record_id == fr.id,
                rm.analysis_run_id == ws.current_analysis_run_id,
            ),
        )
        .where(fr.workspace_id == ws.id, fr.source_record_id.is_not(None))
    ).all()
    return ws.id, run, {r.source_record_id: r._asdict() for r in rows}


def fmt(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.2f}"


def score_row(name: str, s: Scores, note: str = "") -> str:
    return f"| {name} | {s.n} | {s.tp} | {s.fp} | {s.fn} | {s.tn} | {fmt(s.precision)} | {fmt(s.recall)} | {fmt(s.f1)} | {note} |"


def main() -> int:  # noqa: PLR0912, PLR0915 - one linear report
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--source", choices=sorted(SOURCES), default="team")
    parser.add_argument("--out", type=Path, default=REPORT)
    args = parser.parse_args()

    labels = load_labels(args.labels)
    engine = create_engine(normalise_url(get_settings().database_url.get_secret_value()))  # type: ignore[union-attr]
    with engine.begin() as conn:
        _ws, run, outputs = load_outputs(conn, args.workspace)

    missing = [r for r in labels if r["record_id"] not in outputs]
    excluded = Counter(
        outputs[r["record_id"]]["exclusion_reason"] or "not classified"
        for r in labels
        if r["record_id"] in outputs and outputs[r["record_id"]]["status"] != "classified"
    )
    issue_pairs, request_pairs = [], []
    per_category: dict[str, list[tuple[bool, bool]]] = {c: [] for c in CATEGORIES}
    truth_groups, predicted_groups = {}, {}
    unlabelled_predictions: Counter[str] = Counter()
    for row in labels:
        out = outputs.get(row["record_id"])
        if out is None or out["status"] != "classified":
            continue
        predicted_issue = out["category"] in ISSUE_CATEGORIES
        predicted_request = out["request_id"] is not None
        truth_issue, truth_request = yes_no(row["is_issue"]), yes_no(row["is_feature_request"])
        if truth_issue is not None:
            issue_pairs.append((truth_issue, predicted_issue))
        if truth_request is not None:
            request_pairs.append((truth_request, predicted_request))
        if truth_issue is None and truth_request is None and not row["category"].strip():
            unlabelled_predictions[out["category"]] += 1
        if row["category"].strip() in per_category:
            for c in CATEGORIES:
                per_category[c].append((row["category"].strip() == c, out["category"] == c))
        if row["request_group"].strip() and predicted_request:
            truth_groups[row["record_id"]] = row["request_group"].strip()
            predicted_groups[row["record_id"]] = str(out["request_id"])

    issue, request = binary_scores(issue_pairs), binary_scores(request_pairs)
    lines = [
        "# Accuracy report (milestone 2 step 8)",
        "",
        f"Generated {datetime.now(UTC).strftime('%d %b %Y %H:%M UTC')} by `scripts/evaluate.py` from the current analysis run "
        f'of workspace "{args.workspace}" (run `{run.id}`, finished {run.finished_at:%d %b %Y %H:%M} UTC, chat model '
        f"`{run.config.get('chat_model')}`, embedding model `{run.config.get('embedding_model')}`).",
        "",
        f"**Labels:** {SOURCES[args.source]}",
        "",
        *([CAVEATS[args.source], ""] if CAVEATS[args.source] else []),
        f"Label rows: {len(labels)}. Found in the workspace: {len(labels) - len(missing)}. "
        f"Not classified in the run (excluded before analysis or failed): {sum(excluded.values())}"
        + (f" ({', '.join(f'{k} {v}' for k, v in excluded.most_common())})" if excluded else "")
        + ". Those records are left out of every score below.",
        "",
        "## Detection",
        "",
        "| Measure | Records | TP | FP | FN | TN | Precision | Recall | F1 | Note |",
        "|---|---|---|---|---|---|---|---|---|---|",
        score_row("Issue detection (bug, usability or performance)", issue)
        if issue.n
        else "| Issue detection | 0 | | | | | not measured | | | no labels |",
        score_row("Feature-request detection (in a request group)", request)
        if request.n
        else "| Feature-request detection | 0 | | | | | not measured | | | no labels |",
        "",
        "## Per category (CP-02)",
        "",
        "| Category | Labelled as this | Precision | Recall | F1 |",
        "|---|---|---|---|---|",
    ]
    for c, pairs in per_category.items():
        if not pairs:
            continue
        s = binary_scores(pairs)
        if s.tp + s.fn == 0:
            continue  # no record of this category in the labels: nothing to measure
        lines.append(
            f"| `{c}` | {s.tp + s.fn} | {fmt(s.precision)} | {fmt(s.recall)} | {fmt(s.f1)} |"
        )
    report = run.report or {}
    classified = int(report.get("classified") or 0)
    lines += [
        "",
        "## Coverage of themes and request groups (from the run, no labels needed)",
        "",
        "| Measure | Value |",
        "|---|---|",
        f"| Themes | {report.get('themes', 'n/a')} |",
        f"| Classified records in a theme | {report.get('assigned', 0)} of {classified}"
        f" ({(report.get('assigned', 0) / classified) if classified else 0:.0%}) |",
        f"| Request groups | {report.get('requests', 'n/a')} for {report.get('request_records', 0)} request records |",
        "",
        "D03 (EXP-06) asks for at least 70% of records in a theme; many groups with one or two "
        "records mean the grouping threshold is too strict (F-08, F-12).",
    ]
    lines += ["", "## Feature grouping", ""]
    if truth_groups:
        pw = pairwise_scores(truth_groups, predicted_groups)
        lines += [
            f"Records with a labelled group that are in a predicted group: {len(truth_groups)}.",
            "",
            "| Pairwise precision | Pairwise recall | Pairwise F1 | Purity |",
            "|---|---|---|---|",
            f"| {fmt(pw.precision)} | {fmt(pw.recall)} | {fmt(pw.f1)} | {fmt(purity(truth_groups, predicted_groups))} |",
        ]
    else:
        lines.append(
            "**Not measured:** these labels have no `request_group`. Grouping accuracy needs the "
            "team's labelling sheet (LABELLING_GUIDE.md); no number is estimated."
        )
    if unlabelled_predictions:
        lines += [
            "",
            "## Records without a label (description only, not scored)",
            "",
            "How the model labelled the records the labels leave open:",
            "",
            ", ".join(f"`{k}` {v}" for k, v in unlabelled_predictions.most_common()) + ".",
        ]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        f"issue {fmt(issue.precision)}/{fmt(issue.recall)}/{fmt(issue.f1)}  request {fmt(request.precision)}/{fmt(request.recall)}/{fmt(request.f1)}  -> {args.out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
