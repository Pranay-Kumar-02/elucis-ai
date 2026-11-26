"""Retention purges as app_worker (marker ``db``, D07 §8)."""

from __future__ import annotations

import pytest
from sqlalchemy import Engine, text

from elucis.workers.maintenance import purge_expired
from elucis.workers.runtime import Worker
from tests.schema_seed import new_user

pytestmark = pytest.mark.db


def test_purge_removes_only_expired_rows(owner_engine: Engine, worker_engine: Engine) -> None:
    with owner_engine.begin() as conn:
        user = new_user(conn)
        for label, created, seen, expires in [
            ("live", "now()", "now()", "now() + interval '1 hour'"),
            ("idle", "now()", "now() - interval '31 minutes'", "now() + interval '1 hour'"),
            ("absolute", "now() - interval '13 hours'", "now()", "now() - interval '1 hour'"),
        ]:
            conn.execute(
                text(
                    "INSERT INTO sessions (user_id, token_hash, csrf_token_hash, created_at,"
                    f" last_seen_at, expires_at) VALUES (:u, :t, :t, {created}, {seen}, {expires})"
                ),
                {"u": user, "t": label.encode() + user.bytes},
            )
        for age in ("1 day", "31 days"):
            conn.execute(
                text(
                    "INSERT INTO login_attempts (email_lower, succeeded, attempted_at)"
                    f" VALUES ('purge@example.test', false, now() - interval '{age}')"
                )
            )
    with worker_engine.begin() as conn:
        purge_expired(conn, session_idle_minutes=30)
    with owner_engine.connect() as conn:
        sessions = (
            conn.execute(text("SELECT token_hash FROM sessions WHERE user_id = :u"), {"u": user})
            .scalars()
            .all()
        )
        attempts = conn.execute(
            text("SELECT count(*) FROM login_attempts WHERE email_lower = 'purge@example.test'")
        ).scalar_one()
    assert [bytes(s)[:4] for s in sessions] == [b"live"]
    assert attempts == 1


def test_worker_runs_maintenance_once_per_interval(worker_engine: Engine) -> None:
    calls: list[int] = []
    worker = Worker(
        worker_engine,
        {},
        worker_id="w-maint",
        maintenance=lambda _c: calls.append(1),
        maintenance_interval_s=3600,
    )
    assert worker.run_maintenance_if_due() is True
    assert worker.run_maintenance_if_due() is False  # not again within the hour
    assert calls == [1]
