"""Row validation and normalisation (SVC-04; DR-07, DR-08, DR-09, DR-41)."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime

from copilot.modules.ingestion.adapters.base import ColumnMapping, SourceType
from copilot.modules.ingestion.adapters.file_adapter import FileAdapter
from copilot.modules.ingestion.validation import (
    MAX_TEXT_CHARS,
    MetricObservation,
    NormalizedRecord,
    RowError,
    RowValidator,
    ValidationTally,
)

Result = NormalizedRecord | MetricObservation | RowError


def _run(
    data: bytes, name: str, mapping: ColumnMapping | None, source_type: SourceType
) -> tuple[list[Result], ValidationTally, RowValidator]:
    adapter = FileAdapter(data, name, mapping)
    validator = RowValidator(adapter, source_type)
    tally = ValidationTally()
    results = [validator.validate(item, tally) for batch, _ in adapter.fetch() for item in batch]
    return results, tally, validator


REVIEWS = (
    b"id,review,stars,user,when,version\n"
    b"r1,App crashes on upload,1,u-1,25/12/2026,4.2.0\n"
    b"r2,   ,5,u-2,26/12/2026,4.2.0\n"
    b"r3,Love the export,great,,not a date,\n"
    b"r1,Dark mode please,4,u-3,,4.3\n"
)
MAPPING = ColumnMapping(
    text="review",
    rating="stars",
    customer_id="user",
    occurred_at="when",
    source_record_id="id",
    product_version="version",
)


def test_feedback_rows_are_normalised_or_rejected_with_reasons() -> None:
    results, tally, validator = _run(REVIEWS, "r.csv", MAPPING, SourceType.REVIEW)
    first, empty, flagged, dup = results

    assert isinstance(first, NormalizedRecord)
    assert first.raw_text == "App crashes on upload"
    assert first.occurred_at == datetime(2026, 12, 25, tzinfo=UTC)  # day-first inferred
    assert first.occurred_at_missing is False
    assert (first.rating_value, first.rating_raw) == (1.0, "1")
    assert first.customer_ref == "u-1"
    assert first.product_version_raw == "4.2.0"
    assert first.flags == ("duplicate_source_record_id",)  # r1 appears twice

    assert empty == RowError(2, 0, "text", "text_missing", "Text is empty.")  # DR-07

    assert isinstance(flagged, NormalizedRecord)  # kept despite bad date and rating (DR-08)
    assert flagged.occurred_at is None and flagged.occurred_at_missing
    assert flagged.occurred_at_raw == "not a date"
    assert flagged.rating_value is None and flagged.rating_raw == "great"
    assert flagged.customer_ref is None  # unknown identity, never invented (CR-18)
    assert set(flagged.flags) == {"occurred_at_unparseable", "rating_invalid"}

    assert isinstance(dup, NormalizedRecord)
    assert "occurred_at_missing" in dup.flags

    assert (tally.received, tally.valid, tally.rejected) == (4, 3, 1)
    assert tally.reconciled
    assert tally.rejected_by_code == {"text_missing": 1}
    assert tally.flags_by_code["duplicate_source_record_id"] == 2
    assert validator.date_order is not None and not validator.date_order.assumed


def test_long_text_is_kept_and_flagged_not_cut() -> None:
    long_text = "x" * (MAX_TEXT_CHARS + 5)
    data = json.dumps([{"t": long_text}]).encode()
    [record], _, _ = _run(data, "l.json", ColumnMapping(text="t"), SourceType.OTHER)
    assert isinstance(record, NormalizedRecord)
    assert record.raw_text == long_text  # original kept
    assert record.text_truncated and "text_truncated" in record.flags


def test_structural_defects_are_rejected_row_by_row() -> None:
    data = b"text,id\nfine,1\ntoo,many,values\nalso fine,3\n"
    results, tally, _ = _run(data, "d.csv", ColumnMapping(text="text"), SourceType.TICKET)
    assert isinstance(results[1], RowError)
    assert results[1].code == "extra_values"
    assert results[1].row_number == 2
    assert (tally.valid, tally.rejected) == (2, 1)  # processing continued (DR-36)


def test_transcript_segments_keep_their_parent_row_and_speaker() -> None:
    data = b"Interviewer: How do you export?\nCustomer: Weekly, and it is slow.\n"
    results, tally, _ = _run(data, "t.txt", None, SourceType.TRANSCRIPT)
    assert [(r.row_number, r.segment_index, r.speaker) for r in results] == [
        (1, 0, "Interviewer"),
        (1, 1, "Customer"),
    ]
    assert all(
        isinstance(r, NormalizedRecord) and r.source_type is SourceType.TRANSCRIPT for r in results
    )
    assert tally.flags_by_code == {"occurred_at_missing": 2}


def test_metric_rows_follow_dr41() -> None:
    data = (
        b"metric,date,value,platform\n"
        b"weekly_active_users,2026-10-05,1234,android\n"
        b",2026-10-05,5,ios\n"
        b"weekly_active_users,05/10/2026,5,ios\n"
        b"weekly_active_users,2026-10-05,many,ios\n"
        b"weekly_active_users,2026-10-05,99,android\n"
        b"crash_rate,2026-10-05,0.4,\n"
    )
    mapping = ColumnMapping(
        metric_name="metric", occurred_at="date", metric_value="value", dimension="platform"
    )
    results, tally, _ = _run(data, "m.csv", mapping, SourceType.METRICS)
    ok, no_name, bad_date, bad_value, dup, no_dim = results
    assert ok == MetricObservation(
        1, "weekly_active_users", date(2026, 10, 5), 1234.0, "android", {}
    )
    assert isinstance(no_name, RowError) and no_name.code == "metric_name_missing"
    assert isinstance(bad_date, RowError) and bad_date.code == "metric_date_invalid"
    assert isinstance(bad_value, RowError) and bad_value.code == "metric_value_invalid"
    assert isinstance(dup, RowError) and dup.code == "duplicate_metric_observation"
    assert "row 1" in dup.message
    assert isinstance(no_dim, MetricObservation) and no_dim.dimension == ""
    assert (tally.received, tally.valid, tally.rejected) == (6, 2, 4)


def test_duplicate_metric_detection_does_not_depend_on_paging() -> None:
    data = b"metric,date,value\nm,2026-10-05,1\nm,2026-10-05,2\n"
    mapping = ColumnMapping(metric_name="metric", occurred_at="date", metric_value="value")
    adapter = FileAdapter(data, "m.csv", mapping)
    validator = RowValidator(adapter, SourceType.METRICS)
    [(second_page, _)] = list(adapter.fetch_range(1, 2))  # only the later row
    result = validator.validate(second_page[0])
    assert isinstance(result, RowError) and result.code == "duplicate_metric_observation"
