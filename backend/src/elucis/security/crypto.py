"""Encryption at rest with Fernet and ``APP_ENCRYPTION_KEY`` (AGR-16, D07 §3.1).

Used for each workspace's ``customer_key_secret`` and, later, integration credentials.
Without a key, encryption fails loudly; it never falls back to storing plain values.
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from elucis.core.config import Settings
from elucis.core.errors import EncryptionUnavailableError


def _fernet(settings: Settings) -> Fernet:
    if settings.app_encryption_key is None:
        raise EncryptionUnavailableError()
    return Fernet(settings.app_encryption_key.get_secret_value().encode("ascii"))


def encrypt(settings: Settings, plaintext: bytes) -> bytes:
    return _fernet(settings).encrypt(plaintext)


def decrypt(settings: Settings, token: bytes) -> bytes:
    """Raises ``ValueError`` when the value was not encrypted with the configured key."""
    try:
        return _fernet(settings).decrypt(token)
    except InvalidToken as exc:
        raise ValueError("value was not encrypted with the configured APP_ENCRYPTION_KEY") from exc
