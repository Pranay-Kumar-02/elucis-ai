"""The model gateway seam for analysis steps, plus the ``llm_call_records`` writer (AIR-12).

Steps depend on the small ``ModelGateway`` protocol, not on Ollama directly, so tests can
supply a deterministic fake and the worker supplies ``OllamaClient``. Prompt and response
text are never stored; only the hash of the input, the model, timings and the outcome.
"""

from __future__ import annotations

import hashlib
import uuid
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel
from sqlalchemy import insert
from sqlalchemy.orm import Session

from elucis.ai.ollama import CallStats, EmbedResult
from elucis.db.models import LlmCallRecord

T = TypeVar("T", bound=BaseModel)


class ChatGateway(Protocol):
    """What a chat backend offers: the local model, or the optional backup (IMP-38)."""

    def chat_json(
        self,
        messages: list[dict[str, str]],
        schema: type[T],
        *,
        model: str | None = None,
        **kwargs: Any,
    ) -> tuple[T, CallStats]: ...

    def close(self) -> None: ...


class ModelGateway(ChatGateway, Protocol):
    """The local runtime: chat and embeddings (embeddings never leave the machine)."""

    def embed(
        self,
        texts: list[str],
        *,
        model: str | None = None,
        expected_dimension: int | None = None,
        keep_alive: str | None = None,
    ) -> EmbedResult: ...


def input_hash(parts: list[str]) -> bytes:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(part.encode("utf-8"))
        digest.update(b"\x1e")
    return digest.digest()


def _ms(value: float | None) -> int | None:
    return round(value) if value is not None else None


def log_call(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    job_id: uuid.UUID | None,
    call_id: str,
    model: str,
    inputs: list[str],
    outcome: str,
    attempt: int = 1,
    stats: CallStats | None = None,
    prompt_version_id: uuid.UUID | None = None,
    provider: str = "ollama",
) -> None:
    db.execute(
        insert(LlmCallRecord)
        .inline()
        .values(
            workspace_id=workspace_id,
            call_id=call_id,
            model_tag=model,
            prompt_version_id=prompt_version_id,
            input_hash=input_hash(inputs),
            prompt_tokens=stats.prompt_tokens if stats else None,
            output_tokens=stats.output_tokens if stats else None,
            prompt_eval_ms=_ms(stats.prompt_eval_ms) if stats else None,
            eval_ms=_ms(stats.eval_ms) if stats else None,
            total_ms=_ms(stats.total_ms) if stats else None,
            attempt=attempt,
            outcome=outcome,
            provider=provider,
            job_id=job_id,
        )
    )
