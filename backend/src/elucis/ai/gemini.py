"""Minimal client for Google's Gemini API, used only as an optional backup for chat calls
(IMP-38). Plain ``httpx2``, no SDK, the same ``chat_json`` contract as ``OllamaClient``.

* ``POST /v1beta/models/{model}:generateContent`` with the key in the ``x-goog-api-key``
  header (never in the URL, so it cannot end up in logs or error messages);
* JSON output: ``generationConfig.responseMimeType = application/json`` and
  ``responseJsonSchema`` (the Pydantic schema with ``$ref`` inlined), then validated again
  with Pydantic, like every local call;
* network errors, timeouts, 429 and 5xx -> ``ModelUnavailableError``; other 4xx, a blocked
  prompt or an empty or cut-off reply -> ``InvalidModelOutputError``.

Callers send only masked text (DR-29): ``run_task`` builds every message from
``processed_text``. Whether to call Gemini at all is decided by the workspace switch.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Self

import httpx2
from pydantic import BaseModel, ValidationError

from elucis.ai.ollama import CallStats, InvalidModelOutputError
from elucis.core.config import Settings
from elucis.core.errors import ModelUnavailableError

logger = logging.getLogger(__name__)

BASE_URL = "https://generativelanguage.googleapis.com"
RETRYABLE = frozenset({429, 500, 502, 503, 504})


def inline_refs(schema: dict[str, Any]) -> dict[str, Any]:
    """Pydantic puts nested models in ``$defs`` and refers to them with ``$ref``; inline
    them so the schema is one self-contained object, and drop titles."""
    defs = schema.get("$defs", {})

    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                return walk(defs[node["$ref"].rsplit("/", 1)[-1]])
            return {k: walk(v) for k, v in node.items() if k not in {"$defs", "title"}}
        if isinstance(node, list):
            return [walk(v) for v in node]
        return node

    result: dict[str, Any] = walk(schema)
    return result


class GeminiClient:
    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx2.BaseTransport | None = None,
    ) -> None:
        if not settings.gemini_configured:
            raise ModelUnavailableError("GEMINI_API_KEY is not set.")
        assert settings.gemini_api_key is not None  # noqa: S101 - checked above
        self.model = settings.gemini_model
        self._http = httpx2.Client(
            base_url=BASE_URL,
            timeout=httpx2.Timeout(settings.gemini_timeout_s, connect=5.0),
            transport=transport,
            headers={
                "x-goog-api-key": settings.gemini_api_key.get_secret_value(),
                "Content-Type": "application/json",
                "User-Agent": "elucis-backend",
            },
        )

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    def chat_json[T: BaseModel](
        self,
        messages: list[dict[str, str]],
        schema: type[T],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        num_predict: int | None = None,
        **_ignored: Any,  # Ollama-only options such as ``think`` have no meaning here
    ) -> tuple[T, CallStats]:
        model = model or self.model
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        contents = [
            {
                "role": "model" if m["role"] == "assistant" else "user",
                "parts": [{"text": m["content"]}],
            }
            for m in messages
            if m["role"] != "system"
        ]
        config: dict[str, Any] = {
            "temperature": temperature,
            "responseMimeType": "application/json",
            "responseJsonSchema": inline_refs(schema.model_json_schema()),
        }
        if num_predict is not None:
            config["maxOutputTokens"] = num_predict
        body: dict[str, Any] = {"contents": contents, "generationConfig": config}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}

        started = time.perf_counter()
        try:
            response = self._http.post(f"/v1beta/models/{model}:generateContent", json=body)
        except httpx2.TimeoutException as exc:
            raise ModelUnavailableError("The Gemini API timed out.") from exc
        except httpx2.TransportError as exc:
            raise ModelUnavailableError("The Gemini API could not be reached.") from exc
        total_ms = round((time.perf_counter() - started) * 1000, 1)
        if response.status_code in RETRYABLE:
            raise ModelUnavailableError(f"The Gemini API returned HTTP {response.status_code}.")
        if response.status_code >= 400:
            raise InvalidModelOutputError(
                f"Gemini HTTP {response.status_code}: {_error_text(response)}"
            )
        reply = response.json()
        text = _reply_text(reply)
        usage = reply.get("usageMetadata") or {}
        stats = CallStats(
            model=f"gemini:{model}",
            prompt_tokens=usage.get("promptTokenCount"),
            output_tokens=usage.get("candidatesTokenCount"),
            load_ms=None,
            prompt_eval_ms=None,
            eval_ms=None,
            total_ms=total_ms,
        )
        try:
            return schema.model_validate(json.loads(text)), stats
        except (json.JSONDecodeError, ValidationError) as exc:
            raise InvalidModelOutputError(f"reply does not match {schema.__name__}") from exc


def _reply_text(reply: dict[str, Any]) -> str:
    blocked = (reply.get("promptFeedback") or {}).get("blockReason")
    if blocked:
        raise InvalidModelOutputError(f"Gemini blocked the prompt ({blocked})")
    candidates = reply.get("candidates") or []
    if not candidates:
        raise InvalidModelOutputError("Gemini returned no candidates")
    first = candidates[0]
    reason = first.get("finishReason")
    if reason not in {None, "STOP"}:
        raise InvalidModelOutputError(f"Gemini stopped early ({reason})")
    parts = (first.get("content") or {}).get("parts") or []
    text = "".join(str(p.get("text", "")) for p in parts)
    if not text.strip():
        raise InvalidModelOutputError("Gemini returned an empty reply")
    return text


def _error_text(response: httpx2.Response) -> str:
    try:
        return str((response.json().get("error") or {}).get("message", ""))[:200]
    except (json.JSONDecodeError, AttributeError):
        return response.text[:200]
