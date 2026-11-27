"""Standardisation (SVC-05, DR-21 to DR-23): ratings to 1-5, version labels, and the
pseudonymous customer key. Timestamps are already UTC from row validation (DR-21)."""

from __future__ import annotations

import hashlib
import hmac
import re
from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal

SCALES = (5.0, 10.0, 100.0)  # A-24: the scale is detected from the import's maximum
_VERSION = re.compile(r"\d+(?:\.\d+){0,3}")


def detect_scale(values: Iterable[float]) -> float | None:
    """The smallest standard scale that holds every rating without an explicit scale."""
    highest = max(values, default=None)
    if highest is None:
        return None
    return next((s for s in SCALES if highest <= s), None)


def rating_1_to_5(
    value: float | None, out_of: float | None, import_scale: float | None
) -> int | None:
    """``4/5`` -> 4, ``8`` on a 10-point import -> 4, ``80%`` -> 4. ``None`` when the value
    cannot be placed on a scale (DR-22: flagged, not guessed)."""
    if value is None:
        return None
    scale = out_of or import_scale
    if not scale or value < 0 or value > scale:
        return None
    stars = Decimal(str(value)) * 5 / Decimal(str(scale))
    return max(1, min(5, int(stars.quantize(Decimal(1), rounding=ROUND_HALF_UP))))


def product_version(raw: str | None) -> str | None:
    """``"v3.2.1 (build 77)"`` -> ``"3.2.1"`` (DR-22)."""
    if not raw:
        return None
    match = _VERSION.search(raw)
    return match.group(0) if match else None


def customer_key(secret: bytes, identifier: str | None) -> bytes | None:
    """HMAC-SHA256 of the normalised identifier with the workspace secret (DR-23). The raw
    identifier is never stored. ``None`` means unknown identity (CR-18)."""
    if identifier is None:
        return None
    normalised = " ".join(identifier.split()).casefold()
    if not normalised:
        return None
    return hmac.new(secret, normalised.encode("utf-8"), hashlib.sha256).digest()
