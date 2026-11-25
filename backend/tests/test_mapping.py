"""Mapping suggestions and the per-source-type mapping rules (FR-ING-03, D06 step 3)."""

from __future__ import annotations

import pytest

from copilot.core.errors import ValidationFailedError
from copilot.modules.ingestion.adapters.base import ColumnMapping, SourceType
from copilot.modules.ingestion.mapping import (
    check_mapping,
    normalise_header,
    required_fields,
    suggest_mapping,
)


def test_normalise_header() -> None:
    assert normalise_header(" Review Body ") == "review_body"
    assert normalise_header("author.id") == "author_id"
    assert normalise_header("Star-Rating!") == "star_rating"


def test_suggest_mapping_for_a_review_export() -> None:
    columns = ["Review ID", "Review Body", "Star Rating", "App Version", "Author", "Date"]
    assert suggest_mapping(columns, SourceType.REVIEW) == {
        "text": "Review Body",
        "occurred_at": "Date",
        "customer_id": "Author",
        "rating": "Star Rating",
        "product_version": "App Version",
        "source_record_id": "Review ID",
    }


def test_suggest_mapping_uses_each_column_once_and_skips_unknown() -> None:
    suggestion = suggest_mapping(["id", "comment", "foo"], SourceType.TICKET)
    assert suggestion == {"text": "comment", "source_record_id": "id"}


def test_suggest_mapping_for_metrics() -> None:
    suggestion = suggest_mapping(["metric", "date", "value", "platform"], SourceType.METRICS)
    assert suggestion == {
        "metric_name": "metric",
        "metric_value": "value",
        "occurred_at": "date",
        "dimension": "platform",
    }


def test_required_fields() -> None:
    assert required_fields(SourceType.REVIEW) == ("text",)
    assert required_fields(SourceType.METRICS) == ("metric_name", "metric_value", "occurred_at")


def test_feedback_mapping_needs_text_and_rejects_metric_fields() -> None:
    with pytest.raises(ValidationFailedError) as err:
        check_mapping(ColumnMapping(occurred_at="date", metric_value="v"), SourceType.REVIEW, "csv")
    assert {"field": "column_mapping.text", "issue": "required"} in err.value.details
    assert {
        "field": "column_mapping.metric_value",
        "issue": "not_used_for_review",
    } in err.value.details


def test_metric_mapping_needs_name_value_and_date() -> None:
    with pytest.raises(ValidationFailedError) as err:
        check_mapping(ColumnMapping(metric_name="m"), SourceType.METRICS, "csv")
    issues = {d["field"] for d in err.value.details}
    assert issues == {"column_mapping.metric_value", "column_mapping.occurred_at"}


def test_metrics_cannot_come_from_text_files() -> None:
    mapping = ColumnMapping(metric_name="a", metric_value="b", occurred_at="c")
    with pytest.raises(ValidationFailedError, match="must be CSV or JSON"):
        check_mapping(mapping, SourceType.METRICS, "txt")


def test_one_column_cannot_fill_two_fields() -> None:
    with pytest.raises(ValidationFailedError) as err:
        check_mapping(ColumnMapping(text="body", source_record_id="body"), SourceType.REVIEW, "csv")
    assert err.value.details[0]["issue"] == "column 'body' already mapped to source_record_id"


def test_valid_mapping_passes() -> None:
    check_mapping(ColumnMapping(text="body", rating="stars"), SourceType.REVIEW, "csv")
