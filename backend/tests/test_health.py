"""Health endpoints with and without a database / model runtime."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from elucis.main import create_app
from tests.conftest import make_settings


def test_liveness(client: TestClient) -> None:
    r = client.get("/api/v1/health/live")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_health_unavailable_without_database(client: TestClient) -> None:
    r = client.get("/api/v1/health")
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "unavailable"
    assert body["checks"]["database"]["status"] == "unavailable"
    assert body["checks"]["model_runtime"]["status"] == "unavailable"
    assert body["checks"]["worker"]["status"] == "not_configured"


def test_database_health_unreachable_server_is_503() -> None:
    settings = make_settings(
        database_url="postgresql://u:p@127.0.0.1:1/x", database_connect_timeout_s=1
    )
    with TestClient(create_app(settings)) as c:
        r = c.get("/api/v1/health/database")
    assert r.status_code == 503
    assert r.json()["detail"] == "connection failed"
    assert "u:p" not in r.text


def test_model_runtime_unreachable_is_503(client: TestClient) -> None:
    r = client.get("/api/v1/health/model-runtime")
    assert r.status_code == 503
    assert r.json()["status"] == "unavailable"


@pytest.mark.db
def test_health_with_real_database_is_degraded_without_ollama(database_url: str) -> None:
    with TestClient(create_app(make_settings(database_url=database_url))) as c:
        overall = c.get("/api/v1/health")
        db = c.get("/api/v1/health/database")
    assert overall.status_code == 200  # model runtime down only degrades (AIR-22)
    assert overall.json()["status"] == "degraded"
    assert db.status_code == 200
    body = db.json()
    assert body["status"] == "ok"
    assert body["server_version"].startswith("18.")
    assert body["pgvector_version"] == "0.8.7"


@pytest.mark.db
def test_diagnostics_hidden_when_disabled(database_url: str) -> None:
    settings = make_settings(database_url=database_url, expose_diagnostics=False)
    with TestClient(create_app(settings)) as c:
        body = c.get("/api/v1/health/database").json()
    assert body["status"] == "ok"
    assert body["server_version"] is None
    assert body["pgvector_version"] is None
