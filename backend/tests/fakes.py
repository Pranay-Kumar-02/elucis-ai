"""A deterministic stand-in for the model gateway, so analysis tests need no GPU.

Embeddings: texts that mention one of a few topic words get a vector near that topic's
direction (plus small text-specific noise); other texts get a hash-based vector. Chat:
answers CP-02, CP-03 and CP-04 by simple keyword rules. None of this is product logic; it
only gives the pipeline predictable inputs. The real models are exercised by the tests
marked ``ollama``.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

import numpy as np
from pydantic import BaseModel

from elucis.ai.ollama import CallStats, EmbedResult, InvalidModelOutputError
from elucis.ai.prompts import Cp02Out, Cp03Out, Cp04Out
from elucis.core.errors import ModelUnavailableError

STATS = CallStats("fake", 3, 4, None, 1.0, 2.0, 3.0)
TOPICS = ("checkout", "export", "dark mode", "login")
DIM = 1024
_TAG = re.compile(r'<customer_feedback id="([^"]+)">(.*?)</customer_feedback>', re.S)


def _seed(text: str) -> np.random.Generator:
    return np.random.default_rng(int.from_bytes(hashlib.sha256(text.encode()).digest()[:8], "big"))


def fake_vector(text: str) -> list[float]:
    """Not normalised on purpose: the pipeline must normalise."""
    lowered = text.lower()
    topic = next((t for t in TOPICS if t in lowered), None)
    if topic is None:
        return list(_seed(text).normal(0, 1, DIM) * 3)
    base = _seed("topic:" + topic).normal(0, 1, DIM)
    return list((base + _seed(text).normal(0, 0.15, DIM)) * 3)


def records_in(content: str) -> list[tuple[str, str]]:
    return _TAG.findall(content)


def label(text: str) -> tuple[str, str]:
    t = text.lower()
    if "please add" in t or "would love" in t or "i wish" in t:
        return "feature_request", "neutral"
    if "slow" in t:
        return "performance_issue", "negative"
    if "love" in t or "great" in t:
        return "praise", "positive"
    return "bug_report", "negative"


class FakeGateway:
    """``bad``: texts whose embedding fails; ``down``: every call fails as unreachable;
    ``bad_cp02_batches``: CP-02 replies to multi-record batches with wrong keys;
    ``bad_cp03``: CP-03 always cites an unknown ID."""

    def __init__(
        self,
        bad: frozenset[str] = frozenset(),
        *,
        down: bool = False,
        bad_cp02_batches: bool = False,
        bad_cp03: bool = False,
    ) -> None:
        self.bad, self.down = bad, down
        self.bad_cp02_batches, self.bad_cp03 = bad_cp02_batches, bad_cp03
        self.calls = 0  # embedding calls
        self.chat_calls: list[str] = []  # schema names, in order

    def embed(self, texts: list[str], **_: Any) -> EmbedResult:
        self.calls += 1
        if self.down:
            raise ModelUnavailableError()
        if any(t in self.bad for t in texts):
            raise InvalidModelOutputError("bad input")
        return EmbedResult(vectors=[fake_vector(t) for t in texts], stats=STATS)

    def chat_json(
        self, messages: list[dict[str, str]], schema: type[BaseModel], **_: Any
    ) -> tuple[BaseModel, CallStats]:
        self.chat_calls.append(schema.__name__)
        if self.down:
            raise ModelUnavailableError()
        found = records_in(messages[1]["content"])
        if schema is Cp02Out:
            if self.bad_cp02_batches and len(found) > 1:
                return Cp02Out(items=[]), STATS  # misses every key
            items = [
                {"key": k, "category": label(t)[0], "sentiment": label(t)[1]} for k, t in found
            ]
            return Cp02Out.model_validate({"items": items}), STATS
        if schema is Cp03Out:
            record_text = " ".join(t for _, t in found).lower()
            topic = next((w for w in TOPICS if w in record_text), "general")
            cited = ["E99"] if self.bad_cp03 else [k for k, _ in found[:2]]
            out = {
                "name": f"Problems with {topic}",
                "description": f"Customers report problems with {topic}.",
                "cited_ids": cited,
            }
            return Cp03Out.model_validate(out), STATS
        if schema is Cp04Out:
            items = [{"key": k, "ask": _ask(t)} for k, t in found]
            return Cp04Out.model_validate({"items": items}), STATS
        raise AssertionError(f"unexpected schema {schema.__name__}")

    def close(self) -> None:
        pass


def _ask(text: str) -> str:
    t = text.lower()
    if "dark mode" in t:
        return "Add a dark mode"
    if "export" in t:
        return "Export reports to Excel"
    return "Improve the app"
