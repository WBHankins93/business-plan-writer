"""add the minimum owned persistence model for the multi-user beta

Revision ID: 20260719_0003
Revises: 20260719_0002
Create Date: 2026-07-19
"""

from __future__ import annotations

import json
import uuid

from alembic import op
import sqlalchemy as sa


revision = "20260719_0003"
down_revision = "20260719_0002"
branch_labels = None
depends_on = None


LEGACY_PROFILE_ID = "00000000-0000-0000-0000-000000000000"


def _json_dict(value: object) -> dict:
    if isinstance(value, str):
        value = json.loads(value)
    return dict(value or {})


def _owner_setting() -> str:
    return "NULLIF(current_setting('app.current_user_id', true), '')"


def postgres_rls_statements() -> tuple[str, ...]:
    """PostgreSQL policies used in production; kept explicit for review and testing."""
    owner = _owner_setting()
    predicates = {
        "profiles": f"id = {owner}",
        "projects": f"owner_id = {owner}",
        "intake_drafts": (
            "EXISTS (SELECT 1 FROM projects p "
            f"WHERE p.id = intake_drafts.project_id AND p.owner_id = {owner})"
        ),
        "runs": (
            "EXISTS (SELECT 1 FROM projects p "
            f"WHERE p.id = runs.project_id AND p.owner_id = {owner})"
        ),
        "run_events": (
            "EXISTS (SELECT 1 FROM runs r JOIN projects p ON p.id = r.project_id "
            f"WHERE r.id = run_events.run_id AND p.owner_id = {owner})"
        ),
        "artifacts": (
            "EXISTS (SELECT 1 FROM runs r JOIN projects p ON p.id = r.project_id "
            f"WHERE r.id = artifacts.run_id AND p.owner_id = {owner})"
        ),
        "revisions": (
            "EXISTS (SELECT 1 FROM runs r JOIN projects p ON p.id = r.project_id "
            f"WHERE r.id = revisions.run_id AND p.owner_id = {owner})"
        ),
    }
    statements: list[str] = []
    for table, predicate in predicates.items():
        statements.append(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        if table == "run_events":
            statements.extend(
                [
                    f"CREATE POLICY run_events_owner_select ON run_events FOR SELECT USING ({predicate})",
                    f"CREATE POLICY run_events_owner_insert ON run_events FOR INSERT WITH CHECK ({predicate})",
                    "REVOKE UPDATE, DELETE ON run_events FROM PUBLIC",
                ]
            )
        else:
            statements.append(
                f"CREATE POLICY {table}_owner_all ON {table} FOR ALL "
                f"USING ({predicate}) WITH CHECK ({predicate})"
            )
    return tuple(statements)


def _disable_postgres_rls() -> None:
    for table in (
        "revisions",
        "artifacts",
        "run_events",
        "runs",
        "intake_drafts",
        "projects",
        "profiles",
    ):
        if table == "run_events":
            op.execute("DROP POLICY IF EXISTS run_events_owner_insert ON run_events")
            op.execute("DROP POLICY IF EXISTS run_events_owner_select ON run_events")
        else:
            op.execute(f"DROP POLICY IF EXISTS {table}_owner_all ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")


def upgrade() -> None:
    op.create_table(
        "profiles",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deletion_requested_at", sa.DateTime(), nullable=True),
        sa.Column("purge_after", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_profiles_purge_after", "profiles", ["purge_after"])
    op.create_table(
        "projects",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "owner_id",
            sa.String(length=36),
            sa.ForeignKey("profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("purge_after", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "(deleted_at IS NULL AND purge_after IS NULL) OR "
            "(deleted_at IS NOT NULL AND purge_after IS NOT NULL AND purge_after >= deleted_at)",
            name="ck_projects_deletion_window",
        ),
    )
    op.create_index("ix_projects_owner_id", "projects", ["owner_id"])
    op.create_index("ix_projects_purge_after", "projects", ["purge_after"])
    op.create_table(
        "intake_drafts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(length=36),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("data_json", sa.JSON(), nullable=False),
        sa.Column("current_step", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("project_id", name="uq_intake_drafts_project_id"),
        sa.CheckConstraint("current_step >= 0", name="ck_intake_drafts_current_step"),
    )
    op.create_index("ix_intake_drafts_project_id", "intake_drafts", ["project_id"])

    with op.batch_alter_table("runs") as batch_op:
        batch_op.add_column(sa.Column("project_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("provider", sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column("model", sa.String(length=160), nullable=True))
        batch_op.add_column(sa.Column("configuration_json", sa.JSON(), nullable=True))
        batch_op.create_foreign_key(
            "fk_runs_project_id_projects",
            "projects",
            ["project_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_index("ix_runs_project_id", ["project_id"])

    connection = op.get_bind()
    old_runs = sa.table(
        "runs",
        sa.column("id", sa.String()),
        sa.column("client_slug", sa.String()),
        sa.column("intake_json", sa.JSON()),
        sa.column("result_json", sa.JSON()),
        sa.column("artifact_path", sa.String()),
        sa.column("created_at", sa.DateTime()),
        sa.column("updated_at", sa.DateTime()),
        sa.column("started_at", sa.DateTime()),
        sa.column("finished_at", sa.DateTime()),
        sa.column("project_id", sa.String()),
        sa.column("provider", sa.String()),
        sa.column("model", sa.String()),
        sa.column("configuration_json", sa.JSON()),
    )
    existing = list(connection.execute(sa.select(old_runs)).mappings())
    if existing:
        profiles = sa.table(
            "profiles",
            sa.column("id", sa.String()),
            sa.column("created_at", sa.DateTime()),
            sa.column("updated_at", sa.DateTime()),
        )
        first_created = min(row["created_at"] for row in existing)
        last_updated = max(row["updated_at"] for row in existing)
        connection.execute(
            profiles.insert().values(
                id=LEGACY_PROFILE_ID,
                created_at=first_created,
                updated_at=last_updated,
            )
        )
        projects = sa.table(
            "projects",
            sa.column("id", sa.String()),
            sa.column("owner_id", sa.String()),
            sa.column("title", sa.String()),
            sa.column("created_at", sa.DateTime()),
            sa.column("updated_at", sa.DateTime()),
        )
        drafts = sa.table(
            "intake_drafts",
            sa.column("id", sa.String()),
            sa.column("project_id", sa.String()),
            sa.column("data_json", sa.JSON()),
            sa.column("current_step", sa.Integer()),
            sa.column("created_at", sa.DateTime()),
            sa.column("updated_at", sa.DateTime()),
        )
        for row in existing:
            connection.execute(
                projects.insert().values(
                    id=row["id"],
                    owner_id=LEGACY_PROFILE_ID,
                    title=(row["client_slug"] or "Migrated project")[:160],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
            )
            connection.execute(
                drafts.insert().values(
                    id=row["id"],
                    project_id=row["id"],
                    data_json=row["intake_json"],
                    current_step=0,
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
            )
            connection.execute(
                old_runs.update()
                .where(old_runs.c.id == row["id"])
                .values(
                    project_id=row["id"],
                    provider="legacy",
                    model="unrecorded",
                    configuration_json={"migrated_from": revision},
                    started_at=row["started_at"] or row["finished_at"],
                )
            )

    with op.batch_alter_table("runs") as batch_op:
        batch_op.alter_column("project_id", existing_type=sa.String(length=36), nullable=False)
        batch_op.alter_column("provider", existing_type=sa.String(length=40), nullable=False)
        batch_op.alter_column("model", existing_type=sa.String(length=160), nullable=False)
        batch_op.alter_column("configuration_json", existing_type=sa.JSON(), nullable=False)
        batch_op.alter_column(
            "intake_json", new_column_name="input_snapshot_json", existing_type=sa.JSON()
        )
        batch_op.alter_column(
            "result_json", new_column_name="output_summary_json", existing_type=sa.JSON()
        )
        batch_op.drop_column("artifact_path")
        batch_op.create_check_constraint(
            "ck_runs_status", "status IN ('queued', 'running', 'succeeded', 'failed')"
        )
        batch_op.create_check_constraint(
            "ck_runs_finished_after_start", "finished_at IS NULL OR started_at IS NOT NULL"
        )

    op.create_table(
        "artifacts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(length=36),
            sa.ForeignKey("runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("artifact_type", sa.String(length=32), nullable=False),
        sa.Column("storage_provider", sa.String(length=32), nullable=False),
        sa.Column("storage_key", sa.String(length=700), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("storage_provider", "storage_key", name="uq_artifacts_storage_ref"),
    )
    op.create_index("ix_artifacts_run_id", "artifacts", ["run_id"])
    op.create_table(
        "revisions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(length=36),
            sa.ForeignKey("runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "artifact_id",
            sa.String(length=36),
            sa.ForeignKey("artifacts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "parent_revision_id",
            sa.String(length=36),
            sa.ForeignKey("revisions.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("run_id", "revision_number", name="uq_revisions_run_number"),
        sa.UniqueConstraint("artifact_id", name="uq_revisions_artifact_id"),
        sa.CheckConstraint(
            "(revision_number = 0 AND parent_revision_id IS NULL) OR "
            "(revision_number > 0 AND parent_revision_id IS NOT NULL)",
            name="ck_revisions_lineage",
        ),
    )
    op.create_index("ix_revisions_run_id", "revisions", ["run_id"])

    artifacts = sa.table(
        "artifacts",
        sa.column("id", sa.String()),
        sa.column("run_id", sa.String()),
        sa.column("artifact_type", sa.String()),
        sa.column("storage_provider", sa.String()),
        sa.column("storage_key", sa.String()),
        sa.column("content_type", sa.String()),
        sa.column("created_at", sa.DateTime()),
    )
    revisions = sa.table(
        "revisions",
        sa.column("id", sa.String()),
        sa.column("run_id", sa.String()),
        sa.column("artifact_id", sa.String()),
        sa.column("parent_revision_id", sa.String()),
        sa.column("revision_number", sa.Integer()),
        sa.column("created_at", sa.DateTime()),
    )
    new_runs = sa.table(
        "runs",
        sa.column("id", sa.String()),
        sa.column("output_summary_json", sa.JSON()),
    )
    for row in existing:
        result = _json_dict(row["result_json"])
        artifact_specs = []
        if result.get("draft_file"):
            artifact_specs.append(("draft", result["draft_file"], "text/markdown"))
        for artifact_type, filename in result.get("artifact_files", {}).items():
            if filename:
                content_type = {
                    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "pdf": "application/pdf",
                }.get(artifact_type, "application/octet-stream")
                artifact_specs.append((artifact_type, filename, content_type))
        for artifact_type, filename, content_type in artifact_specs:
            artifact_id = str(
                uuid.uuid5(uuid.NAMESPACE_URL, f"filesystem:{row['id']}/{filename}")
            )
            connection.execute(
                artifacts.insert().values(
                    id=artifact_id,
                    run_id=row["id"],
                    artifact_type=artifact_type,
                    storage_provider="filesystem",
                    storage_key=f"{row['id']}/{filename}",
                    content_type=content_type,
                    created_at=row["updated_at"],
                )
            )
            if artifact_type == "draft":
                connection.execute(
                    revisions.insert().values(
                        id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"revision:{row['id']}:0")),
                        run_id=row["id"],
                        artifact_id=artifact_id,
                        parent_revision_id=None,
                        revision_number=0,
                        created_at=row["updated_at"],
                    )
                )
        summary = {
            key: value
            for key, value in result.items()
            if key not in {"artifact_files", "draft_file", "run_id", "client_slug"}
        }
        connection.execute(
            new_runs.update()
            .where(new_runs.c.id == row["id"])
            .values(output_summary_json=summary or None)
        )

    if connection.dialect.name == "postgresql":
        for statement in postgres_rls_statements():
            op.execute(statement)


def downgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        _disable_postgres_rls()

    run_rows = list(
        connection.execute(
            sa.text("SELECT id, output_summary_json FROM runs")
        ).mappings()
    )
    artifact_rows = list(
        connection.execute(
            sa.text(
                "SELECT run_id, artifact_type, storage_key FROM artifacts "
                "WHERE storage_provider = 'filesystem'"
            )
        ).mappings()
    )

    with op.batch_alter_table("runs") as batch_op:
        batch_op.drop_constraint("ck_runs_finished_after_start", type_="check")
        batch_op.drop_constraint("ck_runs_status", type_="check")
        batch_op.add_column(sa.Column("artifact_path", sa.String(length=500), nullable=True))
        batch_op.alter_column(
            "input_snapshot_json", new_column_name="intake_json", existing_type=sa.JSON()
        )
        batch_op.alter_column(
            "output_summary_json", new_column_name="result_json", existing_type=sa.JSON()
        )

    old_runs = sa.table(
        "runs",
        sa.column("id", sa.String()),
        sa.column("result_json", sa.JSON()),
        sa.column("artifact_path", sa.String()),
    )
    by_run: dict[str, list[dict]] = {}
    for artifact in artifact_rows:
        by_run.setdefault(artifact["run_id"], []).append(dict(artifact))
    for row in run_rows:
        result = _json_dict(row["output_summary_json"])
        files: dict[str, str] = {}
        for artifact in by_run.get(row["id"], []):
            filename = artifact["storage_key"].split("/", 1)[-1]
            if artifact["artifact_type"] == "draft":
                result.setdefault("draft_file", filename)
            else:
                files[artifact["artifact_type"]] = filename
        if files:
            result["artifact_files"] = files
        connection.execute(
            old_runs.update()
            .where(old_runs.c.id == row["id"])
            .values(
                result_json=result or None,
                artifact_path=f"output/runs/{row['id']}",
            )
        )

    op.drop_index("ix_revisions_run_id", table_name="revisions")
    op.drop_table("revisions")
    op.drop_index("ix_artifacts_run_id", table_name="artifacts")
    op.drop_table("artifacts")

    with op.batch_alter_table("runs") as batch_op:
        batch_op.alter_column("artifact_path", existing_type=sa.String(length=500), nullable=False)
        batch_op.drop_index("ix_runs_project_id")
        batch_op.drop_constraint("fk_runs_project_id_projects", type_="foreignkey")
        batch_op.drop_column("configuration_json")
        batch_op.drop_column("model")
        batch_op.drop_column("provider")
        batch_op.drop_column("project_id")

    op.drop_index("ix_intake_drafts_project_id", table_name="intake_drafts")
    op.drop_table("intake_drafts")
    op.drop_index("ix_projects_purge_after", table_name="projects")
    op.drop_index("ix_projects_owner_id", table_name="projects")
    op.drop_table("projects")
    op.drop_index("ix_profiles_purge_after", table_name="profiles")
    op.drop_table("profiles")
