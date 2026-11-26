"""Password hashing with Argon2id (SEC-01; D03 SVC-01: passwords 12-128 characters).

Parameters follow the argon2-cffi defaults (RFC 9106 "low memory" profile: t=3, m=64 MiB,
p=4). ``needs_rehash`` lets sign-in upgrade old hashes transparently when parameters change.
Verification is constant-time inside the library; every failure returns ``False``.
"""

from __future__ import annotations

import secrets
from functools import cache
from pathlib import Path

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 128
COMMON_PASSWORDS_FILE = Path(__file__).with_name("common_passwords.txt")

_hasher = PasswordHasher()


@cache
def _common_passwords() -> frozenset[str]:
    lines = COMMON_PASSWORDS_FILE.read_text(encoding="utf-8").splitlines()
    return frozenset(line.strip().lower() for line in lines if line.strip() and line[0] != "#")


def check_password_policy(password: str) -> list[str]:
    """Length 12 to 128 and not a common password (D10 §2); no composition rules."""
    problems: list[str] = []
    if len(password) < MIN_PASSWORD_LENGTH:
        problems.append(f"must be at least {MIN_PASSWORD_LENGTH} characters")
    if len(password) > MAX_PASSWORD_LENGTH:
        problems.append(f"must be at most {MAX_PASSWORD_LENGTH} characters")
    if password.lower() in _common_passwords():
        problems.append("is too common; choose a less predictable password")
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


@cache
def _dummy_hash() -> str:
    return _hasher.hash("not-a-real-password-" + secrets.token_hex(16))


def verify_against_nothing(password: str) -> None:
    """Spend the same time as a real check when the account does not exist, so response
    times do not reveal which emails are registered."""
    verify_password(_dummy_hash(), password)
