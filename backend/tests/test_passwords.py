from __future__ import annotations

import pytest

from elucis.security.passwords import (
    check_password_policy,
    hash_password,
    needs_rehash,
    verify_password,
)


def test_hash_is_argon2id_and_verifies() -> None:
    hashed = hash_password("correct horse battery")
    assert hashed.startswith("$argon2id$")
    assert verify_password(hashed, "correct horse battery")
    assert not verify_password(hashed, "correct horse battery!")
    assert not needs_rehash(hashed)


def test_same_password_gets_different_salts() -> None:
    assert hash_password("correct horse battery") != hash_password("correct horse battery")


@pytest.mark.parametrize("password", ["short", "x" * 129])
def test_policy_enforced(password: str) -> None:
    assert check_password_policy(password)
    with pytest.raises(ValueError, match="password must be"):
        hash_password(password)


def test_garbage_hash_never_raises() -> None:
    assert verify_password("not-a-hash", "whatever-password") is False
