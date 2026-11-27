"""What every analysis step receives besides the job: the run, the model gateway, the chat
model and the workspace's product profile (context for CP-03 and CP-04)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from elucis.modules.analysis.gateway import ModelGateway


@dataclass(frozen=True, slots=True)
class RunContext:
    run_id: uuid.UUID
    gateway: ModelGateway
    chat_model: str
    product: str  # product name, description and users, or "" when not filled in
