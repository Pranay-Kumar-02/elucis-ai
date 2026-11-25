"""Timestamp, number and rating parsers used by row validation."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from copilot.modules.ingestion.parsing import (
    DateOrder,
    infer_date_order,
    parse_iso_date,
    parse_number,
    parse_rating,
    parse_timestamp,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2026-10-02", datetime(2026, 10, 2, tzinfo=UTC)),  # date only -> 00:00 UTC
        ("2026-10-02T09:14:00Z", datetime(2026, 10, 2, 9, 14, tzinfo=UTC)),
        ("2026-10-02 09:14", datetime(2026, 10, 2, 9, 14, tzinfo=UTC)),  # naive -> UTC
        ("2026-10-02T14:44:00+05:30", datetime(2026, 10, 2, 9, 14, tzinfo=UTC)),
        ("1790000000", datetime.fromtimestamp(1790000000, UTC)),  # epoch seconds
        ("1790000000000", datetime.fromtimestamp(1790000000, UTC)),  # epoch milliseconds
        ("Oct 2, 2026 9:14 PM", datetime(2026, 10, 2, 21, 14, tzinfo=UTC)),
        ("2 October 2026", datetime(2026, 10, 2, tzinfo=UTC)),
        ("2026/10/02", datetime(2026, 10, 2, tzinfo=UTC)),
    ],
)
def test_parse_timestamp_accepts_common_forms(raw: str, expected: datetime) -> None:
    assert parse_timestamp(raw) == expected


def test_numeric_dates_follow_the_column_order() -> None:
    assert parse_timestamp("03/04/2026", DateOrder.DMY) == datetime(2026, 4, 3, tzinfo=UTC)
    assert parse_timestamp("03/04/2026", DateOrder.MDY) == datetime(2026, 3, 4, tzinfo=UTC)


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "yesterday",
        "October 2026",
        "October 2",
        "2026-13-01",
        "31/02/2026",
        "1800-01-01",
        "2999-01-01",
        "n/a",
    ],
)
def test_parse_timestamp_refuses_incomplete_or_impossible_values(raw: str) -> None:
    assert parse_timestamp(raw) is None


def test_infer_date_order() -> None:
    dmy = infer_date_order(["25/12/2026", "03/04/2026"])
    assert dmy is not None and dmy.order is DateOrder.DMY and not dmy.assumed
    mdy = infer_date_order(["12/25/2026", "03/04/2026"])
    assert mdy is not None and mdy.order is DateOrder.MDY and not mdy.assumed
    ambiguous = infer_date_order(["03/04/2026", "05/06/2026", "2026-01-01"])
    assert ambiguous is not None and ambiguous.order is DateOrder.DMY and ambiguous.assumed
    inconsistent = infer_date_order(["25/12/2026", "12/25/2026"])
    assert inconsistent is not None and inconsistent.assumed
    assert infer_date_order(["2026-10-02", "Oct 3, 2026", ""]) is None  # nothing to decide


def test_parse_iso_date_is_strict() -> None:
    assert parse_iso_date("2026-10-02") == date(2026, 10, 2)
    for bad in ("2026-10-2", "02/10/2026", "2026-02-30", "2026-10-02T00:00:00"):
        assert parse_iso_date(bad) is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("42", 42.0),
        ("-3.5", -3.5),
        (".5", 0.5),
        ("1,234", 1234.0),
        ("1,234,567.25", 1234567.25),
        ("1\u00a0234", 1234.0),
    ],
)
def test_parse_number(raw: str, expected: float) -> None:
    assert parse_number(raw) == expected


@pytest.mark.parametrize("raw", ["", "abc", "1,23", "12,34.5", "1.2.3", "4 stars"])
def test_parse_number_rejects_ambiguous_text(raw: str) -> None:
    assert parse_number(raw) is None


@pytest.mark.parametrize(
    ("raw", "value", "out_of"),
    [
        ("4", 4.0, None),
        ("4.5", 4.5, None),
        ("4/5", 4.0, 5.0),
        ("8 / 10", 8.0, 10.0),
        ("80%", 80.0, 100.0),
        ("★★★★☆", 4.0, 5.0),
    ],
)
def test_parse_rating(raw: str, value: float, out_of: float | None) -> None:
    rating = parse_rating(raw)
    assert rating is not None
    assert (rating.value, rating.out_of) == (value, out_of)


@pytest.mark.parametrize("raw", ["", "great", "-1", "6/5", "120%", "4/0"])
def test_parse_rating_rejects_invalid(raw: str) -> None:
    assert parse_rating(raw) is None
