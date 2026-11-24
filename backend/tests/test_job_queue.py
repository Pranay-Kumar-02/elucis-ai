"""Job queue claim semantics against real PostgreSQL (marker ``db``).

The ``jobs`` table here is a test fixture in a throwaway schema with exactly the D07 columns
the queue uses. It is not the production schema, which the schema task creates.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.pool import NullPool

from copilot.db.engine import normalise_url
from copilot.workers.queue import JobQueue
from copilot.workers.runtime import JobContext, Worker

pytestmark = pytest.mark.db

JOBS_FIXTURE = """
CREATE TABLE jobs (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id  uuid NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now(),
    job_type      text NOT NULL,
    status        text NOT NULL DEFAULT 'queued'
                  CHECK (status IN ('queued','running','retry_wait','succeeded',
                                    'succeeded_with_errors','failed','cancelled')),
    priority      smallint NOT NULL DEFAULT 5,
    payload       jsonb NOT NULL,
    cursor        jsonb NOT NULL DEFAULT '{}',
    progress      jsonb NOT NULL DEFAULT '{}',
    attempts      smallint NOT NULL DEFAULT 0,
    max_attempts  smallint NOT NULL DEFAULT 3,
    run_after     timestamptz NOT NULL DEFAULT now(),
    locked_by     text,
    heartbeat_at  timestamptz,
    started_at    timestamptz,
    finished_at   timestamptz,
    error         text,
    idempotency_key text,
    created_by    uuid
)
"""


@pytest.fixture
def jobs_engine(schema_engine: Engine, test_schema: str) -> Iterator[Engine]:
    # Always schema-qualified: these statements can only ever touch the throwaway schema.
    drop = text(f'DROP TABLE IF EXISTS "{test_schema}".jobs')
    with schema_engine.begin() as conn:
        conn.execute(drop)
        conn.execute(
            text(JOBS_FIXTURE.replace("CREATE TABLE jobs", f'CREATE TABLE "{test_schema}".jobs'))
        )
    yield schema_engine
    with schema_engine.begin() as conn:
        conn.execute(drop)


def _enqueue(
    engine: Engine, job_type: str = "ingest", priority: int = 5, **cols: object
) -> uuid.UUID:
    with engine.begin() as conn:
        return conn.execute(
            text(
                "INSERT INTO jobs (workspace_id, job_type, priority, payload) "
                "VALUES (:ws, :t, :p, CAST(:payload AS jsonb)) RETURNING id"
            ),
            {"ws": uuid.uuid4(), "t": job_type, "p": priority, "payload": json.dumps(cols)},
        ).scalar_one()


def _status(engine: Engine, job_id: uuid.UUID) -> dict[str, object]:
    with engine.connect() as conn:
        row = conn.execute(text("SELECT * FROM jobs WHERE id = :id"), {"id": job_id}).one()
    return row._asdict()


def test_two_workers_never_claim_the_same_job(jobs_engine: Engine) -> None:
    a_id, b_id = _enqueue(jobs_engine), _enqueue(jobs_engine)
    with jobs_engine.connect() as c1, jobs_engine.connect() as c2:
        t1, t2 = c1.begin(), c2.begin()
        first = JobQueue(c1, "w1").claim()
        second = JobQueue(c2, "w2").claim()  # SKIP LOCKED: does not wait for w1
        third = JobQueue(c2, "w2").claim()
        t1.commit()
        t2.commit()
    assert first is not None and second is not None
    assert {first.id, second.id} == {a_id, b_id}
    assert third is None


def test_priority_order_and_claim_bookkeeping(jobs_engine: Engine) -> None:
    _enqueue(jobs_engine, priority=5)
    urgent = _enqueue(jobs_engine, priority=1)
    with jobs_engine.begin() as conn:
        job = JobQueue(conn, "w1").claim()
    assert job is not None and job.id == urgent
    row = _status(jobs_engine, urgent)
    assert row["status"] == "running"
    assert row["locked_by"] == "w1"
    assert row["attempts"] == 1
    assert row["heartbeat_at"] is not None


def test_stale_heartbeat_job_is_reclaimed(jobs_engine: Engine) -> None:
    job_id = _enqueue(jobs_engine)
    with jobs_engine.begin() as conn:
        assert JobQueue(conn, "crashed").claim() is not None
        conn.execute(
            text("UPDATE jobs SET heartbeat_at = now() - interval '10 minutes' WHERE id = :id"),
            {"id": job_id},
        )
    with jobs_engine.begin() as conn:
        reclaimed = JobQueue(conn, "w2", stale_after_s=120).claim()
    assert reclaimed is not None and reclaimed.id == job_id and reclaimed.attempts == 2


def test_checkpoint_and_finish_only_by_lock_holder(jobs_engine: Engine) -> None:
    job_id = _enqueue(jobs_engine)
    with jobs_engine.begin() as conn:
        job = JobQueue(conn, "w1").claim()
    assert job is not None
    with jobs_engine.begin() as conn:
        JobQueue(conn, "intruder").finish(job, "failed", "should not apply")
        JobQueue(conn, "w1").checkpoint(job, {"step": "validate", "position": 500}, {"done": 500})
    row = _status(jobs_engine, job_id)
    assert row["status"] == "running"
    assert row["cursor"] == {"step": "validate", "position": 500}
    with jobs_engine.begin() as conn:
        JobQueue(conn, "w1").finish(job, "retry_wait", "ModelUnavailableError", retry_delay_s=60)
    row = _status(jobs_engine, job_id)
    assert row["status"] == "retry_wait"
    assert row["locked_by"] is None
    assert row["finished_at"] is None
    with jobs_engine.begin() as conn:
        assert JobQueue(conn, "w1").claim() is None  # run_after is 60 s in the future


def test_worker_runs_handler_and_retries_failures(jobs_engine: Engine) -> None:
    ok_id = _enqueue(jobs_engine, "ingest")
    seen: list[str] = []

    def ingest(ctx: JobContext) -> None:
        with ctx.step() as (session, queue):
            ws = session.execute(text("SELECT current_setting('app.workspace_id', true)")).scalar()
            assert ws == str(ctx.job.workspace_id)  # RLS scope applied inside each step
            queue.checkpoint(ctx.job, {"position": 1}, {"done": 1})
        seen.append(str(ctx.job.id))

    worker = Worker(jobs_engine, {"ingest": ingest}, worker_id="w-test")
    assert worker.run_once() is True
    assert _status(jobs_engine, ok_id)["status"] == "succeeded"
    assert _status(jobs_engine, ok_id)["cursor"] == {"position": 1}
    assert seen == [str(ok_id)]

    bad_id = _enqueue(jobs_engine, "analysis")

    def analysis(_: JobContext) -> None:
        raise RuntimeError("model down")

    worker = Worker(jobs_engine, {"analysis": analysis}, worker_id="w-test")
    assert worker.run_once() is True
    row = _status(jobs_engine, bad_id)
    assert row["status"] == "retry_wait"
    assert row["error"] == "RuntimeError"
    assert worker.run_once() is False  # backoff: not runnable yet


def test_unknown_job_type_fails_cleanly(jobs_engine: Engine) -> None:
    job_id = _enqueue(jobs_engine, "reembed")
    assert Worker(jobs_engine, {}, worker_id="w").run_once() is True
    row = _status(jobs_engine, job_id)
    assert row["status"] == "failed"
    assert "no handler" in str(row["error"])


def test_worker_idles_when_jobs_table_missing(database_url: str, test_schema: str) -> None:
    # search_path is the empty test schema only, so no "jobs" table is visible.
    engine = create_engine(
        normalise_url(database_url),
        poolclass=NullPool,
        connect_args={"options": f"-c search_path={test_schema}"},
    )
    try:
        assert Worker(engine, {}, worker_id="w").run_once() is False
    finally:
        engine.dispose()
