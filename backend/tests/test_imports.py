"""Stored files, imports and the ingest job on the real schema (marker ``db``).

API-14 to API-18, FR-ING-01 to FR-ING-07, DR-07 to DR-10, DR-36 to DR-40, NFR-08.
The CSV rows below are test inputs written for these checks, not product data.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator
from functools import partial
from typing import Any

import pytest
from sqlalchemy import Engine, text

from elucis.core.config import Settings
from elucis.modules.imports import pipeline
from elucis.modules.imports.pipeline import IngestState, run_ingest
from elucis.workers.queue import Job
from elucis.workers.runtime import JobContext, Worker
from tests.conftest import ApiClient
from tests.schema_seed import bind

pytestmark = pytest.mark.db

Browser = Callable[[], ApiClient]

CSV = (
    "review,date,stars,user\n"
    "Checkout spins forever after I tap Pay,2026-10-02,1,u1\n"
    ",2026-10-03,2,u2\n"  # empty text: rejected (DR-07)
    "Love the new dark mode,not a date,5,u3\n"  # unreadable date: kept, flagged (DR-08)
)
MAPPING = {"text": "review", "occurred_at": "date", "rating": "stars", "customer_id": "user"}


def _csv(rows: int) -> bytes:
    lines = ["review,date"] + [f"Feedback number {i} about search,2026-10-01" for i in range(rows)]
    return ("\n".join(lines) + "\n").encode()


@pytest.fixture
def team(
    browser: Browser, worker_engine: Engine, api_settings: Settings
) -> Iterator[dict[str, Any]]:
    """An Owner and a Viewer in one workspace, plus an outsider. Afterwards any import a test
    left queued is run, so other tests always start with an empty job queue."""
    owner, viewer, outsider = browser(), browser(), browser()
    owner.sign_up()
    ws = owner.call("POST", "/workspaces", json={"name": "Imports"}).json()["id"]
    email = viewer.sign_up()
    outsider.sign_up()
    assert owner.call("POST", f"/workspaces/{ws}/members", json={"email": email}).status_code == 201
    yield {"ws": ws, "owner": owner, "viewer": viewer, "outsider": outsider}
    _run_worker(worker_engine, api_settings, "w-drain")


def _upload(b: ApiClient, ws: str, data: bytes, name: str = "reviews.csv") -> Any:
    return b.call(
        "POST",
        f"/workspaces/{ws}/files",
        files={"file": (name, data, "text/csv")},
        data={"source_type": "review"},
    )


def _start(b: ApiClient, ws: str, file_id: str, key: str | None = None, **extra: Any) -> Any:
    body = {"source_file_id": file_id, "source_type": "review", "column_mapping": MAPPING, **extra}
    headers = {"Idempotency-Key": key} if key else {}
    return b.call("POST", f"/workspaces/{ws}/imports", json=body, headers=headers)


def _run_worker(worker_engine: Engine, settings: Settings, worker_id: str = "w-ingest") -> None:
    worker = Worker(
        worker_engine, {"ingest": partial(run_ingest, settings=settings)}, worker_id=worker_id
    )
    while worker.run_once():
        pass


def _count(owner_engine: Engine, ws: str, table: str, import_id: str) -> int:
    with owner_engine.begin() as conn:
        bind(conn, uuid.UUID(ws))
        return int(
            conn.execute(
                text(f"SELECT count(*) FROM {table} WHERE import_job_id = :i"),
                {"i": import_id},
            ).scalar_one()
        )


# ---------------------------------------------------------------- API-14
def test_upload_stores_the_file_and_warns_about_an_identical_one(
    team: dict[str, Any], api_settings: Settings
) -> None:
    owner, ws = team["owner"], team["ws"]
    first = _upload(owner, ws, CSV.encode())
    assert first.status_code == 201, first.text
    body = first.json()
    assert body["detected_format"] == "csv"
    assert body["columns"] == ["review", "date", "stars", "user"]
    assert body["duplicate_of_file"] is None
    stored = api_settings.upload_dir / ws / body["id"]
    assert stored.read_bytes() == CSV.encode()  # stored under UUIDs, never the file name

    again = _upload(owner, ws, CSV.encode(), name="copy.csv").json()
    assert again["duplicate_of_file"]["id"] == body["id"]  # DR-10: warned, not refused
    assert again["duplicate_of_file"]["original_filename"] == "reviews.csv"


def test_pasted_text_is_stored_as_a_file(team: dict[str, Any]) -> None:
    r = team["owner"].call(
        "POST",
        f"/workspaces/{team['ws']}/files",
        data={"pasted_text": "The app logs me out every hour", "source_type": "other"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["input"] == "pasted_text"


def test_uploads_need_an_editor_and_membership(team: dict[str, Any]) -> None:
    assert _upload(team["viewer"], team["ws"], CSV.encode()).status_code == 403
    assert _upload(team["outsider"], team["ws"], CSV.encode()).status_code == 404


def test_unsupported_file_is_refused_and_nothing_is_stored(
    team: dict[str, Any], api_settings: Settings
) -> None:
    r = _upload(team["owner"], team["ws"], b"\x89PNG\r\n\x1a\n\x00\x00binary", name="x.png")
    assert r.status_code in {415, 422}
    assert not (api_settings.upload_dir / team["ws"]).exists() or not any(
        p.suffix == ".partial" for p in (api_settings.upload_dir / team["ws"]).iterdir()
    )


# ---------------------------------------------------------------- check + API-15
def test_check_reports_on_the_stored_file(team: dict[str, Any]) -> None:
    owner, ws = team["owner"], team["ws"]
    file_id = _upload(owner, ws, CSV.encode()).json()["id"]
    r = owner.call(
        "POST",
        f"/workspaces/{ws}/files/{file_id}/check",
        json={"source_type": "review", "column_mapping": MAPPING},
    )
    assert r.status_code == 200, r.text
    summary = r.json()["summary"]
    assert (summary["received"], summary["valid"], summary["rejected"]) == (3, 2, 1)


def test_start_import_refuses_bad_mappings_metrics_and_unknown_files(team: dict[str, Any]) -> None:
    owner, ws = team["owner"], team["ws"]
    file_id = _upload(owner, ws, CSV.encode()).json()["id"]
    bad = _start(owner, ws, file_id, column_mapping={"text": "no such column"})
    assert bad.status_code == 422
    metrics = _start(owner, ws, file_id, source_type="metrics")
    assert metrics.status_code == 422
    assert metrics.json()["error"]["details"][0]["issue"] == "not_supported_yet"
    assert _start(owner, ws, str(uuid.uuid4())).status_code == 404
    assert _start(team["viewer"], ws, file_id).status_code == 403


def test_start_import_is_idempotent_per_key(team: dict[str, Any]) -> None:
    owner, ws = team["owner"], team["ws"]
    file_id = _upload(owner, ws, CSV.encode()).json()["id"]
    key = str(uuid.uuid4())
    first = _start(owner, ws, file_id, key)
    second = _start(owner, ws, file_id, key)
    assert first.status_code == second.status_code == 202
    assert first.json() == second.json()
    listed = owner.call("GET", f"/workspaces/{ws}/imports").json()["items"]
    assert [i["id"] for i in listed].count(first.json()["resource_id"]) == 1
    assert listed[0]["status"] == "queued"
    assert listed[0]["original_filename"] == "reviews.csv"


# ---------------------------------------------------------------- ingest job
def test_ingest_stores_records_and_errors_and_reconciles(
    team: dict[str, Any], worker_engine: Engine, owner_engine: Engine, api_settings: Settings
) -> None:
    owner, ws = team["owner"], team["ws"]
    file_id = _upload(owner, ws, CSV.encode()).json()["id"]
    import_id = _start(owner, ws, file_id).json()["resource_id"]
    _run_worker(worker_engine, api_settings)

    detail = owner.call("GET", f"/workspaces/{ws}/imports/{import_id}").json()
    assert detail["status"] == "completed_with_errors"
    report = detail["report"]
    assert report["received"] == 3
    assert report["rejected"] == 1
    assert report["imported"] + report["duplicates"] + sum(report["filtered"].values()) == 2
    assert report["reconciled"] is True
    assert report["flags"]["occurred_at_unparseable"] == 1
    assert report["date_range"]["from"].startswith("2026-10-02")
    assert detail["progress"] == {"processed": 3, "total": 3}
    assert _count(owner_engine, ws, "feedback_records", import_id) == 2

    errors = owner.call("GET", f"/workspaces/{ws}/imports/{import_id}/errors").json()["items"]
    assert [(e["row_number"], e["kind"], e["stage"], e["code"]) for e in errors] == [
        (2, "rejected", "validation", "text_missing")
    ]
    viewer_view = team["viewer"].call("GET", f"/workspaces/{ws}/imports/{import_id}")
    assert viewer_view.status_code == 200  # Viewers see history (UI-02)
    assert team["outsider"].call("GET", f"/workspaces/{ws}/imports/{import_id}").status_code == 404

    with owner_engine.begin() as conn:
        bind(conn, uuid.UUID(ws))
        row = conn.execute(
            text("SELECT raw_text, occurred_at_missing FROM feedback_records WHERE row_number = 3")
        ).one()
    assert row.raw_text == "Love the new dark mode"
    assert row.occurred_at_missing is True


def test_interrupted_ingest_resumes_without_losing_or_duplicating_rows(
    team: dict[str, Any],
    worker_engine: Engine,
    owner_engine: Engine,
    api_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, ws = team["owner"], team["ws"]
    file_id = _upload(owner, ws, _csv(1200), name="big.csv").json()["id"]
    body = {
        "source_file_id": file_id,
        "source_type": "review",
        "column_mapping": {"text": "review"},
    }
    import_id = owner.call("POST", f"/workspaces/{ws}/imports", json=body).json()["resource_id"]

    real_batch = pipeline._ingest_batch

    def crash_on_second_batch(*args: Any, **kwargs: Any) -> None:
        # Only this import's second batch (other tests' queued jobs may run here too).
        if str(args[1].import_job_id) == import_id and args[4].position == pipeline.BATCH_SIZE:
            raise RuntimeError("simulated worker crash")
        real_batch(*args, **kwargs)

    monkeypatch.setattr(pipeline, "_ingest_batch", crash_on_second_batch)
    _run_worker(worker_engine, api_settings, "w-crash")
    assert _count(owner_engine, ws, "feedback_records", import_id) == 500  # batch 1 committed
    with owner_engine.begin() as conn:  # make the retry runnable now
        bind(conn, uuid.UUID(ws))
        conn.execute(
            text(
                "UPDATE jobs SET run_after = now() - interval '1 hour'"
                " WHERE payload->>'import_job_id' = :i"
            ),
            {"i": import_id},
        )
    monkeypatch.setattr(pipeline, "_ingest_batch", real_batch)
    _run_worker(worker_engine, api_settings, "w-resume")

    report = owner.call("GET", f"/workspaces/{ws}/imports/{import_id}").json()["report"]
    assert report["received"] == 1200
    assert report["reconciled"] is True
    assert _count(owner_engine, ws, "feedback_records", import_id) == 1200


def test_finished_import_is_not_run_twice(
    team: dict[str, Any], worker_engine: Engine, owner_engine: Engine, api_settings: Settings
) -> None:
    owner, ws = team["owner"], team["ws"]
    file_id = _upload(owner, ws, CSV.encode()).json()["id"]
    ref = _start(owner, ws, file_id).json()
    _run_worker(worker_engine, api_settings)
    replay = Job(uuid.UUID(ref["job_id"]), uuid.UUID(ws), "ingest", {
        "import_job_id": ref["resource_id"]
    }, {}, 1, 3)  # fmt: skip
    assert run_ingest(JobContext(replay, worker_engine, "w-replay"), api_settings) == "succeeded"
    assert _count(owner_engine, ws, "feedback_records", ref["resource_id"]) == 2
    assert _count(owner_engine, ws, "import_row_errors", ref["resource_id"]) == 1


def test_a_reconciliation_mismatch_fails_the_import(
    team: dict[str, Any], worker_engine: Engine, api_settings: Settings
) -> None:
    owner, ws = team["owner"], team["ws"]
    file_id = _upload(owner, ws, CSV.encode()).json()["id"]
    ref = _start(owner, ws, file_id).json()
    job = Job(uuid.UUID(ref["job_id"]), uuid.UUID(ws), "ingest", {
        "import_job_id": ref["resource_id"]
    }, {}, 1, 3)  # fmt: skip
    ctx = JobContext(job, worker_engine, "w-mismatch")
    started = pipeline._start(ctx, api_settings, uuid.UUID(ref["resource_id"]))
    assert started is not None
    adapter, validator, batch_ctx = started
    state = IngestState()
    pipeline._ingest_batch(ctx, batch_ctx, adapter, validator, state, total=3)
    # Pretend the file had one more row than was accounted for.
    status = pipeline._finish(ctx, uuid.UUID(ref["resource_id"]), received=4, flags=state.flags)
    assert status == "failed"
    detail = owner.call("GET", f"/workspaces/{ws}/imports/{ref['resource_id']}").json()
    assert detail["status"] == "failed"
    assert detail["report"]["reconciled"] is False
    assert detail["error"].startswith("Reconciliation error")


# ---------------------------------------------------------------- preprocessing in the job
PREP_CSV = (
    "review,date,stars,user\n"
    "Checkout fails. Email me at riya@example.com,2026-10-02,1,u1\n"
    "checkout FAILS!! email me at other@example.com,2026-10-02,2,u1\n"  # same customer copy
    "Checkout fails. Email me at riya@example.com,2026-10-02,1,u2\n"  # another customer
    "ok,2026-10-03,3,u3\n"  # noise
    "<b>Love</b> the export,2026-10-04,8,u4\n"
)


def _records(owner_engine: Engine, ws: str, import_id: str) -> list[Any]:
    with owner_engine.begin() as conn:
        bind(conn, uuid.UUID(ws))
        return list(
            conn.execute(
                text(
                    "SELECT row_number, raw_text, processed_text, analysable, stage,"
                    " exclusion_reason, duplicate_of, customer_id, rating, pii_counts, id"
                    " FROM feedback_records WHERE import_job_id = :i ORDER BY row_number"
                ),
                {"i": import_id},
            ).all()
        )


def test_ingest_masks_standardises_and_marks_duplicates_and_noise(
    team: dict[str, Any], worker_engine: Engine, owner_engine: Engine, api_settings: Settings
) -> None:
    owner, ws = team["owner"], team["ws"]
    file_id = _upload(owner, ws, PREP_CSV.encode()).json()["id"]
    import_id = _start(owner, ws, file_id).json()["resource_id"]
    _run_worker(worker_engine, api_settings)

    rows = {r.row_number: r for r in _records(owner_engine, ws, import_id)}
    first = rows[1]
    assert first.raw_text.endswith("riya@example.com")  # raw text kept (DR-15)
    assert first.processed_text == "Checkout fails. Email me at [EMAIL]"  # masked (DR-29)
    assert first.pii_counts == {"EMAIL": 1}
    assert (first.analysable, first.stage, first.rating) == (True, "prepared", 1)
    # Same customer, same masked text up to case and punctuation: a duplicate (DR-16, DR-18).
    assert rows[2].exclusion_reason == "duplicate"
    assert rows[2].duplicate_of == first.id
    assert rows[2].analysable is False
    # Another customer saying the same thing is corroboration (CR-16).
    assert rows[3].analysable is True
    assert rows[3].customer_id != first.customer_id
    assert rows[4].exclusion_reason == "noise"
    assert rows[4].processed_text == "ok"  # still masked and viewable
    assert rows[5].processed_text == "Love the export"  # markup removed (DR-11)
    assert rows[5].rating == 4  # 8 on the import's 10-point scale (A-24)

    report = owner.call("GET", f"/workspaces/{ws}/imports/{import_id}").json()["report"]
    assert (report["imported"], report["duplicates"], report["filtered"]["noise"]) == (3, 1, 1)
    assert report["pii_masked"] == {"EMAIL": 3}
    assert report["reconciled"] is True
    with owner_engine.begin() as conn:
        bind(conn, uuid.UUID(ws))
        customers = conn.execute(text("SELECT count(*) FROM customers")).scalar_one()
    assert customers == 4  # u1..u4, stored only as keyed hashes (DR-23)


def test_a_masking_failure_fails_closed(
    team: dict[str, Any],
    worker_engine: Engine,
    owner_engine: Engine,
    api_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, ws = team["owner"], team["ws"]
    file_id = _upload(owner, ws, b"review\nMy card is 4111 1111 1111 1111\n").json()["id"]
    body = {
        "source_file_id": file_id,
        "source_type": "review",
        "column_mapping": {"text": "review"},
    }
    import_id = owner.call("POST", f"/workspaces/{ws}/imports", json=body).json()["resource_id"]

    def broken(_text: str) -> Any:
        raise RuntimeError("masking engine unavailable")

    real = pipeline.BatchContext
    monkeypatch.setattr(pipeline, "BatchContext", partial(real, mask=broken))
    _run_worker(worker_engine, api_settings)

    (row,) = _records(owner_engine, ws, import_id)
    assert row.exclusion_reason == "pii_failed"
    assert row.processed_text is None  # unmasked text is never stored as processed text
    assert row.analysable is False
    report = owner.call("GET", f"/workspaces/{ws}/imports/{import_id}").json()["report"]
    assert report["filtered"]["pii_failed"] == 1
    assert report["reconciled"] is True
