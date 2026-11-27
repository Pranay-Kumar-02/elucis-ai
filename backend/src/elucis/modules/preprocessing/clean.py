"""Cleaning (SVC-05, DR-11, DR-19): the processed text without markup, quoted replies,
signatures or control characters, in Unicode NFC with consistent whitespace. The raw text
is never changed (DR-15, DR-35)."""

from __future__ import annotations

import html
import re
import unicodedata

_TAG = re.compile(r"<[^>]{1,200}>")
_BREAK_TAG = re.compile(r"<\s*(br|/p|/div|/li)\s*/?>", re.IGNORECASE)
# "On Mon, 3 Oct 2026, Riya <riya@x.com> wrote:" and everything after it.
_REPLY_HEADER = re.compile(r"^\s*On\b.{0,200}\bwrote:\s*$", re.IGNORECASE | re.MULTILINE)
_SIGNATURE = re.compile(r"^(--\s*|Sent from my\b.*)$", re.IGNORECASE)
# Control characters, zero-width characters, line/paragraph separators and the BOM.
_INVISIBLE = [*range(0x00, 0x09), 0x0B, 0x0C, *range(0x0E, 0x20), *range(0x7F, 0xA0)]
_INVISIBLE += [*range(0x200B, 0x2010), 0x2028, 0x2029, 0xFEFF]
_CONTROL = re.compile("[" + "".join(re.escape(chr(c)) for c in _INVISIBLE) + "]")
_SPACES = re.compile("[ " + chr(9) + chr(0xA0) + "]+")  # spaces, tabs, no-break spaces
_BLANK_LINES = re.compile(r"\n{3,}")


def clean_text(raw: str) -> str:
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    text = _BREAK_TAG.sub("\n", text)
    text = _TAG.sub(" ", text)
    text = html.unescape(text)
    header = _REPLY_HEADER.search(text)
    if header:
        text = text[: header.start()]
    lines: list[str] = []
    for line in text.split("\n"):
        if _SIGNATURE.match(line.strip()):
            break  # the rest is a signature
        if line.lstrip().startswith(">"):
            continue  # quoted reply line
        lines.append(line)
    text = "\n".join(lines)
    text = _CONTROL.sub("", text)
    text = unicodedata.normalize("NFC", text)
    text = "\n".join(_SPACES.sub(" ", line).strip() for line in text.split("\n"))
    return _BLANK_LINES.sub("\n\n", text).strip()
