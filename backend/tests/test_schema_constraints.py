"""D07 CHECK, UNIQUE and cascade rules on the migrated schema (marker ``db``)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import Connection, Engine, text

from elucis.db.base import Base
from elucis.db.models import UNSCOPED_TABLES
from tests.schema_seed import (
    CHECK_VIOLATION,
    FOREIGN_KEY_VIOLATION,
    UNIQUE_VIOLATION,
    Tenant,
    add_record,
    bind,
    expect_sqlstate,
    new_tenant,
    vector,
)

pytestmark = pytest.mark.db


@pytest.fixture
def tenant(owner_engine: Engine) -> Tenant:
    with owner_engine.begin() as conn:
        return new_tenant(conn)


@pytest.fixture
def conn(owner_engine: Engine, tenant: Tenant) -> Iterator[Connection]:
    """A transaction bound to the tenant, rolled back afterwards."""
    with owner_engine.connect() as connection:
        transaction = connection.begin()
        bind(connection, tenant.workspace_id)
        yield connection
        transaction.rollback()


def _savepoint_fails(conn: Connection, code: str, sql: str, **params: object) -> None:
    with expect_sqlstate(code), conn.begin_nested():
        conn.execute(text(sql), params)


def _run(conn: Connection, t: Tenant) -> uuid.UUID:
    return uuid.UUID(
        str(
            conn.execute(
                text(
                    "INSERT INTO analysis_runs (workspace_id, config, config_hash,"
                    " embedding_model_id) VALUES (:ws, '{}', 'h', 'qwen3-embedding:0.6b')"
                    " RETURNING id"
                ),
                {"ws": t.workspace_id},
            ).scalar_one()
        )
    )


def _theme(conn: Connection, t: Tenant, run: uuid.UUID, name: str = "Checkout") -> uuid.UUID:
    return uuid.UUID(
        str(
            conn.execute(
                text(
                    "INSERT INTO themes (workspace_id, name, first_run_id, last_run_id)"
                    " VALUES (:ws, :n, :r, :r) RETURNING id"
                ),
                {"ws": t.workspace_id, "n": name, "r": run},
            ).scalar_one()
        )
    )


@pytest.mark.parametrize(
    ("assignment", "why"),
    [
        ("analysable = true", "analysable records must be prepared"),
        ("stage = 'prepared', analysable = true, exclusion_reason = 'noise'", "excluded"),
        ("exclusion_reason = 'spam_review'", "spam review needs review_required"),
        ("rating = 6", "rating 1 to 5"),
        ("stage = 'embedded'", "unknown stage"),
    ],
)
def test_feedback_record_checks(
    conn: Connection, tenant: Tenant, assignment: str, why: str
) -> None:
    _savepoint_fails(
        conn,
        CHECK_VIOLATION,
        f"UPDATE feedback_records SET {assignment} WHERE id = :id",
        id=tenant.record_id,
    )


def test_duplicate_link_requires_duplicate_reason(conn: Connection, tenant: Tenant) -> None:
    copy = add_record(conn, tenant.workspace_id, tenant.import_job_id, 2, "Same text")
    _savepoint_fails(
        conn,
        CHECK_VIOLATION,
        "UPDATE feedback_records SET duplicate_of = :orig WHERE id = :id",
        orig=tenant.record_id,
        id=copy,
    )
    conn.execute(
        text(
            "UPDATE feedback_records SET duplicate_of = :orig, exclusion_reason = 'duplicate'"
            " WHERE id = :id"
        ),
        {"orig": tenant.record_id, "id": copy},
    )


def test_one_record_per_import_row(conn: Connection, tenant: Tenant) -> None:
    with expect_sqlstate(UNIQUE_VIOLATION), conn.begin_nested():
        add_record(conn, tenant.workspace_id, tenant.import_job_id, 1, "Same row again")


def test_classification_outcome_checks(conn: Connection, tenant: Tenant) -> None:
    run = _run(conn, tenant)
    insert = (
        "INSERT INTO record_classifications (workspace_id, analysis_run_id, record_id, status,"
        " category, sentiment, method, near_duplicate_of)"
        " VALUES (:ws, :run, :r, :status, :cat, :sent, :method, :dup)"
    )
    base = {"ws": tenant.workspace_id, "run": run, "r": tenant.record_id}
    _savepoint_fails(  # classified without its labels
        conn,
        CHECK_VIOLATION,
        insert,
        **base,
        status="classified",
        cat=None,
        sent=None,
        method=None,
        dup=None,
    )
    _savepoint_fails(  # near duplicate without the record it duplicates
        conn,
        CHECK_VIOLATION,
        insert,
        **base,
        status="near_duplicate",
        cat=None,
        sent=None,
        method=None,
        dup=None,
    )
    conn.execute(
        text(insert),
        {
            **base,
            "status": "classified",
            "cat": "bug_report",
            "sent": "negative",
            "method": "llm",
            "dup": None,
        },
    )
    _savepoint_fails(  # one outcome per record per run
        conn,
        UNIQUE_VIOLATION,
        insert,
        **base,
        status="unclassified",
        cat=None,
        sent=None,
        method=None,
        dup=None,
    )


def test_claim_has_exactly_one_parent(conn: Connection, tenant: Tenant) -> None:
    doc = conn.execute(
        text(
            "INSERT INTO documents (workspace_id, doc_type, title, created_by)"
            " VALUES (:ws, 'prd', 'Checkout', :u) RETURNING id"
        ),
        {"ws": tenant.workspace_id, "u": tenant.user_id},
    ).scalar_one()
    insert = (
        "INSERT INTO claims (workspace_id, document_id, position, claim_type, text)"
        " VALUES (:ws, :doc, 1, 'qualitative', 'Checkout stalls')"
    )
    _savepoint_fails(conn, CHECK_VIOLATION, insert, ws=tenant.workspace_id, doc=None)
    conn.execute(text(insert), {"ws": tenant.workspace_id, "doc": doc})


def test_opportunity_has_exactly_one_matching_source(conn: Connection, tenant: Tenant) -> None:
    theme = _theme(conn, tenant, _run(conn, tenant))
    insert = (
        "INSERT INTO opportunities (workspace_id, source_kind, theme_id, title)"
        " VALUES (:ws, :kind, :theme, 'Fix checkout')"
    )
    _savepoint_fails(
        conn, CHECK_VIOLATION, insert, ws=tenant.workspace_id, kind="theme", theme=None
    )
    _savepoint_fails(
        conn, CHECK_VIOLATION, insert, ws=tenant.workspace_id, kind="request", theme=theme
    )
    conn.execute(text(insert), {"ws": tenant.workspace_id, "kind": "theme", "theme": theme})
    _savepoint_fails(  # one opportunity per theme
        conn, UNIQUE_VIOLATION, insert, ws=tenant.workspace_id, kind="theme", theme=theme
    )


def test_score_inputs_keep_one_current_value_per_input(conn: Connection, tenant: Tenant) -> None:
    theme = _theme(conn, tenant, _run(conn, tenant))
    opportunity = conn.execute(
        text(
            "INSERT INTO opportunities (workspace_id, source_kind, theme_id, title)"
            " VALUES (:ws, 'theme', :t, 'Fix checkout') RETURNING id"
        ),
        {"ws": tenant.workspace_id, "t": theme},
    ).scalar_one()
    insert = (
        "INSERT INTO score_inputs (workspace_id, opportunity_id, framework, input_name, value,"
        " origin, rationale) VALUES (:ws, :o, :fw, :name, 2, :origin, :why)"
    )
    base = {"ws": tenant.workspace_id, "o": opportunity}
    conn.execute(
        text(insert), {**base, "fw": "rice", "name": "impact", "origin": "person", "why": None}
    )
    _savepoint_fails(
        conn, UNIQUE_VIOLATION, insert, **base, fw="rice", name="impact", origin="data", why=None
    )
    _savepoint_fails(  # only effort is shared between frameworks
        conn, CHECK_VIOLATION, insert, **base, fw=None, name="reach", origin="data", why=None
    )
    _savepoint_fails(  # an AI value must carry its rationale
        conn, CHECK_VIOLATION, insert, **base, fw="ice", name="ease", origin="ai", why=None
    )
    conn.execute(
        text(insert), {**base, "fw": None, "name": "effort", "origin": "person", "why": None}
    )


def test_canonical_ask_is_at_most_twelve_words(conn: Connection, tenant: Tenant) -> None:
    run = _run(conn, tenant)
    request = conn.execute(
        text(
            "INSERT INTO aggregated_requests (workspace_id, title, first_run_id, last_run_id)"
            " VALUES (:ws, 'Dark mode', :r, :r) RETURNING id"
        ),
        {"ws": tenant.workspace_id, "r": run},
    ).scalar_one()
    insert = (
        "INSERT INTO request_memberships (workspace_id, analysis_run_id, request_id, record_id,"
        " canonical_ask) VALUES (:ws, :run, :req, :rec, :ask)"
    )
    params = {"ws": tenant.workspace_id, "run": run, "req": request, "rec": tenant.record_id}
    _savepoint_fails(conn, CHECK_VIOLATION, insert, **params, ask=" ".join(["word"] * 13))
    conn.execute(text(insert), {**params, "ask": " ".join(["word"] * 12)})


def test_roadmap_dependencies_stay_inside_one_roadmap(conn: Connection, tenant: Tenant) -> None:
    run = _run(conn, tenant)
    items: dict[str, list[uuid.UUID]] = {}
    for roadmap_name in ("Q1", "Q2"):
        roadmap = conn.execute(
            text("INSERT INTO roadmaps (workspace_id, name) VALUES (:ws, :n) RETURNING id"),
            {"ws": tenant.workspace_id, "n": roadmap_name},
        ).scalar_one()
        for i in range(2):
            theme = _theme(conn, tenant, run, f"{roadmap_name}-{i}")
            opportunity = conn.execute(
                text(
                    "INSERT INTO opportunities (workspace_id, source_kind, theme_id, title)"
                    " VALUES (:ws, 'theme', :t, 'Work') RETURNING id"
                ),
                {"ws": tenant.workspace_id, "t": theme},
            ).scalar_one()
            item = conn.execute(
                text(
                    "INSERT INTO roadmap_items (workspace_id, roadmap_id, opportunity_id, lane,"
                    " position) VALUES (:ws, :rm, :o, 'now', :p) RETURNING id"
                ),
                {"ws": tenant.workspace_id, "rm": roadmap, "o": opportunity, "p": i},
            ).scalar_one()
            items.setdefault(str(roadmap), []).append(item)
    (q1, q1_items), (_, q2_items) = items.items()
    insert = (
        "INSERT INTO roadmap_dependencies (workspace_id, roadmap_id, item_id, depends_on_item_id)"
        " VALUES (:ws, :rm, :a, :b)"
    )
    ws = tenant.workspace_id
    _savepoint_fails(
        conn, FOREIGN_KEY_VIOLATION, insert, ws=ws, rm=q1, a=q1_items[0], b=q2_items[0]
    )
    _savepoint_fails(conn, CHECK_VIOLATION, insert, ws=ws, rm=q1, a=q1_items[0], b=q1_items[0])
    conn.execute(text(insert), {"ws": ws, "rm": q1, "a": q1_items[0], "b": q1_items[1]})
    conn.execute(text("DELETE FROM roadmaps WHERE id = :rm"), {"rm": q1})  # cascades to items
    assert conn.execute(text("SELECT count(*) FROM roadmap_dependencies")).scalar_one() == 0


def test_removing_an_import_job_removes_its_row_errors(conn: Connection, tenant: Tenant) -> None:
    job = conn.execute(
        text(
            "INSERT INTO import_jobs (workspace_id, data_source_id, source_type, column_mapping,"
            " submitted_by) VALUES (:ws, :src, 'review', '{}', :u) RETURNING id"
        ),
        {"ws": tenant.workspace_id, "src": tenant.data_source_id, "u": tenant.user_id},
    ).scalar_one()
    conn.execute(
        text(
            "INSERT INTO import_row_errors (workspace_id, import_job_id, row_number, kind, stage,"
            " code, message) VALUES (:ws, :j, 7, 'rejected', 'validation', 'empty_text',"
            " 'Text is empty')"
        ),
        {"ws": tenant.workspace_id, "j": job},
    )
    conn.execute(text("DELETE FROM import_jobs WHERE id = :j"), {"j": job})
    assert (
        conn.execute(
            text("SELECT count(*) FROM import_row_errors WHERE import_job_id = :j"), {"j": job}
        ).scalar_one()
        == 0
    )
    # Records are never deleted implicitly: an import that produced records is protected.
    _savepoint_fails(
        conn, FOREIGN_KEY_VIOLATION, "DELETE FROM import_jobs WHERE id = :j", j=tenant.import_job_id
    )


def test_deleting_a_workspace_removes_all_its_rows(owner_engine: Engine, tenant: Tenant) -> None:
    ws = tenant.workspace_id
    with owner_engine.begin() as conn:
        bind(conn, ws)
        run = _run(conn, tenant)
        theme = _theme(conn, tenant, run)
        conn.execute(
            text("UPDATE workspaces SET current_analysis_run_id = :r WHERE id = :ws"),
            {"r": run, "ws": ws},
        )
        conn.execute(
            text(
                "INSERT INTO record_embeddings (workspace_id, record_id, model_id, embedding)"
                " VALUES (:ws, :r, 'qwen3-embedding:0.6b', CAST(:v AS vector))"
            ),
            {"ws": ws, "r": tenant.record_id, "v": vector(0.3)},
        )
        conn.execute(
            text(
                "INSERT INTO theme_memberships (workspace_id, analysis_run_id, theme_id,"
                " record_id) VALUES (:ws, :run, :t, :r)"
            ),
            {"ws": ws, "run": run, "t": theme, "r": tenant.record_id},
        )
        conn.execute(
            text(
                "INSERT INTO workspace_memberships (workspace_id, user_id, role)"
                " VALUES (:ws, :u, 'owner')"
            ),
            {"ws": ws, "u": tenant.user_id},
        )
    with owner_engine.begin() as conn:
        conn.execute(text("DELETE FROM workspaces WHERE id = :ws"), {"ws": ws})
    with owner_engine.begin() as conn:
        bind(conn, ws)
        for table in Base.metadata.tables:
            if table in UNSCOPED_TABLES - {"workspace_memberships"} or table == "llm_call_records":
                continue
            remaining = conn.execute(
                text(f"SELECT count(*) FROM {table} WHERE workspace_id = :ws"),
                {"ws": ws},
            ).scalar_one()
            assert remaining == 0, table
