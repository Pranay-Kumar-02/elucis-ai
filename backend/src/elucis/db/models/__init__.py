"""ORM models for the 54 D07 tables, registered on ``elucis.db.base.Base.metadata``.

Migration 0002 is the source of the schema; these models mirror it exactly (columns,
keys, constraints and indexes), which ``tests/test_schema_drift.py`` verifies against the
live database. Row-level security, grants and the ``raw_text`` trigger live only in the
migration.
"""

from elucis.db.models.analysis import (
    AggregatedRequest,
    AnalysisRun,
    LlmCallRecord,
    PromptVersion,
    RecordClassification,
    RecordEmbedding,
    RequestMembership,
    ReviewItem,
    Theme,
    ThemeMembership,
    ThemeOverride,
    ThemeRunStats,
)
from elucis.db.models.analytics import (
    MetricDefinition,
    MetricObservation,
    ProductRelease,
    ThemeMetricLink,
)
from elucis.db.models.assistant import ChatMessage, ChatSession, ToolCallRecord
from elucis.db.models.documents import (
    AcceptanceCriterion,
    Approval,
    Claim,
    ClaimEvidence,
    Document,
    DocumentVersion,
    UserStory,
    VerificationResult,
)
from elucis.db.models.feedback import Customer, FeedbackRecord
from elucis.db.models.identity import (
    LoginAttempt,
    Session,
    User,
    Workspace,
    WorkspaceMembership,
)
from elucis.db.models.ingestion import (
    ColumnMapping,
    DataSource,
    ImportJob,
    ImportRowError,
    IntegrationConfig,
    Job,
    SourceFile,
)
from elucis.db.models.integrations import ExternalItemLink, IntegrationAction
from elucis.db.models.operations import (
    AuditLog,
    EvaluationDataset,
    EvaluationItem,
    EvaluationRun,
)
from elucis.db.models.prioritisation import (
    Opportunity,
    ScoreInput,
    ScoreSnapshot,
    ScoringConfig,
)
from elucis.db.models.roadmaps import Roadmap, RoadmapDependency, RoadmapItem

# Tables without row-level security (D07 §5): identity and global registries.
UNSCOPED_TABLES = frozenset(
    {
        "users",
        "sessions",
        "login_attempts",
        "prompt_versions",
        "workspaces",
        "workspace_memberships",
    }
)

__all__ = [
    "UNSCOPED_TABLES",
    "AcceptanceCriterion",
    "AggregatedRequest",
    "AnalysisRun",
    "Approval",
    "AuditLog",
    "ChatMessage",
    "ChatSession",
    "Claim",
    "ClaimEvidence",
    "ColumnMapping",
    "Customer",
    "DataSource",
    "Document",
    "DocumentVersion",
    "EvaluationDataset",
    "EvaluationItem",
    "EvaluationRun",
    "ExternalItemLink",
    "FeedbackRecord",
    "ImportJob",
    "ImportRowError",
    "IntegrationAction",
    "IntegrationConfig",
    "Job",
    "LlmCallRecord",
    "LoginAttempt",
    "MetricDefinition",
    "MetricObservation",
    "Opportunity",
    "ProductRelease",
    "PromptVersion",
    "RecordClassification",
    "RecordEmbedding",
    "RequestMembership",
    "ReviewItem",
    "Roadmap",
    "RoadmapDependency",
    "RoadmapItem",
    "ScoreInput",
    "ScoreSnapshot",
    "ScoringConfig",
    "Session",
    "SourceFile",
    "Theme",
    "ThemeMembership",
    "ThemeMetricLink",
    "ThemeOverride",
    "ThemeRunStats",
    "ToolCallRecord",
    "User",
    "UserStory",
    "VerificationResult",
    "Workspace",
    "WorkspaceMembership",
]
