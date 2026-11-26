"""Vector and keyword search on the migrated schema use their indexes (marker ``db``)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import Connection, Engine, text

from tests.schema_seed import (
    DATA_EXCEPTION,
    Tenant,
    add_record,
    bind,
    expect_sqlstate,
    new_tenant,
    vector,
)

pytestmark = pytest.mark.db

EMBED = (
    "INSERT INTO record_embeddings (workspace_id, record_id, model_id, embedding)"
    " VALUES (:ws, :r, :m, CAST(:v AS vector))"
)


@pytest.fixture
def conn(owner_engine: Engine) -> Iterator[tuple[Connection, Tenant]]:
    with owner_engine.connect() as connection:
        transaction = connection.begin()
        tenant = new_tenant(connection)
        bind(connection, tenant.workspace_id)
        yield connection, tenant
        transaction.rollback()


def _plan(conn: Connection, sql: str, *disabled: str, **params: object) -> str:
    """The plan with the given competing strategies switched off for this transaction.

    The test tables are tiny and unanalysed, so the planner would rightly prefer a scan
    and a sort. Switching those off proves the index can serve the query under the
    row-level security filter, which is the property that matters at real sizes.
    """
    for setting in ("enable_seqscan", *disabled):
        conn.execute(text(f"SET LOCAL {setting} = off"))
    rows = conn.execute(text(f"EXPLAIN {sql}"), params).scalars()
    return "\n".join(rows)


def test_embeddings_must_have_1024_dimensions(conn: tuple[Connection, Tenant]) -> None:
    c, t = conn
    params = {"ws": t.workspace_id, "r": t.record_id, "m": "qwen3-embedding:0.6b"}
    c.execute(text(EMBED), {**params, "v": vector(0.2)})
    with expect_sqlstate(DATA_EXCEPTION), c.begin_nested():
        c.execute(text(EMBED), {**params, "m": "other-model", "v": vector(0.2, dims=768)})


def test_cosine_search_uses_the_hnsw_index_for_the_current_model(
    conn: tuple[Connection, Tenant],
) -> None:
    c, t = conn
    for i in range(20):
        record = add_record(c, t.workspace_id, t.import_job_id, 100 + i, f"Feedback {i}")
        c.execute(
            text(EMBED),
            {"ws": t.workspace_id, "r": record, "m": "qwen3-embedding:0.6b", "v": vector(i / 20)},
        )
    query = (
        "SELECT record_id FROM record_embeddings WHERE model_id = 'qwen3-embedding:0.6b'"
        " ORDER BY embedding <=> CAST(:q AS vector) LIMIT 5"
    )
    assert "ix_record_embeddings_embedding_hnsw" in _plan(c, query, "enable_sort", q=vector(0.5))
    nearest = c.execute(text(query), {"q": vector(0.5)}).scalars().all()
    assert len(nearest) == 5


def test_keyword_search_under_rls_is_correct_but_cannot_use_the_gin_index(
    conn: tuple[Connection, Tenant],
) -> None:
    """Finding F-06 (FOUNDATION_NOTES), measured rather than assumed.

    With row-level security forced, PostgreSQL only uses a predicate as an index condition
    ahead of the policy when its operator is LEAKPROOF. ``tsvector @@ tsquery``
    (``ts_match_vq``) is not, so the D07 GIN index is not used and each workspace's rows
    are filtered one by one. Results stay correct. When F-06 is decided (for example by
    marking ``ts_match_vq`` LEAKPROOF in the bootstrap), this test must change to assert
    the index is used.
    """
    c, t = conn
    leakproof = c.execute(
        text(
            "SELECT p.proleakproof FROM pg_operator o JOIN pg_proc p ON p.oid = o.oprcode"
            " WHERE o.oprname = '@@' AND o.oprleft = 'tsvector'::regtype"
            " AND o.oprright = 'tsquery'::regtype"
        )
    ).scalar_one()
    assert leakproof is False
    c.execute(
        text(
            "INSERT INTO feedback_records (workspace_id, import_job_id, row_number, source_type,"
            " raw_text, processed_text)"
            " SELECT :ws, :ij, n, 'review', 'Dark mode please ' || n, 'Dark mode please ' || n"
            " FROM generate_series(1000, 4999) AS n"
        ),
        {"ws": t.workspace_id, "ij": t.import_job_id},
    )
    add_record(c, t.workspace_id, t.import_job_id, 5000, "Checkout freezes on Pay")
    c.execute(text("ANALYZE feedback_records"))
    query = (
        "SELECT id FROM feedback_records"
        " WHERE search_tsv @@ websearch_to_tsquery('english', 'checkout')"
    )
    plan = "\n".join(c.execute(text(f"EXPLAIN {query}")).scalars())
    assert "ix_feedback_records_search_tsv" not in plan  # F-06: see the docstring
    assert len(c.execute(text(query)).all()) == 2  # the seeded record and "Checkout freezes"
    index = c.execute(
        text(
            "SELECT indexdef FROM pg_indexes WHERE schemaname = current_schema()"
            " AND indexname = 'ix_feedback_records_search_tsv'"
        )
    ).scalar_one()
    assert "USING gin (search_tsv)" in index
