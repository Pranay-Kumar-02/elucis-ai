"""PostgreSQL job queue (D03 SVC-21, D07 ``jobs``, D09 ``JobQueue`` protocol).

Claiming uses ``FOR UPDATE SKIP LOCKED`` so several workers never take the same job and
never block each other. A claim, its heartbeat and its checkpoints are ordinary rows, so a
crashed worker's job is reclaimed once its heartbeat is stale. Steps must be idempotent:
the guarantee is *at-least-once* execution with checkpoints, not exactly-once.

The ``jobs`` table itself is created by the schema migration (next task). ``JobQueue``
works against it unchanged; until it exists ``table_exists()`` returns ``False`` and the
worker idles.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

# One statement: pick the best runnable job, lock it, mark it running. Jobs whose worker
# stopped heart-beating for `stale_after` seconds are runnable again (crash recovery).
CLAIM_SQL = text(
    """
    WITH next_job AS (
        SELECT id
          FROM jobs
         WHERE (status IN ('queued', 'retry_wait') AND run_after <= now())
            OR (status = 'running'
                AND heartbeat_at < now() - make_interval(secs => :stale_after))
         ORDER BY priority, run_after, created_at
         LIMIT 1
         FOR UPDATE SKIP LOCKED
    )
    UPDATE jobs AS j
       SET status       = 'running',
           locked_by    = :worker_id,
           heartbeat_at = now(),
           started_at   = coalesce(j.started_at, now()),
           attempts     = j.attempts + 1
      FROM next_job
     WHERE j.id = next_job.id
    RETURNING j.id, j.workspace_id, j.job_type, j.payload, j.cursor, j.attempts, j.max_attempts
    """
)

HEARTBEAT_SQL = text(
    "UPDATE jobs SET heartbeat_at = now() WHERE id = :id AND locked_by = :worker_id"
)

CHECKPOINT_SQL = text(
    """
    UPDATE jobs SET cursor = CAST(:cursor AS jsonb), progress = CAST(:progress AS jsonb),
                    heartbeat_at = now()
     WHERE id = :id AND locked_by = :worker_id
    """
)

FINISH_SQL = text(
    """
    UPDATE jobs
       SET status      = :status,
           error       = :error,
           finished_at = CASE WHEN :status IN ('succeeded', 'succeeded_with_errors', 'failed',
                                                'cancelled') THEN now() END,
           run_after   = CASE WHEN :status = 'retry_wait'
                              THEN now() + make_interval(secs => :retry_delay) ELSE run_after END,
           locked_by   = NULL
     WHERE id = :id AND locked_by = :worker_id
    """
)

TERMINAL = frozenset({"succeeded", "succeeded_with_errors", "failed", "cancelled"})


@dataclass(frozen=True, slots=True)
class Job:
    id: uuid.UUID
    workspace_id: uuid.UUID
    job_type: str
    payload: dict[str, Any]
    cursor: dict[str, Any]
    attempts: int
    max_attempts: int


class JobQueue:
    def __init__(self, conn: Connection, worker_id: str, *, stale_after_s: float = 120.0) -> None:
        self.conn = conn
        self.worker_id = worker_id
        self.stale_after_s = stale_after_s

    def table_exists(self) -> bool:
        return bool(self.conn.execute(text("SELECT to_regclass('jobs') IS NOT NULL")).scalar_one())

    def claim(self) -> Job | None:
        row = self.conn.execute(
            CLAIM_SQL, {"worker_id": self.worker_id, "stale_after": self.stale_after_s}
        ).one_or_none()
        if row is None:
            return None
        return Job(**row._asdict())

    def heartbeat(self, job: Job) -> bool:
        result = self.conn.execute(HEARTBEAT_SQL, {"id": job.id, "worker_id": self.worker_id})
        return result.rowcount == 1

    def checkpoint(self, job: Job, cursor: dict[str, Any], progress: dict[str, Any]) -> None:
        """Call in the same transaction as the step's writes, so both commit or neither does."""
        self.conn.execute(
            CHECKPOINT_SQL,
            {
                "id": job.id,
                "worker_id": self.worker_id,
                "cursor": json.dumps(cursor),
                "progress": json.dumps(progress),
            },
        )

    def finish(
        self, job: Job, status: str, error: str | None = None, *, retry_delay_s: float = 0
    ) -> None:
        if status not in TERMINAL | {"retry_wait"}:
            raise ValueError(f"invalid final status {status!r}")
        self.conn.execute(
            FINISH_SQL,
            {
                "id": job.id,
                "worker_id": self.worker_id,
                "status": status,
                "error": error[:2000] if error else None,
                "retry_delay": retry_delay_s,
            },
        )
