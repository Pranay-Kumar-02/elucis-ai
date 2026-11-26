"""Tenant isolation, grants and append-only rules on the migrated schema (marker ``db``).

TC-10 (D10 §7): RLS with unset and wrong ``app.workspace_id``, composite foreign keys,
the raw-text trigger and audit immutability, as the real application roles.
"""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import Engine, text

from elucis.workers.queue import JobQueue
from tests.schema_seed import (
    CHECK_VIOLATION,
    FOREIGN_KEY_VIOLATION,
    INSUFFICIENT_PRIVILEGE,
    Tenant,
    bind,
    expect_sqlstate,
    new_tenant,
    vector,
)

pytestmark = pytest.mark.db


@pytest.fixture
def tenants(owner_engine: Engine) -> tuple[Tenant, Tenant]:
    """Two workspaces, each with an import, a record, an embedding, a claim, a job and an
    audit entry."""
    seeded = []
    with owner_engine.begin() as conn:
        for name in ("Alpha", "Beta"):
            t = new_tenant(conn, name)
            params = {"ws": t.workspace_id, "r": t.record_id, "u": t.user_id}
            conn.execute(
                text(
                    "INSERT INTO record_embeddings (workspace_id, record_id, model_id, embedding)"
                    " VALUES (:ws, :r, 'qwen3-embedding:0.6b', CAST(:v AS vector))"
                ),
                {**params, "v": vector(0.5)},
            )
            conn.execute(
                text(
                    "INSERT INTO documents (workspace_id, doc_type, title, created_by)"
                    " VALUES (:ws, 'prd', 'Checkout', :u)"
                ),
                params,
            )
            claim = conn.execute(
                text(
                    "INSERT INTO claims (workspace_id, document_id, position, claim_type, text)"
                    " SELECT :ws, id, 1, 'qualitative', 'Checkout stalls'"
                    " FROM documents WHERE workspace_id = :ws RETURNING id"
                ),
                params,
            ).scalar_one()
            conn.execute(
                text(
                    "INSERT INTO claim_evidence (workspace_id, claim_id, record_id)"
                    " VALUES (:ws, :c, :r)"
                ),
                {**params, "c": claim},
            )
            conn.execute(
                text(
                    "INSERT INTO jobs (workspace_id, job_type, payload)"
                    " VALUES (:ws, 'ingest', '{}')"
                ),
                params,
            )
            conn.execute(
                text(
                    "INSERT INTO audit_logs (workspace_id, actor_user_id, action, outcome)"
                    " VALUES (:ws, :u, 'import.created', 'success')"
                ),
                params,
            )
            seeded.append(t)
    return seeded[0], seeded[1]


TENANT_SAMPLES = ("feedback_records", "record_embeddings", "claim_evidence", "jobs", "audit_logs")


@pytest.fixture(params=["api", "worker"])
def role_engine(request: pytest.FixtureRequest) -> Engine:
    engine: Engine = request.getfixturevalue(f"{request.param}_engine")
    return engine


def _count(conn: object, table: str, ws: uuid.UUID) -> int:
    return int(
        conn.execute(  # type: ignore[attr-defined]
            text(f"SELECT count(*) FROM {table} WHERE workspace_id = :ws"), {"ws": ws}
        ).scalar_one()
    )


@pytest.mark.parametrize("table", TENANT_SAMPLES)
def test_unset_workspace_sees_no_rows(
    tenants: tuple[Tenant, Tenant], api_engine: Engine, table: str
) -> None:
    alpha, _ = tenants
    with api_engine.begin() as conn:
        assert conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() == 0
        bind(conn, alpha.workspace_id)
        assert _count(conn, table, alpha.workspace_id) == 1


def test_setting_left_empty_by_a_pooled_connection_means_no_rows(
    tenants: tuple[Tenant, Tenant], api_engine: Engine
) -> None:
    # After a SET LOCAL transaction ends, the setting reads back as '' (not NULL). The
    # policy must treat that as "no workspace", not fail with an invalid uuid.
    alpha, _ = tenants
    with api_engine.connect() as conn:
        with conn.begin():
            bind(conn, alpha.workspace_id)
            assert conn.execute(text("SELECT count(*) FROM feedback_records")).scalar_one() == 1
        with conn.begin():
            assert (
                conn.execute(text("SELECT current_setting('app.workspace_id', true)")).scalar()
                == ""
            )
            assert conn.execute(text("SELECT count(*) FROM feedback_records")).scalar_one() == 0


@pytest.mark.parametrize("table", TENANT_SAMPLES)
def test_workspace_a_cannot_read_workspace_b(
    tenants: tuple[Tenant, Tenant], role_engine: Engine, table: str
) -> None:
    alpha, beta = tenants
    with role_engine.begin() as conn:
        bind(conn, alpha.workspace_id)
        if table == "jobs" and role_engine.url.username == "app_worker":
            # The worker's queue policy reads jobs across workspaces by design (D07 §5).
            assert _count(conn, table, beta.workspace_id) == 1
        else:
            assert _count(conn, table, beta.workspace_id) == 0


def test_workspace_a_cannot_change_or_create_rows_in_b(
    tenants: tuple[Tenant, Tenant], role_engine: Engine
) -> None:
    alpha, beta = tenants
    with role_engine.begin() as conn:
        bind(conn, alpha.workspace_id)
        updated = conn.execute(
            text("UPDATE feedback_records SET processed_text = 'x' WHERE id = :id"),
            {"id": beta.record_id},
        )
        deleted = conn.execute(
            text("DELETE FROM record_embeddings WHERE record_id = :id"), {"id": beta.record_id}
        )
        assert updated.rowcount == 0
        assert deleted.rowcount == 0
    with role_engine.begin() as conn, expect_sqlstate(INSUFFICIENT_PRIVILEGE):
        bind(conn, alpha.workspace_id)
        conn.execute(
            text("INSERT INTO jobs (workspace_id, job_type, payload) VALUES (:ws, 'ingest', '{}')"),
            {"ws": beta.workspace_id},
        )


def test_composite_foreign_key_rejects_cross_workspace_reference(
    tenants: tuple[Tenant, Tenant], owner_engine: Engine
) -> None:
    alpha, beta = tenants
    with owner_engine.begin() as conn, expect_sqlstate(FOREIGN_KEY_VIOLATION):
        bind(conn, alpha.workspace_id)
        conn.execute(
            text(
                "INSERT INTO import_jobs (workspace_id, data_source_id, source_type,"
                " column_mapping, submitted_by) VALUES (:ws, :src, 'review', '{}', :u)"
            ),
            {"ws": alpha.workspace_id, "src": beta.data_source_id, "u": alpha.user_id},
        )


def test_worker_claims_across_workspaces_but_reads_no_tenant_data(
    tenants: tuple[Tenant, Tenant], worker_engine: Engine, owner_engine: Engine
) -> None:
    claimed = set()
    with worker_engine.begin() as conn:
        queue = JobQueue(conn, "w-rls")
        while (job := queue.claim()) is not None:
            claimed.add(job.workspace_id)
        assert conn.execute(text("SELECT count(*) FROM feedback_records")).scalar_one() == 0
    assert {t.workspace_id for t in tenants} <= claimed
    with owner_engine.begin() as conn:  # leave the queue empty for other tests
        for t in tenants:
            bind(conn, t.workspace_id)
            conn.execute(text("DELETE FROM jobs WHERE workspace_id = :ws"), {"ws": t.workspace_id})


def test_api_role_cannot_run_ddl(api_engine: Engine, migrated_schema: str) -> None:
    with api_engine.begin() as conn, expect_sqlstate(INSUFFICIENT_PRIVILEGE):
        conn.execute(text(f'CREATE TABLE "{migrated_schema}".intruder (id int)'))
    with api_engine.begin() as conn, expect_sqlstate(INSUFFICIENT_PRIVILEGE):
        conn.execute(text("ALTER TABLE feedback_records DISABLE ROW LEVEL SECURITY"))


@pytest.mark.parametrize(
    "statement",
    ["UPDATE audit_logs SET outcome = 'failure'", "DELETE FROM audit_logs"],
)
def test_audit_log_is_append_only(
    tenants: tuple[Tenant, Tenant], role_engine: Engine, statement: str
) -> None:
    alpha, _ = tenants
    with role_engine.begin() as conn, expect_sqlstate(INSUFFICIENT_PRIVILEGE):
        bind(conn, alpha.workspace_id)
        conn.execute(text(statement))


def test_score_input_values_cannot_be_rewritten(
    tenants: tuple[Tenant, Tenant], owner_engine: Engine, api_engine: Engine
) -> None:
    alpha, _ = tenants
    with owner_engine.begin() as conn:
        bind(conn, alpha.workspace_id)
        theme_run = conn.execute(
            text(
                "INSERT INTO analysis_runs (workspace_id, config, config_hash, embedding_model_id)"
                " VALUES (:ws, '{}', 'h', 'qwen3-embedding:0.6b') RETURNING id"
            ),
            {"ws": alpha.workspace_id},
        ).scalar_one()
        theme = conn.execute(
            text(
                "INSERT INTO themes (workspace_id, name, first_run_id, last_run_id)"
                " VALUES (:ws, 'Checkout', :r, :r) RETURNING id"
            ),
            {"ws": alpha.workspace_id, "r": theme_run},
        ).scalar_one()
        opportunity = conn.execute(
            text(
                "INSERT INTO opportunities (workspace_id, source_kind, theme_id, title)"
                " VALUES (:ws, 'theme', :t, 'Fix checkout') RETURNING id"
            ),
            {"ws": alpha.workspace_id, "t": theme},
        ).scalar_one()
        score_input = conn.execute(
            text(
                "INSERT INTO score_inputs (workspace_id, opportunity_id, framework, input_name,"
                " value, origin) VALUES (:ws, :o, 'rice', 'reach', 168, 'data') RETURNING id"
            ),
            {"ws": alpha.workspace_id, "o": opportunity},
        ).scalar_one()
    with api_engine.begin() as conn:
        bind(conn, alpha.workspace_id)
        conn.execute(
            text(
                "UPDATE score_inputs SET is_current = false, superseded_at = now() WHERE id = :id"
            ),
            {"id": score_input},
        )
    with api_engine.begin() as conn, expect_sqlstate(INSUFFICIENT_PRIVILEGE):
        bind(conn, alpha.workspace_id)
        conn.execute(
            text("UPDATE score_inputs SET value = 999 WHERE id = :id"), {"id": score_input}
        )


def test_raw_text_is_immutable_but_processed_text_is_not(
    tenants: tuple[Tenant, Tenant], api_engine: Engine
) -> None:
    alpha, _ = tenants
    with api_engine.begin() as conn:
        bind(conn, alpha.workspace_id)
        conn.execute(
            text(
                "UPDATE feedback_records SET processed_text = 'Checkout stalls at [EMAIL]'"
                " WHERE id = :id"
            ),
            {"id": alpha.record_id},
        )
        matched = conn.execute(
            text(
                "SELECT count(*) FROM feedback_records"
                " WHERE search_tsv @@ websearch_to_tsquery('english', 'stalls')"
            ),
        ).scalar_one()
        assert matched == 1  # the generated search column follows processed_text
    with api_engine.begin() as conn, expect_sqlstate(CHECK_VIOLATION):
        bind(conn, alpha.workspace_id)
        conn.execute(
            text("UPDATE feedback_records SET raw_text = 'rewritten' WHERE id = :id"),
            {"id": alpha.record_id},
        )


def test_workspace_deletion_keeps_only_the_deletion_event(
    tenants: tuple[Tenant, Tenant],
    owner_engine: Engine,
    api_engine: Engine,
    worker_engine: Engine,
) -> None:
    alpha, beta = tenants
    with api_engine.begin() as conn:  # Alpha has 3 audit entries in total, Beta 1
        bind(conn, alpha.workspace_id)
        for action in ("document.approved", "member.added"):
            conn.execute(
                text(
                    "INSERT INTO audit_logs (workspace_id, actor_user_id, action, outcome)"
                    " VALUES (:ws, :u, :a, 'success')"
                ),
                {"ws": alpha.workspace_id, "u": alpha.user_id, "a": action},
            )

    # The delete_workspace job: delete the workspace (cascade), then record the event.
    with worker_engine.begin() as conn:
        name = conn.execute(
            text("SELECT name FROM workspaces WHERE id = :ws"), {"ws": alpha.workspace_id}
        ).scalar_one()
        conn.execute(text("DELETE FROM workspaces WHERE id = :ws"), {"ws": alpha.workspace_id})
        conn.execute(
            text(
                "INSERT INTO audit_logs (workspace_id, actor_user_id, action, target_type,"
                " target_id, outcome, details) VALUES (NULL, :u, 'workspace.deleted',"
                " 'workspace', :ws, 'success', CAST(:d AS jsonb))"
            ),
            {
                "u": alpha.user_id,
                "ws": alpha.workspace_id,
                "d": json.dumps({"workspace_name": name}),
            },
        )

    with owner_engine.begin() as conn:
        bind(conn, alpha.workspace_id)
        assert _count(conn, "audit_logs", alpha.workspace_id) == 0
        assert _count(conn, "feedback_records", alpha.workspace_id) == 0
        bind(conn, beta.workspace_id)
        assert _count(conn, "audit_logs", beta.workspace_id) == 1
        bind(conn, None)
        event = conn.execute(
            text("SELECT * FROM audit_logs WHERE target_id = :ws"), {"ws": alpha.workspace_id}
        ).one()
    assert event.workspace_id is None
    assert event.action == "workspace.deleted"
    assert event.actor_user_id == alpha.user_id
    assert event.created_at is not None
    assert event.target_type == "workspace"
    assert event.details == {"workspace_name": "Alpha"}  # no customer text

    for engine in (api_engine, worker_engine):  # global events are not readable by app roles
        with engine.begin() as conn:
            hidden = conn.execute(
                text("SELECT count(*) FROM audit_logs WHERE action = 'workspace.deleted'")
            ).scalar_one()
            assert hidden == 0
