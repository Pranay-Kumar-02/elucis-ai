"""Document generation (D07 §3.7): PRDs, stories, claims with evidence, approvals."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, Integer, Text, Uuid
from sqlalchemy import text as sql  # the claims table has a column named "text"
from sqlalchemy.dialects.postgresql import BYTEA
from sqlalchemy.orm import Mapped, mapped_column

from elucis.db.base import Base
from elucis.db.models._common import (
    EMPTY_ARRAY,
    NOW,
    Json,
    StdColumns,
    Timestamp,
    UuidArray,
    check,
    check_in,
    std_args,
    tenant_fk,
    unique,
    user_fk,
    workspace_fk,
)


class Document(StdColumns, Base):
    __tablename__ = "documents"
    __table_args__ = std_args(
        "documents",
        check_in("documents", "doc_type", "prd", "executive_summary"),
        check_in("documents", "status", "generating", "draft", "approved", "generation_failed"),
        tenant_fk("documents", "opportunity_id", "opportunities"),
        tenant_fk("documents", "job_id", "jobs"),
        user_fk("documents", "created_by"),
    )

    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)  # NULL for summaries
    doc_type: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default=sql("'generating'"))
    current_version: Mapped[int] = mapped_column(Integer, server_default=sql("0"))
    approved_version: Mapped[int | None] = mapped_column(Integer)
    job_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid)


class DocumentVersion(StdColumns, Base):
    __tablename__ = "document_versions"
    __table_args__ = std_args(
        "document_versions",
        unique("document_versions", "document_id_version", "document_id", "version"),
        tenant_fk("document_versions", "document_id", "documents", ondelete="CASCADE"),
        user_fk("document_versions", "created_by"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    version: Mapped[int] = mapped_column(Integer)
    content: Mapped[dict[str, Any]] = mapped_column(Json)
    evidence_pack: Mapped[dict[str, Any]] = mapped_column(Json)  # E-code -> record ID
    model_tags: Mapped[dict[str, Any]] = mapped_column(Json)
    prompt_versions: Mapped[dict[str, Any]] = mapped_column(Json)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)  # NULL = system
    change_note: Mapped[str | None] = mapped_column(Text)


class UserStory(StdColumns, Base):
    __tablename__ = "user_stories"
    __table_args__ = std_args(
        "user_stories",
        unique(
            "user_stories",
            "document_version_position",
            "document_id",
            "document_version",
            "position",
        ),
        check_in("user_stories", "status", "draft", "approved"),
        tenant_fk("user_stories", "document_id", "documents"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    document_version: Mapped[int] = mapped_column(Integer)
    position: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(Text)
    as_a: Mapped[str] = mapped_column(Text)
    i_want: Mapped[str] = mapped_column(Text)
    so_that: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default=sql("'draft'"))


class AcceptanceCriterion(StdColumns, Base):
    __tablename__ = "acceptance_criteria"
    __table_args__ = std_args(
        "acceptance_criteria",
        tenant_fk("acceptance_criteria", "story_id", "user_stories", ondelete="CASCADE"),
    )

    story_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    position: Mapped[int] = mapped_column(Integer)
    given_text: Mapped[str] = mapped_column(Text)
    when_text: Mapped[str] = mapped_column(Text)
    then_text: Mapped[str] = mapped_column(Text)


class Claim(StdColumns, Base):
    """One claim model for PRDs, chat answers and AI score rationales (D08 §8)."""

    __tablename__ = "claims"
    __table_args__ = std_args(
        "claims",
        check(
            "claims", "one_parent", "num_nonnulls(document_id, chat_message_id, score_input_id) = 1"
        ),
        check_in(
            "claims", "claim_type", "quantitative", "qualitative", "quotation", "recommendation"
        ),
        tenant_fk("claims", "document_id", "documents"),
        tenant_fk("claims", "chat_message_id", "chat_messages"),
        tenant_fk("claims", "score_input_id", "score_inputs"),
    )

    document_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    document_version: Mapped[int | None] = mapped_column(Integer)
    chat_message_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    score_input_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    section: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer)
    claim_type: Mapped[str] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)  # after placeholder resolution
    quote: Mapped[str | None] = mapped_column(Text)
    individual_report: Mapped[bool] = mapped_column(Boolean, server_default=sql("false"))


class ClaimEvidence(Base):
    __tablename__ = "claim_evidence"
    __table_args__ = (
        workspace_fk("claim_evidence"),
        tenant_fk("claim_evidence", "claim_id", "claims", ondelete="CASCADE"),
        tenant_fk("claim_evidence", "record_id", "feedback_records"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    claim_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    record_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)


class VerificationResult(StdColumns, Base):
    __tablename__ = "verification_results"
    __table_args__ = std_args(
        "verification_results",
        check_in(
            "verification_results",
            "check_kind",
            "evidence_ids",
            "quotation",
            "numbers",
            "customer_minimum",
            "support",
        ),
        check_in(
            "verification_results",
            "outcome",
            "pass",
            "fail",
            "supported",
            "partly",
            "unsupported",
            "not_checked",
        ),
        tenant_fk("verification_results", "claim_id", "claims", ondelete="CASCADE"),
        tenant_fk("verification_results", "llm_call_id", "llm_call_records", ondelete="SET NULL"),
    )

    claim_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    check_kind: Mapped[str] = mapped_column(Text)
    outcome: Mapped[str] = mapped_column(Text)
    detail: Mapped[str | None] = mapped_column(Text)
    llm_call_id: Mapped[int | None] = mapped_column(BigInteger)
    checked_at: Mapped[datetime] = mapped_column(Timestamp, server_default=NOW)


class Approval(StdColumns, Base):
    __tablename__ = "approvals"
    __table_args__ = std_args(
        "approvals",
        check_in("approvals", "subject_kind", "document", "jira_batch", "roadmap"),
        check_in("approvals", "decision", "approved", "rejected"),
        user_fk("approvals", "approved_by"),
    )

    subject_kind: Mapped[str] = mapped_column(Text)
    subject_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    subject_version: Mapped[int | None] = mapped_column(Integer)
    decision: Mapped[str] = mapped_column(Text)
    approved_by: Mapped[uuid.UUID] = mapped_column(Uuid)
    approved_at: Mapped[datetime] = mapped_column(Timestamp, server_default=NOW)
    payload_hash: Mapped[bytes | None] = mapped_column(BYTEA)  # exact content approved
    acknowledged_claim_ids: Mapped[list[uuid.UUID]] = mapped_column(
        UuidArray, server_default=EMPTY_ARRAY
    )
    note: Mapped[str | None] = mapped_column(Text)
