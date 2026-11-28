"""Insights API (IMP-35, API-33, API-34, API-37, API-38) on the real schema after an
analysis run with the fake gateway. Checks the figures against the known test inputs of
``test_themes.FEEDBACK``: 12 checkout bugs, 12 slow exports, 12 dark-mode requests, 1 praise.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from sqlalchemy import Engine

from elucis.core.config import Settings
from tests.conftest import ApiClient
from tests.fakes import FakeGateway
from tests.test_themes import _run, _work, analysed  # noqa: F401 - shared fixture

pytestmark = pytest.mark.db
Browser = Callable[[], ApiClient]


@pytest.fixture
def run(
    analysed: dict[str, Any],  # noqa: F811
    worker_engine: Engine,
    api_settings: Settings,
) -> dict[str, Any]:
    run_id = _run(analysed["owner"], analysed["ws"])
    _work(worker_engine, api_settings, FakeGateway())
    return {**analysed, "run_id": run_id}


def _get(run: dict[str, Any], path: str, **params: Any) -> Any:
    return run["owner"].call("GET", f"/workspaces/{run['ws']}{path}", params=params)


def test_insights_before_any_run_are_empty_not_an_error(browser: Browser) -> None:
    b = browser()
    b.sign_up()
    ws = b.call("POST", "/workspaces", json={"name": "Nothing yet"}).json()["id"]
    body = b.call("GET", f"/workspaces/{ws}/insights").json()
    assert body["run_id"] is None
    assert (body["themes"], body["requests"], body["records_analysed"]) == ([], [], 0)
    assert b.call("GET", f"/workspaces/{ws}/themes").json()["items"] == []


def test_dashboard_insights_match_the_stored_run(run: dict[str, Any]) -> None:
    body = _get(run, "/insights").json()
    assert body["run_id"] == run["run_id"]
    assert body["records_analysed"] == 37
    assert body["source_types"] == ["review"]
    names = [t["name"] for t in body["themes"]]
    assert sorted(names) == [
        "Problems with checkout",
        "Problems with dark mode",
        "Problems with export",
    ]
    by_name = {t["name"]: t for t in body["themes"]}
    # Pain points: mostly issues or negative (checkout bugs, slow exports), not the requests.
    assert by_name["Problems with checkout"]["pain_point"] is True
    assert by_name["Problems with export"]["pain_point"] is True
    assert by_name["Problems with dark mode"]["pain_point"] is False
    assert body["pain_points"] == 2
    assert body["unassigned"] == 37 - sum(t["record_count"] for t in body["themes"])
    for theme in body["themes"]:
        assert sum(w["n"] for w in theme["weekly"]) + theme["undated"] == theme["record_count"]
        assert theme["trend"] in {"up", "flat", "down"}
        assert theme["known_customers"] == theme["record_count"]  # every test line has a user
        evidence = theme["evidence"]
        assert 1 <= len(evidence) <= 3
        assert [e["cited"] for e in evidence][:2] == [True, True]  # cited quotes come first
        assert all("@" not in e["text"] for e in evidence)  # masked text only
    (request,) = body["requests"]
    assert request["title"] == "Add a dark mode"
    assert request["record_count"] == 12
    assert request["asks"] == [{"ask": "Add a dark mode", "n": 12}]

    only = _get(run, "/insights", pain_points_only="true").json()
    assert sorted(t["name"] for t in only["themes"]) == [
        "Problems with checkout",
        "Problems with export",
    ]


def test_filters_narrow_every_figure(run: dict[str, Any]) -> None:
    none = _get(run, "/insights", source_type="ticket").json()
    assert none["records_analysed"] == 0 and none["themes"] == [] and none["requests"] == []

    early = _get(run, "/insights", **{"from": "2026-10-01", "to": "2026-10-07"}).json()
    full = _get(run, "/insights").json()
    assert 0 < early["records_analysed"] < full["records_analysed"]
    assert (
        sum(t["record_count"] for t in early["themes"]) + early["unassigned"]
        == early["records_analysed"]
    )
    for theme in early["themes"]:
        # Weeks start on Monday: 1 Oct 2026 is a Thursday, in the week of 28 Sep.
        assert all("2026-09-28" <= w["start"] <= "2026-10-07" for w in theme["weekly"])

    bad = _get(run, "/insights", **{"from": "2026-10-09", "to": "2026-10-01"})
    assert bad.status_code == 422


def test_theme_and_request_detail_return_more_evidence(run: dict[str, Any]) -> None:
    themes = _get(run, "/themes").json()["items"]
    checkout = next(t for t in themes if t["name"] == "Problems with checkout")
    detail = _get(run, f"/themes/{checkout['id']}").json()
    assert detail["record_count"] == checkout["record_count"]
    assert 3 < len(detail["evidence"]) <= 10
    assert len({e["record_id"] for e in detail["evidence"]}) == len(detail["evidence"])
    requests = _get(run, "/requests").json()["items"]
    req = _get(run, f"/requests/{requests[0]['id']}").json()
    assert len(req["evidence"]) == 10
    assert _get(run, f"/themes/{requests[0]['id']}").status_code == 404  # not a theme
