"""Feature-request detection and grouping (SVC-12, CP-04): rules, grouping, and the step in
a whole analysis run with the fake gateway. Test inputs only."""

from __future__ import annotations

import uuid
from typing import Any

import numpy as np
import pytest
from sqlalchemy import Engine

from elucis.ai.prompts import Cp04Out
from elucis.core.config import Settings
from elucis.modules.analysis.requests import ask_rules, cut_words, group_asks, is_candidate
from elucis.modules.analysis.tasks import OutputRuleError
from tests.fakes import FakeGateway, fake_vector
from tests.test_themes import _rows, _run, _work, analysed  # noqa: F401 - shared fixture

# ---------------------------------------------------------------- unit


@pytest.mark.parametrize(
    ("category", "text", "expected"),
    [
        ("feature_request", "Dark mode", True),
        ("bug_report", "It crashes. Please add an offline mode too", True),  # request cue
        ("praise", "I wish it had widgets", True),
        ("bug_report", "It crashes on start", False),
        ("other", "Would be great if exports were faster", True),
    ],
)
def test_candidates_are_requests_or_records_with_a_request_cue(
    category: str, text: str, expected: bool
) -> None:
    assert is_candidate(category, text) is expected


def test_ask_rules_need_every_key_and_short_asks() -> None:
    check = ask_rules(["r1", "r2"])
    check(
        Cp04Out.model_validate(
            {"items": [{"key": "r1", "ask": "Add dark mode"}, {"key": "r2", "ask": "Add widgets"}]}
        )
    )
    with pytest.raises(OutputRuleError):
        check(Cp04Out.model_validate({"items": [{"key": "r1", "ask": "Add dark mode"}]}))
    long = " ".join(["word"] * 13)
    with pytest.raises(OutputRuleError):
        check(
            Cp04Out.model_validate(
                {"items": [{"key": "r1", "ask": long}, {"key": "r2", "ask": "Add widgets"}]}
            )
        )
    assert len(cut_words(long).split()) == 12


def _unit(text: str) -> np.ndarray:
    v = np.asarray(fake_vector(text))
    return v / np.linalg.norm(v)


def test_same_asks_group_together_and_different_asks_apart() -> None:
    asks = ["Add a dark mode"] * 3 + ["Export reports to Excel"] * 2 + ["Add login with Face ID"]
    labels = group_asks(np.array([_unit(a) for a in asks]))
    assert len(set(labels[:3])) == 1 and len(set(labels[3:5])) == 1
    assert len({labels[0], labels[3], labels[5]}) == 3
    assert group_asks(np.array([_unit("one")])).tolist() == [0]


# ---------------------------------------------------------------- database


@pytest.mark.db
def test_a_run_groups_feature_requests_under_a_canonical_title(
    analysed: dict[str, Any],  # noqa: F811
    worker_engine: Engine,
    owner_engine: Engine,
    api_settings: Settings,
) -> None:
    owner, ws = analysed["owner"], analysed["ws"]
    run_id = _run(owner, ws)
    _work(worker_engine, api_settings, FakeGateway())
    report = owner.call("GET", f"/workspaces/{ws}/analysis-runs/{run_id}").json()["report"]
    assert (report["requests"], report["request_records"]) == (1, 12)
    (group,) = _rows(
        owner_engine,
        ws,
        "SELECT r.title, count(m.*) AS n, bool_or(m.low_confidence) AS low"
        " FROM aggregated_requests r JOIN request_memberships m ON m.request_id = r.id"
        " WHERE r.first_run_id = :r GROUP BY r.title",
        r=run_id,
    )
    assert (group.title, group.n, group.low) == ("Add a dark mode", 12, False)


@pytest.mark.db
def test_without_a_valid_ask_the_text_is_used_and_marked_low_confidence(
    analysed: dict[str, Any],  # noqa: F811
    worker_engine: Engine,
    owner_engine: Engine,
    api_settings: Settings,
) -> None:
    owner, ws = analysed["owner"], analysed["ws"]
    run_id = _run(owner, ws)
    _work(worker_engine, api_settings, FakeGateway(bad_cp04=True))
    rows = _rows(
        owner_engine,
        ws,
        "SELECT canonical_ask, low_confidence FROM request_memberships WHERE analysis_run_id = :r",
        r=uuid.UUID(run_id),
    )
    assert len(rows) == 12 and all(r.low_confidence for r in rows)
    assert all(r.canonical_ask.startswith("Please add dark mode") for r in rows)
    assert all(len(r.canonical_ask.split()) <= 12 for r in rows)
