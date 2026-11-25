"""Source endpoints end to end: multipart upload -> preview -> validate -> fetch."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from copilot.main import create_app
from tests.conftest import make_settings

FIXTURES = Path(__file__).parent / "fixtures"
BASE = "/api/v1/dev/sources"
REVIEWS = (FIXTURES / "reviews.csv").read_bytes()
REVIEW_MAPPING = json.dumps(
    {
        "text": "review",
        "rating": "rating",
        "customer_id": "customer",
        "occurred_at": "created",
        "source_record_id": "id",
    }
)


def _post(
    client: TestClient, path: str, *, file: tuple[str, bytes] | None = None, **form: str
) -> Any:
    files = {"file": (file[0], file[1], "application/octet-stream")} if file else None
    return client.post(f"{BASE}/{path}", files=files, data=form or None)


# ------------------------------------------------------------------ catalogue
def test_adapter_catalogue(client: TestClient) -> None:
    r = client.get(f"{BASE}/adapters")
    assert r.status_code == 200
    kinds = {a["kind"]: a["status"] for a in r.json()}
    assert kinds["file"] == "implemented"
    assert kinds["zendesk"] == "designed"


# ------------------------------------------------------------------ preview
def test_preview_csv_with_suggested_mapping(client: TestClient) -> None:
    r = _post(client, "preview", file=("reviews.csv", REVIEWS))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["input"] == "file"
    assert body["detected_format"] == "csv"
    assert body["detected_encoding"] == "utf-8"
    assert body["columns"] == ["id", "review", "rating", "customer", "created"]
    assert body["total_rows"] == body["record_count"] == 3
    assert body["sha256"] == hashlib.sha256(REVIEWS).hexdigest()
    assert body["source_type"] == "review"
    assert body["required_fields"] == ["text"]
    assert body["suggested_mapping"] == {
        "text": "review",
        "occurred_at": "created",
        "customer_id": "customer",
        "rating": "rating",
        "source_record_id": "id",
    }


def test_preview_pasted_text(client: TestClient) -> None:
    r = _post(client, "preview", pasted_text="Alice: The export is slow\nBob: Same for me\n")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["input"] == "pasted_text"
    assert body["original_filename"] == "pasted-text.txt"
    assert body["transcript_mode"] == "speaker_turns"
    assert body["suggested_mapping"] == {"text": "text", "speaker": "speaker"}
    assert body["record_count"] == 1 and body["total_rows"] == 2


def test_preview_metrics_suggestion(client: TestClient) -> None:
    data = b"metric,date,value\nweekly_active_users,2026-10-05,1200\n"
    r = _post(client, "preview", file=("m.csv", data), source_type="metrics")
    assert r.json()["required_fields"] == ["metric_name", "metric_value", "occurred_at"]
    assert r.json()["suggested_mapping"] == {
        "metric_name": "metric",
        "metric_value": "value",
        "occurred_at": "date",
    }


def test_preview_row_limit_query(client: TestClient) -> None:
    data = json.dumps([{"text": str(i)} for i in range(50)]).encode()
    r = client.post(f"{BASE}/preview?rows=5", files={"file": ("x.json", data, "application/json")})
    assert len(r.json()["preview_rows"]) == 5
    assert r.json()["total_rows"] == 50


def test_preview_needs_exactly_one_input(client: TestClient) -> None:
    neither = _post(client, "preview")
    both = _post(client, "preview", file=("a.txt", b"hi"), pasted_text="hi")
    for r in (neither, both):
        assert r.status_code == 422
        assert r.json()["error"]["details"] == [
            {"field": "file", "issue": "exactly_one_of_file_or_pasted_text"}
        ]


# ------------------------------------------------------------------ validate
def test_validate_reports_counts_errors_and_normalised_sample(client: TestClient) -> None:
    data = REVIEWS + b"4,,3,c-004,2026-10-04\n5,Slow sync,abc,c-005,soon\n"
    r = _post(
        client, "validate", file=("reviews.csv", data), source_type="review", mapping=REVIEW_MAPPING
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["summary"] == {
        "received": 5,
        "valid": 4,
        "rejected": 1,
        "rejected_by_code": {"text_missing": 1},
        "flags_by_code": {"rating_invalid": 1, "occurred_at_unparseable": 1},
        "reconciled": True,
    }
    assert body["errors"] == [
        {
            "row_number": 4,
            "segment_index": 0,
            "field": "text",
            "code": "text_missing",
            "message": "Text is empty.",
        }
    ]
    assert body["errors_truncated"] is False
    first = body["sample_records"][0]
    assert first["raw_text"] == "App crashes, every time"
    assert first["occurred_at"] == "2026-10-01T00:00:00Z"
    assert first["rating_value"] == 1.0
    assert first["customer_ref"] == "c-001"
    assert body["sample_records"][2]["customer_ref"] is None
    assert body["column_mapping"]["text"] == "review"
    assert body["date_order"] is None  # ISO dates only: no day/month order to decide
    assert not any("either way" in w for w in body["warnings"])
    assert body["sample_metrics"] == []


def test_validate_warns_when_date_order_is_assumed(client: TestClient) -> None:
    data = b"text,date\nSlow,03/04/2026\nCrash,05/06/2026\n"
    mapping = '{"text": "text", "occurred_at": "date"}'
    r = _post(client, "validate", file=("d.csv", data), source_type="review", mapping=mapping)
    body = r.json()
    assert body["date_order"] == {"order": "dmy", "assumed": True}
    assert any("day/month/year" in w for w in body["warnings"])
    assert body["sample_records"][0]["occurred_at"] == "2026-04-03T00:00:00Z"


def test_validate_metrics(client: TestClient) -> None:
    data = b"metric,date,value\nwau,2026-10-05,1200\nwau,2026-10-06,n/a\n"
    mapping = json.dumps({"metric_name": "metric", "occurred_at": "date", "metric_value": "value"})
    r = _post(client, "validate", file=("m.csv", data), source_type="metrics", mapping=mapping)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["summary"]["valid"] == 1 and body["summary"]["rejected"] == 1
    assert body["sample_metrics"] == [
        {
            "row_number": 1,
            "metric_name": "wau",
            "observed_on": "2026-10-05",
            "value": 1200.0,
            "dimension": "",
            "metadata": {},
        }
    ]
    assert body["errors"][0]["code"] == "metric_value_invalid"
    assert body["date_order"] is None


def test_validate_transcript_without_mapping(client: TestClient) -> None:
    data = (FIXTURES / "interview.txt").read_bytes()
    r = _post(client, "validate", file=("interview.txt", data), source_type="transcript")
    assert r.status_code == 200, r.text
    assert r.json()["summary"]["valid"] == 3
    assert r.json()["sample_records"][1]["speaker"] == "Customer"


def test_validate_requires_a_mapping_for_tables(client: TestClient) -> None:
    r = _post(client, "validate", file=("reviews.csv", REVIEWS), source_type="review")
    assert r.status_code == 422
    assert r.json()["error"]["details"] == [{"field": "column_mapping", "issue": "required"}]


def test_validate_rejects_mapping_to_unknown_column(client: TestClient) -> None:
    r = _post(
        client,
        "validate",
        file=("reviews.csv", REVIEWS),
        source_type="review",
        mapping='{"text": "body"}',
    )
    assert r.status_code == 422
    assert r.json()["error"]["details"] == [
        {"field": "column_mapping.text", "issue": "column 'body' not in file"}
    ]


def test_validate_rejects_incomplete_metric_mapping(client: TestClient) -> None:
    data = b"metric,date,value\nwau,2026-10-05,1\n"
    r = _post(
        client,
        "validate",
        file=("m.csv", data),
        source_type="metrics",
        mapping='{"metric_name": "metric"}',
    )
    assert r.status_code == 422
    fields = {d["field"] for d in r.json()["error"]["details"]}
    assert fields == {"column_mapping.metric_value", "column_mapping.occurred_at"}


def test_validate_requires_source_type(client: TestClient) -> None:
    r = _post(client, "validate", file=("reviews.csv", REVIEWS), mapping=REVIEW_MAPPING)
    assert r.status_code == 422
    assert r.json()["error"]["details"] == [{"field": "source_type", "issue": "missing"}]


def test_validate_rejects_bad_mapping_json(client: TestClient) -> None:
    r = _post(
        client, "validate", file=("r.csv", b"text\nx\n"), source_type="review", mapping="{not json"
    )
    assert r.status_code == 422
    assert r.json()["error"]["details"] == [{"field": "mapping", "issue": "invalid"}]


def test_validate_refuses_files_over_the_record_limit(client: TestClient) -> None:
    rows = "\n".join(f"feedback {i}" for i in range(20_001))
    r = _post(
        client,
        "validate",
        file=("big.csv", f"text\n{rows}\n".encode()),
        source_type="review",
        mapping='{"text": "text"}',
    )
    assert r.status_code == 422
    assert r.json()["error"]["details"] == [{"field": "file", "issue": "too_many_records"}]


# ------------------------------------------------------------------ fetch
def test_fetch_pages_through_all_records_with_cursor(client: TestClient) -> None:
    rows = [{"text": f"feedback {i}", "id": str(i)} for i in range(1, 121)]
    rows[59]["text"] = "  "  # row 60 rejected
    data = json.dumps(rows).encode()
    mapping = '{"text": "text", "source_record_id": "id"}'
    seen, rejected, cursor, pages = [], [], None, 0
    while True:
        url = f"{BASE}/fetch?limit=50" + (f"&cursor={cursor}" if cursor else "")
        r = client.post(
            url,
            files={"file": ("r.json", data, "application/json")},
            data={"source_type": "ticket", "mapping": mapping},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total_items"] == 120
        seen += [i["row_number"] for i in body["items"]]
        rejected += [e["row_number"] for e in body["rejected"]]
        pages += 1
        cursor = body["next_cursor"]
        if cursor is None:
            break
    assert pages == 3
    assert rejected == [60]
    assert seen == [n for n in range(1, 121) if n != 60]


def test_fetch_cursor_is_bound_to_the_file(client: TestClient) -> None:
    first = _post(
        client,
        "fetch",
        file=("a.csv", b"text\na\nb\n"),
        source_type="review",
        mapping='{"text": "text"}',
    )
    assert first.status_code == 200
    page = client.post(
        f"{BASE}/fetch?limit=1",
        files={"file": ("a.csv", b"text\na\nb\n", "text/csv")},
        data={"source_type": "review", "mapping": '{"text": "text"}'},
    )
    cursor = page.json()["next_cursor"]
    other = client.post(
        f"{BASE}/fetch?cursor={cursor}",
        files={"file": ("b.csv", b"text\nx\ny\n", "text/csv")},
        data={"source_type": "review", "mapping": '{"text": "text"}'},
    )
    assert other.status_code == 422
    assert other.json()["error"]["details"] == [{"field": "cursor", "issue": "file_mismatch"}]
    garbage = client.post(
        f"{BASE}/fetch?cursor=not-a-cursor",
        files={"file": ("a.csv", b"text\na\n", "text/csv")},
        data={"source_type": "review", "mapping": '{"text": "text"}'},
    )
    assert garbage.json()["error"]["details"] == [{"field": "cursor", "issue": "invalid"}]


def test_fetch_pasted_text(client: TestClient) -> None:
    r = _post(
        client, "fetch", pasted_text="First idea.\n\nSecond idea.", source_type="feature_request"
    )
    assert r.status_code == 200, r.text
    assert [i["raw_text"] for i in r.json()["items"]] == ["First idea.", "Second idea."]
    assert r.json()["next_cursor"] is None


# ------------------------------------------------------------------ file-level failures
def test_unsupported_file_415(client: TestClient) -> None:
    r = _post(client, "preview", file=("data.xlsx", b"PK\x03\x04"))
    assert r.status_code == 415
    assert r.json()["error"]["code"] == "unsupported_format"


def test_binary_with_csv_extension_415(client: TestClient) -> None:
    r = _post(client, "preview", file=("x.csv", b"\x00\x01\x02binary"))
    assert r.status_code == 415


def test_invalid_json_422_with_position(client: TestClient) -> None:
    r = _post(client, "preview", file=("x.json", b'[{"a":1},'))
    assert r.status_code == 422
    assert r.json()["error"]["details"] == [{"field": "file", "issue": "invalid_json"}]
    assert "line 1" in r.json()["error"]["message"]


def test_empty_file_422(client: TestClient) -> None:
    r = _post(client, "preview", file=("e.csv", b"\n\n"))
    assert r.status_code == 422
    assert r.json()["error"]["details"] == [{"field": "file", "issue": "empty"}]


def test_upload_over_limit_413() -> None:
    app = create_app(make_settings(upload_max_bytes=1024))
    with TestClient(app) as c:
        r = c.post(
            f"{BASE}/preview", files={"file": ("big.csv", b"text\n" + b"x" * 4096, "text/csv")}
        )
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "file_too_large"


def test_dev_endpoints_absent_when_disabled() -> None:
    with TestClient(create_app(make_settings(enable_dev_endpoints=False))) as c:
        assert c.get(f"{BASE}/adapters").status_code == 404
        assert c.post(f"{BASE}/validate").status_code == 404
