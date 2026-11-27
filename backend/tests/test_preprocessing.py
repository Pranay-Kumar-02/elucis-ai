"""Preprocessing stages (SVC-05 to SVC-07): cleaning, noise, standardisation, PII masking
and exact-duplicate keys. Unit tests; the PII tests load the real Presidio + spaCy engine.

The sentences below are test inputs written for these checks (TST-14 seeded PII set), not
customer data. The card numbers are standard test numbers; the Aadhaar number is a
published checksum-valid sample.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from elucis.modules.preprocessing import duplicates
from elucis.modules.preprocessing.clean import clean_text
from elucis.modules.preprocessing.noise import is_noise
from elucis.modules.preprocessing.pii import PiiMasker
from elucis.modules.preprocessing.standardise import (
    customer_key,
    detect_scale,
    product_version,
    rating_1_to_5,
)


# ---------------------------------------------------------------- cleaning: DR-11, DR-19
def test_cleaning_removes_markup_replies_signatures_and_control_characters() -> None:
    raw = (
        "<p>Checkout&nbsp;spins   forever</p><br>after I tap <b>Pay</b>\u200b\n"
        "> previous message quoted\n"
        "Thanks\n"
        "-- \n"
        "Riya, Head of Ops\n"
    )
    assert clean_text(raw) == "Checkout spins forever\n\nafter I tap Pay\nThanks"


def test_cleaning_cuts_the_quoted_reply_chain_and_normalises_unicode() -> None:
    raw = "Cafe\u0301 menu is slow\n\nOn Mon, 3 Oct 2026, Support <help@x.com> wrote:\nHello"
    assert clean_text(raw) == "Caf\u00e9 menu is slow"
    assert clean_text("Sent from my iPhone") == ""


# ---------------------------------------------------------------- noise (CR-02)
@pytest.mark.parametrize(
    ("text", "noise"),
    [
        ("app crashes", False),  # signal term kept (CR-02 example)
        ("login broken", False),
        ("nice", False),  # praise, low weight but kept
        ("ok", True),
        ("👍", True),
        ("N/A", True),
        ("12345", True),
        ("blue sky", True),  # two words, no signal term
        ("the colour scheme feels dated", False),  # three or more words
    ],
)
def test_noise_rule(text: str, noise: bool) -> None:
    assert is_noise(text) is noise


# ---------------------------------------------------------------- standardisation
def test_rating_scale_detection_and_mapping_to_five() -> None:
    assert detect_scale([1, 4, 5]) == 5
    assert detect_scale([2, 9]) == 10
    assert detect_scale([40, 80]) == 100
    assert detect_scale([]) is None
    assert rating_1_to_5(4, None, 5) == 4
    assert rating_1_to_5(8, None, 10) == 4
    assert rating_1_to_5(80, 100, None) == 4  # "80%"
    assert rating_1_to_5(3, 5, 100) == 3  # an explicit scale wins
    assert rating_1_to_5(0, None, 10) == 1  # clamped to the 1-5 range
    assert rating_1_to_5(7, None, 5) is None  # outside the scale: flagged, never guessed
    assert rating_1_to_5(None, None, 5) is None


def test_version_extraction() -> None:
    assert product_version("v3.2.1 (build 77)") == "3.2.1"
    assert product_version("Android 14") == "14"
    assert product_version("beta") is None


def test_customer_key_is_a_keyed_hash_of_the_normalised_identifier() -> None:
    secret = b"k" * 32
    key = customer_key(secret, "  Riya@Example.com ")
    assert key == customer_key(secret, "riya@example.com")
    assert key != customer_key(b"o" * 32, "riya@example.com")  # per-workspace secret
    assert key is not None and b"riya" not in key
    assert customer_key(secret, None) is None
    assert customer_key(secret, "   ") is None


# ---------------------------------------------------------------- exact duplicates (CR-16)
def _cand(
    text: str, customer: uuid.UUID | None, when: datetime | None, imp: uuid.UUID
) -> duplicates.Candidate:
    return duplicates.Candidate(
        uuid.uuid4(), duplicates.content_hash(text), customer, "review", when, imp
    )


def test_duplicate_key_ignores_case_punctuation_and_spacing() -> None:
    assert duplicates.content_hash("App CRASHES on login!!") == duplicates.content_hash(
        "app crashes   on login"
    )
    assert duplicates.content_hash("app crashes") != duplicates.content_hash("app crashed")


def test_duplicates_are_scoped_to_the_same_customer() -> None:
    imp = uuid.uuid4()
    a, b = uuid.uuid4(), uuid.uuid4()
    day = datetime(2026, 10, 2, tzinfo=UTC)
    first = _cand("Checkout fails", a, day, imp)
    assert duplicates.is_duplicate_of(_cand("checkout fails!", a, day, imp), first)
    # Different customers saying the same thing is corroboration, not duplication.
    assert not duplicates.is_duplicate_of(_cand("Checkout fails", b, day, imp), first)
    # Unknown identity: same source within 24 hours only.
    unknown = _cand("Checkout fails", None, day, imp)
    assert duplicates.is_duplicate_of(
        _cand("Checkout fails", None, day + timedelta(hours=23), uuid.uuid4()), unknown
    )
    assert not duplicates.is_duplicate_of(
        _cand("Checkout fails", None, day + timedelta(hours=25), imp), unknown
    )
    assert not duplicates.is_duplicate_of(_cand("Checkout fails", a, day, imp), unknown)


# ---------------------------------------------------------------- PII: DR-28, DR-29, TST-14
SEEDED_PII = [
    ("My name is Riya Sharma and the app keeps crashing", ["NAME"]),
    ("Email me at riya.sharma@example.com when it is fixed", ["EMAIL"]),
    ("Call me on +91 98765 43210 about the refund", ["PHONE"]),
    ("my number is 9876543210", ["PHONE"]),
    ("US office (415) 555-0132 never answers", ["PHONE"]),
    ("Charged twice on card 4111 1111 1111 1111", ["CARD"]),
    ("PAN ABCPE1234F was rejected at KYC", ["ID"]),
    ("Aadhaar 4991 1866 5246 verification fails", ["ID"]),
    ("Thanks Priya, the export is still slow", ["NAME"]),
    ("John from support was rude to me", ["NAME"]),
]
CLEAN = [
    "Checkout spins forever after I tap Pay in version 3.2.1",
    "Order 4111 was delayed by 3 days",  # not a card number (fails the Luhn check)
    "Dark mode would be great, thanks team",
]


@pytest.fixture(scope="module")
def masker() -> PiiMasker:
    return PiiMasker()


def test_seeded_pii_is_masked_with_typed_placeholders(masker: PiiMasker) -> None:
    found = 0
    expected = 0
    misses = []
    for text, labels in SEEDED_PII:
        result = masker.mask(text)
        expected += len(labels)
        hit = sum(1 for label in labels if f"[{label}]" in result.text)
        found += hit
        if hit < len(labels):
            misses.append((text, result.text))
    recall = found / expected
    print(f"PII recall on the seeded set: {found}/{expected} = {recall:.2f}")  # noqa: T201
    assert misses == []
    assert recall == 1.0


def test_masking_leaves_ordinary_feedback_alone(masker: PiiMasker) -> None:
    for text in CLEAN:
        result = masker.mask(text)
        assert result.text == text, result.text
        assert result.counts == {}


def test_masking_counts_each_type(masker: PiiMasker) -> None:
    result = masker.mask("Riya Sharma here, riya@example.com or riya2@example.com")
    assert result.counts["EMAIL"] == 2
    assert "riya@example.com" not in result.text
