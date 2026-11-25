"""FileAdapter: format and encoding detection, parsing, mapping and batching (SVC-02)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from copilot.core.errors import UnsupportedFormatError, ValidationFailedError
from copilot.modules.ingestion.adapters.base import (
    BATCH_SIZE,
    MAX_RECORDS_PER_IMPORT,
    ColumnMapping,
    RowDefect,
    SourceAdapter,
)
from copilot.modules.ingestion.adapters.file_adapter import (
    FileAdapter,
    parse_file,
    split_transcript,
)
from copilot.modules.ingestion.adapters.registry import get_adapter_class, list_sources

FIXTURES = Path(__file__).parent / "fixtures"


def _read(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


# ------------------------------------------------------------------------- CSV
def test_csv_header_rows_and_blank_lines() -> None:
    parsed = parse_file(_read("reviews.csv"), "reviews.csv")
    assert parsed.format == "csv"
    assert parsed.encoding == "utf-8"
    assert parsed.csv_delimiter == ","
    assert parsed.columns == ["id", "review", "rating", "customer", "created"]
    assert len(parsed.rows) == 3  # blank line is not a record
    assert parsed.rows[0][1] == "App crashes, every time"  # quoted comma kept
    assert parsed.row_numbers == [1, 2, 3]


def test_semicolon_csv_detected() -> None:
    data = b"text;score\nGood app;5\nBad app;1\n"
    parsed = parse_file(data, "x.csv")
    assert parsed.csv_delimiter == ";"
    assert parsed.rows == [["Good app", "5"], ["Bad app", "1"]]


def test_utf8_bom_removed() -> None:
    parsed = parse_file(b"\xef\xbb\xbftext,id\nhello,1\n", "bom.csv")
    assert parsed.columns == ["text", "id"]
    assert parsed.warnings == []


def test_windows_1252_is_converted_with_warning() -> None:
    data = "text,id\nCaf\u00e9 is slow \u2013 really slow,1\nNa\u00efve UI,2\n".encode("cp1252")
    parsed = parse_file(data, "legacy.csv")
    assert "Café is slow \u2013 really slow" in parsed.rows[0][0]
    assert any("not UTF-8" in w for w in parsed.warnings)


def test_utf16_with_bom_is_decoded() -> None:
    data = "text,id\nhello,1\n".encode("utf-16")
    parsed = parse_file(data, "excel-unicode.csv")
    assert parsed.rows == [["hello", "1"]]
    assert parsed.encoding == "utf-16"


def test_duplicate_and_empty_headers_renamed() -> None:
    parsed = parse_file(b"text,text,,id\na,b,c,1\n", "h.csv")
    assert parsed.columns == ["text", "text_2", "column_3", "id"]
    assert len(parsed.warnings) == 2


def test_short_rows_padded_and_long_rows_marked_as_defects() -> None:
    parsed = parse_file(b"a,b,c\n1,2\n1,2,3,4\n", "r.csv")
    assert parsed.rows == [["1", "2", ""], ["1", "2", "3"]]
    assert parsed.defects == {
        2: RowDefect("extra_values", "Row has 4 values but the header has 3 columns.")
    }
    assert any("fewer values" in w for w in parsed.warnings)
    assert any("will be rejected" in w for w in parsed.warnings)


def test_delimiter_taken_from_header_when_sniffer_gives_up() -> None:
    data = "id;text;stars\n1;Crash ★;1\n2;Slow;4;extra\n3;;5\n".encode()
    parsed = parse_file(data, "irregular.csv")
    assert parsed.csv_delimiter == ";"
    assert parsed.columns == ["id", "text", "stars"]
    assert not any("separator" in w for w in parsed.warnings)


def test_single_column_file_is_read_with_a_note() -> None:
    parsed = parse_file(b"feedback\nCrashes a lot\nToo slow\n", "one.csv")
    assert parsed.columns == ["feedback"]
    assert len(parsed.rows) == 2


def test_excel_sep_hint_line_sets_delimiter() -> None:
    parsed = parse_file(b"sep=;\ntext;id\nhello, world;1\n", "excel.csv")
    assert parsed.csv_delimiter == ";"
    assert parsed.columns == ["text", "id"]
    assert parsed.rows == [["hello, world", "1"]]


def test_unclosed_quote_is_an_error_not_a_merged_row() -> None:
    with pytest.raises(ValidationFailedError, match="unclosed quotation mark") as err:
        parse_file(b'text,id\n"never closed,1\nnext,2\n', "q.csv")
    assert err.value.details == [{"field": "file", "issue": "malformed_csv"}]


def test_multiline_quoted_field_is_one_record() -> None:
    parsed = parse_file(b'text,id\n"line one\nline two",1\nsecond,2\n', "m.csv")
    assert parsed.rows == [["line one\nline two", "1"], ["second", "2"]]
    assert parsed.row_numbers == [1, 2]


def test_empty_header_row_rejected() -> None:
    with pytest.raises(ValidationFailedError, match="header row is empty"):
        parse_file(b",,\na,b,c\n", "h.csv")


def test_header_only_csv_warns_no_rows() -> None:
    parsed = parse_file(b"text,id\n", "empty-body.csv")
    assert parsed.rows == []
    assert "The file has no data rows." in parsed.warnings


# ------------------------------------------------------------------------- JSON
def test_json_nested_objects_flattened_to_dotted_columns() -> None:
    parsed = parse_file(_read("tickets.json"), "tickets.json")
    assert parsed.columns == ["ticket_id", "body", "meta.plan", "priority", "tags"]
    assert parsed.rows[0] == ["T-1", "Login fails with SSO", "pro", "2", ""]
    assert parsed.rows[1][4] == '["export","perf"]'  # arrays stay compact JSON
    assert parsed.defects == {3: RowDefect("not_an_object", "Array element is not an object.")}


def test_json_flattening_stops_at_three_levels_and_keeps_scalars_readable() -> None:
    data = json.dumps([{"a": {"b": {"c": {"d": 1}}}, "ok": True, "n": None, "x": 1.5}])
    parsed = parse_file(data.encode(), "deep.json")
    assert parsed.columns == ["a.b.c", "ok", "n", "x"]
    assert parsed.rows[0] == ['{"d":1}', "true", "", "1.5"]


def test_json_object_wrapper_gets_a_helpful_message() -> None:
    data = json.dumps({"reviews": [{"text": "a"}, {"text": "b"}]})
    with pytest.raises(ValidationFailedError, match='"reviews" field holds 2 records'):
        parse_file(data.encode(), "wrapped.json")


@pytest.mark.parametrize(
    ("data", "issue"),
    [(b'{"text": "x"}', "json_not_array"), (b'[{"text": "x"},', "invalid_json")],
)
def test_json_must_be_valid_array(data: bytes, issue: str) -> None:
    with pytest.raises(ValidationFailedError) as err:
        parse_file(data, "bad.json")
    assert err.value.details[0]["issue"] == issue


# ------------------------------------------------------------------------- TXT
def test_transcript_split_into_speaker_turns() -> None:
    parsed = parse_file(_read("interview.txt"), "interview.txt")
    assert parsed.transcript_mode == "speaker_turns"
    assert parsed.columns == ["segment_index", "speaker", "text"]
    assert [r[1] for r in parsed.rows] == ["Interviewer", "Customer", "Interviewer"]
    assert parsed.rows[1][2] == "Mostly weekly. It is slow\nwhen the file is big."


def test_transcript_turns_with_leading_time_stamps() -> None:
    mode, segments = split_transcript("[00:00:05] Alice: Hi there\n00:01:10 Bob: Export is slow\n")
    assert mode == "speaker_turns"
    assert segments == [("Alice", "Hi there"), ("Bob", "Export is slow")]


def test_pasted_text_reads_like_a_text_file() -> None:
    adapter = FileAdapter.from_pasted_text("First note.\n\nSecond note.")
    assert adapter.parsed.format == "txt"
    assert adapter.filename == "pasted-text.txt"
    [(batch, _)] = list(adapter.fetch())
    assert [i.text for i in batch] == ["First note.", "Second note."]


def test_record_limit_reported_on_parse() -> None:
    rows = "\n".join(f"r{i}" for i in range(MAX_RECORDS_PER_IMPORT + 1))
    parsed = parse_file(f"text\n{rows}\n".encode(), "big.csv")
    assert parsed.exceeds_record_limit
    assert any("at most 20,000" in w for w in parsed.warnings)


def test_transcript_counts_as_one_record() -> None:
    parsed = parse_file(_read("interview.txt"), "interview.txt")
    assert len(parsed.rows) == 3
    assert parsed.record_count == 1


def test_transcript_preamble_kept_without_speaker() -> None:
    mode, segments = split_transcript("Call notes 1 Oct\nAlice: Hi\nBob: Hello there\n")
    assert mode == "speaker_turns"
    assert segments == [(None, "Call notes 1 Oct"), ("Alice", "Hi"), ("Bob", "Hello there")]


def test_plain_text_split_into_paragraphs() -> None:
    parsed = parse_file(b"First note about export.\n\nSecond note: login.\n\n\n", "notes.txt")
    assert parsed.transcript_mode == "paragraphs"
    assert parsed.rows == [["0", "First note about export."], ["1", "Second note: login."]]


# ------------------------------------------------------------------------- rejections
@pytest.mark.parametrize("name", ["data.xlsx", "data", "data.csv.exe"])
def test_unsupported_extension_rejected(name: str) -> None:
    with pytest.raises(UnsupportedFormatError):
        parse_file(b"text\nx\n", name)


def test_binary_content_rejected_even_with_csv_extension() -> None:
    with pytest.raises(UnsupportedFormatError):
        parse_file(b"PK\x03\x04\x00\x00binary", "renamed.csv")


def test_empty_file_rejected() -> None:
    with pytest.raises(ValidationFailedError, match="empty"):
        parse_file(b"  \n", "empty.csv")


# ------------------------------------------------------------------------- mapping + fetch
def test_mapping_produces_raw_items_with_metadata() -> None:
    mapping = ColumnMapping(
        text="review", rating="rating", customer_id="customer", occurred_at="created"
    )
    adapter = FileAdapter(_read("reviews.csv"), "reviews.csv", mapping)
    [(batch, cursor)] = list(adapter.fetch())
    assert cursor == {"position": 3}
    first, third = batch[0], batch[2]
    assert first.text == "App crashes, every time"
    assert first.rating_raw == "1"
    assert first.customer_ref == "c-001"
    assert first.occurred_at_raw == "2026-10-01"
    assert first.metadata == {"id": "1"}  # unmapped column kept as metadata
    assert third.customer_ref is None  # empty value -> None (unknown identity, CR-18)


def test_mapping_to_unknown_column_rejected() -> None:
    with pytest.raises(ValidationFailedError) as err:
        FileAdapter(_read("reviews.csv"), "reviews.csv", ColumnMapping(text="comment"))
    assert err.value.details == [
        {"field": "column_mapping.text", "issue": "column 'comment' not in file"}
    ]


def test_tabular_fetch_requires_mapping() -> None:
    adapter = FileAdapter(_read("reviews.csv"), "reviews.csv")
    with pytest.raises(ValidationFailedError, match="mapping is required"):
        next(adapter.fetch())


def test_transcript_has_implicit_mapping_and_segments() -> None:
    adapter = FileAdapter(_read("interview.txt"), "interview.txt")
    [(batch, _)] = list(adapter.fetch())
    assert [(i.row_number, i.segment_index, i.speaker) for i in batch] == [
        (1, 0, "Interviewer"),
        (1, 1, "Customer"),
        (1, 2, "Interviewer"),
    ]


def test_invalid_json_element_carries_a_defect_for_row_level_rejection() -> None:
    adapter = FileAdapter(_read("tickets.json"), "tickets.json", ColumnMapping(text="body"))
    [(batch, _)] = list(adapter.fetch())
    assert len(batch) == 3  # every received row is accounted for (DR-40)
    assert batch[2].text == ""
    assert batch[2].defect == RowDefect("not_an_object", "Array element is not an object.")
    assert batch[0].metadata == {"ticket_id": "T-1", "meta.plan": "pro", "priority": "2"}


def test_fetch_range_returns_exact_slice() -> None:
    rows = [{"text": f"feedback {i}"} for i in range(30)]
    adapter = FileAdapter(json.dumps(rows).encode(), "r.json", ColumnMapping(text="text"))
    [(batch, cursor)] = list(adapter.fetch_range(10, 15))
    assert [i.row_number for i in batch] == [11, 12, 13, 14, 15]
    assert cursor == {"position": 15}
    assert list(adapter.fetch_range(30, 40)) == []


def test_fetch_batches_of_500_and_resumes_from_cursor() -> None:
    rows = [{"text": f"feedback {i}"} for i in range(1203)]
    adapter = FileAdapter(json.dumps(rows).encode(), "many.json", ColumnMapping(text="text"))
    batches = list(adapter.fetch())
    assert [len(b) for b, _ in batches] == [BATCH_SIZE, BATCH_SIZE, 203]
    assert [c for _, c in batches] == [{"position": 500}, {"position": 1000}, {"position": 1203}]
    resumed = list(adapter.fetch({"position": 1000}))
    assert len(resumed) == 1
    assert resumed[0][0][0].row_number == 1001
    assert list(adapter.fetch({"position": 1203})) == []


def test_preview_limits_rows_and_clips_long_cells() -> None:
    rows = [{"text": "x" * 800} for _ in range(30)]
    adapter = FileAdapter(json.dumps(rows).encode(), "long.json")
    preview = adapter.preview(20)
    assert len(preview) == 20
    assert len(preview[0][0]) == 503 and preview[0][0].endswith("...")


# ------------------------------------------------------------------------- registry
def test_file_adapter_satisfies_protocol_and_catalogue_is_honest() -> None:
    adapter = FileAdapter(b"text\nx\n", "a.csv", ColumnMapping(text="text"))
    assert isinstance(adapter, SourceAdapter)
    statuses = {s.kind: s.status.value for s in list_sources()}
    assert statuses["file"] == "implemented"
    assert {k for k, v in statuses.items() if v == "implemented"} == {"file"}
    assert get_adapter_class("file") is FileAdapter


def test_designed_connector_cannot_be_instantiated() -> None:
    with pytest.raises(ValidationFailedError, match="not implemented"):
        get_adapter_class("zendesk")
