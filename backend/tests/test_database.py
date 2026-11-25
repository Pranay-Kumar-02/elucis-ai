"""Real PostgreSQL 18 + pgvector checks (marker ``db``)."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from elucis.db import check as db_check
from elucis.db.engine import normalise_url, workspace_scope
from elucis.repositories.system import SystemRepository, pgvector_ok

pytestmark = pytest.mark.db


def test_normalise_url_forces_psycopg3() -> None:
    assert normalise_url("postgres://u:p@h:5432/d").startswith("postgresql+psycopg://")
    assert normalise_url("postgresql://u:p@h/d").startswith("postgresql+psycopg://")
    with pytest.raises(ValueError, match="Unsupported"):
        normalise_url("mysql://u:p@h/d")


def test_server_is_postgresql_18_with_pgvector(schema_engine: Engine) -> None:
    with schema_engine.connect() as conn:
        info = SystemRepository(conn).info()
    assert info.server_version_num // 10000 == 18
    assert pgvector_ok(info.pgvector_installed)
    assert info.pgvector_installed == info.pgvector_available


def test_vector_column_hnsw_index_and_cosine_query(schema_engine: Engine) -> None:
    with schema_engine.begin() as conn:
        conn.execute(text("CREATE TEMP TABLE emb (id int PRIMARY KEY, e vector(4)) ON COMMIT DROP"))
        conn.execute(
            text("INSERT INTO emb VALUES (1,'[1,0,0,0]'), (2,'[0,1,0,0]'), (3,'[0.9,0.1,0,0]')")
        )
        conn.execute(text("CREATE INDEX emb_hnsw ON emb USING hnsw (e vector_cosine_ops)"))
        ids = (
            conn.execute(text("SELECT id FROM emb ORDER BY e <=> '[1,0,0,0]' LIMIT 2"))
            .scalars()
            .all()
        )
        dims = conn.execute(text("SELECT vector_dims(e) FROM emb LIMIT 1")).scalar_one()
    assert ids == [1, 3]
    assert dims == 4


def test_1024_dimension_vector_supported(schema_engine: Engine) -> None:
    """The design's assumed dimension (D07); the real model dimension is measured separately."""
    vec = "[" + ",".join(["0.01"] * 1024) + "]"
    with schema_engine.begin() as conn:
        conn.execute(text("CREATE TEMP TABLE e1024 (e vector(1024)) ON COMMIT DROP"))
        conn.execute(text("INSERT INTO e1024 VALUES (CAST(:v AS vector))"), {"v": vec})
        assert conn.execute(text("SELECT vector_dims(e) FROM e1024")).scalar_one() == 1024


def test_workspace_scope_is_transaction_local(schema_engine: Engine) -> None:
    ws = uuid.uuid4()
    with Session(schema_engine) as session:
        with session.begin():
            workspace_scope(session, ws)
            inside = session.execute(
                text("SELECT current_setting('app.workspace_id', true)")
            ).scalar()
        outside = session.execute(text("SELECT current_setting('app.workspace_id', true)")).scalar()
    assert inside == str(ws)
    assert outside in (None, "")


def test_workspace_scope_rejects_non_uuid(schema_engine: Engine) -> None:
    with Session(schema_engine) as session, pytest.raises(TypeError):
        workspace_scope(session, "not-a-uuid")  # type: ignore[arg-type]


def test_db_check_cli_passes(
    database_url: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:

    monkeypatch.setenv("DATABASE_URL", database_url)
    db_check.get_settings.cache_clear()
    try:
        report_path = tmp_path / "db-check.json"
        assert db_check.main(["--report", str(report_path)]) == 0
        report = report_path.read_text(encoding="utf-8")
    finally:
        db_check.get_settings.cache_clear()
    assert '"pgvector_version": "0.8.7"' in report
    password = database_url.split(":")[2].split("@", maxsplit=1)[0]
    assert password not in report  # credentials never written to reports
