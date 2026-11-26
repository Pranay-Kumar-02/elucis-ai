"""Jira integration (D07 §3.10). ``integration_configs`` lives in ``ingestion``, because
data sources reference it too."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Text, Uuid, text
from sqlalchemy.dialects.postgresql import BYTEA
from sqlalchemy.orm import Mapped, mapped_column

from elucis.db.base import Base
from elucis.db.models._common import (
    Json,
    StdColumns,
    Timestamp,
    check_in,
    std_args,
    tenant_fk,
    unique,
)


class IntegrationAction(StdColumns, Base):
    __tablename__ = "integration_actions"
    __table_args__ = std_args(
        "integration_actions",
        check_in("integration_actions", "action", "create_issue"),
        check_in(
            "integration_actions",
            "status",
            "previewed",
            "approved",
            "rejected",
            "sending",
            "created",
            "failed",
            "unknown",
        ),
        tenant_fk("integration_actions", "integration_config_id", "integration_configs"),
        tenant_fk("integration_actions", "approval_id", "approvals"),
        tenant_fk("integration_actions", "story_id", "user_stories"),
    )

    integration_config_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    approval_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    story_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    action: Mapped[str] = mapped_column(Text, server_default=text("'create_issue'"))
    payload: Mapped[dict[str, Any]] = mapped_column(Json)  # exact fields previewed
    payload_hash: Mapped[bytes] = mapped_column(BYTEA)
    status: Mapped[str] = mapped_column(Text, server_default=text("'previewed'"))
    external_key: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    attempted_at: Mapped[datetime | None] = mapped_column(Timestamp)


class ExternalItemLink(StdColumns, Base):
    """At most one Jira issue per story (AGR-23)."""

    __tablename__ = "external_item_links"
    __table_args__ = std_args(
        "external_item_links",
        unique(
            "external_item_links", "story_system", "workspace_id", "story_id", "external_system"
        ),
        unique("external_item_links", "config_key", "integration_config_id", "external_key"),
        check_in("external_item_links", "external_system", "jira"),
        tenant_fk("external_item_links", "story_id", "user_stories"),
        tenant_fk("external_item_links", "integration_config_id", "integration_configs"),
    )

    story_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    integration_config_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    external_system: Mapped[str] = mapped_column(Text)
    external_key: Mapped[str] = mapped_column(Text)
    external_url: Mapped[str] = mapped_column(Text)
