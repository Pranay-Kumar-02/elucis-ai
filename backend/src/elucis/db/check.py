"""Database verification CLI (``elucis-db-check``).

Checks, in order, and records each result:

1. connection with the configured role;
2. server version (expects PostgreSQL 18);
3. pgvector installed in the database, and its version;
4. a ``vector`` column can be created, written, indexed (HNSW) and queried by cosine distance;
5. PostgreSQL full-text search works (``to_tsvector`` / ``websearch_to_tsquery``).

Steps 4 and 5 use a TEMPORARY table, which PostgreSQL drops at the end of the session, so
the check never creates or changes real schema objects. Credentials are never printed.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text

from elucis.core.config import REPO_ROOT, get_settings
from elucis.core.logging import redact_text
from elucis.db.engine import build_engine
from elucis.repositories.system import SystemRepository, pgvector_ok


def run_checks(role: str) -> dict[str, Any]:
    settings = get_settings()
    report: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "role": role,
        "url": settings.dsn_redacted(role),
        "checks": [],
    }
    checks: list[dict[str, Any]] = report["checks"]

    def record(name: str, ok: bool, **data: Any) -> None:
        checks.append({"name": name, "ok": ok, **data})

    raw = settings.dsn(role)
    if not raw:
        record("configured", False, error="DATABASE_URL is not set (see .env.example)")
        report["ok"] = False
        return report

    engine = build_engine(raw, settings, application_name="elucis-db-check", pooled=False)
    try:
        started = time.perf_counter()
        with engine.connect() as conn:
            record("connect", True, latency_ms=round((time.perf_counter() - started) * 1000, 1))
            info = SystemRepository(conn).info()
            report["server_version"] = info.server_version
            report["database"] = info.database
            report["current_user"] = info.current_user
            record(
                "postgresql_18",
                info.server_version_num // 10000 == 18,
                server_version=info.server_version,
            )
            record(
                "pgvector_installed",
                pgvector_ok(info.pgvector_installed),
                installed=info.pgvector_installed,
                available=info.pgvector_available,
            )
            report["pgvector_version"] = info.pgvector_installed
            conn.commit()  # end the implicit read transaction before the explicit one below

            if info.pgvector_installed:
                with conn.begin():
                    conn.execute(
                        text(
                            "CREATE TEMP TABLE _elucis_vector_check "
                            "(id int PRIMARY KEY, body text, embedding vector(3)) ON COMMIT DROP"
                        )
                    )
                    conn.execute(
                        text(
                            "INSERT INTO _elucis_vector_check VALUES "
                            "(1, 'App crashes when I upload a photo', '[1,0,0]'),"
                            "(2, 'Please add a dark mode', '[0,1,0]'),"
                            "(3, 'Crash on photo upload since update', '[0.9,0.1,0]')"
                        )
                    )
                    conn.execute(
                        text(
                            "CREATE INDEX ON _elucis_vector_check "
                            "USING hnsw (embedding vector_cosine_ops)"
                        )
                    )
                    nearest = conn.execute(
                        text(
                            "SELECT id, round((embedding <=> '[1,0,0]')::numeric, 4) AS distance "
                            "FROM _elucis_vector_check ORDER BY embedding <=> '[1,0,0]' LIMIT 2"
                        )
                    ).all()
                    order = [r.id for r in nearest]
                    record(
                        "vector_column_query",
                        order == [1, 3],
                        nearest_ids=order,
                        distances=[float(r.distance) for r in nearest],
                    )
                    fts = conn.execute(
                        text(
                            "SELECT array_agg(id ORDER BY id) FROM _elucis_vector_check "
                            "WHERE to_tsvector('english', body) @@ "
                            "websearch_to_tsquery('english', 'crash upload')"
                        )
                    ).scalar_one()
                    record("full_text_search", fts == [1, 3], matched_ids=fts)
            else:
                record("vector_column_query", False, error="pgvector is not installed")
    except Exception as exc:  # report every failure instead of crashing the verifier
        record(
            "error",
            False,
            error=type(exc).__name__,
            message=redact_text(str(exc).splitlines()[0][:300]),
        )
    finally:
        engine.dispose()

    report["ok"] = all(c["ok"] for c in checks)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify PostgreSQL + pgvector setup")
    parser.add_argument("--role", choices=["api", "worker", "migration"], default="api")
    parser.add_argument(
        "--report",
        type=Path,
        default=REPO_ROOT / ".setup-reports" / "db-check.json",
        help="where to write the JSON report",
    )
    args = parser.parse_args(argv)
    report = run_checks(args.role)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    for check in report["checks"]:
        mark = "PASS" if check["ok"] else "FAIL"
        detail = {k: v for k, v in check.items() if k not in {"name", "ok"}}
        print(f"[{mark}] {check['name']} {json.dumps(detail, default=str)}")  # noqa: T201
    print(f"Report: {args.report}")  # noqa: T201
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
