"""Password hashing with Argon2id (SEC-01; D03 SVC-01: passwords 12-128 characters).

Parameters follow the argon2-cffi defaults (RFC 9106 "low memory" profile: t=3, m=64 MiB,
p=4). ``needs_rehash`` lets sign-in upgrade old hashes transparently when parameters change.
Verification is constant-time inside the library; every failure returns ``False``.
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 128

_hasher = PasswordHasher()


def check_password_policy(password: str) -> list[str]:
    problems: list[str] = []
    if len(password) < MIN_PASSWORD_LENGTH:
        problems.append(f"must be at least {MIN_PASSWORD_LENGTH} characters")
    if len(password) > MAX_PASSWORD_LENGTH:
        problems.append(f"must be at most {MAX_PASSWORD_LENGTH} characters")
    return problems


def hash_password(password: str) -> str:
    if problems := check_password_policy(password):
        raise ValueError("password " + "; ".join(problems))
    return _hasher.hash(password)


def verify_password(stored_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(stored_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(stored_hash: str) -> bool:
    return _hasher.check_needs_rehash(stored_hash)
