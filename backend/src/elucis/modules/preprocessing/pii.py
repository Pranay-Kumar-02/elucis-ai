"""PII masking (SVC-06, DR-28, DR-29).

Presidio's analyzer with the small spaCy English model finds e-mail addresses, card
numbers (Luhn-checked), Aadhaar numbers (checksum-validated) and personal names. Our own
pattern recognisers add what the built-ins score too low for this product: phone numbers
(Indian mobiles and international formats) and PAN numbers. A small cue rule masks a
capitalised name after "my name is", "thanks", "regards" and similar, which the small NER
model often misses. Every detection becomes a typed placeholder::

    "Email me at riya@example.com, Riya" -> "Email me at [EMAIL], [NAME]"

The engine loads once per process (about 30 s cold, then ~25 ms per record). Callers must
fail closed: if ``mask`` raises, the record is not analysable (``pii_failed``).
"""

from __future__ import annotations

import logging
import re
import threading
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from presidio_analyzer import AnalyzerEngine

SCORE_THRESHOLD = 0.5  # D03 SVC-06

PLACEHOLDERS = {
    "EMAIL_ADDRESS": "EMAIL",
    "PHONE_NUMBER": "PHONE",
    "ELUCIS_PHONE": "PHONE",
    "CREDIT_CARD": "CARD",
    "IN_AADHAAR": "ID",
    "ELUCIS_PAN": "ID",
    "US_SSN": "ID",
    "PERSON": "NAME",
    "ELUCIS_CUE_NAME": "NAME",
}
ENTITIES = [e for e in PLACEHOLDERS if e != "ELUCIS_CUE_NAME"]  # the cue rule runs in our code

# Indian mobile numbers (+91 / 0 prefix optional, 10 digits starting 6-9) and international
# numbers written with a + country code; US-style (415) 555-0132.
_PHONE_PATTERNS = (
    r"(?<![\w+])(?:\+91[\s-]?|0)?[6-9]\d{4}[\s-]?\d{5}(?!\d)",
    r"(?<![\w])\+\d{1,3}(?:[\s-]?\d{2,5}){2,4}(?!\d)",
    r"(?<!\w)\(\d{3}\)\s?\d{3}-\d{4}(?!\d)",
)
_PAN = r"\b[A-Z]{3}[ABCFGHLJPT][A-Z]\d{4}[A-Z]\b"  # 4th letter: holder type
# Cue words are matched in any case; the name itself must be capitalised.
_CUE_NAME = re.compile(
    r"\b(?i:my name is|thanks|thank you|regards|cheers|sincerely|spoke (?:to|with)|"
    r"agent named|called)\b[,:]?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)"
)
# Capitalised words after a cue that are not names ("Thanks Team", "I am Unable").
_NOT_NAMES = frozenset(
    {"team", "support", "you", "again", "all", "everyone", "guys", "so", "very", "not", "the",
     "a", "an", "unable", "able", "happy", "sad", "using", "still", "really", "just", "for",
     "in", "on", "a lot", "your", "app", "and"}
)  # fmt: skip


@dataclass(frozen=True, slots=True)
class Masked:
    text: str
    counts: dict[str, int]


@dataclass(frozen=True, slots=True)
class _Span:
    start: int
    end: int
    label: str
    score: float


class PiiMasker:
    """Thread-safe lazy wrapper around one Presidio engine."""

    def __init__(self) -> None:
        self._engine: AnalyzerEngine | None = None
        self._lock = threading.Lock()

    def _load(self) -> AnalyzerEngine:
        with self._lock:
            if self._engine is None:
                self._engine = _build_engine()
            return self._engine

    def mask(self, text: str) -> Masked:
        if not text:
            return Masked(text, {})
        engine = self._load()
        spans = [
            _Span(r.start, r.end, PLACEHOLDERS[r.entity_type], r.score)
            for r in engine.analyze(
                text=text, language="en", entities=ENTITIES, score_threshold=SCORE_THRESHOLD
            )
            if r.entity_type in PLACEHOLDERS
        ]
        spans += _cue_names(text)
        return _replace(text, spans)


def _cue_names(text: str) -> list[_Span]:
    found = []
    for match in _CUE_NAME.finditer(text):
        first = match.group(1).split()[0]
        if first.casefold() in _NOT_NAMES:
            continue
        found.append(_Span(match.start(1), match.end(1), "NAME", 0.6))
    return found


def _replace(text: str, spans: list[_Span]) -> Masked:
    """Overlapping detections keep the higher score, then the longer span."""
    chosen: list[_Span] = []
    for span in sorted(spans, key=lambda s: (-s.score, -(s.end - s.start), s.start)):
        if all(span.end <= c.start or span.start >= c.end for c in chosen):
            chosen.append(span)
    counts: Counter[str] = Counter()
    out = text
    for span in sorted(chosen, key=lambda s: s.start, reverse=True):
        out = out[: span.start] + f"[{span.label}]" + out[span.end :]
        counts[span.label] += 1
    return Masked(out, dict(counts))


def _build_engine() -> AnalyzerEngine:
    from presidio_analyzer import (  # noqa: PLC0415 - heavy import, loaded on first use
        AnalyzerEngine,
        Pattern,
        PatternRecognizer,
        RecognizerRegistry,
    )
    from presidio_analyzer.nlp_engine import NlpEngineProvider  # noqa: PLC0415
    from presidio_analyzer.predefined_recognizers import InAadhaarRecognizer  # noqa: PLC0415

    # Presidio warns once per call about spaCy labels it does not map (CARDINAL, DATE...);
    # we only ask for the DR-28 entities, so those warnings carry no information.
    logging.getLogger("presidio-analyzer").setLevel(logging.ERROR)
    nlp = NlpEngineProvider(
        nlp_configuration={
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
        }
    ).create_engine()
    registry = RecognizerRegistry(supported_languages=["en"])
    registry.load_predefined_recognizers(languages=["en"], nlp_engine=nlp)
    registry.add_recognizer(InAadhaarRecognizer())
    registry.add_recognizer(
        PatternRecognizer(
            supported_entity="ELUCIS_PHONE",
            patterns=[Pattern(f"phone_{i}", p, 0.7) for i, p in enumerate(_PHONE_PATTERNS)],
        )
    )
    registry.add_recognizer(
        PatternRecognizer(supported_entity="ELUCIS_PAN", patterns=[Pattern("pan", _PAN, 0.8)])
    )
    return AnalyzerEngine(nlp_engine=nlp, registry=registry, supported_languages=["en"])


_default = PiiMasker()


def mask(text: str) -> Masked:
    """Mask with the process-wide engine."""
    return _default.mask(text)
