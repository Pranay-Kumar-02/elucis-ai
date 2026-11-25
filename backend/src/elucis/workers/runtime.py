"""Background worker runtime: poll, claim, run, heartbeat, finish (D01 ``worker``, SVC-21).

* Handlers are registered per ``job_type`` and receive a ``JobContext``. Each handler
  step runs inside ``ctx.step()``: results and ``queue.checkpoint()`` commit together.
* A heartbeat thread keeps ``heartbeat_at`` fresh while a handler runs, so a crashed worker
  is detected and its job reclaimed (``JobQueue.CLAIM_SQL``).
* Failures go to ``retry_wait`` with exponential backoff until ``max_attempts``.
* SIGINT / SIGTERM (and SIGBREAK on Windows) stop the loop after the current job.
"""

from __future__ import annotations

import logging
import os
import signal
import socket
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from elucis.core.logging import job_id_var
from elucis.db.engine import workspace_scope
from elucis.workers.queue import Job, JobQueue

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class JobContext:
    job: Job
    engine: Engine
    worker_id: str

    @contextmanager
    def step(self) -> Iterator[tuple[Session, JobQueue]]:
        """One idempotent step: a workspace-scoped transaction in which the handler writes its
        results and calls ``queue.checkpoint(...)``, so results and cursor commit together."""
        with Session(self.engine) as session, session.begin():
            workspace_scope(session, self.job.workspace_id)
            yield session, JobQueue(session.connection(), self.worker_id)


Handler = Callable[[JobContext], str | None]  # returns final status or None for "succeeded"


class Worker:
    def __init__(
        self,
        engine: Engine,
        handlers: dict[str, Handler],
        *,
        poll_interval_s: float = 2.0,
        heartbeat_interval_s: float = 15.0,
        worker_id: str | None = None,
    ) -> None:
        self.engine = engine
        self.handlers = handlers
        self.poll_interval_s = poll_interval_s
        self.heartbeat_interval_s = heartbeat_interval_s
        self.worker_id = worker_id or f"{socket.gethostname()}:{os.getpid()}"
        self.stopping = threading.Event()
        self._warned_no_table = False

    # ------------------------------------------------------------------ lifecycle
    def install_signal_handlers(self) -> None:
        def stop(signum: int, _frame: object) -> None:
            logger.info("stop requested", extra={"signal": signum})
            self.stopping.set()

        signal.signal(signal.SIGINT, stop)
        signal.signal(signal.SIGTERM, stop)
        if hasattr(signal, "SIGBREAK"):  # Windows Ctrl+Break
            signal.signal(signal.SIGBREAK, stop)

    def run_forever(self) -> None:
        logger.info(
            "worker started",
            extra={"worker_id": self.worker_id, "job_types": sorted(self.handlers)},
        )
        while not self.stopping.is_set():
            try:
                worked = self.run_once()
            except Exception:
                logger.exception("worker loop error; backing off")
                worked = False
            if not worked:
                self.stopping.wait(self.poll_interval_s)
        logger.info("worker stopped", extra={"worker_id": self.worker_id})

    # ------------------------------------------------------------------ one iteration
    def run_once(self) -> bool:
        """Claim and run at most one job. Returns True if a job was processed."""
        with self.engine.begin() as conn:
            queue = JobQueue(conn, self.worker_id)
            if not queue.table_exists():
                if not self._warned_no_table:
                    logger.warning("jobs table not found; run migrations. Worker is idling.")
                    self._warned_no_table = True
                return False
            job = queue.claim()
        if job is None:
            return False
        self._process(job)
        return True

    def _process(self, job: Job) -> None:
        token = job_id_var.set(str(job.id))
        try:
            handler = self.handlers.get(job.job_type)
            if job.attempts > job.max_attempts:
                self._finish(job, "failed", "attempts exhausted")
                return
            if handler is None:
                self._finish(job, "failed", f"no handler for job type {job.job_type!r}")
                return
            beat_stop = threading.Event()
            beat = threading.Thread(target=self._heartbeat_loop, args=(job, beat_stop), daemon=True)
            beat.start()
            try:
                status = handler(JobContext(job, self.engine, self.worker_id)) or "succeeded"
                self._finish(job, status)
            except Exception as exc:
                logger.exception(
                    "job failed", extra={"job_type": job.job_type, "attempt": job.attempts}
                )
                if job.attempts < job.max_attempts:
                    delay = min(30 * 2 ** (job.attempts - 1), 600)
                    self._finish(job, "retry_wait", type(exc).__name__, retry_delay_s=delay)
                else:
                    self._finish(job, "failed", type(exc).__name__)
            finally:
                beat_stop.set()
                beat.join(timeout=5)
        finally:
            job_id_var.reset(token)

    def _finish(
        self, job: Job, status: str, error: str | None = None, *, retry_delay_s: float = 0
    ) -> None:
        with self.engine.begin() as conn:
            JobQueue(conn, self.worker_id).finish(job, status, error, retry_delay_s=retry_delay_s)
        logger.info("job finished", extra={"job_type": job.job_type, "status": status})

    def _heartbeat_loop(self, job: Job, stop: threading.Event) -> None:
        while not stop.wait(self.heartbeat_interval_s):
            try:
                with self.engine.begin() as conn:
                    if not JobQueue(conn, self.worker_id).heartbeat(job):
                        logger.warning("lost job lock; another worker reclaimed it")
                        return
            except Exception:
                logger.exception("heartbeat failed")
