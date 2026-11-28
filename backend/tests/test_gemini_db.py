"""The Gemini backup on the real schema (marker ``db``): the Owner's switch, and a run in
which the local model fails and the backup answers. The backup is a recording fake; nothing
is sent to Google."""

from __future__ import annotations

import ipaddress
import json
import secrets
import uuid
from collections.abc import Callable, Iterator
from functools import partial
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel, SecretStr
from sqlalchemy import Engine, text

from elucis.core.config import Settings
from elucis.main import create_app
from elucis.modules.analysis import service
from elucis.modules.analysis.orchestrator import run_analysis
from elucis.modules.imports.pipeline import run_ingest
from elucis.workers.runtime import Worker
from tests.conftest import ApiClient
from tests.fakes import FakeGateway
from tests.schema_seed import bind

pytestmark = pytest.mark.db
Browser = Callable[[], ApiClient]


@pytest.fixture
def gemini_settings(api_settings: Settings) -> Settings:
    return api_settings.model_copy(update={"gemini_api_key": SecretStr("test-key-not-real")})


@pytest.fixture
def gemini_browser(gemini_settings: Settings) -> Iterator[Callable[[], ApiClient]]:
    app = create_app(gemini_settings)
    opened: list[TestClient] = []

    def open_browser() -> ApiClient:
        ip = str(ipaddress.IPv6Address((0x20010DB8 << 96) | secrets.randbits(96)))
        client = TestClient(app, raise_server_exceptions=False, client=(ip, 50000))
        client.__enter__()
        opened.append(client)
        return ApiClient(client)

    yield open_browser
    for client in opened:
        client.__exit__(None, None, None)


def _workspace(b: ApiClient, name: str) -> str:
    b.sign_up()
    return str(b.call("POST", "/workspaces", json={"name": name}).json()["id"])


def test_the_switch_is_off_by_default_and_needs_a_key(browser: Browser) -> None:
    owner = browser()
    ws = _workspace(owner, "No key")
    body = owner.call("GET", f"/workspaces/{ws}").json()
    assert (body["gemini_fallback"], body["gemini_available"]) == (False, False)
    r = owner.call("PATCH", f"/workspaces/{ws}", json={"gemini_fallback": True})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "gemini_not_configured"


def test_only_owners_switch_it_and_every_change_is_audited(
    gemini_browser: Callable[[], ApiClient], owner_engine: Engine
) -> None:
    owner, viewer = gemini_browser(), gemini_browser()
    ws = _workspace(owner, "With key")
    email = viewer.sign_up()
    owner.call("POST", f"/workspaces/{ws}/members", json={"email": email})
    assert (
        viewer.call("PATCH", f"/workspaces/{ws}", json={"gemini_fallback": True}).status_code == 403
    )
    on = owner.call("PATCH", f"/workspaces/{ws}", json={"gemini_fallback": True})
    assert on.status_code == 200, on.text
    assert (on.json()["gemini_fallback"], on.json()["gemini_available"]) == (True, True)
    owner.call("PATCH", f"/workspaces/{ws}", json={"gemini_fallback": True})  # no change: no row
    owner.call("PATCH", f"/workspaces/{ws}", json={"gemini_fallback": False})
    with owner_engine.begin() as conn:
        bind(conn, uuid.UUID(ws))
        rows = conn.execute(
            text(
                "SELECT details FROM audit_logs WHERE workspace_id = :ws"
                " AND action = 'workspace.gemini_fallback_changed' ORDER BY created_at, id"
            ),
            {"ws": ws},
        ).all()
    assert [r.details for r in rows] == [{"enabled": True}, {"enabled": False}]


class RecordingBackup(FakeGateway):
    """Answers like the fake local model, and keeps every request it receives."""

    def __init__(self) -> None:
        super().__init__()
        self.requests: list[str] = []

    def chat_json(self, messages: list[dict[str, str]], schema: type[BaseModel], **kw: Any) -> Any:
        self.requests.append(json.dumps(messages))
        return super().chat_json(messages, schema, **kw)


FEEDBACK = (
    "\n".join(
        ["review,user"]
        + [f"Checkout fails on screen {i}. Mail me at user{i}@example.com,c{i}" for i in range(12)]
        + [f"Please add dark mode to page {i},d{i}" for i in range(12)]
    )
    + "\n"
)


def test_a_run_uses_the_backup_only_when_the_local_model_fails_and_sends_masked_text(
    gemini_browser: Callable[[], ApiClient],
    gemini_settings: Settings,
    worker_engine: Engine,
    owner_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(service, "check_models", lambda _settings: None)
    owner = gemini_browser()
    ws = _workspace(owner, "Backup run")
    file_id = owner.call(
        "POST",
        f"/workspaces/{ws}/files",
        files={"file": ("f.csv", FEEDBACK.encode(), "text/csv")},
        data={"source_type": "review"},
    ).json()["id"]
    body = {
        "source_file_id": file_id,
        "source_type": "review",
        "column_mapping": {"text": "review", "customer_id": "user"},
    }
    assert owner.call("POST", f"/workspaces/{ws}/imports", json=body).status_code == 202
    assert (
        owner.call("PATCH", f"/workspaces/{ws}", json={"gemini_fallback": True}).status_code == 200
    )

    local = FakeGateway(bad_cp02_batches=True)  # every CP-02 batch is invalid locally
    backup = RecordingBackup()
    worker = Worker(
        worker_engine,
        {
            "ingest": partial(run_ingest, settings=gemini_settings),
            "analysis": partial(
                run_analysis,
                settings=gemini_settings,
                gateway_factory=lambda _s: local,
                fallback_factory=lambda _s: backup,
            ),
        },
        worker_id="w-gemini",
    )
    while worker.run_once():
        pass
    run_id = owner.call("POST", f"/workspaces/{ws}/analysis-runs", json={}).json()["resource_id"]
    while worker.run_once():
        pass

    run = owner.call("GET", f"/workspaces/{ws}/analysis-runs/{run_id}").json()
    assert run["status"] == "succeeded"
    assert run["config"]["fallback"] == f"gemini:{gemini_settings.gemini_model}"
    assert run["report"]["classified"] == 24
    assert run["report"]["calls_by_provider"].get("gemini", 0) >= 3  # the CP-02 batches
    # Only calls the local model failed went to the backup: CP-03/CP-04 succeeded locally.
    assert all('"CP-02"' not in r for r in backup.requests)  # no call IDs, only content
    assert backup.requests and all("<customer_feedback" in r for r in backup.requests)
    sent = " ".join(backup.requests)
    assert "[EMAIL]" in sent and "@example.com" not in sent  # masked text only (DR-29)
    with owner_engine.begin() as conn:
        bind(conn, uuid.UUID(ws))
        providers = dict(
            conn.execute(
                text(
                    "SELECT provider, count(*) FROM llm_call_records"
                    " WHERE call_id = 'CP-02' GROUP BY provider"
                )
            ).all()
        )
    assert set(providers) == {"ollama", "gemini"}
