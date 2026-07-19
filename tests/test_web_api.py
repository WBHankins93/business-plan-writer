import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from web_api import app as app_module
from web_api import db as db_module
from web_api.db import RunStore
from web_api.execution import (
    ExecutionFailed,
    ExecutionResult,
    ExecutionTimedOut,
    SubprocessExecutor,
)


ROOT = Path(__file__).resolve().parents[1]
VALID_INTAKE = json.loads(
    (ROOT / "sample_intake" / "fictional_bywater_grounds.json").read_text(encoding="utf-8")
)


class SuccessfulExecutor:
    def execute(self, *, run_id, intake, artifact_directory, on_progress):
        artifact_directory.mkdir(parents=True, exist_ok=False)
        events = [
            ("validator", "started"),
            ("validator", "completed"),
            ("market", "started"),
            ("financial", "started"),
            ("market", "completed"),
            ("financial", "completed"),
            ("writer", "started"),
            ("writer", "completed"),
            ("critic", "started"),
            ("critic", "completed"),
        ]
        for step, event_type in events:
            on_progress(
                {
                    "run_id": run_id,
                    "step": step,
                    "event_type": event_type,
                    "occurred_at": "2026-07-19T12:00:00+00:00",
                    "message": f"operator detail for {step}",
                    "details": {},
                }
            )
        (artifact_directory / "agent-4.draft.v0.md").write_text("# Plan", encoding="utf-8")
        (artifact_directory / "agent-1.validator.json").write_text(
            json.dumps({"completeness_score": 91, "missing_required": [], "thin_fields": []}),
            encoding="utf-8",
        )
        (artifact_directory / "agent-5.critic.v0.json").write_text(
            json.dumps({"approval_status": "GO"}), encoding="utf-8"
        )
        (artifact_directory / "test_business_plan.docx").write_bytes(b"docx-content")
        (artifact_directory / "test_business_plan.pdf").write_bytes(b"pdf-content")
        return ExecutionResult(0, "completed", "")


class FailedExecutor:
    def execute(self, **kwargs):
        kwargs["artifact_directory"].mkdir(parents=True, exist_ok=False)
        raise ExecutionFailed(ExecutionResult(7, "provider output", "private operator failure"))


class TimedOutExecutor:
    def execute(self, **kwargs):
        kwargs["artifact_directory"].mkdir(parents=True, exist_ok=False)
        raise ExecutionTimedOut(3, ExecutionResult(-9, "", "killed after timeout"))


class NeverFinishesProcess:
    def __init__(self):
        self.returncode = None
        self.killed = False

    def poll(self):
        return self.returncode

    def kill(self):
        self.killed = True
        self.returncode = -9

    def wait(self):
        return self.returncode


class ExecutionBoundaryTests(unittest.TestCase):
    def test_subprocess_executor_kills_work_after_configured_timeout(self):
        process = NeverFinishesProcess()
        with tempfile.TemporaryDirectory() as directory, patch(
            "web_api.execution.subprocess.Popen", return_value=process
        ):
            executor = SubprocessExecutor(timeout_seconds=0.002, poll_interval=0.001)

            with self.assertRaises(ExecutionTimedOut):
                executor.execute(
                    run_id="00000000-0000-0000-0000-000000000001",
                    intake={},
                    artifact_directory=Path(directory) / "run",
                    on_progress=lambda _event: None,
                )

        self.assertTrue(process.killed)


class DatabaseHarness(unittest.TestCase):
    migrate_on_setup = True

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.database_path = root / "api.db"
        self.artifact_root = root / "artifacts"
        self.original_environment = {
            name: os.environ.get(name)
            for name in ("DATABASE_URL", "ARTIFACT_ROOT", "BUSINESS_PLAN_API_KEY")
        }
        os.environ["DATABASE_URL"] = f"sqlite:///{self.database_path}"
        os.environ["ARTIFACT_ROOT"] = str(self.artifact_root)
        os.environ["BUSINESS_PLAN_API_KEY"] = "beta-key"

        if self.migrate_on_setup:
            command.upgrade(self._alembic_config(), "head")

        self.original_engine = db_module.engine
        self.original_session = db_module.SessionLocal
        self.engine = create_engine(
            os.environ["DATABASE_URL"], connect_args={"check_same_thread": False}
        )
        db_module.engine = self.engine
        db_module.SessionLocal = sessionmaker(
            bind=self.engine, autoflush=False, autocommit=False
        )
        self.client = TestClient(app_module.app)
        self.headers = {"X-API-Key": "beta-key"}

    def tearDown(self):
        self.client.close()
        self.engine.dispose()
        db_module.engine = self.original_engine
        db_module.SessionLocal = self.original_session
        for name, value in self.original_environment.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        self.temporary.cleanup()

    @staticmethod
    def _alembic_config():
        return Config(str(ROOT / "alembic.ini"))

    def generate(self, executor=SuccessfulExecutor):
        with patch.object(app_module, "SubprocessExecutor", executor):
            return self.client.post(
                "/generate-plan", json={"intake": VALID_INTAKE}, headers=self.headers
            )


class APILifecycleTests(DatabaseHarness):
    def test_queue_returns_explicit_run_id_and_polling_url(self):
        with patch.object(app_module, "_execute_run", return_value=None):
            response = self.client.post(
                "/generate-plan", json={"intake": VALID_INTAKE}, headers=self.headers
            )

        self.assertEqual(response.status_code, 202)
        body = response.json()
        self.assertEqual(body["status"], "queued")
        self.assertEqual(body["status_url"], f"/runs/{body['run_id']}")
        stored = RunStore().get(body["run_id"])
        self.assertEqual(stored.status, "queued")
        self.assertIsNotNone(stored.project_id)
        self.assertEqual(stored.provider, "groq")

    def test_polling_reports_actual_agent_level_progress_and_audit_events(self):
        response = self.generate()
        run_id = response.json()["run_id"]

        poll = self.client.get(f"/runs/{run_id}", headers=self.headers)

        self.assertEqual(poll.status_code, 200)
        body = poll.json()
        self.assertEqual(body["status"], "succeeded")
        self.assertEqual(
            {item["name"]: item["status"] for item in body["progress"]},
            {
                "validator": "complete",
                "market": "complete",
                "financial": "complete",
                "writer": "complete",
                "critic": "complete",
            },
        )
        self.assertEqual(body["events"][0]["status"], "queued")
        self.assertEqual(body["events"][-1]["status"], "succeeded")
        self.assertEqual(body["result"]["draft_markdown"], "# Plan")
        self.assertNotIn("draft_markdown", RunStore().get(run_id).output_summary_json)
        self.assertEqual(
            {artifact.artifact_type for artifact in RunStore().artifacts(run_id)},
            {"draft", "docx", "pdf"},
        )

    def test_two_runs_for_same_business_have_distinct_artifact_directories(self):
        with patch.object(app_module, "_execute_run", return_value=None):
            first = self.client.post(
                "/generate-plan", json={"intake": VALID_INTAKE}, headers=self.headers
            ).json()
            second = self.client.post(
                "/generate-plan", json={"intake": VALID_INTAKE}, headers=self.headers
            ).json()

        first_run = RunStore().get(first["run_id"])
        second_run = RunStore().get(second["run_id"])
        self.assertEqual(first_run.client_slug, second_run.client_slug)
        self.assertNotEqual(first_run.id, second_run.id)
        self.assertNotEqual(
            app_module._artifact_store().run_directory(first_run.id),
            app_module._artifact_store().run_directory(second_run.id),
        )

    def test_failure_exposes_safe_error_and_persists_operator_details(self):
        response = self.generate(FailedExecutor)
        run_id = response.json()["run_id"]

        body = self.client.get(f"/runs/{run_id}", headers=self.headers).json()

        self.assertEqual(body["status"], "failed")
        self.assertEqual(body["error"]["code"], "pipeline_failed")
        self.assertNotIn("private operator failure", body["error"]["message"])
        stored = RunStore().get(run_id)
        self.assertIn("private operator failure", stored.error_details)

    def test_timeout_is_persisted_as_a_distinct_failure(self):
        response = self.generate(TimedOutExecutor)
        run_id = response.json()["run_id"]

        body = self.client.get(f"/runs/{run_id}", headers=self.headers).json()

        self.assertEqual(body["status"], "failed")
        self.assertEqual(body["error"]["code"], "pipeline_timeout")
        self.assertIn("took too long", body["error"]["message"])

    def test_artifact_download_accepts_signed_link_when_api_key_is_enabled(self):
        response = self.generate()
        run_id = response.json()["run_id"]
        poll = self.client.get(f"/runs/{run_id}", headers=self.headers).json()
        download_url = poll["result"]["exports"]["docx"]

        unauthorized_path = urlsplit(download_url).path
        unauthorized = self.client.get(unauthorized_path)
        download = self.client.get(download_url)

        self.assertEqual(unauthorized.status_code, 401)
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download.content, b"docx-content")

    def test_api_key_is_required_for_queue_and_polling(self):
        self.assertEqual(
            self.client.post("/generate-plan", json={"intake": VALID_INTAKE}).status_code,
            401,
        )


class MigrationAndHealthTests(DatabaseHarness):
    migrate_on_setup = False

    def test_health_is_live_while_readiness_requires_current_migrations(self):
        self.assertEqual(self.client.get("/healthz").status_code, 200)
        self.assertEqual(self.client.get("/readyz").status_code, 503)
        blocked = self.client.post(
            "/generate-plan", json={"intake": VALID_INTAKE}, headers=self.headers
        )
        self.assertEqual(blocked.status_code, 503)
        self.assertEqual(blocked.json()["detail"]["code"], "database_not_ready")

        command.upgrade(self._alembic_config(), "head")

        ready = self.client.get("/readyz")
        self.assertEqual(ready.status_code, 200)
        self.assertEqual(ready.json()["database_revision"], "20260719_0003")

    def test_migration_upgrade_and_downgrade_are_explicit_and_complete(self):
        config = self._alembic_config()
        self.assertNotIn("runs", inspect(self.engine).get_table_names())

        command.upgrade(config, "head")
        self.assertEqual(
            set(inspect(self.engine).get_table_names()),
            {
                "alembic_version",
                "profiles",
                "projects",
                "intake_drafts",
                "runs",
                "run_events",
                "artifacts",
                "revisions",
            },
        )

        command.downgrade(config, "base")
        self.assertNotIn("runs", inspect(self.engine).get_table_names())


if __name__ == "__main__":
    unittest.main()
