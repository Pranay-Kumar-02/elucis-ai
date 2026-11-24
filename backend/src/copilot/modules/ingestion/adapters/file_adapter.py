"""File source adapter: CSV, JSON and TXT (DR-05, DR-27, D03 SVC-02, D06 step 2).

Pipeline for one uploaded file::

    bytes -> detect_encoding -> decode -> parse (CSV dialect / JSON array / TXT turns)
          -> columns + rows -> preview(20)  or  fetch() -> batches of RawItem via mapping

Design rules implemented here:

* encoding: BOM first, then strict UTF-8, then ``charset-normalizer``; a non-UTF-8 file is
  converted and the conversion is reported as a warning (DR-05 names UTF-8 as the format);
* CSV dialect from ``csv.Sniffer`` on the first 64 KB; the first row is the header;
* JSON must be an array of objects; nested values are kept as compact JSON strings;
* TXT transcripts split into speaker turns with ``^\\s*([A-Z][\\w .'-]{0,40}):\\s``,
  else into paragraphs (DR-27);
* the extension must agree with the content, binary content is refused.

The adapter never stores, logs or interprets file content.
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

from copilot.core.errors import UnsupportedFormatError, ValidationFailedError
from copilot.modules.ingestion.adapters.base import (
    BATCH_SIZE,
    AdapterStatus,
    ColumnMapping,
    Cursor,
    RawItem,
    SourceInfo,
)

FileFormat = Literal["csv", "json", "txt"]
SUPPORTED_EXTENSIONS: dict[str, FileFormat] = {".csv": "csv", ".json": "json", ".txt": "txt"}
SNIFF_BYTES = 64 * 1024
PREVIEW_CELL_CHARS = 500
SPEAKER_TURN = re.compile(r"^\s*([A-Z][\w .'-]{0,40}):\s", re.MULTILINE)
PARAGRAPH_BREAK = re.compile(r"\n\s*\n")
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
    transcript_mode: Literal["speaker_turns", "paragraphs"] | None = None
    warnings: list[str] = field(default_factory=list)
    invalid_rows: dict[int, str] = field(default_factory=dict)  # row_number -> reason


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
                raise ValidationFailedError(
                    "The file's byte-order mark does not match its content."
                ) from exc
    if b"\x00" in data[:SNIFF_BYTES]:
        raise UnsupportedFormatError("The file looks binary, not text.")
    try:
        return EncodingResult("utf-8", data.decode("utf-8"), converted=False)
    except UnicodeDecodeError:
        pass
    best = from_bytes(data).best()
    if best is None or best.encoding is None:
        raise ValidationFailedError(
            "The file's text encoding could not be detected. Save it as UTF-8 and upload again.",
            details=[{"field": "file", "issue": "undetectable_encoding"}],
        )
    return EncodingResult(best.encoding, str(best), converted=True)


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


def _parse_csv(text: str, parsed: ParsedFile) -> None:
    csv.field_size_limit(1024 * 1024)
    sample = text[:SNIFF_BYTES]
    try:
        dialect: type[csv.Dialect] | csv.Dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
        parsed.warnings.append("CSV dialect could not be detected; assuming comma-separated.")
    parsed.csv_delimiter = dialect.delimiter
    reader = csv.reader(io.StringIO(text, newline=""), dialect)
    try:
        header = next(reader)
    except StopIteration:
        raise ValidationFailedError("The CSV file has no header row.") from None
    parsed.columns = _unique_headers(header, parsed.warnings)
    width = len(parsed.columns)
    ragged = 0
    row_number = 0
    try:
        for record in reader:
            if not record or all(not cell.strip() for cell in record):
                continue  # blank line: not a record
            row_number += 1
            if len(record) != width:
                ragged += 1
                if len(record) > width:
                    parsed.invalid_rows[row_number] = f"{len(record)} values but {width} columns"
            parsed.rows.append((record + [""] * width)[:width])
            parsed.row_numbers.append(row_number)
    except csv.Error as exc:
        raise ValidationFailedError(
            f"The CSV file is malformed near data row {row_number + 1}.",
            details=[{"field": "file", "issue": "malformed_csv"}],
        ) from exc
    if ragged:
        parsed.warnings.append(
            f"{ragged} row(s) have a different number of values than the header."
        )


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _parse_json(text: str, parsed: ParsedFile) -> None:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValidationFailedError(
            f"The file is not valid JSON (line {exc.lineno}, column {exc.colno}).",
            details=[{"field": "file", "issue": "invalid_json"}],
        ) from None
    if not isinstance(data, list):
        raise ValidationFailedError(
            'JSON must be an array of records, for example [{"text": "..."}].',
            details=[{"field": "file", "issue": "json_not_array"}],
        )
    columns: dict[str, None] = {}
    for item in data:
        if isinstance(item, dict):
            columns.update(dict.fromkeys(str(k) for k in item))
    parsed.columns = list(columns)
    for index, item in enumerate(data, start=1):
        parsed.row_numbers.append(index)
        if isinstance(item, dict):
            parsed.rows.append([_cell(item.get(col)) for col in parsed.columns])
        else:
            parsed.invalid_rows[index] = "array element is not an object"
            parsed.rows.append([""] * len(parsed.columns))
    if parsed.invalid_rows:
        parsed.warnings.append(f"{len(parsed.invalid_rows)} array element(s) are not objects.")


def split_transcript(
    text: str,
) -> tuple[Literal["speaker_turns", "paragraphs"], list[tuple[str | None, str]]]:
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
    mode, segments = split_transcript(text.replace("\r\n", "\n"))
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
        raise ValidationFailedError(
            "The file is empty.", details=[{"field": "file", "issue": "empty"}]
        )
    enc = detect_encoding(data)
    parsed = ParsedFile(format=fmt, encoding=enc.encoding, columns=[], rows=[], row_numbers=[])
    if enc.converted:
        parsed.warnings.append(
            f"The file is encoded as {enc.encoding}, not UTF-8; it was converted."
        )
    text = enc.text.lstrip("﻿")
    {"csv": _parse_csv, "json": _parse_json, "txt": _parse_txt}[fmt](text, parsed)
    if not parsed.rows:
        parsed.warnings.append("The file has no data rows.")
    return parsed


class FileAdapter:
    """``SourceAdapter`` for uploaded files. Holds the parsed file in memory (<= 20 MB)."""

    kind = "file"

    def __init__(self, data: bytes, filename: str, mapping: ColumnMapping | None = None) -> None:
        self.filename = filename
        self.parsed = parse_file(data, filename)
        self.mapping = mapping or self._default_mapping()
        if self.mapping is not None:
            self._check_mapping(self.mapping)

    # ------------------------------------------------------------------ SourceAdapter
    def describe(self) -> SourceInfo:
        return FILE_SOURCE

    def fetch(self, cursor: Cursor | None = None) -> Iterator[tuple[list[RawItem], Cursor]]:
        """Yield mapped items in batches; ``cursor = {"position": n}`` resumes after item n."""
        if self.mapping is None:
            raise ValidationFailedError(
                "A column mapping with a text column is required for this file.",
                details=[{"field": "column_mapping.text", "issue": "required"}],
            )
        start = int((cursor or {}).get("position", 0))
        batch: list[RawItem] = []
        position = start
        for position in range(start, len(self.parsed.rows)):
            batch.append(self._to_item(position))
            if len(batch) == BATCH_SIZE:
                yield batch, {"position": position + 1}
                batch = []
        if batch:
            yield batch, {"position": position + 1}

    # ------------------------------------------------------------------ helpers
    def preview(self, n: int = 20) -> list[list[str]]:
        def clip(value: str) -> str:
            return value if len(value) <= PREVIEW_CELL_CHARS else value[:PREVIEW_CELL_CHARS] + "..."

        return [[clip(v) for v in row] for row in self.parsed.rows[:n]]

    @property
    def item_count(self) -> int:
        return len(self.parsed.rows)

    def _default_mapping(self) -> ColumnMapping | None:
        if self.parsed.format == "txt":
            speaker = "speaker" if self.parsed.transcript_mode == "speaker_turns" else None
            return ColumnMapping(text="text", speaker=speaker)
        return None

    def _check_mapping(self, mapping: ColumnMapping) -> None:
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
        assert self.mapping is not None  # noqa: S101 - guarded in fetch()
        row = dict(zip(self.parsed.columns, self.parsed.rows[position], strict=True))
        m = self.mapping.mapped_columns()
        used = set(m.values()) | ({"segment_index"} if self.parsed.format == "txt" else set())

        def get(fld: str) -> str | None:
            col = m.get(fld)
            value = row.get(col, "") if col else ""
            return value.strip() or None

        row_number = self.parsed.row_numbers[position]
        metadata = {k: v for k, v in row.items() if k not in used and v != ""}
        if row_number in self.parsed.invalid_rows and self.parsed.format != "txt":
            metadata["_invalid"] = self.parsed.invalid_rows[row_number]
        return RawItem(
            row_number=row_number,
            segment_index=int(row["segment_index"]) if self.parsed.format == "txt" else 0,
            text=row.get(m["text"], ""),
            source_record_id=get("source_record_id"),
            occurred_at_raw=get("occurred_at"),
            customer_ref=get("customer_id"),
            rating_raw=get("rating"),
            version_raw=get("product_version"),
            speaker=get("speaker"),
            metadata=metadata,
        )


FILE_SOURCE = SourceInfo(
    kind="file",
    label="File upload (CSV, JSON, TXT)",
    status=AdapterStatus.IMPLEMENTED,
    formats=("csv", "json", "txt"),
    auth=None,
    requirement="FR-ING-01, FR-ING-03, DR-05, DR-27",
)
