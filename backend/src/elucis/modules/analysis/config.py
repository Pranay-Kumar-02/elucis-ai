"""The configuration snapshot stored with every run (D07 ``analysis_runs.config``, DR-34)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from elucis.core.config import Settings
from elucis.db.models._common import CURRENT_EMBEDDING_MODEL, EMBEDDING_DIMENSION

EMBED_BATCH_SIZE = 64  # D03 SVC-08 (tuned in EXP-04)
EMBED_RETRIES = 2  # DR-38


def run_config(settings: Settings, *, backup: bool = False) -> dict[str, Any]:
    return {
        "embedding_model": CURRENT_EMBEDDING_MODEL,
        "embedding_dimension": EMBEDDING_DIMENSION,
        "embed_batch_size": EMBED_BATCH_SIZE,
        "chat_model": settings.ollama_chat_model,
        # Optional backup for chat calls (IMP-38), as it was when the run started.
        "fallback": f"gemini:{settings.gemini_model}"
        if backup and settings.gemini_configured
        else None,
    }


def config_hash(config: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
