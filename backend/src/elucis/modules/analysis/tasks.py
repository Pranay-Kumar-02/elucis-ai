"""One schema-checked model call with retries and a call record (D04 §4: the LLM gateway).

``run_task`` is the only way analysis steps call the chat model:

* the schema goes to Ollama as ``format`` and is validated again with Pydantic;
* ``check`` adds the call's own rules (every key exactly once, cited IDs among those
  supplied...); a broken rule counts as invalid output;
* invalid output is retried twice with the error fed back (A-15); then the call returns
  ``None`` and the caller uses its fallback;
* an unreachable runtime is retried twice with a short wait, then raised, so the step fails
  and the job retries later rather than marking records as failed;
* every attempt is written to ``llm_call_records`` with the prompt version (AIR-12).
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from elucis.ai.ollama import InvalidModelOutputError
from elucis.ai.prompts import PromptSpec
from elucis.core.errors import ModelUnavailableError
from elucis.db.models import PromptVersion
from elucis.modules.analysis.gateway import ModelGateway, log_call

logger = logging.getLogger(__name__)

INVALID_RETRIES = 2  # A-15
TRANSPORT_RETRIES = 2
TRANSPORT_WAIT_S = (2.0, 5.0)


class OutputRuleError(ValueError):
    """The reply matched the schema but broke one of the call's own rules."""


@dataclass(slots=True)
class TaskContext:
    db: Session
    gateway: ModelGateway
    workspace_id: uuid.UUID
    job_id: uuid.UUID | None
    model: str


def prompt_version_id(db: Session, spec: PromptSpec) -> uuid.UUID:
    """Register the prompt on first use (``prompt_versions`` is global, not per workspace).
    Looked up on every call: one indexed query, and never a stale ID from another database."""
    db.execute(
        pg_insert(PromptVersion)
        .values(
            call_id=spec.call_id,
            version=spec.version,
            content_hash=spec.content_hash,
            template=spec.system,
            output_schema=spec.schema.model_json_schema(),
        )
        .on_conflict_do_nothing(index_elements=["call_id", "version"])
    )
    row = db.execute(
        select(PromptVersion.id, PromptVersion.content_hash).where(
            PromptVersion.call_id == spec.call_id, PromptVersion.version == spec.version
        )
    ).one()
    if bytes(row.content_hash) != spec.content_hash:
        raise RuntimeError(
            f"{spec.call_id} {spec.version} changed without a new version number; bump it"
        )
    return uuid.UUID(str(row.id))


def run_task[T: BaseModel](
    tc: TaskContext,
    spec: PromptSpec,
    user_content: str,
    schema: type[T],
    check: Callable[[T], None] | None = None,
    *,
    sleep: Callable[[float], None] = time.sleep,
) -> T | None:
    version_id = prompt_version_id(tc.db, spec)
    messages = [
        {"role": "system", "content": spec.system},
        {"role": "user", "content": user_content},
    ]
    attempt, invalid, unavailable = 0, 0, 0
    while True:
        attempt += 1
        try:
            result, stats = tc.gateway.chat_json(
                messages,
                schema,
                model=tc.model,
                think=False,
                temperature=0.0,
                num_predict=spec.max_output_tokens,
            )
            if check is not None:
                check(result)
        except ModelUnavailableError:
            _log(tc, spec, version_id, user_content, "error", attempt)
            if unavailable >= TRANSPORT_RETRIES:
                raise
            sleep(TRANSPORT_WAIT_S[unavailable])
            unavailable += 1
            continue
        except (InvalidModelOutputError, OutputRuleError) as exc:
            _log(tc, spec, version_id, user_content, "invalid_output", attempt)
            if invalid >= INVALID_RETRIES:
                logger.warning(
                    "model output invalid after retries", extra={"call_id": spec.call_id}
                )
                return None
            invalid += 1
            messages = [
                *messages[:2],
                {
                    "role": "user",
                    "content": f"Your previous reply was not valid: {exc}. "
                    "Reply again with JSON that matches the schema and the rules.",
                },
            ]
            continue
        _log(tc, spec, version_id, user_content, "ok", attempt, stats)
        return result


def _log(  # noqa: PLR0917 - internal helper
    tc: TaskContext,
    spec: PromptSpec,
    version_id: uuid.UUID,
    content: str,
    outcome: str,
    attempt: int,
    stats: object = None,
) -> None:
    log_call(
        tc.db,
        workspace_id=tc.workspace_id,
        job_id=tc.job_id,
        call_id=spec.call_id,
        model=tc.model,
        inputs=[spec.system, content],
        outcome=outcome,
        attempt=attempt,
        stats=stats,  # type: ignore[arg-type]
        prompt_version_id=version_id,
    )
