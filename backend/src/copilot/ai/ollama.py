"""Minimal, typed client for the local Ollama HTTP API.

This is the only module that talks to the model runtime (the "model gateway" boundary of
D04). It uses plain HTTP; no LLM framework is involved (ADR / B-04).

* ``chat_json`` sends a JSON Schema in ``format`` so Ollama constrains decoding to that
  schema (structured outputs), then validates the reply with Pydantic. A reply that still
  fails validation raises ``InvalidModelOutputError``; callers decide on repair or fallback.
* ``embed`` uses ``/api/embed`` (batch input) and checks the vector dimension.
* Connection failures and 5xx responses raise ``ModelUnavailableError`` (HTTP 503 upstream,
  AIR-22): the rest of the product keeps working when Ollama is down.
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from typing import Any, Self, TypeVar

import httpx2
from pydantic import BaseModel, ValidationError

from copilot.core.config import Settings, get_settings
from copilot.core.errors import ModelUnavailableError

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class InvalidModelOutputError(Exception):
    """The model replied, but not with output matching the requested schema."""


@dataclass(frozen=True, slots=True)
class CallStats:
    """Timings and token counts reported by Ollama (durations are in nanoseconds there)."""

    model: str
    prompt_tokens: int | None
    output_tokens: int | None
    load_ms: float | None
    prompt_eval_ms: float | None
    eval_ms: float | None
    total_ms: float | None

    @property
    def tokens_per_second(self) -> float | None:
        if self.output_tokens and self.eval_ms:
            return round(self.output_tokens / (self.eval_ms / 1000), 2)
        return None

    @classmethod
    def from_response(cls, body: dict[str, Any]) -> Self:
        def ms(key: str) -> float | None:
            value = body.get(key)
            return round(value / 1e6, 1) if isinstance(value, int | float) else None

        return cls(
            model=str(body.get("model", "")),
            prompt_tokens=body.get("prompt_eval_count"),
            output_tokens=body.get("eval_count"),
            load_ms=ms("load_duration"),
            prompt_eval_ms=ms("prompt_eval_duration"),
            eval_ms=ms("eval_duration"),
            total_ms=ms("total_duration"),
        )


@dataclass(frozen=True, slots=True)
class ChatResult:
    content: str
    stats: CallStats
    thinking: str | None = None


@dataclass(frozen=True, slots=True)
class EmbedResult:
    vectors: list[list[float]]
    stats: CallStats
    dimension: int = field(init=False)

    def __post_init__(self) -> None:
        dims = {len(v) for v in self.vectors}
        if len(dims) != 1:
            raise InvalidModelOutputError(f"inconsistent embedding dimensions: {sorted(dims)}")
        object.__setattr__(self, "dimension", dims.pop())


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


class OllamaClient:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        transport: httpx2.BaseTransport | None = None,
        timeout_s: float | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._http = httpx2.Client(
            base_url=self.settings.ollama_base_url,
            timeout=httpx2.Timeout(timeout_s or self.settings.ollama_timeout_s, connect=3.0),
            transport=transport,
            headers={"User-Agent": "copilot-backend"},
        )

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    # ------------------------------------------------------------------ transport
    def _request(self, method: str, path: str, json_body: dict[str, Any] | None = None) -> Any:
        try:
            response = self._http.request(method, path, json=json_body)
        except httpx2.TimeoutException as exc:
            raise ModelUnavailableError("The local model runtime timed out.") from exc
        except httpx2.TransportError as exc:
            raise ModelUnavailableError() from exc
        if response.status_code >= 500:
            raise ModelUnavailableError(f"The model runtime returned HTTP {response.status_code}.")
        if response.status_code == 404:
            detail = _error_text(response)
            raise ModelUnavailableError(f"Model or endpoint not found: {detail}")
        if response.status_code >= 400:
            raise InvalidModelOutputError(f"HTTP {response.status_code}: {_error_text(response)}")
        return response.json()

    # ------------------------------------------------------------------ metadata
    def version(self) -> str:
        return str(self._request("GET", "/api/version")["version"])

    def list_models(self) -> list[dict[str, Any]]:
        return list(self._request("GET", "/api/tags").get("models", []))

    def running_models(self) -> list[dict[str, Any]]:
        return list(self._request("GET", "/api/ps").get("models", []))

    def has_model(self, name: str) -> bool:
        wanted = name if ":" in name else f"{name}:latest"
        return any(m.get("name") == wanted or m.get("model") == wanted for m in self.list_models())

    # ------------------------------------------------------------------ inference
    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        format_schema: dict[str, Any] | None = None,
        think: bool = False,
        temperature: float = 0.0,
        seed: int | None = 42,
        num_predict: int | None = None,
        keep_alive: str | None = None,
    ) -> ChatResult:
        options: dict[str, Any] = {
            "temperature": temperature,
            "num_ctx": self.settings.ollama_num_ctx,
        }
        if seed is not None:
            options["seed"] = seed
        if num_predict is not None:
            options["num_predict"] = num_predict
        body: dict[str, Any] = {
            "model": model or self.settings.ollama_chat_model,
            "messages": messages,
            "stream": False,
            "think": think,
            "options": options,
        }
        if format_schema is not None:
            body["format"] = format_schema
        if keep_alive is not None:
            body["keep_alive"] = keep_alive
        reply = self._request("POST", "/api/chat", body)
        message = reply.get("message") or {}
        return ChatResult(
            content=str(message.get("content", "")),
            thinking=message.get("thinking"),
            stats=CallStats.from_response(reply),
        )

    def chat_json(
        self,
        messages: list[dict[str, str]],
        schema: type[T],
        *,
        model: str | None = None,
        **kwargs: Any,
    ) -> tuple[T, CallStats]:
        result = self.chat(
            messages, model=model, format_schema=schema.model_json_schema(), **kwargs
        )
        try:
            return schema.model_validate(json.loads(result.content)), result.stats
        except (json.JSONDecodeError, ValidationError) as exc:
            raise InvalidModelOutputError(f"reply does not match {schema.__name__}") from exc

    def embed(
        self,
        texts: list[str],
        *,
        model: str | None = None,
        expected_dimension: int | None = None,
        keep_alive: str | None = None,
    ) -> EmbedResult:
        if not texts:
            raise ValueError("texts must not be empty")
        body: dict[str, Any] = {"model": model or self.settings.ollama_embed_model, "input": texts}
        if keep_alive is not None:
            body["keep_alive"] = keep_alive
        reply = self._request("POST", "/api/embed", body)
        vectors = reply.get("embeddings") or []
        if len(vectors) != len(texts):
            raise InvalidModelOutputError(f"expected {len(texts)} embeddings, got {len(vectors)}")
        result = EmbedResult(vectors=vectors, stats=CallStats.from_response(reply))
        if expected_dimension is not None and result.dimension != expected_dimension:
            raise InvalidModelOutputError(
                f"embedding dimension {result.dimension} != expected {expected_dimension}"
            )
        return result


def _error_text(response: httpx2.Response) -> str:
    try:
        return str(response.json().get("error", ""))[:200]
    except (json.JSONDecodeError, AttributeError):
        return response.text[:200]
