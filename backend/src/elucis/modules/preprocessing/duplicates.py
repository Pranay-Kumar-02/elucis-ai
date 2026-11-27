"""Exact-duplicate detection (SVC-07, DR-16, DR-18, CR-16).

The key is the masked text with case, punctuation and whitespace removed, so two copies of
a complaint that differ only in an e-mail address or spacing match. A record is a duplicate
only of an earlier record from the **same customer**; when both customers are unknown, of an
earlier record of the same source type within 24 hours (or, with no dates, in the same
import). Identical text from different customers is corroboration, never a duplicate.
"""

from __future__ import annotations

import hashlib
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

UNKNOWN_IDENTITY_WINDOW = timedelta(hours=24)


def content_hash(masked_text: str) -> bytes:
    folded = unicodedata.normalize("NFKC", masked_text).casefold()
    kept = "".join(ch for ch in folded if ch.isalnum())
    return hashlib.sha256(kept.encode("utf-8")).digest()


@dataclass(frozen=True, slots=True)
class Candidate:
    """A primary record that later records may duplicate."""

    id: uuid.UUID
    content_hash: bytes
    customer_id: uuid.UUID | None
    source_type: str
    occurred_at: datetime | None
    import_job_id: uuid.UUID


def is_duplicate_of(record: Candidate, earlier: Candidate) -> bool:
    if record.content_hash != earlier.content_hash:
        return False
    if record.customer_id is not None or earlier.customer_id is not None:
        return record.customer_id == earlier.customer_id
    if record.source_type != earlier.source_type:
        return False
    if record.occurred_at is not None and earlier.occurred_at is not None:
        return abs(record.occurred_at - earlier.occurred_at) <= UNKNOWN_IDENTITY_WINDOW
    if record.occurred_at is None and earlier.occurred_at is None:
        return record.import_job_id == earlier.import_job_id
    return False


def find_primary(record: Candidate, earlier: list[Candidate]) -> uuid.UUID | None:
    """The first earlier record this one duplicates (``earlier`` is in arrival order)."""
    return next((e.id for e in earlier if is_duplicate_of(record, e)), None)
