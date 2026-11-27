"""Analysis runs and the embedding step on the real schema (marker ``db``).

API-31, API-32, SVC-08 (DR-26, DR-38), D06 §10.2, AIR-22. The model is a deterministic fake
(``FakeGateway``) so these tests need no GPU; a separate live test (marker ``ollama``) uses
the real embedding model.
"""

from __future__ import annotations

import math
import uuid
from collections.abc import Callable, Iterator
from functools import partial
from typing import Any

import pytest
from sqlalchemy import Engine, text

from elucis.core.config import Settings
from elucis.modules.analysis import service
from elucis.modules.analysis.orchestrator import run_analysis
from elucis.modules.imports.pipeline import run_ingest
from elucis.workers.runtime import Worker
from tests.conftest import ApiClient
from tests.fakes import FakeGateway, fake_vector
from tests.schema_seed import bind

pytestmark = pytest.mark.db

Browser = Callable[[], ApiClient]
FEEDBACK = (
    "review,user\n"
    "Checkout spins forever after I tap Pay,u1\n"
    "The export to Excel is slow,u2\n"
    "Please add dark mode,u3\n"
)


@pytest.fixture
def no_model_check(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service, "check_models", lambda _settings: None)


@pytest.fixture
def workspace(
    browser: Browser, worker_engine: Engine, api_settings: Settings
) -> Iterator[dict[str, Any]]:
    """An Owner's workspace with three imported, analysable records."""
    owner = browser()
    owner.sign_up()
    ws = owner.call("POST", "/workspaces", json={"name": "Analysis"}).json()["id"]
    file_id = owner.call(
        "POST",
        f"/workspaces/{ws}/files",
        files={"file": ("f.csv", FEEDBACK.encode(), "text/csv")},
        data={"source_type": "review"},
    ).json()["id"]
    body = {
        "source_file_id": file_id,
        "source_type": "review",
        "column_mapping": {"text": "review", "customer_id": "user"},
    }
    assert owner.call("POST", f"/workspaces/{ws}/imports", json=body).status_code == 202
    _work(worker_engine, api_settings, FakeGateway())
    yield {"ws": ws, "owner": owner}
    _work(worker_engine, api_settings, FakeGateway())  # leave no queued job behind


def _work(engine: Engine, settings: Settings, gateway: FakeGateway, wid: str = "w-an") -> None:
    worker = Worker(
        engine,
        {
            "ingest": partial(run_ingest, settings=settings),
            "analysis": partial(
                run_analysis, settings=settings, gateway_factory=lambda _s: gateway
            ),
        },
        worker_id=wid,
    )
    while worker.run_once():
        pass


def _start(b: ApiClient, ws: str, key: str | None = None) -> Any:
    headers = {"Idempotency-Key": key} if key else {}
    return b.call("POST", f"/workspaces/{ws}/analysis-runs", json={}, headers=headers)


def _scalar(owner_engine: Engine, ws: str, sql: str, **params: Any) -> Any:
    with owner_engine.begin() as conn:
        bind(conn, uuid.UUID(ws))
        return conn.execute(text(sql), params).scalar_one()


def test_a_run_needs_records_and_a_reachable_model(browser: Browser) -> None:
    owner = browser()
    owner.sign_up()
    ws = owner.call("POST", "/workspaces", json={"name": "Empty"}).json()["id"]
    r = _start(owner, ws)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "no_analysable_records"


def test_model_runtime_down_is_503_before_any_job(workspace: dict[str, Any]) -> None:
    r = _start(workspace["owner"], workspace["ws"])  # test settings point at a closed port
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "model_unavailable"
    runs = workspace["owner"].call("GET", f"/workspaces/{workspace['ws']}/analysis-runs").json()
    assert runs == []


@pytest.mark.usefixtures("no_model_check")
def test_run_embeds_every_analysable_record_and_becomes_current(
    workspace: dict[str, Any], worker_engine: Engine, owner_engine: Engine, api_settings: Settings
) -> None:
    owner, ws = workspace["owner"], workspace["ws"]
    key = str(uuid.uuid4())
    ref = _start(owner, ws, key)
    assert ref.status_code == 202, ref.text
    assert _start(owner, ws, key).json() == ref.json()  # Idempotency-Key repeat
    conflict = _start(owner, ws)
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "run_in_progress"

    _work(worker_engine, api_settings, FakeGateway())
    run_id = ref.json()["resource_id"]
    run = owner.call("GET", f"/workspaces/{ws}/analysis-runs/{run_id}").json()
    assert run["status"] == "succeeded"
    assert run["is_current"] is True
    assert run["report"]["eligible"] == run["report"]["embedded"] == 3
    assert run["report"]["embedding_failed"] == 0
    assert run["config"]["embedding_model"] == "qwen3-embedding:0.6b"

    norm = _scalar(
        owner_engine, ws, "SELECT max(abs(vector_norm(embedding) - 1)) FROM record_embeddings"
    )
    assert norm < 1e-5  # stored L2-normalised
    calls = _scalar(
        owner_engine, ws, "SELECT count(*) FROM llm_call_records WHERE call_id = 'EMBED'"
    )
    assert calls >= 1  # every model call is recorded (AIR-12)

    status = owner.call("GET", f"/workspaces/{ws}/analysis").json()
    assert status["analysable_records"] == 3
    assert status["current_run"]["id"] == run_id
    assert status["records_since_last_run"] == 0


@pytest.mark.usefixtures("no_model_check")
def test_a_record_that_cannot_be_embedded_is_marked_for_this_run_only(
    workspace: dict[str, Any], worker_engine: Engine, owner_engine: Engine, api_settings: Settings
) -> None:
    owner, ws = workspace["owner"], workspace["ws"]
    run_id = _start(owner, ws).json()["resource_id"]
    gateway = FakeGateway(bad=frozenset({"The export to Excel is slow"}))
    _work(worker_engine, api_settings, gateway)
    run = owner.call("GET", f"/workspaces/{ws}/analysis-runs/{run_id}").json()
    assert run["status"] == "succeeded"
    assert (run["report"]["embedded"], run["report"]["embedding_failed"]) == (2, 1)
    assert gateway.calls == 3 + 3  # first try + 2 retries, then one call per record
    failed = _scalar(
        owner_engine,
        ws,
        "SELECT count(*) FROM record_classifications WHERE analysis_run_id = :r"
        " AND status = 'embedding_failed'",
        r=run_id,
    )
    assert failed == 1


@pytest.mark.usefixtures("no_model_check")
def test_runtime_down_leaves_the_run_for_a_retry_and_keeps_the_current_one(
    workspace: dict[str, Any], worker_engine: Engine, owner_engine: Engine, api_settings: Settings
) -> None:
    owner, ws = workspace["owner"], workspace["ws"]
    first = _start(owner, ws).json()["resource_id"]
    _work(worker_engine, api_settings, FakeGateway())
    _scalar(owner_engine, ws, "SELECT 1")
    with owner_engine.begin() as conn:  # force a re-embed for the second run
        bind(conn, uuid.UUID(ws))
        conn.execute(text("DELETE FROM record_embeddings"))
    second = _start(owner, ws).json()["resource_id"]
    _work(worker_engine, api_settings, FakeGateway(down=True))

    run = owner.call("GET", f"/workspaces/{ws}/analysis-runs/{second}").json()
    assert run["status"] == "running"  # the job waits for a retry; nothing marked failed
    status = owner.call("GET", f"/workspaces/{ws}/analysis").json()
    assert status["current_run"]["id"] == first  # previous results stay visible (AIR-22)
    failed = _scalar(
        owner_engine,
        ws,
        "SELECT count(*) FROM record_classifications WHERE analysis_run_id = :r",
        r=second,
    )
    assert failed == 0
    with owner_engine.begin() as conn:  # let the retry run now, with the model back
        bind(conn, uuid.UUID(ws))
        conn.execute(
            text(
                "UPDATE jobs SET run_after = now() - interval '1 hour' WHERE status = 'retry_wait'"
            )
        )
    _work(worker_engine, api_settings, FakeGateway())
    assert owner.call("GET", f"/workspaces/{ws}/analysis-runs/{second}").json()["status"] == (
        "succeeded"
    )


def test_fake_vectors_are_not_normalised_so_the_norm_check_means_something() -> None:
    vec = fake_vector("x")
    assert abs(math.sqrt(sum(v * v for v in vec)) - 1) > 0.5
