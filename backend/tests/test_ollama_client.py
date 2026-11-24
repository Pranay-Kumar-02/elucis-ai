"""Model gateway client against a mocked Ollama HTTP API (no network)."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx2
import pytest
from pydantic import BaseModel

from copilot.ai.ollama import InvalidModelOutputError, OllamaClient, cosine
from copilot.core.errors import ModelUnavailableError
from tests.conftest import make_settings

Handler = Callable[[httpx2.Request], httpx2.Response]


class Label(BaseModel):
    category: str
    score: int


def _client(handler: Handler) -> OllamaClient:
    return OllamaClient(
        make_settings(ollama_base_url="http://ollama.test"), transport=httpx2.MockTransport(handler)
    )


def _chat_reply(content: str) -> dict[str, Any]:
    return {
        "model": "qwen3:4b",
        "message": {"role": "assistant", "content": content},
        "prompt_eval_count": 20,
        "eval_count": 10,
        "eval_duration": 500_000_000,
        "total_duration": 900_000_000,
        "load_duration": 100_000_000,
    }


def test_version_and_model_listing() -> None:
    def handler(req: httpx2.Request) -> httpx2.Response:
        if req.url.path == "/api/version":
            return httpx2.Response(200, json={"version": "0.30.0"})
        return httpx2.Response(
            200, json={"models": [{"name": "qwen3:4b"}, {"name": "qwen3-embedding:0.6b"}]}
        )

    with _client(handler) as c:
        assert c.version() == "0.30.0"
        assert c.has_model("qwen3:4b")
        assert not c.has_model("qwen3:8b")


def test_chat_json_sends_schema_disables_thinking_and_validates() -> None:
    seen: dict[str, Any] = {}

    def handler(req: httpx2.Request) -> httpx2.Response:
        seen.update(json.loads(req.content))
        return httpx2.Response(200, json=_chat_reply('{"category": "bug_report", "score": 3}'))

    with _client(handler) as c:
        label, stats = c.chat_json([{"role": "user", "content": "x"}], Label)
    assert label == Label(category="bug_report", score=3)
    assert seen["format"]["properties"]["score"]["type"] == "integer"
    assert seen["think"] is False
    assert seen["stream"] is False
    assert seen["options"]["temperature"] == 0.0
    assert seen["options"]["num_ctx"] == 4096
    assert stats.tokens_per_second == 20.0
    assert stats.total_ms == 900.0


@pytest.mark.parametrize("content", ["not json", '{"category": "x"}'])
def test_chat_json_invalid_output_raises(content: str) -> None:
    with (
        _client(lambda _: httpx2.Response(200, json=_chat_reply(content))) as c,
        pytest.raises(InvalidModelOutputError),
    ):
        c.chat_json([{"role": "user", "content": "x"}], Label)


def test_embed_measures_dimension_and_checks_expected() -> None:
    def handler(req: httpx2.Request) -> httpx2.Response:
        n = len(json.loads(req.content)["input"])
        return httpx2.Response(200, json={"model": "e", "embeddings": [[0.1] * 1024] * n})

    with _client(handler) as c:
        result = c.embed(["a", "b"], expected_dimension=1024)
        assert result.dimension == 1024
        assert len(result.vectors) == 2
        with pytest.raises(InvalidModelOutputError, match="1024 != expected 768"):
            c.embed(["a"], expected_dimension=768)


def test_embed_count_mismatch_raises() -> None:
    with (
        _client(lambda _: httpx2.Response(200, json={"embeddings": [[1.0]]})) as c,
        pytest.raises(InvalidModelOutputError),
    ):
        c.embed(["a", "b"])


def test_connection_refused_is_model_unavailable() -> None:
    def handler(req: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("refused", request=req)

    with _client(handler) as c, pytest.raises(ModelUnavailableError):
        c.version()


def test_missing_model_404_is_model_unavailable() -> None:
    with (
        _client(lambda _: httpx2.Response(404, json={"error": "model 'qwen3:4b' not found"})) as c,
        pytest.raises(ModelUnavailableError, match="not found"),
    ):
        c.chat([{"role": "user", "content": "x"}])


def test_server_error_is_model_unavailable() -> None:
    with (
        _client(lambda _: httpx2.Response(500, text="boom")) as c,
        pytest.raises(ModelUnavailableError),
    ):
        c.embed(["x"])


def test_cosine() -> None:
    assert cosine([1, 0], [1, 0]) == pytest.approx(1.0)
    assert cosine([1, 0], [0, 1]) == pytest.approx(0.0)
    assert cosine([0, 0], [1, 1]) == 0.0
