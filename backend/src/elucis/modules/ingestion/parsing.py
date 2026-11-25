"""Value parsers used by row validation: timestamps, ratings and numbers.

Timestamps (DR-08, DR-21, SVC-05 "date-only treated as 00:00 UTC"):

* ISO 8601 first (``2026-10-02``, ``2026-10-02T09:14:00Z``, with offsets);
* Unix epoch seconds (10 digits) or milliseconds (13 digits);
* numeric dates such as ``03/04/2026``: the day/month order is inferred once per column
  from values that can only be read one way (a first part above 12 means day first). When
  every value is ambiguous, day-month-year is assumed and the caller reports that;
* other written forms (``Oct 2, 2026 9:14 PM``) through ``dateutil``, accepted only when the
  text fully specifies the date (nothing filled in from today's date).

Results are timezone-aware UTC. Naive values are read as UTC. Anything outside
1970-01-01 .. one year from now is treated as unparseable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum

from dateutil import parser as date_parser

_NUMERIC_DATE = re.compile(r"^\s*(\d{1,4})[/.-](\d{1,2})[/.-](\d{1,4})(?:[ T](.+))?\s*$")
_EPOCH = re.compile(r"^\d{10}(?:\d{3})?$")
_EARLIEST = datetime(1970, 1, 1, tzinfo=UTC)
_DEFAULT_A = datetime(2001, 1, 1)  # noqa: DTZ001 - sentinels for completeness detection
_DEFAULT_B = datetime(2002, 2, 2)  # noqa: DTZ001


class DateOrder(StrEnum):
    DMY = "dmy"
    MDY = "mdy"


@dataclass(frozen=True, slots=True)
class DateOrderInference:
    order: DateOrder
    assumed: bool  # True when no value settled the question


def infer_date_order(values: list[str]) -> DateOrderInference | None:
    """Day/month order of a column's numeric dates, or None when it has none to decide."""
    day_first = month_first = False
    numeric = 0
    for value in values:
        match = _NUMERIC_DATE.match(value)
        if not match or len(match.group(1)) == 4:  # year-first is unambiguous
            continue
        numeric += 1
        first, second = int(match.group(1)), int(match.group(2))
        if first > 12 >= second:
            day_first = True
        elif second > 12 >= first:
            month_first = True
    if numeric == 0:
        return None
    if month_first and not day_first:
        return DateOrderInference(DateOrder.MDY, assumed=False)
    if day_first and not month_first:
        return DateOrderInference(DateOrder.DMY, assumed=False)
    # Every value ambiguous, or the column is inconsistent: fall back to day first.
    return DateOrderInference(DateOrder.DMY, assumed=True)


def _to_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _in_range(value: datetime) -> datetime | None:
    latest = datetime.now(UTC) + timedelta(days=366)
    return value if _EARLIEST <= value <= latest else None


def _parse_epoch(text: str) -> datetime | None:
    seconds = int(text) / (1000 if len(text) == 13 else 1)
    try:
        return datetime.fromtimestamp(seconds, UTC)
    except (OverflowError, OSError, ValueError):
        return None


def _parse_written(text: str, order: DateOrder) -> datetime | None:
    match = _NUMERIC_DATE.match(text)
    # yyyy/mm/dd is never day-first; other numeric and written forms follow the column order.
    day_first = order is DateOrder.DMY and not (match and len(match.group(1)) == 4)
    try:
        first = date_parser.parse(text, dayfirst=day_first, default=_DEFAULT_A)
        second = date_parser.parse(text, dayfirst=day_first, default=_DEFAULT_B)
    except (ValueError, OverflowError, TypeError):
        return None
    if first.date() != second.date():
        return None  # part of the date was missing and would have been invented
    return _to_utc(first)


def parse_timestamp(raw: str, order: DateOrder = DateOrder.DMY) -> datetime | None:
    """Return an aware UTC datetime, or None when the value cannot be read safely."""
    text = raw.strip()
    if not text:
        return None
    if _EPOCH.match(text):
        parsed = _parse_epoch(text)
    else:
        try:
            parsed = _to_utc(datetime.fromisoformat(text.replace("z", "Z")))
        except ValueError:
            parsed = _parse_written(text, order)
    return _in_range(parsed) if parsed is not None else None


def parse_iso_date(raw: str) -> date | None:
    """Strict ISO calendar date (``YYYY-MM-DD``) for metric rows (DR-41, SVC-04)."""
    text = raw.strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


_PLAIN_NUMBER = re.compile(r"^[+-]?(?:\d+(?:\.\d+)?|\.\d+)$")
_THOUSANDS = re.compile(r"^[+-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?$")


def parse_number(raw: str) -> float | None:
    """Plain decimal numbers; ``1,234.5`` style thousands separators are accepted."""
    text = raw.strip().replace("\u00a0", "")  # no-break space used as a separator
    if _PLAIN_NUMBER.match(text):
        return float(text)
    if _THOUSANDS.match(text):
        return float(text.replace(",", ""))
    return None


@dataclass(frozen=True, slots=True)
class RatingValue:
    value: float
    out_of: float | None  # the scale when the source states it, for example "4/5"


def parse_rating(raw: str) -> RatingValue | None:
    """Accept ``4``, ``4.5``, ``4/5``, ``80%`` and star strings such as ``★★★★☆``.

    Mapping to the 1-5 scale (A-24) is standardisation (SVC-05), not done here.
    """
    text = raw.strip()
    if not text:
        return None
    if set(text) <= {"★", "☆"}:
        return RatingValue(float(text.count("★")), float(len(text)))
    if text.endswith("%"):
        number = parse_number(text[:-1])
        return RatingValue(number, 100.0) if number is not None and 0 <= number <= 100 else None
    if "/" in text:
        left, _, right = text.partition("/")
        value, scale = parse_number(left), parse_number(right)
        if value is None or scale is None or scale <= 0 or not 0 <= value <= scale:
            return None
        return RatingValue(value, scale)
    number = parse_number(text)
    return RatingValue(number, None) if number is not None and number >= 0 else None
