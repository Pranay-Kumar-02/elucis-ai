"""Column mapping rules (FR-ING-03, UI-03, D06 step 3).

* ``required_fields`` says which standard fields a source type needs.
* ``check_mapping`` enforces them for a given file; a missing required field means the
  import cannot start (D06 step 3).
* ``suggest_mapping`` pre-fills the UI-03 dropdowns from header names. It only proposes:
  the person confirms or changes every field before anything is imported.
"""

from __future__ import annotations

import re

from copilot.core.errors import ValidationFailedError
from copilot.modules.ingestion.adapters.base import ColumnMapping, SourceType

FEEDBACK_FIELDS = (
    "text",
    "occurred_at",
    "customer_id",
    "rating",
    "product_version",
    "source_record_id",
    "speaker",
)
METRIC_FIELDS = ("metric_name", "metric_value", "occurred_at", "dimension")

# Normalised header names, most specific first. Matching is exact after normalisation.
_ALIASES: dict[str, tuple[str, ...]] = {
    "text": (
        "text",
        "review_text",
        "review_body",
        "review",
        "body",
        "content",
        "comment",
        "comments",
        "feedback",
        "feedback_text",
        "message",
        "description",
        "ticket_body",
        "transcript",
        "utterance",
        "notes",
        "note",
    ),
    "occurred_at": (
        "occurred_at",
        "created_at",
        "created",
        "submitted_at",
        "review_date",
        "date",
        "timestamp",
        "datetime",
        "time",
        "date_time",
        "posted_at",
        "at",
    ),
    "customer_id": (
        "customer_id",
        "customer",
        "user_id",
        "userid",
        "account_id",
        "author_id",
        "author",
        "reviewer_id",
        "reviewer",
        "client_id",
        "requester_id",
        "user",
        "email",
    ),
    "rating": ("rating", "star_rating", "stars", "score", "review_rating"),
    "product_version": (
        "product_version",
        "app_version",
        "version",
        "release",
        "build",
        "app_version_name",
    ),
    "source_record_id": (
        "source_record_id",
        "review_id",
        "ticket_id",
        "record_id",
        "external_id",
        "id",
        "uuid",
    ),
    "speaker": ("speaker", "speaker_name"),
    "metric_name": ("metric_name", "metric", "kpi", "name"),
    "metric_value": ("metric_value", "value", "count", "amount"),
    "dimension": ("dimension", "segment", "platform", "region", "country"),
}


def normalise_header(name: str) -> str:
    """'Review Body ' -> 'review_body'; 'author.id' -> 'author_id'."""
    return re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")


def required_fields(source_type: SourceType) -> tuple[str, ...]:
    if source_type is SourceType.METRICS:
        return ("metric_name", "metric_value", "occurred_at")
    return ("text",)


def allowed_fields(source_type: SourceType) -> tuple[str, ...]:
    return METRIC_FIELDS if source_type is SourceType.METRICS else FEEDBACK_FIELDS


def suggest_mapping(columns: list[str], source_type: SourceType) -> dict[str, str]:
    """Propose a column for each standard field; each column is used at most once."""
    by_normal: dict[str, str] = {}
    for column in columns:
        by_normal.setdefault(normalise_header(column), column)
    used: set[str] = set()
    suggestion: dict[str, str] = {}
    for fld in allowed_fields(source_type):
        for alias in _ALIASES[fld]:
            candidate = by_normal.get(alias)
            if candidate is not None and candidate not in used:
                suggestion[fld] = candidate
                used.add(candidate)
                break
    return suggestion


def check_mapping(mapping: ColumnMapping, source_type: SourceType, file_format: str) -> None:
    """Raise ``ValidationFailedError`` listing every problem with the mapping."""
    problems: list[dict[str, str]] = []
    mapped = mapping.mapped_columns()
    if source_type is SourceType.METRICS and file_format == "txt":
        raise ValidationFailedError(
            "Metric files must be CSV or JSON with metric name, date and value columns.",
            details=[{"field": "source_type", "issue": "metrics_need_tabular_file"}],
        )
    for fld in required_fields(source_type):
        if fld not in mapped:
            problems.append({"field": f"column_mapping.{fld}", "issue": "required"})
    allowed = set(allowed_fields(source_type))
    for fld in mapped:
        if fld not in allowed:
            problems.append(
                {"field": f"column_mapping.{fld}", "issue": f"not_used_for_{source_type.value}"}
            )
    columns = list(mapped.values())
    for column in {c for c in columns if columns.count(c) > 1}:
        fields = sorted(f for f, c in mapped.items() if c == column)
        problems.append(
            {
                "field": f"column_mapping.{fields[1]}",
                "issue": f"column {column!r} already mapped to {fields[0]}",
            }
        )
    if problems:
        raise ValidationFailedError(
            "The column mapping is incomplete or inconsistent.", details=problems
        )
