"""Accuracy metrics for the evaluation report (AIR-20, NFR-28 to NFR-30; milestone 2 step 8).

Plain functions on plain values, tested on hand-computable cases in ``tests/test_metrics.py``:

* ``binary_scores``: precision, recall and F1 for one yes/no decision (issue detection,
  feature-request detection);
* ``pairwise_scores``: pairwise precision, recall and F1 for a grouping (two records in the
  same predicted group count as a "same" decision);
* ``purity``: share of records whose predicted group's majority label matches theirs;
* ``cohen_kappa``: agreement between two labellers, beyond chance.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Hashable, Mapping, Sequence
from dataclasses import dataclass
from itertools import combinations


@dataclass(frozen=True, slots=True)
class Scores:
    tp: int
    fp: int
    fn: int
    tn: int

    @property
    def n(self) -> int:
        return self.tp + self.fp + self.fn + self.tn

    @property
    def precision(self) -> float | None:
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else None

    @property
    def recall(self) -> float | None:
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else None

    @property
    def f1(self) -> float | None:
        p, r = self.precision, self.recall
        if p is None or r is None or p + r == 0:
            return None
        return 2 * p * r / (p + r)


def binary_scores(pairs: Sequence[tuple[bool, bool]]) -> Scores:
    """``pairs`` = [(truth, prediction)]."""
    tp = sum(1 for t, p in pairs if t and p)
    fp = sum(1 for t, p in pairs if not t and p)
    fn = sum(1 for t, p in pairs if t and not p)
    tn = sum(1 for t, p in pairs if not t and not p)
    return Scores(tp, fp, fn, tn)


def pairwise_scores(
    truth: Mapping[Hashable, Hashable], predicted: Mapping[Hashable, Hashable]
) -> Scores:
    """Over records present in both mappings: a pair is positive when both records share a
    group. TP = same truth and same prediction; FP = same prediction only; FN = same truth
    only; TN = different in both."""
    items = sorted((k for k in truth if k in predicted), key=str)
    pairs = [
        (truth[a] == truth[b], predicted[a] == predicted[b]) for a, b in combinations(items, 2)
    ]
    return binary_scores(pairs)


def purity(
    truth: Mapping[Hashable, Hashable], predicted: Mapping[Hashable, Hashable]
) -> float | None:
    items = [k for k in truth if k in predicted]
    if not items:
        return None
    by_group: dict[Hashable, Counter[Hashable]] = {}
    for k in items:
        by_group.setdefault(predicted[k], Counter())[truth[k]] += 1
    return sum(c.most_common(1)[0][1] for c in by_group.values()) / len(items)


def cohen_kappa(a: Sequence[Hashable], b: Sequence[Hashable]) -> float | None:
    if len(a) != len(b) or not a:
        return None
    n = len(a)
    observed = sum(1 for x, y in zip(a, b, strict=True) if x == y) / n
    ca, cb = Counter(a), Counter(b)
    expected = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return 1.0 if expected == 1 else (observed - expected) / (1 - expected)
