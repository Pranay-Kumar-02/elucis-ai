"""Development data-source endpoints (multipart upload -> detect -> preview -> map)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient

from copilot.main import create_app
from tests.conftest import make_settings

FIXTURES = Path(__file__).parent / "fixtures"
BASE = "/api/v1/dev/sources"


def test_adapter_catalogue(client: TestClient) -> None:
    r = client.get(f"{BASE}/adapters")
    assert r.status_code == 200
    kinds = {a["kind"]: a["status"] for a in r.json()}
    assert kinds["file"] == "implemented"
    assert kinds["zendesk"] == "designed"


def test_preview_csv_matches_source_file_contract(client: TestClient) -> None:
    data = (FIXTURES / "reviews.csv").read_bytes()
    r = client.post(f"{BASE}/preview", files={"file": ("reviews.csv", data, "text/csv")})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["detected_format"] == "csv"
    assert body["detected_encoding"] == "utf-8"
    assert body["columns"] == ["id", "review", "rating", "customer", "created"]
    assert body["total_rows"] == 3
    assert len(body["preview_rows"]) == 3
    assert body["sha256"] == hashlib.sha256(data).hexdigest()
    assert body["size_bytes"] == len(data)


def test_preview_row_limit_query(client: TestClient) -> None:
    data = json.dumps([{"text": str(i)} for i in range(50)]).encode()
    r = client.post(f"{BASE}/preview?rows=5", files={"file": ("x.json", data, "application/json")})
    assert r.status_code == 200
    assert len(r.json()["preview_rows"]) == 5
    assert r.json()["total_rows"] == 50


def test_map_returns_raw_items(client: TestClient) -> None:
    data = (FIXTURES / "reviews.csv").read_bytes()
    r = client.post(
        f"{BASE}/map",
        files={"file": ("reviews.csv", data, "text/csv")},
        data={"mapping": json.dumps({"text": "review", "customer_id": "customer"})},
    )
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert items[0]["text"] == "App crashes, every time"
    assert items[0]["customer_ref"] == "c-001"
    assert items[2]["customer_ref"] is None


def test_map_rejects_bad_mapping_json(client: TestClient) -> None:
    r = client.post(
        f"{BASE}/map",
        files={"file": ("r.csv", b"text\nx\n", "text/csv")},
        data={"mapping": "{not json"},
    )
    assert r.status_code == 422
    assert r.json()["error"]["details"] == [{"field": "mapping", "issue": "invalid"}]


def test_unsupported_file_415(client: TestClient) -> None:
    r = client.post(
        f"{BASE}/preview", files={"file": ("data.xlsx", b"PK\x03\x04", "application/zip")}
    )
    assert r.status_code == 415
    assert r.json()["error"]["code"] == "unsupported_format"


def test_invalid_json_422(client: TestClient) -> None:
    r = client.post(f"{BASE}/preview", files={"file": ("x.json", b'{"a":1}', "application/json")})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_failed"


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
