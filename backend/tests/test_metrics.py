"""Evaluation metrics on cases small enough to check by hand."""

from __future__ import annotations

import pytest

from elucis.modules.evaluation.metrics import (
    binary_scores,
    cohen_kappa,
    pairwise_scores,
    purity,
)


def test_binary_scores() -> None:
    # truth, prediction: 2 TP, 1 FP, 1 FN, 1 TN
    s = binary_scores([(True, True), (True, True), (False, True), (True, False), (False, False)])
    assert (s.tp, s.fp, s.fn, s.tn, s.n) == (2, 1, 1, 1, 5)
    assert s.precision == pytest.approx(2 / 3)
    assert s.recall == pytest.approx(2 / 3)
    assert s.f1 == pytest.approx(2 / 3)


def test_scores_without_positives_are_undefined_not_zero() -> None:
    s = binary_scores([(False, False), (False, False)])
    assert s.precision is None and s.recall is None and s.f1 is None


def test_pairwise_scores_and_purity() -> None:
    truth = {"a": "dark", "b": "dark", "c": "dark", "d": "export"}
    predicted = {"a": 1, "b": 1, "c": 2, "d": 2, "z": 9}  # "z" has no label: ignored
    # Pairs: ab same/same TP; ac same/diff FN; ad diff/diff TN; bc same/diff FN; bd diff/diff TN;
    # cd diff/same FP.
    s = pairwise_scores(truth, predicted)
    assert (s.tp, s.fp, s.fn, s.tn) == (1, 1, 2, 2)
    assert s.precision == pytest.approx(0.5)
    assert s.recall == pytest.approx(1 / 3)
    assert purity(truth, predicted) == pytest.approx(3 / 4)  # group 1: 2 of 2; group 2: 1 of 2


def test_cohen_kappa() -> None:
    assert cohen_kappa(["y", "n", "y", "n"], ["y", "n", "y", "n"]) == pytest.approx(1.0)
    # observed 0.5, expected 0.5 -> 0
    assert cohen_kappa(["y", "y", "n", "n"], ["y", "n", "y", "n"]) == pytest.approx(0.0)
    assert cohen_kappa([], []) is None
