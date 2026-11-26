"""Authentication against the real schema as app_api (marker ``db``).

FR-AUTH-01 to FR-AUTH-04, SEC-01, SEC-02, SEC-05, AC-AUTH-02 and AC-AUTH-03.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

import pytest
from argon2 import PasswordHasher
from sqlalchemy import Engine, text

from elucis.main import create_app
from tests.conftest import ApiClient, make_settings

pytestmark = pytest.mark.db

Browser = Callable[[], ApiClient]
PUBLIC_ROUTES = {
    "/api/v1/auth/register",
    "/api/v1/auth/login",
    "/api/v1/health",
    "/api/v1/health/live",
    "/api/v1/health/database",
    "/api/v1/health/model-runtime",
}


def _session_count(owner_engine: Engine, email: str) -> int:
    with owner_engine.connect() as conn:
        return int(
            conn.execute(
                text(
                    "SELECT count(*) FROM sessions s JOIN users u ON u.id = s.user_id"
                    " WHERE lower(u.email) = lower(:e)"
                ),
                {"e": email},
            ).scalar_one()
        )


# ---------------------------------------------------------------- registration
def test_register_and_sign_in(browser: Browser) -> None:
    b = browser()
    email = b.sign_up(f"Mixed.Case.{uuid.uuid4().hex[:6]}@Example.test")
    me = b.call("GET", "/auth/me")
    assert me.status_code == 200
    body = me.json()
    assert body["user"]["email"] == email
    assert body["memberships"] == []
    assert body["csrf_token"] == b.csrf  # stable: /me returns the same token after a reload


def test_email_is_unique_regardless_of_case(browser: Browser) -> None:
    b = browser()
    email = b.sign_up()
    again = b.call(
        "POST", "/auth/register", json={"email": email.upper(), "password": "another long phrase"}
    )
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "email_taken"


@pytest.mark.parametrize(
    ("password", "issue"),
    [("short pass", "at least 12"), ("Password1234", "too common"), ("x" * 129, "string_too_long")],
)
def test_weak_passwords_are_refused(browser: Browser, password: str, issue: str) -> None:
    response = browser().call(
        "POST", "/auth/register", json={"email": "weak@example.test", "password": password}
    )
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_failed"
    assert any(d["field"] == "password" and issue in d["issue"] for d in error["details"])


def test_email_shape_is_checked(browser: Browser) -> None:
    response = browser().call(
        "POST", "/auth/register", json={"email": "not-an-email", "password": "long enough phrase"}
    )
    assert response.status_code == 422


# ---------------------------------------------------------------- the session cookie
def test_session_cookie_flags(browser: Browser) -> None:
    b = browser()
    email = b.sign_up()
    b.http.cookies.clear()
    response = b.sign_in(email)
    cookie = response.headers["set-cookie"]
    assert cookie.startswith("session=")
    for flag in ("HttpOnly", "Path=/api", "SameSite=lax", "Max-Age=43200"):
        assert flag in cookie
    assert "Secure" not in cookie  # plain HTTP in development; production sets Secure


def test_signed_out_token_is_refused(browser: Browser) -> None:
    b = browser()
    b.sign_up()
    token = b.http.cookies["session"]
    assert b.call("POST", "/auth/logout").status_code == 204
    b.http.cookies.set("session", token, path="/api")  # replay the old cookie (AC-AUTH-03)
    response = b.call("GET", "/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_sign_in_rotates_the_session(browser: Browser, owner_engine: Engine) -> None:
    b = browser()
    email = b.sign_up()
    first = b.http.cookies["session"]
    b.sign_in(email)
    assert b.http.cookies["session"] != first
    assert _session_count(owner_engine, email) == 1


@pytest.mark.parametrize(
    "aged",
    ["last_seen_at = now() - interval '31 minutes'", "created_at = now() - interval '13 hours'"],
)
def test_idle_and_absolute_expiry(browser: Browser, owner_engine: Engine, aged: str) -> None:
    b = browser()
    email = b.sign_up()
    with owner_engine.begin() as conn:
        conn.execute(
            text(
                f"UPDATE sessions SET {aged} WHERE user_id ="
                " (SELECT id FROM users WHERE lower(email) = lower(:e))"
            ),
            {"e": email},
        )
    response = b.call("GET", "/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "session_expired"
    assert _session_count(owner_engine, email) == 0


def test_outdated_password_hash_is_upgraded_at_sign_in(
    browser: Browser, owner_engine: Engine
) -> None:
    b = browser()
    email = b.sign_up()
    weak = PasswordHasher(time_cost=1, memory_cost=8192, parallelism=1).hash(
        "correct horse battery"
    )
    with owner_engine.begin() as conn:
        conn.execute(
            text("UPDATE users SET password_hash = :h WHERE lower(email) = lower(:e)"),
            {"h": weak, "e": email},
        )
    assert b.sign_in(email).status_code == 200
    with owner_engine.connect() as conn:
        stored = conn.execute(
            text("SELECT password_hash FROM users WHERE lower(email) = lower(:e)"), {"e": email}
        ).scalar_one()
    assert stored != weak
    assert stored.startswith("$argon2id$")


# ---------------------------------------------------------------- credentials and throttling
def test_unknown_email_and_wrong_password_look_the_same(browser: Browser) -> None:
    b = browser()
    email = b.sign_up()
    wrong = b.call("POST", "/auth/login", json={"email": email, "password": "wrong password!!"})
    unknown = b.call(
        "POST", "/auth/login", json={"email": "nobody@example.test", "password": "wrong password!!"}
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["error"]["message"] == unknown.json()["error"]["message"]
    assert wrong.json()["error"]["code"] == "invalid_credentials"


def test_five_failures_block_the_account_for_fifteen_minutes(browser: Browser) -> None:
    owner, attacker = browser(), browser()
    email = owner.sign_up()
    for _ in range(5):
        attacker.call("POST", "/auth/login", json={"email": email, "password": "guess guess 1"})
    blocked = attacker.call(
        "POST", "/auth/login", json={"email": email, "password": "correct horse battery"}
    )
    assert blocked.status_code == 429
    error = blocked.json()["error"]
    assert error["code"] == "too_many_attempts"
    retry = int(error["details"][0]["issue"])
    assert 1 <= retry <= 900
    assert blocked.headers["Retry-After"] == str(retry)


def test_one_address_is_limited_across_accounts(browser: Browser) -> None:
    b = browser()
    for i in range(20):
        b.call(
            "POST", "/auth/login", json={"email": f"spray{i}@example.test", "password": "x" * 12}
        )
    response = b.call(
        "POST", "/auth/login", json={"email": "fresh@example.test", "password": "x" * 12}
    )
    assert response.status_code == 429


def test_audit_entries_never_contain_the_email(browser: Browser, owner_engine: Engine) -> None:
    b = browser()
    email = b.sign_up()
    b.call("POST", "/auth/login", json={"email": email, "password": "wrong password!!"})
    with owner_engine.begin() as conn:
        rows = conn.execute(
            text("SELECT action, details::text FROM audit_logs WHERE workspace_id IS NULL")
        ).all()
    assert {"auth.login", "auth.login_failed"} <= {r[0] for r in rows}
    assert all(email.lower() not in r[1].lower() and "@" not in r[1] for r in rows)


# ---------------------------------------------------------------- generated from the routes
def _protected_routes() -> list[tuple[str, str]]:
    """Every operation in the OpenAPI document except the public ones.

    FastAPI 0.162 wraps included routers, so ``app.routes`` does not list them; the OpenAPI
    document is the supported, complete list (no route here is hidden from the schema).
    """
    paths = create_app(make_settings()).openapi()["paths"]
    found = []
    for path, operations in paths.items():
        if path in PUBLIC_ROUTES:
            continue
        concrete = path.replace("{ws}", str(uuid.uuid4())).replace("{user_id}", str(uuid.uuid4()))
        found += [(method.upper(), concrete) for method in sorted(operations)]
    return found


PROTECTED = _protected_routes()


def test_routes_are_discovered() -> None:
    paths = {p for _, p in PROTECTED}
    assert any(p.startswith("/api/v1/workspaces/") for p in paths)
    assert any(p.startswith("/api/v1/dev/") for p in paths)  # dev endpoints need a session too
    assert len(PROTECTED) >= 15


@pytest.mark.parametrize(("method", "path"), PROTECTED)
def test_every_protected_route_refuses_anonymous_requests(
    browser: Browser, method: str, path: str
) -> None:
    response = browser().http.request(method, path)  # AC-AUTH-02
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


UNSAFE = [(m, p) for m, p in PROTECTED if m in {"POST", "PUT", "PATCH", "DELETE"}]


@pytest.mark.parametrize(("method", "path"), UNSAFE)
def test_every_unsafe_route_requires_the_csrf_token(
    browser: Browser, method: str, path: str
) -> None:
    b = browser()
    b.sign_up()
    missing = b.http.request(method, path)
    wrong = b.http.request(method, path, headers={"X-CSRF-Token": "not-the-token"})
    assert (missing.status_code, missing.json()["error"]["code"]) == (400, "csrf_missing")
    assert (wrong.status_code, wrong.json()["error"]["code"]) == (403, "csrf_invalid")
