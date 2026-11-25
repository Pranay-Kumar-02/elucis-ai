"""Error envelope, request IDs, body limits, security headers and CORS."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient
from pydantic import BaseModel

from elucis.core.errors import ConflictError
from elucis.main import create_app
from tests.conftest import make_settings


class Echo(BaseModel):
    name: str
    count: int


probe = APIRouter(prefix="/api/v1/_probe")


@probe.post("/echo")
def echo(body: Echo) -> Echo:
    return body


@probe.get("/boom")
def boom() -> None:
    raise RuntimeError("secret internal detail")


@probe.get("/conflict")
def conflict() -> None:
    raise ConflictError(code="version_conflict")


@pytest.fixture
def api() -> Iterator[TestClient]:
    app = create_app(make_settings())
    app.include_router(probe)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _assert_envelope(body: dict[str, object], code: str) -> None:
    error = body["error"]
    assert isinstance(error, dict)
    assert error["code"] == code
    assert isinstance(error["message"], str)
    assert isinstance(error["details"], list)
    assert isinstance(error["request_id"], str)
    assert len(error["request_id"]) == 26  # ULID


def test_unknown_route_uses_envelope_and_request_id(api: TestClient) -> None:
    r = api.get("/api/v1/does-not-exist")
    assert r.status_code == 404
    _assert_envelope(r.json(), "not_found")
    assert r.headers["x-request-id"] == r.json()["error"]["request_id"]


def test_validation_error_lists_fields(api: TestClient) -> None:
    r = api.post("/api/v1/_probe/echo", json={"name": "x", "count": "many"})
    assert r.status_code == 422
    body = r.json()
    _assert_envelope(body, "validation_failed")
    assert body["error"]["details"] == [{"field": "count", "issue": "int_parsing"}]


def test_typed_app_error_maps_status_and_code(api: TestClient) -> None:
    r = api.get("/api/v1/_probe/conflict")
    assert r.status_code == 409
    _assert_envelope(r.json(), "version_conflict")


def test_unhandled_exception_is_generic_500_without_details(api: TestClient) -> None:
    r = api.get("/api/v1/_probe/boom")
    assert r.status_code == 500
    _assert_envelope(r.json(), "internal_error")
    assert "secret internal detail" not in r.text
    assert r.headers["x-request-id"] == r.json()["error"]["request_id"]


def test_method_not_allowed_envelope(api: TestClient) -> None:
    r = api.delete("/api/v1/health")
    assert r.status_code == 405
    _assert_envelope(r.json(), "method_not_allowed")


def test_valid_incoming_request_id_is_kept_and_invalid_replaced(api: TestClient) -> None:
    kept = api.get("/api/v1/health/live", headers={"X-Request-ID": "client-trace-1234"})
    assert kept.headers["x-request-id"] == "client-trace-1234"
    replaced = api.get("/api/v1/health/live", headers={"X-Request-ID": "bad id with spaces"})
    assert replaced.headers["x-request-id"] != "bad id with spaces"
    assert len(replaced.headers["x-request-id"]) == 26


def test_json_body_over_1mb_rejected_413(api: TestClient) -> None:
    r = api.post(
        "/api/v1/_probe/echo",
        content=b'{"name":"' + b"x" * (1024 * 1024 + 10) + b'","count":1}',
        headers={"content-type": "application/json"},
    )
    assert r.status_code == 413
    _assert_envelope(r.json(), "bad_request")


def test_error_responses_carry_cors_headers(api: TestClient) -> None:
    r = api.get("/api/v1/_probe/boom", headers={"Origin": "http://localhost:5173"})
    assert r.status_code == 500
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_security_headers_present(api: TestClient) -> None:
    r = api.get("/api/v1/health/live")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "no-referrer"
    assert "default-src 'none'" in r.headers["content-security-policy"]
    assert r.headers["cache-control"] == "no-store"


def test_cors_allows_dev_origin_only(api: TestClient) -> None:
    preflight = {
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type,x-csrf-token",
    }
    ok = api.options("/api/v1/health", headers={"Origin": "http://localhost:5173", **preflight})
    assert ok.status_code == 200
    assert ok.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert ok.headers["access-control-allow-credentials"] == "true"
    bad = api.options("/api/v1/health", headers={"Origin": "http://evil.example", **preflight})
    assert "access-control-allow-origin" not in bad.headers


def test_openapi_served_in_development(api: TestClient) -> None:
    r = api.get("/api/v1/openapi.json")
    assert r.status_code == 200
    assert "/api/v1/health" in r.json()["paths"]


def test_docs_disabled_in_production() -> None:
    app = create_app(
        make_settings(
            app_env="production",
            enable_dev_endpoints=False,
            database_url="postgresql://u:p@127.0.0.1:1/x",
            session_secret="s" * 32,
            app_encryption_key="k" * 32,
        )
    )
    with TestClient(app) as c:
        assert c.get("/api/v1/openapi.json").status_code == 404
        assert c.get("/api/v1/docs").status_code == 404
        assert c.get("/api/v1/dev/sources/adapters").status_code == 404
