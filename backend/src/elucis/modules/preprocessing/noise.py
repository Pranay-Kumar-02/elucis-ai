"""Noise rule (CR-02, D03 SVC-05, DR-12).

A record is noise if no alphabetic word remains, if the whole text is boilerplate, or if it
has fewer than 3 words and none of them is a signal term. "app crashes" is kept; "ok" and
"👍" are noise. The lexicons are small on purpose and tuned with data later (A-09).
"""

from __future__ import annotations

import re

_WORD = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)?", re.UNICODE)

BOILERPLATE = frozenset(
    {"test", "testing", "n/a", "na", "none", "ok", "okay", "k", "nil", "no comment", "nothing",
     "asdf", "hi", "hello", "thanks", "thank you", "good", "fine", "yes", "no"}
)  # fmt: skip

# Problem, product, feature and emotion words (D03 SVC-05). Matched on word stems.
SIGNAL_TERMS = (
    "crash", "freez", "hang", "slow", "lag", "bug", "error", "broke", "fail", "fix", "login",
    "log in", "sign", "password", "pay", "payment", "checkout", "refund", "charge", "price",
    "cost", "subscri", "account", "load", "sync", "export", "import", "search", "notif",
    "feature", "add", "option", "support", "update", "install", "battery", "ads",
    "love", "hate", "great", "awful", "terrible", "useless", "nice", "amazing", "bad",
    "worst", "best", "annoy", "confus", "hard", "easy", "wish", "please", "need", "want",
    "missing", "stuck", "spin", "work", "dark mode", "ui", "design", "app",
)  # fmt: skip


def words(text: str) -> list[str]:
    return _WORD.findall(text.casefold())


def is_noise(text: str) -> bool:
    found = words(text)
    if not found:
        return True  # no alphabetic word: emoji, punctuation, numbers only
    normalised = " ".join(found)
    if normalised in BOILERPLATE or text.strip().casefold() in BOILERPLATE:
        return True
    if len(found) >= 3:
        return False
    return not has_signal(found)


def has_signal(found: list[str]) -> bool:
    """Single-word terms match the start of a word ("crash" in "crashes"); multi-word terms
    match the phrase ("log in")."""
    phrase = " ".join(found)
    for term in SIGNAL_TERMS:
        if " " in term:
            if term in phrase:
                return True
        elif any(word.startswith(term) for word in found):
            return True
    return False
