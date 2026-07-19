"""add run artifacts, safe failures, and event audit trail

Revision ID: 20260719_0002
Revises: 20260512_0001
Create Date: 2026-07-19
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260719_0002"
down_revision = "20260512_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("runs") as batch_op:
        batch_op.add_column(sa.Column("artifact_path", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("error_code", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("error_message", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("error_details", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("started_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("finished_at", sa.DateTime(), nullable=True))

    op.execute("UPDATE runs SET artifact_path = 'output/runs/' || id")
    op.execute("UPDATE runs SET error_details = error_text WHERE error_text IS NOT NULL")

    with op.batch_alter_table("runs") as batch_op:
        batch_op.alter_column("artifact_path", existing_type=sa.String(length=500), nullable=False)
        batch_op.drop_column("error_text")

    op.create_table(
        "run_events",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column(
            "run_id",
            sa.String(length=36),
            sa.ForeignKey("runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=True),
        sa.Column("step", sa.String(length=32), nullable=True),
        sa.Column("event_type", sa.String(length=24), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("details_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_run_events_run_id", "run_events", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_run_events_run_id", table_name="run_events")
    op.drop_table("run_events")

    with op.batch_alter_table("runs") as batch_op:
        batch_op.add_column(sa.Column("error_text", sa.Text(), nullable=True))
    op.execute("UPDATE runs SET error_text = error_details WHERE error_details IS NOT NULL")
    with op.batch_alter_table("runs") as batch_op:
        batch_op.drop_column("finished_at")
        batch_op.drop_column("started_at")
        batch_op.drop_column("error_details")
        batch_op.drop_column("error_message")
        batch_op.drop_column("error_code")
        batch_op.drop_column("artifact_path")
