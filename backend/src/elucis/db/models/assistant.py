"""Conversational assistant (D07 §3.9)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, Integer, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from elucis.db.base import Base
from elucis.db.models._common import (
    EMPTY_ARRAY,
    NOW,
    Json,
    StdColumns,
    Timestamp,
    UuidArray,
    check_in,
    std_args,
    tenant_fk,
    user_fk,
)


class ChatSession(StdColumns, Base):
    __tablename__ = "chat_sessions"
    __table_args__ = std_args("chat_sessions", user_fk("chat_sessions", "user_id"))

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    title: Mapped[str | None] = mapped_column(Text)
    last_active_at: Mapped[datetime] = mapped_column(Timestamp, server_default=NOW)


class ChatMessage(StdColumns, Base):
    __tablename__ = "chat_messages"
    __table_args__ = std_args(
        "chat_messages",
        check_in("chat_messages", "role", "user", "assistant"),
        check_in("chat_messages", "status", "complete", "partial", "failed"),
        check_in("chat_messages", "feedback", "helpful", "incorrect"),
        tenant_fk("chat_messages", "session_id", "chat_sessions", ondelete="CASCADE"),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    role: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    insufficient: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    feedback: Mapped[str | None] = mapped_column(Text)  # FR-AST-10


class ToolCallRecord(StdColumns, Base):
    __tablename__ = "tool_call_records"
    __table_args__ = std_args(
        "tool_call_records",
        check_in(
            "tool_call_records",
            "outcome",
            "ok",
            "invalid_args",
            "error",
            "refused",
            "duplicate",
            "timeout",
        ),
        tenant_fk("tool_call_records", "message_id", "chat_messages", ondelete="CASCADE"),
    )

    message_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    tool_name: Mapped[str] = mapped_column(Text)
    arguments: Mapped[dict[str, Any]] = mapped_column(Json)
    outcome: Mapped[str] = mapped_column(Text)
    result_summary: Mapped[dict[str, Any] | None] = mapped_column(Json)
    evidence_ids: Mapped[list[uuid.UUID]] = mapped_column(UuidArray, server_default=EMPTY_ARRAY)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
