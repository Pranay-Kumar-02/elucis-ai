"""Read-only database diagnostics used by health checks and the setup verifier.

Repositories own SQL; services and routers never build queries. Tenant repositories added
with the schema will take ``workspace_id`` on every method (D09 section 5).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Connection

MIN_PGVECTOR = (0, 8, 0)


@dataclass(frozen=True, slots=True)
class DatabaseInfo:
    server_version: str
    server_version_num: int
    database: str
    current_user: str
    pgvector_installed: str | None
    pgvector_available: str | None
    jobs_table_present: bool


def _version_tuple(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split(".") if part.isdigit())


def pgvector_ok(version: str | None) -> bool:
    return version is not None and _version_tuple(version) >= MIN_PGVECTOR


class SystemRepository:
    def __init__(self, conn: Connection) -> None:
        self.conn = conn

    def ping(self) -> None:
        self.conn.execute(text("SELECT 1"))

    def info(self) -> DatabaseInfo:
        row = self.conn.execute(
            text(
                """
                SELECT current_setting('server_version')                     AS server_version,
                       current_setting('server_version_num')::int             AS server_version_num,
                       current_database()                                     AS database,
                       current_user                                           AS current_user,
                       (SELECT extversion FROM pg_extension WHERE extname = 'vector')
                                                                              AS pgvector_installed,
                       (SELECT default_version FROM pg_available_extensions
                         WHERE name = 'vector')                               AS pgvector_available,
                       to_regclass('public.jobs') IS NOT NULL                 AS jobs_table_present
                """
            )
        ).one()
        return DatabaseInfo(**row._asdict())
