"""add authenticated intake projects and run ownership

Revision ID: 20260719_0003
Revises: 20260719_0002
Create Date: 2026-07-19
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260719_0003"
down_revision = "20260719_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "intake_projects",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("owner_id", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("intake_json", sa.JSON(), nullable=False),
        sa.Column("current_step", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_intake_projects_owner_id", "intake_projects", ["owner_id"])

    with op.batch_alter_table("runs") as batch_op:
        batch_op.add_column(sa.Column("owner_id", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("project_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_runs_project_id_intake_projects",
            "intake_projects",
            ["project_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_runs_owner_id", ["owner_id"])
        batch_op.create_index("ix_runs_project_id", ["project_id"])


def downgrade() -> None:
    with op.batch_alter_table("runs") as batch_op:
        batch_op.drop_index("ix_runs_project_id")
        batch_op.drop_index("ix_runs_owner_id")
        batch_op.drop_constraint("fk_runs_project_id_intake_projects", type_="foreignkey")
        batch_op.drop_column("project_id")
        batch_op.drop_column("owner_id")

    op.drop_index("ix_intake_projects_owner_id", table_name="intake_projects")
    op.drop_table("intake_projects")
