"""Server-side session tokens and CSRF tokens (D09 §1, D10 §2, D07 ``sessions``).

The browser holds an opaque 256-bit token in an HttpOnly cookie; the database stores only
its SHA-256, so a database leak does not reveal usable sessions. The CSRF token is a second
random value, returned by ``GET /auth/me`` and stored hashed as well.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

SESSION_COOKIE = "session"
CSRF_HEADER = "X-CSRF-Token"
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
LAST_SEEN_WRITE_INTERVAL = timedelta(minutes=1)


def new_token() -> str:
    """256 random bits, URL-safe."""
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()


def tokens_match(presented: str, stored_hash: bytes) -> bool:
    return hmac.compare_digest(token_hash(presented), stored_hash)


def csrf_token_for(session_token: str, signing_secret: str) -> str:
    """The session's CSRF token: HMAC-SHA256(SESSION_SECRET, session token).

    Derived rather than stored, so ``GET /auth/me`` can return it again after a page reload
    while the database keeps only its hash (D07 ``csrf_token_hash``, IMP-28).
    """
    digest = hmac.new(signing_secret.encode("utf-8"), session_token.encode("utf-8"), "sha256")
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class SessionWindow:
    """When a session ends: idle timeout (A-07) or absolute limit, whichever is first."""

    idle: timedelta
    absolute: timedelta

    def expires_at(self, created_at: datetime) -> datetime:
        return created_at + self.absolute

    def is_expired(self, *, created_at: datetime, last_seen_at: datetime, now: datetime) -> bool:
        return now >= created_at + self.absolute or now >= last_seen_at + self.idle

    @staticmethod
    def should_touch(last_seen_at: datetime, now: datetime) -> bool:
        """Write ``last_seen_at`` at most once a minute, not on every request."""
        return now - last_seen_at >= LAST_SEEN_WRITE_INTERVAL
