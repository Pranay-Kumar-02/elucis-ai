"""Source adapter contract (D01 section 3.2, D03 SVC-02, D09 section 5).

Every source, file or live connector, produces the same ``RawItem`` stream, so the ingest
pipeline never changes when a source is added. Only ``FileAdapter`` is implemented in the
MVP (ADR-04). Live connectors are designed but need vendor accounts, credentials and mentor
approval (AR-05), so they are listed in the catalogue as ``designed`` and are not claimed
as working.

Naming note: D03 calls the item ``RawItem`` and D09's protocol sketch calls it ``RawRow``;
they are the same contract. The code uses ``RawItem`` (the LLD name) and exports the alias.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

BATCH_SIZE = 500  # D03 SVC-03: ingest in batches of 500 rows
MAX_RECORDS_PER_IMPORT = 20_000  # A-05


class SourceType(StrEnum):
    """Import label (FR-ING-02; D07 ``import_jobs.source_type``)."""

    REVIEW = "review"
    TICKET = "ticket"
    FEATURE_REQUEST = "feature_request"
    TRANSCRIPT = "transcript"
    OTHER = "other"
    METRICS = "metrics"


@dataclass(frozen=True, slots=True)
class RawItem:
    """One source record before validation. Values stay raw strings; SVC-04 parses them."""

    row_number: int  # 1-based data row (header excluded) or JSON array position
    text: str
    segment_index: int = 0  # > 0 only for transcript segments (DR-27)
    source_record_id: str | None = None
    occurred_at_raw: str | None = None
    customer_ref: str | None = None
    rating_raw: str | None = None
    version_raw: str | None = None
    speaker: str | None = None
    # Metric files only (DR-41; D09 ImportIn.column_mapping metric fields).
    metric_name_raw: str | None = None
    metric_value_raw: str | None = None
    dimension_raw: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)
    # Structural problem found while reading (for example extra CSV values), if any.
    defect: RowDefect | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "row_number": self.row_number,
            "segment_index": self.segment_index,
            "text": self.text,
            "source_record_id": self.source_record_id,
            "occurred_at_raw": self.occurred_at_raw,
            "customer_ref": self.customer_ref,
            "rating_raw": self.rating_raw,
            "version_raw": self.version_raw,
            "speaker": self.speaker,
            "metric_name_raw": self.metric_name_raw,
            "metric_value_raw": self.metric_value_raw,
            "dimension_raw": self.dimension_raw,
            "metadata": self.metadata,
        }


@dataclass(frozen=True, slots=True)
class RowDefect:
    """A record the reader could not represent faithfully; validation rejects it."""

    code: str  # "extra_values" | "not_an_object"
    message: str


RawRow = RawItem


class ColumnMapping(BaseModel):
    """Column -> standard field mapping (FR-ING-03; D09 ``ImportIn.column_mapping``).

    Which fields are required depends on the source type and is checked against the file
    by ``mapping.check_mapping``: feedback needs ``text``; metrics need ``metric_name``,
    ``metric_value`` and ``occurred_at`` (DR-41).
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    text: str | None = Field(default=None, min_length=1)
    occurred_at: str | None = None
    customer_id: str | None = None
    rating: str | None = None
    product_version: str | None = None
    source_record_id: str | None = None
    speaker: str | None = None
    metric_name: str | None = None
    metric_value: str | None = None
    dimension: str | None = None

    def mapped_columns(self) -> dict[str, str]:
        return {k: v for k, v in self.model_dump().items() if v}


class AdapterStatus(StrEnum):
    IMPLEMENTED = "implemented"
    DESIGNED = "designed"  # contract designed (D01 section 3.1), no code, needs approval


@dataclass(frozen=True, slots=True)
class SourceInfo:
    kind: str
    label: str
    status: AdapterStatus
    formats: tuple[str, ...] = ()
    auth: str | None = None
    requirement: str | None = None
    notes: str | None = None


Cursor = dict[str, Any]


@runtime_checkable
class SourceAdapter(Protocol):
    kind: str

    def describe(self) -> SourceInfo: ...

    def fetch(self, cursor: Cursor | None = None) -> Iterator[tuple[list[RawItem], Cursor]]:
        """Yield batches of items and the cursor to store after each batch is committed."""
        ...
