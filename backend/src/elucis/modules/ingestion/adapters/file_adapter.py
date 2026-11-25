"""File source adapter: CSV, JSON and TXT (DR-05, DR-27, D03 SVC-02, D06 step 2).

Pipeline for one uploaded file (or pasted text, FR-ING-10)::

    bytes -> detect_encoding -> decode -> parse (CSV dialect / JSON array / TXT turns)
          -> columns + rows -> preview(n)  or  fetch() -> batches of RawItem via mapping

Rules implemented here:

* encoding: BOM first, then strict UTF-8, then ``charset-normalizer`` on the first 64 KB
  (D06 step 2) followed by a strict decode of the whole file. A non-UTF-8 file is converted
  and the conversion is reported (DR-05 names UTF-8);
* CSV: dialect from ``csv.Sniffer`` on the first 64 KB, an Excel ``sep=`` hint line is
  honoured, quoting is strict (an unclosed quote is an error, not a silently merged row),
  the first row is the header, blank lines are not records;
* JSON: must be an array of objects. Nested objects are flattened to dotted columns
  (``author.id``) up to three levels so they can be mapped; arrays stay compact JSON;
* TXT: transcripts split into speaker turns with ``^\\s*([A-Z][\\w .'-]{0,40}):\\s``
  (an optional leading time stamp such as ``[00:01:23]`` is allowed), else paragraphs
  (DR-27);
* the extension must agree with the content, binary content is refused.

Structural problems in single records (extra CSV values, non-object JSON elements) are
attached to that record as a ``RowDefect`` so validation can reject just that row
(DR-36). The adapter never stores, logs or interprets file content.
"""

from __future__ import annotations

import csv
import io
import json
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import PurePath
from typing import Any, Literal

from charset_normalizer import from_bytes

from elucis.core.errors import UnsupportedFormatError, ValidationFailedError
from elucis.modules.ingestion.adapters.base import (
    BATCH_SIZE,
    MAX_RECORDS_PER_IMPORT,
    AdapterStatus,
    ColumnMapping,
    Cursor,
    RawItem,
    RowDefect,
    SourceInfo,
)

FileFormat = Literal["csv", "json", "txt"]
TranscriptMode = Literal["speaker_turns", "paragraphs"]
SUPPORTED_EXTENSIONS: dict[str, FileFormat] = {".csv": "csv", ".json": "json", ".txt": "txt"}
SNIFF_BYTES = 64 * 1024
PREVIEW_CELL_CHARS = 500
MAX_JSON_DEPTH = 3
PASTED_FILENAME = "pasted-text.txt"
SPEAKER_TURN = re.compile(
    r"^[ \t]*(?:\[?\d{1,2}:\d{2}(?::\d{2})?\]?[ \t]+)?([A-Z][\w .'-]{0,40}):\s", re.MULTILINE
)
PARAGRAPH_BREAK = re.compile(r"\n\s*\n")
EXCEL_SEP_HINT = re.compile(r"^sep=(.)\r?\n", re.IGNORECASE)
_BOMS: tuple[tuple[bytes, str], ...] = (
    (b"\xef\xbb\xbf", "utf-8-sig"),
    (b"\xff\xfe", "utf-16"),
    (b"\xfe\xff", "utf-16"),
)


@dataclass(frozen=True, slots=True)
class EncodingResult:
    encoding: str
    text: str
    converted: bool


@dataclass(slots=True)
class ParsedFile:
    format: FileFormat
    encoding: str
    columns: list[str]
    rows: list[list[str]]
    row_numbers: list[int]
    csv_delimiter: str | None = None
    transcript_mode: TranscriptMode | None = None
    warnings: list[str] = field(default_factory=list)
    defects: dict[int, RowDefect] = field(default_factory=dict)  # row_number -> defect

    @property
    def record_count(self) -> int:
        """Source records (a transcript counts once, however many segments it has)."""
        return len(set(self.row_numbers))

    @property
    def exceeds_record_limit(self) -> bool:
        return self.record_count > MAX_RECORDS_PER_IMPORT


def _file_error(message: str, issue: str) -> ValidationFailedError:
    return ValidationFailedError(message, details=[{"field": "file", "issue": issue}])


def detect_format(filename: str) -> FileFormat:
    ext = PurePath(filename).suffix.lower()
    fmt = SUPPORTED_EXTENSIONS.get(ext)
    if fmt is None:
        raise UnsupportedFormatError(
            details=[
                {
                    "field": "file",
                    "issue": f"extension {ext or '(none)'} is not .csv, .json or .txt",
                }
            ]
        )
    return fmt


def detect_encoding(data: bytes) -> EncodingResult:
    for bom, codec in _BOMS:
        if data.startswith(bom):
            try:
                return EncodingResult(
                    codec.replace("-sig", ""), data.decode(codec), converted=codec == "utf-16"
                )
            except UnicodeDecodeError as exc:
                raise _file_error(
                    "The file's byte-order mark does not match its content.", "bad_bom"
                ) from exc
    if b"\x00" in data[:SNIFF_BYTES]:
        raise UnsupportedFormatError("The file looks binary, not text.")
    try:
        return EncodingResult("utf-8", data.decode("utf-8"), converted=False)
    except UnicodeDecodeError:
        pass
    best = from_bytes(data[:SNIFF_BYTES]).best()
    if best is None or best.encoding is None:
        raise _file_error(
            "The file's text encoding could not be detected. Save it as UTF-8 and upload again.",
            "undetectable_encoding",
        )
    try:
        text = data.decode(best.encoding)
    except (UnicodeDecodeError, LookupError) as exc:
        raise _file_error(
            "The file mixes text encodings and cannot be read reliably. "
            "Save it as UTF-8 and upload again.",
            "mixed_encoding",
        ) from exc
    return EncodingResult(best.encoding, text, converted=True)


def _unique_headers(raw: list[str], warnings: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    out: list[str] = []
    for i, name in enumerate(raw, start=1):
        clean = name.strip() or f"column_{i}"
        if clean != name.strip():
            warnings.append(f"Column {i} has no name; it is shown as {clean!r}.")
        if clean in seen:
            seen[clean] += 1
            renamed = f"{clean}_{seen[clean]}"
            warnings.append(f"Duplicate column name {clean!r}; the repeat is shown as {renamed!r}.")
            clean = renamed
        else:
            seen[clean] = 1
        out.append(clean)
    return out


class _StrictDialect(csv.Dialect):
    """A sniffed dialect with strict quoting, so an unclosed quote raises an error."""

    def __init__(self, base: type[csv.Dialect] | csv.Dialect) -> None:
        self.delimiter = base.delimiter
        self.quotechar = base.quotechar or '"'
        self.escapechar = base.escapechar
        self.doublequote = base.doublequote
        self.skipinitialspace = base.skipinitialspace
        self.lineterminator = "\r\n"
        self.quoting = csv.QUOTE_MINIMAL
        self.strict = True
        super().__init__()


def _sniff_dialect(text: str, parsed: ParsedFile) -> csv.Dialect:
    hint = EXCEL_SEP_HINT.match(text)
    if hint:
        delimiter = hint.group(1)

        class _Hinted(csv.excel):
            pass

        _Hinted.delimiter = delimiter
        return _StrictDialect(_Hinted)
    try:
        sniffed = csv.Sniffer().sniff(text[:SNIFF_BYTES], delimiters=",;\t|")
    except csv.Error:
        # The sniffer gives up on irregular files (ragged rows, quoted line breaks). The
        # header line is still a reliable signal: use its most frequent candidate.
        header = text.split("\n", 1)[0]
        counts = {d: header.count(d) for d in ",;\t|"}
        best = max(counts, key=lambda d: counts[d])
        if counts[best] == 0:
            parsed.warnings.append(
                "Only one column was found. If the file uses another separator, save it as "
                "comma-separated CSV."
            )
            return _StrictDialect(csv.excel)

        class _FromHeader(csv.excel):
            pass

        _FromHeader.delimiter = best
        return _StrictDialect(_FromHeader)
    return _StrictDialect(sniffed)


def _parse_csv(text: str, parsed: ParsedFile) -> None:
    csv.field_size_limit(1024 * 1024)
    dialect = _sniff_dialect(text, parsed)
    parsed.csv_delimiter = dialect.delimiter
    body = EXCEL_SEP_HINT.sub("", text, count=1)
    reader = csv.reader(io.StringIO(body, newline=""), dialect)
    try:
        header = next(reader)
    except StopIteration:
        raise _file_error("The CSV file has no header row.", "no_header") from None
    except csv.Error as exc:
        raise _file_error(f"The CSV header row is malformed ({exc}).", "malformed_csv") from None
    if not any(cell.strip() for cell in header):
        raise _file_error("The CSV header row is empty.", "no_header")
    parsed.columns = _unique_headers(header, parsed.warnings)
    width = len(parsed.columns)
    short_rows = 0
    row_number = 0
    try:
        for record in reader:
            if not record or all(not cell.strip() for cell in record):
                continue  # blank line: not a record
            row_number += 1
            if len(record) > width:
                parsed.defects[row_number] = RowDefect(
                    "extra_values",
                    f"Row has {len(record)} values but the header has {width} columns.",
                )
            elif len(record) < width:
                short_rows += 1
            parsed.rows.append((record + [""] * width)[:width])
            parsed.row_numbers.append(row_number)
    except csv.Error as exc:
        raise _file_error(
            f"The CSV file is malformed at data row {row_number + 1}: {exc}. "
            "Check for an unclosed quotation mark.",
            "malformed_csv",
        ) from None
    if short_rows:
        parsed.warnings.append(
            f"{short_rows} row(s) have fewer values than the header; missing values are empty."
        )
    if parsed.defects:
        parsed.warnings.append(
            f"{len(parsed.defects)} row(s) have more values than the header and will be rejected."
        )


def _flatten(value: dict[str, Any], prefix: str, depth: int, out: dict[str, str]) -> None:
    for key, item in value.items():
        name = f"{prefix}{key}"
        if isinstance(item, dict) and depth < MAX_JSON_DEPTH:
            _flatten(item, f"{name}.", depth + 1, out)
        else:
            out[name] = _cell(item)


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _wrapped_array_hint(data: dict[str, Any]) -> str:
    for key, value in data.items():
        if isinstance(value, list) and value and isinstance(value[0], dict):
            return (
                f' The file is an object whose "{key}" field holds {len(value)} records;'
                " export that array on its own."
            )
    return ""


def _parse_json(text: str, parsed: ParsedFile) -> None:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise _file_error(
            f"The file is not valid JSON (line {exc.lineno}, column {exc.colno}: {exc.msg}).",
            "invalid_json",
        ) from None
    if not isinstance(data, list):
        hint = _wrapped_array_hint(data) if isinstance(data, dict) else ""
        raise _file_error(
            'JSON must be an array of records, for example [{"text": "..."}].' + hint,
            "json_not_array",
        )
    flattened: list[dict[str, str] | None] = []
    columns: dict[str, None] = {}
    for item in data:
        if isinstance(item, dict):
            flat: dict[str, str] = {}
            _flatten(item, "", 1, flat)
            columns.update(dict.fromkeys(flat))
            flattened.append(flat)
        else:
            flattened.append(None)
    parsed.columns = list(columns)
    for index, record in enumerate(flattened, start=1):
        parsed.row_numbers.append(index)
        if record is None:
            parsed.defects[index] = RowDefect("not_an_object", "Array element is not an object.")
            parsed.rows.append([""] * len(parsed.columns))
        else:
            parsed.rows.append([record.get(col, "") for col in parsed.columns])
    if parsed.defects:
        parsed.warnings.append(
            f"{len(parsed.defects)} array element(s) are not objects and will be rejected."
        )


def split_transcript(text: str) -> tuple[TranscriptMode, list[tuple[str | None, str]]]:
    """Split a transcript into (speaker, text) segments (DR-27)."""
    matches = list(SPEAKER_TURN.finditer(text))
    if len(matches) >= 2:
        segments: list[tuple[str | None, str]] = []
        preamble = text[: matches[0].start()].strip()
        if preamble:
            segments.append((None, preamble))
        for i, m in enumerate(matches):
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            body = text[m.end() : end].strip()
            if body:
                segments.append((m.group(1).strip(), body))
        return "speaker_turns", segments
    paragraphs = [p.strip() for p in PARAGRAPH_BREAK.split(text) if p.strip()]
    return "paragraphs", [(None, p) for p in paragraphs]


def _parse_txt(text: str, parsed: ParsedFile) -> None:
    mode, segments = split_transcript(text.replace("\r\n", "\n").replace("\r", "\n"))
    parsed.transcript_mode = mode
    parsed.columns = (
        ["segment_index", "speaker", "text"]
        if mode == "speaker_turns"
        else ["segment_index", "text"]
    )
    for i, (speaker, body) in enumerate(segments):
        parsed.row_numbers.append(1)  # one transcript = one parent record
        parsed.rows.append(
            [str(i), speaker or "", body] if mode == "speaker_turns" else [str(i), body]
        )


def parse_file(data: bytes, filename: str) -> ParsedFile:
    fmt = detect_format(filename)
    if not data.strip():
        raise _file_error("The file is empty.", "empty")
    enc = detect_encoding(data)
    parsed = ParsedFile(format=fmt, encoding=enc.encoding, columns=[], rows=[], row_numbers=[])
    if enc.converted:
        parsed.warnings.append(
            f"The file is encoded as {enc.encoding}, not UTF-8; it was converted."
        )
    text = enc.text.lstrip("﻿")
    if not text.strip():
        raise _file_error("The file is empty.", "empty")
    {"csv": _parse_csv, "json": _parse_json, "txt": _parse_txt}[fmt](text, parsed)
    if not parsed.rows:
        parsed.warnings.append("The file has no data rows.")
    if parsed.exceeds_record_limit:
        parsed.warnings.append(
            f"The file has {parsed.record_count:,} records; one import can hold at most "
            f"{MAX_RECORDS_PER_IMPORT:,}. Split it into smaller files."
        )
    return parsed


class FileAdapter:
    """``SourceAdapter`` for uploaded files and pasted text. Holds the parsed file in memory
    (uploads are capped at 20 MB, A-06)."""

    kind = "file"

    def __init__(self, data: bytes, filename: str, mapping: ColumnMapping | None = None) -> None:
        self.filename = filename
        self.parsed = parse_file(data, filename)
        self.mapping = mapping or self.default_mapping()
        if self.mapping is not None:
            self._check_columns(self.mapping)

    @classmethod
    def from_pasted_text(cls, text: str, mapping: ColumnMapping | None = None) -> FileAdapter:
        """Pasted feedback (FR-ING-10) is read exactly like a TXT upload."""
        return cls(text.encode("utf-8"), PASTED_FILENAME, mapping)

    # ------------------------------------------------------------------ SourceAdapter
    def describe(self) -> SourceInfo:
        return FILE_SOURCE

    def fetch(self, cursor: Cursor | None = None) -> Iterator[tuple[list[RawItem], Cursor]]:
        """Yield mapped items in batches; ``cursor = {"position": n}`` resumes after item n."""
        yield from self.fetch_range(int((cursor or {}).get("position", 0)), len(self.parsed.rows))

    def fetch_range(self, start: int, stop: int) -> Iterator[tuple[list[RawItem], Cursor]]:
        if self.mapping is None:
            raise ValidationFailedError(
                "A column mapping is required for this file.",
                details=[{"field": "column_mapping", "issue": "required"}],
            )
        stop = min(stop, len(self.parsed.rows))
        batch: list[RawItem] = []
        for position in range(max(start, 0), stop):
            batch.append(self._to_item(position))
            if len(batch) == BATCH_SIZE:
                yield batch, {"position": position + 1}
                batch = []
        if batch:
            yield batch, {"position": stop}

    # ------------------------------------------------------------------ helpers
    def preview(self, n: int = 20) -> list[list[str]]:
        def clip(value: str) -> str:
            return value if len(value) <= PREVIEW_CELL_CHARS else value[:PREVIEW_CELL_CHARS] + "..."

        return [[clip(v) for v in row] for row in self.parsed.rows[:n]]

    @property
    def item_count(self) -> int:
        return len(self.parsed.rows)

    def default_mapping(self) -> ColumnMapping | None:
        if self.parsed.format == "txt":
            speaker = "speaker" if self.parsed.transcript_mode == "speaker_turns" else None
            return ColumnMapping(text="text", speaker=speaker)
        return None

    def column_values(self, column: str) -> list[str]:
        index = self.parsed.columns.index(column)
        return [row[index] for row in self.parsed.rows]

    def _check_columns(self, mapping: ColumnMapping) -> None:
        missing = [
            {"field": f"column_mapping.{fld}", "issue": f"column {col!r} not in file"}
            for fld, col in mapping.mapped_columns().items()
            if col not in self.parsed.columns
        ]
        if missing:
            raise ValidationFailedError(
                "The column mapping refers to unknown columns.", details=missing
            )

    def _to_item(self, position: int) -> RawItem:
        assert self.mapping is not None  # noqa: S101 - guarded in fetch_range()
        row = dict(zip(self.parsed.columns, self.parsed.rows[position], strict=True))
        m = self.mapping.mapped_columns()
        used = set(m.values()) | ({"segment_index"} if self.parsed.format == "txt" else set())

        def get(fld: str) -> str | None:
            col = m.get(fld)
            value = row.get(col, "") if col else ""
            return value.strip() or None

        row_number = self.parsed.row_numbers[position]
        text_col = m.get("text")
        return RawItem(
            row_number=row_number,
            segment_index=int(row["segment_index"]) if self.parsed.format == "txt" else 0,
            text=row.get(text_col, "") if text_col else "",
            source_record_id=get("source_record_id"),
            occurred_at_raw=get("occurred_at"),
            customer_ref=get("customer_id"),
            rating_raw=get("rating"),
            version_raw=get("product_version"),
            speaker=get("speaker"),
            metric_name_raw=get("metric_name"),
            metric_value_raw=get("metric_value"),
            dimension_raw=get("dimension"),
            metadata={k: v for k, v in row.items() if k not in used and v != ""},
            defect=self.parsed.defects.get(row_number) if self.parsed.format != "txt" else None,
        )


FILE_SOURCE = SourceInfo(
    kind="file",
    label="File upload (CSV, JSON, TXT)",
    status=AdapterStatus.IMPLEMENTED,
    formats=("csv", "json", "txt"),
    auth=None,
    requirement="FR-ING-01, FR-ING-03, FR-ING-10, DR-05, DR-27",
)
