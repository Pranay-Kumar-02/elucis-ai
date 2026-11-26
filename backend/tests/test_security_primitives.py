"""Session tokens, CSRF tokens, password policy and encryption (no database)."""

from __future__ import annotations

import base64
import os
from datetime import UTC, datetime, timedelta

import pytest

from elucis.core.errors import EncryptionUnavailableError
from elucis.security import crypto, sessions
from elucis.security.passwords import check_password_policy
from tests.conftest import make_settings


def test_tokens_are_256_bit_and_stored_only_as_hashes() -> None:
    token = sessions.new_token()
    assert len(base64.urlsafe_b64decode(token + "=")) == 32
    assert sessions.new_token() != token
    stored = sessions.token_hash(token)
    assert len(stored) == 32 and token.encode() not in stored
    assert sessions.tokens_match(token, stored)
    assert not sessions.tokens_match(token + "x", stored)


def test_csrf_token_is_stable_per_session_and_secret() -> None:
    token = sessions.new_token()
    a = sessions.csrf_token_for(token, "secret-one")
    assert a == sessions.csrf_token_for(token, "secret-one")  # /auth/me can return it again
    assert a != sessions.csrf_token_for(token, "secret-two")
    assert a != sessions.csrf_token_for(sessions.new_token(), "secret-one")


def test_session_window_idle_and_absolute() -> None:
    window = sessions.SessionWindow(idle=timedelta(minutes=30), absolute=timedelta(hours=12))
    start = datetime(2026, 11, 26, 9, 0, tzinfo=UTC)
    assert not window.is_expired(
        created_at=start, last_seen_at=start, now=start + timedelta(minutes=29)
    )
    assert window.is_expired(
        created_at=start, last_seen_at=start, now=start + timedelta(minutes=30)
    )
    busy = start + timedelta(hours=11, minutes=59)
    assert window.is_expired(created_at=start, last_seen_at=busy, now=start + timedelta(hours=12))
    assert window.should_touch(start, start + timedelta(minutes=1))
    assert not window.should_touch(start, start + timedelta(seconds=59))


@pytest.mark.parametrize(
    ("password", "ok"),
    [
        ("correct horse battery", True),
        ("Password1234", False),  # common, compared case-insensitively
        ("QWERTY123456", False),
        ("eleven char", False),
        ("x" * 129, False),
    ],
)
def test_password_policy(password: str, ok: bool) -> None:
    assert (check_password_policy(password) == []) is ok


def test_encryption_round_trip_and_wrong_key() -> None:
    key = base64.urlsafe_b64encode(os.urandom(32)).decode()
    settings = make_settings(app_encryption_key=key)
    token = crypto.encrypt(settings, b"customer-key-secret")
    assert b"customer-key-secret" not in token
    assert crypto.decrypt(settings, token) == b"customer-key-secret"
    other = make_settings(app_encryption_key=base64.urlsafe_b64encode(os.urandom(32)).decode())
    with pytest.raises(ValueError, match="not encrypted with the configured"):
        crypto.decrypt(other, token)


def test_encryption_without_a_key_fails_loudly() -> None:
    with pytest.raises(EncryptionUnavailableError):
        crypto.encrypt(make_settings(app_encryption_key=None), b"x")
