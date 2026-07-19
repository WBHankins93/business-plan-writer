from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from web_api.db import Base


def utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    client_slug: Mapped[str] = mapped_column(String(120), index=True)
    status: Mapped[str] = mapped_column(String(24), index=True)
    intake_json: Mapped[dict] = mapped_column(JSON)
    progress_json: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    artifact_path: Mapped[str] = mapped_column(String(500))
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now_naive, onupdate=utc_now_naive
    )
    events: Mapped[list[RunEvent]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="RunEvent.id"
    )


class RunEvent(Base):
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
