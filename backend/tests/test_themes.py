"""Classification (CP-02), themes (SVC-11), naming (CP-03) and theme statistics.

Unit tests for the deterministic parts (clustering, rules, weekly series and trends) and
database tests for the whole analysis job with the fake gateway (``tests/fakes.py``). The
feedback lines are test inputs written for these checks, not product data.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime, timedelta
from functools import partial
from typing import Any

import numpy as np
import pytest
from sqlalchemy import Engine, text

from elucis.ai.prompts import Cp02Out, Cp03Out
from elucis.core.config import Settings
from elucis.modules.analysis import service
from elucis.modules.analysis.classify import keys_exactly
from elucis.modules.analysis.orchestrator import run_analysis
from elucis.modules.analysis.tasks import OutputRuleError
from elucis.modules.analysis.themes import cluster_vectors, naming_rules
from elucis.modules.imports.pipeline import run_ingest
from elucis.modules.insights.stats import trend_direction, weekly_series
from elucis.workers.runtime import Worker
from tests.conftest import ApiClient
from tests.fakes import FakeGateway, fake_vector
from tests.schema_seed import bind

Browser = Callable[[], ApiClient]


# ---------------------------------------------------------------- unit: rules
def test_cp02_rule_needs_every_key_exactly_once() -> None:
    check = keys_exactly(["r1", "r2"])
    ok = Cp02Out.model_validate(
        {"items": [{"key": k, "category": "other", "sentiment": "neutral"} for k in ("r2", "r1")]}
    )
    check(ok)
    for keys in (["r1"], ["r1", "r1"], ["r1", "r2", "r3"]):
        bad = Cp02Out.model_validate(
            {"items": [{"key": k, "category": "other", "sentiment": "neutral"} for k in keys]}
        )
        with pytest.raises(OutputRuleError):
            check(bad)


def test_cp03_rule_needs_supplied_ids_and_no_numbers() -> None:
    check = naming_rules(["E1", "E2"])
    check(
        Cp03Out(name="Checkout freezes", description="Customers report a freeze.", cited_ids=["E1"])
    )
    with pytest.raises(OutputRuleError):
        check(
            Cp03Out(name="Checkout freezes", description="Customers report it.", cited_ids=["E7"])
        )
    with pytest.raises(OutputRuleError):
        check(Cp03Out(name="Top 3 bugs", description="Customers report bugs.", cited_ids=["E1"]))


# ---------------------------------------------------------------- unit: clustering
def _unit(v: list[float]) -> np.ndarray:
    a = np.asarray(v)
    return a / np.linalg.norm(a)


def test_clustering_separates_topics_reproducibly() -> None:
    texts = [
        f"{topic} problem number {i}"
        for topic in ("checkout", "export", "login")
        for i in range(12)
    ]
    vectors = np.array([_unit(fake_vector(t)) for t in texts])
    labels, strengths = cluster_vectors(vectors)
    groups = [set(labels[i * 12 : (i + 1) * 12]) for i in range(3)]
    assert all(len(g) == 1 and -1 not in g for g in groups)  # one cluster per topic
    assert len({next(iter(g)) for g in groups}) == 3
    assert ((strengths >= 0) & (strengths <= 1)).all()
    again, _ = cluster_vectors(vectors)
    assert (again == labels).all()  # AIR-04


def test_too_few_records_stay_unassigned() -> None:
    vectors = np.array([_unit(fake_vector(f"checkout {i}")) for i in range(5)])
    labels, _ = cluster_vectors(vectors)
    assert (labels == -1).all()


# ---------------------------------------------------------------- unit: weekly and trend
def _days(start: date, counts: list[int]) -> list[datetime]:
    out = []
    for week, n in enumerate(counts):
        day = datetime.combine(start + timedelta(weeks=week), datetime.min.time(), UTC)
        out += [day] * n
    return out


def test_weekly_series_fills_empty_weeks() -> None:
    series = weekly_series(_days(date(2026, 9, 28), [2, 0, 3]))  # Mondays
    assert [(w["week"], w["n"]) for w in series] == [
        ("2026-W40", 2),
        ("2026-W41", 0),
        ("2026-W42", 3),
    ]


@pytest.mark.parametrize(
    ("counts", "trend"),
    [
        ([1, 1, 2, 2, 3, 3, 4, 5], "up"),
        ([5, 4, 4, 3, 2, 2, 1, 1], "down"),
        ([3, 3, 3, 3, 3, 3, 3, 3], "flat"),
        ([0, 0, 0, 0, 0, 0, 1, 1], "flat"),  # too few records in the window to call it
    ],
)
def test_trend_direction(counts: list[int], trend: str) -> None:
    start = date(2026, 8, 3)
    series = weekly_series(_days(start, counts))
    end = start + timedelta(weeks=len(counts) - 1)
    assert trend_direction(series, end) == trend


# ---------------------------------------------------------------- database: the whole run
FEEDBACK = (
    "\n".join(
        ["review,user,date"]
        + [
            f"Checkout fails when I tap pay on screen {i},c{i},2026-10-{1 + i % 20:02d}"
            for i in range(12)
        ]
        + [
            f"Export to Excel is slow with report {i},e{i},2026-10-{1 + i % 20:02d}"
            for i in range(12)
        ]
        + [f"Please add dark mode to page {i},d{i},2026-10-{1 + i % 20:02d}" for i in range(12)]
        + ["Love it,z1,2026-10-05"]
    )
    + "\n"
)


def _work(engine: Engine, settings: Settings, gateway: FakeGateway) -> None:
    worker = Worker(
        engine,
        {
            "ingest": partial(run_ingest, settings=settings),
            "analysis": partial(
                run_analysis, settings=settings, gateway_factory=lambda _s: gateway
            ),
        },
        worker_id="w-themes",
    )
    while worker.run_once():
        pass


@pytest.fixture
def analysed(
    browser: Browser,
    worker_engine: Engine,
    api_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[dict[str, Any]]:
    """A workspace with 37 imported records, ready for analysis."""
    monkeypatch.setattr(service, "check_models", lambda _settings: None)
    owner = browser()
    owner.sign_up()
    ws = owner.call("POST", "/workspaces", json={"name": "Themes"}).json()["id"]
    file_id = owner.call(
        "POST",
        f"/workspaces/{ws}/files",
        files={"file": ("f.csv", FEEDBACK.encode(), "text/csv")},
        data={"source_type": "review"},
    ).json()["id"]
    mapping = {"text": "review", "customer_id": "user", "occurred_at": "date"}
    body = {"source_file_id": file_id, "source_type": "review", "column_mapping": mapping}
    assert owner.call("POST", f"/workspaces/{ws}/imports", json=body).status_code == 202
    _work(worker_engine, api_settings, FakeGateway())
    yield {"ws": ws, "owner": owner}
    _work(worker_engine, api_settings, FakeGateway())


def _run(b: ApiClient, ws: str) -> str:
    r = b.call("POST", f"/workspaces/{ws}/analysis-runs", json={})
    assert r.status_code == 202, r.text
    return str(r.json()["resource_id"])


def _rows(owner_engine: Engine, ws: str, sql: str, **params: Any) -> list[Any]:
    with owner_engine.begin() as conn:
        bind(conn, uuid.UUID(ws))
        return list(conn.execute(text(sql), params).all())


@pytest.mark.db
def test_a_run_classifies_clusters_and_names_themes_with_citations(
    analysed: dict[str, Any], worker_engine: Engine, owner_engine: Engine, api_settings: Settings
) -> None:
    owner, ws = analysed["owner"], analysed["ws"]
    run_id = _run(owner, ws)
    gateway = FakeGateway()
    _work(worker_engine, api_settings, gateway)

    run = owner.call("GET", f"/workspaces/{ws}/analysis-runs/{run_id}").json()
    assert run["status"] == "succeeded", run
    report = run["report"]
    assert report["classified"] == 37 and report["unclassified"] == 0
    assert report["categories"] == {
        "bug_report": 12,
        "performance_issue": 12,
        "feature_request": 12,
        "praise": 1,
    }
    assert report["themes"] == 3
    # HDBSCAN may keep the lone "Love it" in the nearest theme with a low membership
    # strength, or leave it unassigned (FR-THM-07); the three topics are always intact.
    assert report["assigned"] in {36, 37}

    themes = _rows(
        owner_engine,
        ws,
        "SELECT t.id, t.name, t.description, s.record_count, s.known_customers, s.cited_record_ids,"
        " s.trend, s.weekly FROM themes t JOIN theme_run_stats s ON s.theme_id = t.id"
        " WHERE t.first_run_id = :r ORDER BY t.name",
        r=run_id,
    )
    assert sorted(t.name for t in themes) == [
        "Problems with checkout",
        "Problems with dark mode",
        "Problems with export",
    ]
    for theme in themes:
        members = {
            r.record_id
            for r in _rows(
                owner_engine,
                ws,
                "SELECT record_id FROM theme_memberships WHERE theme_id = :t",
                t=theme.id,
            )
        }
        assert theme.record_count == theme.known_customers == len(members) in {12, 13}
        assert len(theme.cited_record_ids) == 2
        assert set(theme.cited_record_ids) <= members  # citations are real members (AIR-14)
        assert sum(w["n"] for w in theme.weekly) == theme.record_count
    # Only masked text reached the model, and every call was recorded with its prompt version.
    calls = _rows(
        owner_engine,
        ws,
        "SELECT call_id, count(*) AS n, bool_and(prompt_version_id IS NOT NULL) AS versioned"
        " FROM llm_call_records WHERE call_id IN ('CP-02', 'CP-03')"
        " GROUP BY call_id ORDER BY call_id",
    )
    assert [(c.call_id, c.n, c.versioned) for c in calls] == [
        ("CP-02", 4, True),
        ("CP-03", 3, True),
    ]


@pytest.mark.db
def test_invalid_model_output_falls_back_without_losing_records(
    analysed: dict[str, Any], worker_engine: Engine, owner_engine: Engine, api_settings: Settings
) -> None:
    owner, ws = analysed["owner"], analysed["ws"]
    run_id = _run(owner, ws)
    gateway = FakeGateway(bad_cp02_batches=True, bad_cp03=True)
    _work(worker_engine, api_settings, gateway)
    run = owner.call("GET", f"/workspaces/{ws}/analysis-runs/{run_id}").json()
    assert run["status"] == "succeeded"
    assert run["report"]["classified"] == 37  # batch failed three times, then one by one
    names = [
        r.name
        for r in _rows(
            owner_engine, ws, "SELECT name FROM themes WHERE first_run_id = :r", r=run_id
        )
    ]
    assert sorted(names) == [
        "Unnamed theme 1",
        "Unnamed theme 2",
        "Unnamed theme 3",
    ]  # CP-03 fallback
    cited = _rows(
        owner_engine,
        ws,
        "SELECT cited_record_ids FROM theme_run_stats WHERE analysis_run_id = :r",
        r=run_id,
    )
    assert all(r.cited_record_ids == [] for r in cited)


@pytest.mark.db
def test_a_new_run_replaces_the_current_themes(
    analysed: dict[str, Any], worker_engine: Engine, owner_engine: Engine, api_settings: Settings
) -> None:
    owner, ws = analysed["owner"], analysed["ws"]
    first = _run(owner, ws)
    _work(worker_engine, api_settings, FakeGateway())
    second = _run(owner, ws)
    _work(worker_engine, api_settings, FakeGateway())
    status = {
        r.first_run_id: r.status
        for r in _rows(owner_engine, ws, "SELECT DISTINCT first_run_id, status FROM themes")
    }
    assert status == {uuid.UUID(first): "archived", uuid.UUID(second): "active"}
