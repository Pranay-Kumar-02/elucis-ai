"""Workspaces, members, roles and deletion on the real schema (marker ``db``).

FR-AUTH-05 to FR-AUTH-11, SEC-03, SEC-04, SEC-14, SEC-21, AC-AUTH-01, AC-AUTH-04, IMP-24.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

import pytest
from sqlalchemy import Engine, text

from elucis.core.config import Settings
from elucis.security import crypto
from elucis.workers.handlers.workspaces import delete_workspace
from elucis.workers.queue import Job
from elucis.workers.runtime import JobContext, Worker
from tests.conftest import ApiClient
from tests.schema_seed import bind

pytestmark = pytest.mark.db

Browser = Callable[[], ApiClient]


def _create(b: ApiClient, name: str = "Checkout insights") -> dict[str, Any]:
    response = b.call("POST", "/workspaces", json={"name": name, "description": "Payments"})
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def _audit(owner_engine: Engine, ws: str, action: str) -> list[Any]:
    with owner_engine.begin() as conn:
        bind(conn, uuid.UUID(ws))
        return list(
            conn.execute(
                text("SELECT * FROM audit_logs WHERE workspace_id = :ws AND action = :a"),
                {"ws": ws, "a": action},
            ).all()
        )


@pytest.fixture
def team(browser: Browser) -> dict[str, Any]:
    """An Owner with a workspace, plus an Editor and a Viewer added by email."""
    owner, editor, viewer, outsider = browser(), browser(), browser(), browser()
    owner.sign_up()
    ws = _create(owner)
    emails = {"editor": editor.sign_up(), "viewer": viewer.sign_up()}
    outsider.sign_up()
    for role, email in emails.items():
        added = owner.call(
            "POST",
            f"/workspaces/{ws['id']}/members",
            json={"email": email, **({"role": role} if role != "viewer" else {})},
        )
        assert added.status_code == 201, added.text
        assert added.json()["role"] == role  # a member added without a role is a Viewer
    return {"ws": ws, "owner": owner, "editor": editor, "viewer": viewer, "outsider": outsider}


def test_create_workspace_makes_the_creator_owner(
    browser: Browser, owner_engine: Engine, api_settings: Settings
) -> None:
    b = browser()
    b.sign_up()
    ws = _create(b)
    assert ws["role"] == "owner"
    memberships = b.call("GET", "/auth/me").json()["memberships"]
    assert memberships == [
        {"workspace_id": ws["id"], "workspace_name": ws["name"], "role": "owner"}
    ]
    with owner_engine.connect() as conn:
        secret = conn.execute(
            text("SELECT customer_key_secret FROM workspaces WHERE id = :id"), {"id": ws["id"]}
        ).scalar_one()
    assert len(crypto.decrypt(api_settings, bytes(secret))) == 32  # encrypted at rest (D07)
    assert len(_audit(owner_engine, ws["id"], "workspace.created")) == 1


def test_list_my_workspaces_is_paginated(browser: Browser) -> None:
    b = browser()
    b.sign_up()
    names = [f"Space {i}" for i in range(3)]
    for name in names:
        _create(b, name)
    first = b.call("GET", "/workspaces?limit=2").json()
    second = b.call("GET", f"/workspaces?limit=2&cursor={first['next_cursor']}").json()
    assert [w["name"] for w in first["items"] + second["items"]] == names
    assert second["next_cursor"] is None
    assert b.call("GET", "/workspaces?cursor=nonsense").status_code == 422


def test_update_profile_and_glossary(team: dict[str, Any]) -> None:
    ws, owner = team["ws"], team["owner"]
    patched = owner.call(
        "PATCH",
        f"/workspaces/{ws['id']}",
        json={"product_name": "PayFlow", "glossary": {"KYC": "Know your customer"}},
    )
    assert patched.status_code == 200
    body = patched.json()
    assert body["product_name"] == "PayFlow"
    assert body["glossary"] == {"KYC": "Know your customer"}
    assert body["name"] == ws["name"]  # fields not sent are unchanged
    cleared = owner.call("PATCH", f"/workspaces/{ws['id']}", json={"name": None})
    assert cleared.status_code == 422


@pytest.mark.parametrize(
    ("method", "suffix", "body"),
    [
        ("GET", "", None),
        ("PATCH", "", {"description": "hijack"}),
        ("DELETE", "", {"confirm_name": "Checkout insights"}),
        ("GET", "/members", None),
        ("POST", "/members", {"email": "x@example.test"}),
    ],
)
def test_non_members_get_not_found_and_no_data(
    team: dict[str, Any], method: str, suffix: str, body: dict[str, Any] | None
) -> None:
    response = team["outsider"].call(method, f"/workspaces/{team['ws']['id']}{suffix}", json=body)
    assert response.status_code == 404  # AC-AUTH-01: not 403, so IDs cannot be probed
    assert team["ws"]["name"] not in response.text


OWNER_ACTIONS = [
    ("PATCH", "", {"description": "changed"}),
    ("POST", "/members", {"email": "x@example.test"}),
    ("DELETE", "", {"confirm_name": "Checkout insights"}),
]


@pytest.mark.parametrize("role", ["viewer", "editor"])
@pytest.mark.parametrize("action", OWNER_ACTIONS)
def test_owner_actions_are_refused_and_logged_for_other_roles(
    team: dict[str, Any], owner_engine: Engine, role: str, action: tuple[str, str, dict[str, Any]]
) -> None:
    method, suffix, body = action
    ws = team["ws"]["id"]
    before = len(_audit(owner_engine, ws, "authz.refused"))
    response = team[role].call(method, f"/workspaces/{ws}{suffix}", json=body)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden_role"
    refused = _audit(owner_engine, ws, "authz.refused")
    assert len(refused) == before + 1  # AC-AUTH-04
    assert refused[-1].outcome == "failure"
    assert refused[-1].details["required_role"] == "owner"


def test_every_member_can_read(team: dict[str, Any]) -> None:
    ws = team["ws"]["id"]
    for role in ("owner", "editor", "viewer"):
        assert team[role].call("GET", f"/workspaces/{ws}").json()["role"] == role
        members = team[role].call("GET", f"/workspaces/{ws}/members").json()["items"]
        assert sorted(m["role"] for m in members) == ["editor", "owner", "viewer"]


def test_member_rules(team: dict[str, Any], owner_engine: Engine) -> None:
    ws, owner = team["ws"]["id"], team["owner"]
    unknown = owner.call("POST", f"/workspaces/{ws}/members", json={"email": "ghost@example.test"})
    assert unknown.status_code == 404
    viewer_email = team["viewer"].call("GET", "/auth/me").json()["user"]["email"]
    again = owner.call("POST", f"/workspaces/{ws}/members", json={"email": viewer_email})
    assert again.status_code == 409

    me = owner.call("GET", "/auth/me").json()["user"]["id"]
    demote = owner.call("PATCH", f"/workspaces/{ws}/members/{me}", json={"role": "editor"})
    leave = owner.call("DELETE", f"/workspaces/{ws}/members/{me}")
    assert demote.status_code == leave.status_code == 409  # the last Owner stays

    viewer_id = team["viewer"].call("GET", "/auth/me").json()["user"]["id"]
    promoted = owner.call("PATCH", f"/workspaces/{ws}/members/{viewer_id}", json={"role": "owner"})
    assert promoted.json()["role"] == "owner"
    assert (
        owner.call("PATCH", f"/workspaces/{ws}/members/{me}", json={"role": "editor"}).status_code
        == 200
    )
    assert team["viewer"].call("DELETE", f"/workspaces/{ws}/members/{me}").status_code == 204
    assert owner.call("GET", f"/workspaces/{ws}").status_code == 404  # removed: no access
    for action in ("member.added", "member.role_changed", "member.removed"):
        assert _audit(owner_engine, ws, action), action


def test_switching_between_workspaces(browser: Browser) -> None:
    a, b = browser(), browser()
    a_email = a.sign_up()
    b.sign_up()
    mine = _create(a, "Mine")
    theirs = _create(b, "Theirs")
    b.call("POST", f"/workspaces/{theirs['id']}/members", json={"email": a_email})
    memberships = {
        m["workspace_name"]: m["role"] for m in a.call("GET", "/auth/me").json()["memberships"]
    }
    assert memberships == {"Mine": "owner", "Theirs": "viewer"}
    assert a.call("GET", f"/workspaces/{theirs['id']}").json()["role"] == "viewer"
    assert a.call("GET", f"/workspaces/{mine['id']}").json()["role"] == "owner"


def test_deleting_a_workspace(
    team: dict[str, Any], owner_engine: Engine, worker_engine: Engine
) -> None:
    ws, owner = team["ws"], team["owner"]
    wrong = owner.call("DELETE", f"/workspaces/{ws['id']}", json={"confirm_name": "nope"})
    assert wrong.status_code == 422
    bad_key = owner.call(
        "DELETE",
        f"/workspaces/{ws['id']}",
        json={"confirm_name": ws["name"]},
        headers={"Idempotency-Key": "not-a-uuid"},
    )
    assert bad_key.status_code == 422

    key = {"Idempotency-Key": str(uuid.uuid4())}
    first = owner.call(
        "DELETE", f"/workspaces/{ws['id']}", json={"confirm_name": ws["name"]}, headers=key
    )
    repeat = owner.call(
        "DELETE", f"/workspaces/{ws['id']}", json={"confirm_name": ws["name"]}, headers=key
    )
    assert first.status_code == repeat.status_code == 202
    assert first.json() == repeat.json()  # one job, not two (D09 §1)
    assert first.json()["resource_id"] == ws["id"]

    worker = Worker(worker_engine, {"delete_workspace": delete_workspace}, worker_id="w-delete")
    while worker.run_once():  # unrelated queued test jobs fail cleanly (no handler)
        pass

    assert owner.call("GET", f"/workspaces/{ws['id']}").status_code == 404
    assert team["viewer"].call("GET", "/auth/me").json()["memberships"] == []
    with owner_engine.begin() as conn:
        bind(conn, None)
        events = conn.execute(
            text("SELECT * FROM audit_logs WHERE target_id = :ws AND workspace_id IS NULL"),
            {"ws": ws["id"]},
        ).all()
        bind(conn, uuid.UUID(ws["id"]))
        remaining = conn.execute(
            text("SELECT count(*) FROM audit_logs WHERE workspace_id = :ws"), {"ws": ws["id"]}
        ).scalar_one()
    assert remaining == 0  # its history went with it (A-21)
    assert [e.action for e in events] == ["workspace.deleted"]
    owner_id = owner.call("GET", "/auth/me").json()["user"]["id"]
    assert str(events[0].actor_user_id) == owner_id
    assert events[0].details == {"workspace_name": ws["name"]}


def test_deleting_twice_is_a_no_op(
    browser: Browser, owner_engine: Engine, worker_engine: Engine
) -> None:
    b = browser()
    b.sign_up()
    ws = _create(b, "Twice")
    b.call("DELETE", f"/workspaces/{ws['id']}", json={"confirm_name": "Twice"})
    with owner_engine.begin() as conn:  # keep a copy of the job, as a crashed retry would
        bind(conn, uuid.UUID(ws["id"]))
        job = conn.execute(
            text(
                "SELECT payload FROM jobs"
                " WHERE workspace_id = :ws AND job_type = 'delete_workspace'"
            ),
            {"ws": ws["id"]},
        ).scalar_one()
    worker = Worker(worker_engine, {"delete_workspace": delete_workspace}, worker_id="w-twice")
    while worker.run_once():
        pass
    replay = Job(uuid.uuid4(), uuid.UUID(ws["id"]), "delete_workspace", job, {}, 1, 3)
    assert delete_workspace(JobContext(replay, worker_engine, "w-replay")) == "succeeded"
    with owner_engine.begin() as conn:
        events = conn.execute(
            text("SELECT count(*) FROM audit_logs WHERE target_id = :ws AND workspace_id IS NULL"),
            {"ws": ws["id"]},
        ).scalar_one()
    assert events == 1
