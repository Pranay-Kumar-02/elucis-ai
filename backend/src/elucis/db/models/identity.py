"""Identity and workspaces (D07 §3.1). Global tables: no row-level security (D07 §5)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, ForeignKeyConstraint, Identity, Index, Text, Uuid, text
from sqlalchemy.dialects.postgresql import BYTEA, INET
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.elements import conv

from elucis.db.base import Base
from elucis.db.models._common import (
    EMPTY_OBJECT,
    NOW,
    Json,
    Timestamp,
    check,
    check_in,
    unique,
    user_fk,
    workspace_fk,
)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (Index("uq_users_email_lower", text("lower(email)"), unique=True),)

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    email: Mapped[str] = mapped_column(Text)
    password_hash: Mapped[str] = mapped_column(Text)  # Argon2id encoded hash
    display_name: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(Timestamp, server_default=NOW)
    last_login_at: Mapped[datetime | None] = mapped_column(Timestamp)


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        unique("sessions", "token_hash", "token_hash"),
        user_fk("sessions", "user_id", ondelete="CASCADE"),
        Index("ix_sessions_user_id", "user_id"),
        Index("ix_sessions_expires_at", "expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    token_hash: Mapped[bytes] = mapped_column(BYTEA)  # SHA-256 of the cookie token
    csrf_token_hash: Mapped[bytes] = mapped_column(BYTEA)
    created_at: Mapped[datetime] = mapped_column(Timestamp, server_default=NOW)
    last_seen_at: Mapped[datetime] = mapped_column(Timestamp, server_default=NOW)
    expires_at: Mapped[datetime] = mapped_column(Timestamp)
    ip: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(Text)


class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    __table_args__ = (
        Index(
            "ix_login_attempts_email_lower_attempted_at",
            "email_lower",
            text("attempted_at DESC"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    email_lower: Mapped[str] = mapped_column(Text)
    ip: Mapped[str | None] = mapped_column(INET)
    succeeded: Mapped[bool] = mapped_column(Boolean)
    attempted_at: Mapped[datetime] = mapped_column(Timestamp, server_default=NOW)


class Workspace(Base):
    __tablename__ = "workspaces"
    __table_args__ = (
        check("workspaces", "name_length", "char_length(name) BETWEEN 1 AND 120"),
        user_fk("workspaces", "created_by"),
        ForeignKeyConstraint(
            ["id", "current_analysis_run_id"],
            ["analysis_runs.workspace_id", "analysis_runs.id"],
            ondelete="SET NULL (current_analysis_run_id)",
            deferrable=True,
            initially="DEFERRED",
            name=conv("fk_workspaces_current_analysis_run_id"),
            use_alter=True,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    product_name: Mapped[str | None] = mapped_column(Text)
    product_description: Mapped[str | None] = mapped_column(Text)
    target_users: Mapped[str | None] = mapped_column(Text)
    glossary: Mapped[dict[str, Any]] = mapped_column(Json, server_default=EMPTY_OBJECT)
    customer_key_secret: Mapped[bytes] = mapped_column(BYTEA)  # encrypted with the app key
    current_analysis_run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    # Optional Gemini backup for chat calls, off by default (migration 0004, IMP-38).
    gemini_fallback: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(Timestamp, server_default=NOW)


class WorkspaceMembership(Base):
    __tablename__ = "workspace_memberships"
    __table_args__ = (
        check_in("workspace_memberships", "role", "owner", "editor", "viewer"),
        workspace_fk("workspace_memberships"),
        user_fk("workspace_memberships", "user_id", ondelete="CASCADE"),
        user_fk("workspace_memberships", "added_by"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    role: Mapped[str] = mapped_column(Text, server_default=text("'viewer'"))
    added_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(Timestamp, server_default=NOW)
