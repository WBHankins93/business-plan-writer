from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
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
    purge_after: Mapped[datetime | None] = mapped_column(DateTime, index=True, nullable=True)

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
    purge_after: Mapped[datetime | None] = mapped_column(DateTime, index=True, nullable=True)

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
