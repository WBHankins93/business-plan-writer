from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from web_api.db import Base


def utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def uuid_string() -> str:
    return str(uuid.uuid4())


class Profile(Base):
    """Application-owned lifecycle data for one external authentication user."""

    __tablename__ = "profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now_naive, onupdate=utc_now_naive
    )
    deletion_requested_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    purge_after: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    projects: Mapped[list[Project]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )


class Project(Base):
    """User-owned business-plan container and its retention state."""

    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint(
            "(deleted_at IS NULL AND purge_after IS NULL) OR "
            "(deleted_at IS NOT NULL AND purge_after IS NOT NULL AND purge_after >= deleted_at)",
            name="ck_projects_deletion_window",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    owner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("profiles.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(160), default="Untitled business")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now_naive, onupdate=utc_now_naive
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    purge_after: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    owner: Mapped[Profile] = relationship(back_populates="projects")
    intake_draft: Mapped[IntakeDraft | None] = relationship(
        back_populates="project", cascade="all, delete-orphan", uselist=False
    )
    runs: Mapped[list[Run]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class IntakeDraft(Base):
    """The single mutable saved intake workspace for a project."""

    __tablename__ = "intake_drafts"
    __table_args__ = (
        UniqueConstraint("project_id", name="uq_intake_drafts_project_id"),
        CheckConstraint("current_step >= 0", name="ck_intake_drafts_current_step"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    data_json: Mapped[dict] = mapped_column(JSON, default=dict)
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now_naive, onupdate=utc_now_naive
    )

    project: Mapped[Project] = relationship(back_populates="intake_draft")


class Run(Base):
    """Mutable execution state plus an immutable snapshot of its input/configuration."""

    __tablename__ = "runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name="ck_runs_status",
        ),
        CheckConstraint(
            "finished_at IS NULL OR started_at IS NOT NULL",
            name="ck_runs_finished_after_start",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    entitlement_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("entitlements.id"), index=True, nullable=True
    )
    # Presentation metadata only. It is never an ownership or uniqueness key.
    client_slug: Mapped[str] = mapped_column(String(120), index=True)
    status: Mapped[str] = mapped_column(String(24), index=True)
    input_snapshot_json: Mapped[dict] = mapped_column(JSON)
    progress_json: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(160))
    configuration_json: Mapped[dict] = mapped_column(JSON, default=dict)
    output_summary_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now_naive, onupdate=utc_now_naive
    )

    project: Mapped[Project] = relationship(back_populates="runs")
    events: Mapped[list[RunEvent]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="RunEvent.id"
    )
    artifacts: Mapped[list[Artifact]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    revisions: Mapped[list[Revision]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class RunEvent(Base):
    """Append-only audit event for a run state or pipeline progress change."""

    __tablename__ = "run_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("runs.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(24))
    status: Mapped[str | None] = mapped_column(String(24), nullable=True)
    step: Mapped[str | None] = mapped_column(String(32), nullable=True)
    event_type: Mapped[str | None] = mapped_column(String(24), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    details_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)

    run: Mapped[Run] = relationship(back_populates="events")


class Artifact(Base):
    """Metadata reference to a run output stored outside the database."""

    __tablename__ = "artifacts"
    __table_args__ = (
        UniqueConstraint("storage_provider", "storage_key", name="uq_artifacts_storage_ref"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("runs.id", ondelete="CASCADE"), index=True
    )
    artifact_type: Mapped[str] = mapped_column(String(32))
    storage_provider: Mapped[str] = mapped_column(String(32))
    storage_key: Mapped[str] = mapped_column(String(700))
    content_type: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)

    run: Mapped[Run] = relationship(back_populates="artifacts")
    revision: Mapped[Revision | None] = relationship(
        back_populates="artifact", cascade="all, delete-orphan", uselist=False
    )


class Revision(Base):
    """Ordered draft lineage; sequence zero is the original generated draft."""

    __tablename__ = "revisions"
    __table_args__ = (
        UniqueConstraint("run_id", "revision_number", name="uq_revisions_run_number"),
        UniqueConstraint("artifact_id", name="uq_revisions_artifact_id"),
        CheckConstraint(
            "(revision_number = 0 AND parent_revision_id IS NULL) OR "
            "(revision_number > 0 AND parent_revision_id IS NOT NULL)",
            name="ck_revisions_lineage",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("runs.id", ondelete="CASCADE"), index=True
    )
    artifact_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("artifacts.id", ondelete="CASCADE")
    )
    parent_revision_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("revisions.id", ondelete="CASCADE"), nullable=True
    )
    revision_number: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)

    run: Mapped[Run] = relationship(back_populates="revisions")
    artifact: Mapped[Artifact] = relationship(back_populates="revision")
    parent: Mapped[Revision | None] = relationship(
        remote_side="Revision.id", back_populates="children"
    )
    children: Mapped[list[Revision]] = relationship(back_populates="parent")


class Payment(Base):
    """One server-priced Stripe Checkout attempt and its transaction state."""

    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('checkout_pending', 'processing', 'paid', 'failed', "
            "'abandoned', 'partially_refunded', 'refunded')",
            name="ck_payments_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    owner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("profiles.id", ondelete="CASCADE"), index=True
    )
    package_code: Mapped[str] = mapped_column(String(64))
    provider: Mapped[str] = mapped_column(String(24), default="stripe")
    status: Mapped[str] = mapped_column(String(32), index=True)
    amount_total: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    provider_livemode: Mapped[bool] = mapped_column(Boolean, default=False)
    provider_checkout_session_id: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True
    )
    provider_payment_intent_id: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True
    )
    provider_charge_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now_naive, onupdate=utc_now_naive
    )


class Entitlement(Base):
    """One paid generation credit, independent of payment and run state."""

    __tablename__ = "entitlements"
    __table_args__ = (
        CheckConstraint(
            "status IN ('available', 'reserved', 'consumed', 'refunded')",
            name="ck_entitlements_status",
        ),
        CheckConstraint("revision_limit >= 0", name="ck_entitlements_revision_limit"),
        CheckConstraint("revisions_used >= 0", name="ck_entitlements_revisions_used"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    owner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("profiles.id", ondelete="CASCADE"), index=True
    )
    payment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("payments.id", ondelete="CASCADE"), unique=True, index=True
    )
    package_code: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), index=True)
    reserved_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    revision_limit: Mapped[int] = mapped_column(Integer)
    revisions_used: Mapped[int] = mapped_column(Integer, default=0)
    activated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now_naive, onupdate=utc_now_naive
    )


class WebhookEvent(Base):
    """Stripe event receipt used for webhook delivery idempotency."""

    __tablename__ = "webhook_events"

    provider_event_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    provider_object_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(24))
    received_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Refund(Base):
    """Provider refund state; successful totals determine entitlement revocation."""

    __tablename__ = "refunds"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    payment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("payments.id", ondelete="CASCADE"), index=True
    )
    provider_refund_id: Mapped[str] = mapped_column(String(255), unique=True)
    status: Mapped[str] = mapped_column(String(24), index=True)
    amount: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now_naive, onupdate=utc_now_naive
    )


class SupportRequest(Base):
    """Idempotent customer support or refund request linked to operational records."""

    __tablename__ = "support_requests"
    __table_args__ = (
        UniqueConstraint("owner_id", "client_request_id", name="uq_support_owner_request"),
        CheckConstraint(
            "kind IN ('payment', 'refund', 'generation', 'human_qa', 'other')",
            name="ck_support_requests_kind",
        ),
        CheckConstraint(
            "status IN ('open', 'in_progress', 'resolved', 'closed')",
            name="ck_support_requests_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    owner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("profiles.id", ondelete="CASCADE"), index=True
    )
    client_request_id: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(24), index=True)
    status: Mapped[str] = mapped_column(String(24), index=True)
    payment_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("payments.id", ondelete="SET NULL"), nullable=True
    )
    run_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("runs.id", ondelete="SET NULL"), nullable=True
    )
    message: Mapped[str] = mapped_column(Text)
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now_naive, onupdate=utc_now_naive
    )
