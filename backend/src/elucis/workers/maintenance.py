"""Retention purges run by the worker (D07 §8).

* Sessions: expired rows are deleted (each user's own are also removed at sign-in).
* Login attempts: kept 30 days, enough for the A-08 throttle window and investigation.

Only ``app_worker`` may delete login attempts (IMP-23), so these purges live here and not
in the API. They touch global tables only, so no workspace binding is needed.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Connection

LOGIN_ATTEMPT_RETENTION_DAYS = 30
MAINTENANCE_INTERVAL_S = 3600.0


@dataclass(frozen=True, slots=True)
class PurgeResult:
    sessions: int
    login_attempts: int


def purge_expired(conn: Connection, *, session_idle_minutes: int) -> PurgeResult:
    sessions = conn.execute(
        text(
            "DELETE FROM sessions WHERE expires_at <= now()"
            " OR last_seen_at <= now() - make_interval(mins => :idle)"
        ),
        {"idle": session_idle_minutes},
    ).rowcount
    attempts = conn.execute(
        text("DELETE FROM login_attempts WHERE attempted_at < now() - make_interval(days => :d)"),
        {"d": LOGIN_ATTEMPT_RETENTION_DAYS},
    ).rowcount
    return PurgeResult(sessions=sessions, login_attempts=attempts)
