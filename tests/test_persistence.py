import json
import os
import runpy
import tempfile
import unittest
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, func, select, text
from sqlalchemy.orm import sessionmaker

from web_api.db import IntakeDraftStore, ProfileStore, ProjectStore, RunStore
from web_api.models import Artifact, IntakeDraft, Profile, Project, Revision, Run, RunEvent


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "alembic" / "versions" / "20260719_0003_multi_user_beta_model.py"


class PersistenceHarness(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary.name) / "persistence.db"
        self.database_url = f"sqlite:///{self.database_path}"
        self.original_database_url = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_URL"] = self.database_url
        self.engine = create_engine(self.database_url)

        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
        self.session_factory = sessionmaker(
            bind=self.engine, autoflush=False, autocommit=False
        )
        self.profiles = ProfileStore(self.session_factory)
        self.projects = ProjectStore(self.session_factory)
        self.drafts = IntakeDraftStore(self.session_factory)
        self.runs = RunStore(self.session_factory)

    def tearDown(self):
        self.engine.dispose()
        if self.original_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = self.original_database_url
        self.temporary.cleanup()

    def owned_project(self, owner_id: str, title: str = "Acme"):
        self.profiles.create(owner_id)
        project = self.projects.create(owner_id, title=title)
        draft = self.drafts.save_owned(
            project_id=project.id,
            owner_id=owner_id,
            data={"business_information": {"business_name": title}},
            current_step=2,
        )
        return project, draft

    def create_run(self, owner_id: str, project_id: str) -> str:
        run_id = str(uuid.uuid4())
        created = self.runs.create_owned(
            run_id=run_id,
            project_id=project_id,
            owner_id=owner_id,
            client_slug="acme",
            provider="openai",
            model="gpt-test",
            configuration={"writer_provider": "anthropic", "writer_model": "claude-test"},
        )
        self.assertTrue(created)
        return run_id


class OwnershipAndAuditTests(PersistenceHarness):
    def test_cross_user_project_draft_and_run_access_is_denied(self):
        project, _draft = self.owned_project("11111111-1111-1111-1111-111111111111")
        self.profiles.create("22222222-2222-2222-2222-222222222222")
        run_id = self.create_run("11111111-1111-1111-1111-111111111111", project.id)

        self.assertIsNone(
            self.projects.get_owned(project.id, "22222222-2222-2222-2222-222222222222")
        )
        self.assertIsNone(
            self.drafts.get_owned(project.id, "22222222-2222-2222-2222-222222222222")
        )
        self.assertIsNone(
            self.runs.get_owned(run_id, "22222222-2222-2222-2222-222222222222")
        )
        self.assertFalse(
            self.runs.create_owned(
                run_id=str(uuid.uuid4()),
                project_id=project.id,
                owner_id="22222222-2222-2222-2222-222222222222",
                client_slug="stolen",
                provider="openai",
                model="gpt-test",
                configuration={},
            )
        )

    def test_run_snapshots_draft_and_configuration_and_appends_history(self):
        owner_id = "11111111-1111-1111-1111-111111111111"
        project, _draft = self.owned_project(owner_id)
        run_id = self.create_run(owner_id, project.id)
        self.drafts.save_owned(
            project_id=project.id,
            owner_id=owner_id,
            data={"business_information": {"business_name": "Changed"}},
            current_step=3,
        )
        self.runs.transition(run_id, "running", "Run started.")
        self.runs.fail(
            run_id,
            code="provider_failure",
            message="Generation failed.",
            operator_details="safe internal detail",
        )

        run = self.runs.get_owned(run_id, owner_id)
        self.assertEqual(run.input_snapshot_json["business_information"]["business_name"], "Acme")
        self.assertEqual(run.provider, "openai")
        self.assertEqual(run.model, "gpt-test")
        self.assertEqual(run.configuration_json["writer_provider"], "anthropic")
        self.assertEqual(
            [event["status"] for event in self.runs.events(run_id) if event["kind"] == "status"],
            ["queued", "running", "failed"],
        )
        self.assertLessEqual(run.created_at, run.started_at)
        self.assertLessEqual(run.started_at, run.finished_at)

    def test_secret_shaped_configuration_is_rejected(self):
        owner_id = "11111111-1111-1111-1111-111111111111"
        project, _draft = self.owned_project(owner_id)
        with self.assertRaisesRegex(ValueError, "cannot contain secrets"):
            self.runs.create_owned(
                run_id=str(uuid.uuid4()),
                project_id=project.id,
                owner_id=owner_id,
                client_slug="acme",
                provider="openai",
                model="gpt-test",
                configuration={"provider_api_key": "do-not-store"},
            )

    def test_artifacts_are_references_and_revisions_have_explicit_lineage(self):
        owner_id = "11111111-1111-1111-1111-111111111111"
        project, _draft = self.owned_project(owner_id)
        run_id = self.create_run(owner_id, project.id)
        self.runs.transition(run_id, "running", "Run started.")
        self.runs.succeed(
            run_id,
            {
                "run_id": run_id,
                "validation_warnings": {},
                "draft_file": "agent-4.draft.v0.md",
                "artifact_files": {
                    "docx": "acme_business_plan.docx",
                    "pdf": "acme_business_plan.pdf",
                },
            },
        )
        revision = self.runs.create_revision(
            run_id=run_id,
            owner_id=owner_id,
            storage_provider="filesystem",
            storage_key=f"{run_id}/agent-4.draft.v1.md",
        )

        with self.session_factory() as db:
            artifacts = db.scalars(select(Artifact).where(Artifact.run_id == run_id)).all()
            revisions = db.scalars(
                select(Revision)
                .where(Revision.run_id == run_id)
                .order_by(Revision.revision_number)
            ).all()
        self.assertEqual({artifact.artifact_type for artifact in artifacts}, {"draft", "docx", "pdf"})
        self.assertTrue(all(artifact.storage_key.startswith(f"{run_id}/") for artifact in artifacts))
        self.assertFalse(any(hasattr(artifact, "data") or hasattr(artifact, "blob") for artifact in artifacts))
        self.assertEqual([item.revision_number for item in revisions], [0, 1])
        self.assertIsNone(revisions[0].parent_revision_id)
        self.assertEqual(revisions[1].parent_revision_id, revisions[0].id)
        self.assertEqual(revision.revision_number, 1)


class RetentionTests(PersistenceHarness):
    def test_soft_delete_hides_data_then_hard_purge_cascades_metadata(self):
        owner_id = "11111111-1111-1111-1111-111111111111"
        project, _draft = self.owned_project(owner_id)
        run_id = self.create_run(owner_id, project.id)
        self.runs.transition(run_id, "running", "Run started.")
        self.runs.succeed(
            run_id,
            {
                "run_id": run_id,
                "draft_file": "draft.md",
                "artifact_files": {"pdf": "plan.pdf"},
            },
        )
        deletion_time = datetime(2026, 7, 19, 12, 0, 0)
        self.assertTrue(
            self.projects.schedule_deletion(
                project.id, owner_id, retention_days=30, now=deletion_time
            )
        )
        self.assertIsNone(self.projects.get_owned(project.id, owner_id))
        self.assertIsNone(self.runs.get_owned(run_id, owner_id))
        self.assertEqual(
            self.projects.due_for_purge(now=deletion_time + timedelta(days=29)), []
        )
        self.assertEqual(
            [item.id for item in self.projects.due_for_purge(now=deletion_time + timedelta(days=30))],
            [project.id],
        )

        external_keys = [artifact.storage_key for artifact in self.runs.artifacts(run_id)]
        self.assertEqual(len(external_keys), 2)
        self.assertTrue(self.projects.purge(project.id))
        with self.session_factory() as db:
            self.assertIsNone(db.get(Project, project.id))
            self.assertEqual(db.scalar(select(func.count()).select_from(IntakeDraft)), 0)
            self.assertEqual(db.scalar(select(func.count()).select_from(Run)), 0)
            self.assertEqual(db.scalar(select(func.count()).select_from(RunEvent)), 0)
            self.assertEqual(db.scalar(select(func.count()).select_from(Artifact)), 0)
            self.assertEqual(db.scalar(select(func.count()).select_from(Revision)), 0)


class MigrationPolicyTests(unittest.TestCase):
    def test_rls_covers_every_owned_table_and_keeps_events_append_only(self):
        namespace = runpy.run_path(str(MIGRATION))
        statements = namespace["postgres_rls_statements"]()
        sql = "\n".join(statements)
        for table in (
            "profiles",
            "projects",
            "intake_drafts",
            "runs",
            "run_events",
            "artifacts",
            "revisions",
        ):
            self.assertIn(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY", sql)
        self.assertIn("current_setting('app.current_user_id', true)", sql)
        self.assertIn("run_events_owner_select", sql)
        self.assertIn("run_events_owner_insert", sql)
        self.assertNotIn("run_events_owner_all", sql)
        self.assertIn("REVOKE UPDATE, DELETE ON run_events FROM PUBLIC", sql)

    def test_existing_run_is_backfilled_and_upgrade_remains_reversible(self):
        with tempfile.TemporaryDirectory() as directory:
            database_url = f"sqlite:///{Path(directory) / 'migration.db'}"
            previous = os.environ.get("DATABASE_URL")
            os.environ["DATABASE_URL"] = database_url
            config = Config(str(ROOT / "alembic.ini"))
            try:
                command.upgrade(config, "20260719_0002")
                engine = create_engine(database_url)
                now = datetime(2026, 7, 19, 10, 0, 0)
                run_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
                with engine.begin() as connection:
                    connection.execute(
                        text(
                            "INSERT INTO runs "
                            "(id, client_slug, status, intake_json, progress_json, result_json, "
                            "artifact_path, created_at, updated_at) "
                            "VALUES (:id, :slug, 'queued', :intake, NULL, NULL, :path, :created, :updated)"
                        ),
                        {
                            "id": run_id,
                            "slug": "legacy-acme",
                            "intake": json.dumps({"business": "Acme"}),
                            "path": f"output/runs/{run_id}",
                            "created": now,
                            "updated": now,
                        },
                    )
                command.upgrade(config, "head")
                with engine.connect() as connection:
                    migrated = connection.execute(
                        text(
                            "SELECT project_id, provider, model, input_snapshot_json "
                            "FROM runs WHERE id = :id"
                        ),
                        {"id": run_id},
                    ).mappings().one()
                self.assertEqual(migrated["project_id"], run_id)
                self.assertEqual(migrated["provider"], "legacy")
                self.assertEqual(migrated["model"], "unrecorded")
                command.downgrade(config, "base")
                with engine.connect() as connection:
                    tables = connection.execute(
                        text("SELECT name FROM sqlite_master WHERE type='table' AND name='runs'")
                    ).all()
                self.assertEqual(tables, [])
                engine.dispose()
            finally:
                if previous is None:
                    os.environ.pop("DATABASE_URL", None)
                else:
                    os.environ["DATABASE_URL"] = previous


if __name__ == "__main__":
    unittest.main()
