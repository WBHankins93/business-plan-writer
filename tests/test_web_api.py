import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from intake.schema import canonicalize_intake
from web_api import app as app_module
from web_api import db as db_module
from web_api.auth import AuthenticatedUser, get_token_verifier
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


class FakeTokenVerifier:
    users = {
        "user-a-token": AuthenticatedUser(id="user-a", email="a@example.com"),
        "user-b-token": AuthenticatedUser(id="user-b", email="b@example.com"),
    }

    def verify(self, token: str) -> AuthenticatedUser:
        if token == "expired-token":
            raise HTTPException(
                status_code=401,
                detail={"code": "session_expired", "message": "Your session has expired. Sign in again."},
            )
        if token not in self.users:
            raise HTTPException(
                status_code=401,
                detail={"code": "invalid_session", "message": "Your session is invalid. Sign in again."},
            )
        return self.users[token]


class SuccessfulExecutor:
    def execute(self, *, run_id, intake, artifact_directory, on_progress):
        artifact_directory.mkdir(parents=True, exist_ok=False)
        for step, event_type in [
            ("validator", "started"),
            ("validator", "completed"),
            ("market", "completed"),
            ("financial", "completed"),
            ("writer", "completed"),
            ("critic", "completed"),
        ]:
            on_progress(
                {
                    "run_id": run_id,
                    "step": step,
                    "event_type": event_type,
                    "occurred_at": "2026-07-19T12:00:00+00:00",
                    "message": "operator-only detail",
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
            for name in ("DATABASE_URL", "ARTIFACT_ROOT", "ENABLE_DEMO_MODE")
        }
        os.environ["DATABASE_URL"] = f"sqlite:///{self.database_path}"
        os.environ["ARTIFACT_ROOT"] = str(self.artifact_root)
        os.environ["ENABLE_DEMO_MODE"] = "true"

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
        app_module.app.dependency_overrides[get_token_verifier] = lambda: FakeTokenVerifier()
        self.client = TestClient(app_module.app)
        self.headers = {"Authorization": "Bearer user-a-token"}
        self.other_headers = {"Authorization": "Bearer user-b-token"}

    def tearDown(self):
        self.client.close()
        app_module.app.dependency_overrides.clear()
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

    def create_saved_project(self, headers=None):
        selected_headers = headers or self.headers
        project = self.client.post("/projects", headers=selected_headers).json()
        saved = self.client.put(
            f"/projects/{project['id']}/draft",
            json={"intake": VALID_INTAKE, "current_step": 3},
            headers=selected_headers,
        )
        self.assertEqual(saved.status_code, 200)
        return saved.json()

    def generate(self, executor=SuccessfulExecutor):
        project = self.create_saved_project()
        with patch.object(app_module, "SubprocessExecutor", executor):
            response = self.client.post(
                f"/projects/{project['id']}/generate-plan", headers=self.headers
            )
        return project, response


class AuthenticationAndResumeTests(DatabaseHarness):
    def test_unauthenticated_private_routes_are_rejected(self):
        self.assertEqual(self.client.get("/projects").status_code, 401)
        self.assertEqual(self.client.post("/projects").status_code, 401)
        self.assertEqual(
            self.client.get("/runs/00000000-0000-0000-0000-000000000000").status_code,
            401,
        )

    def test_expired_session_returns_actionable_401(self):
        response = self.client.get(
            "/projects", headers={"Authorization": "Bearer expired-token"}
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"]["code"], "session_expired")

    def test_authenticated_user_can_save_refresh_and_resume(self):
        project = self.create_saved_project()
        refreshed_client = TestClient(app_module.app)
        try:
            resumed = refreshed_client.get(
                f"/projects/{project['id']}", headers=self.headers
            )
        finally:
            refreshed_client.close()

        self.assertEqual(resumed.status_code, 200)
        body = resumed.json()
        self.assertEqual(body["current_step"], 3)
        self.assertEqual(
            body["intake"]["business_information"]["business_name"],
            VALID_INTAKE["business_information"]["business_name"],
        )
        self.assertEqual(body["title"], VALID_INTAKE["business_information"]["business_name"])

        listing = self.client.get("/projects", headers=self.headers).json()
        self.assertEqual(listing[0]["id"], project["id"])
        self.assertNotIn("intake", listing[0])

    def test_project_ownership_is_enforced_server_side(self):
        project = self.create_saved_project()
        self.assertEqual(
            self.client.get(f"/projects/{project['id']}", headers=self.other_headers).status_code,
            404,
        )
        self.assertEqual(
            self.client.put(
                f"/projects/{project['id']}/draft",
                json={"intake": VALID_INTAKE, "current_step": 0, "owner_id": "user-b"},
                headers=self.other_headers,
            ).status_code,
            404,
        )


class APILifecycleTests(DatabaseHarness):
    def test_generation_uses_owned_saved_draft_and_returns_run(self):
        project, response = self.generate()
        self.assertEqual(response.status_code, 202)
        body = response.json()
        run = RunStore().get(body["run_id"])
        self.assertEqual(run.owner_id, "user-a")
        self.assertEqual(run.project_id, project["id"])
        self.assertEqual(run.intake_json, canonicalize_intake(VALID_INTAKE))

        poll = self.client.get(f"/runs/{run.id}", headers=self.headers)
        self.assertEqual(poll.status_code, 200)
        self.assertEqual(poll.json()["status"], "succeeded")
        self.assertEqual(poll.json()["result"]["draft_markdown"], "# Plan")

    def test_run_and_artifact_cannot_be_read_by_another_user(self):
        _, response = self.generate()
        run_id = response.json()["run_id"]
        poll = self.client.get(f"/runs/{run_id}", headers=self.headers).json()
        artifact_path = poll["result"]["exports"]["docx"]

        self.assertEqual(self.client.get(f"/runs/{run_id}").status_code, 401)
        self.assertEqual(
            self.client.get(f"/runs/{run_id}", headers=self.other_headers).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(artifact_path, headers=self.other_headers).status_code,
            404,
        )
        artifact = self.client.get(artifact_path, headers=self.headers)
        self.assertEqual(artifact.status_code, 200)
        self.assertEqual(artifact.content, b"docx-content")

    def test_failures_expose_safe_messages_only(self):
        _, response = self.generate(FailedExecutor)
        body = self.client.get(
            f"/runs/{response.json()['run_id']}", headers=self.headers
        ).json()
        self.assertEqual(body["error"]["code"], "pipeline_failed")
        self.assertNotIn("private operator failure", body["error"]["message"])
        self.assertIn("private operator failure", RunStore().get(body["run_id"]).error_details)

    def test_timeout_is_a_distinct_safe_failure(self):
        _, response = self.generate(TimedOutExecutor)
        body = self.client.get(
            f"/runs/{response.json()['run_id']}", headers=self.headers
        ).json()
        self.assertEqual(body["error"]["code"], "pipeline_timeout")

    def test_demo_flow_is_explicit_and_separate_from_private_runs(self):
        self.assertEqual(self.client.get("/demo/intake").status_code, 200)
        with patch.object(app_module, "SubprocessExecutor", SuccessfulExecutor):
            queued = self.client.post(
                "/demo/generate-plan", json={"intake": VALID_INTAKE}
            )
        self.assertEqual(queued.status_code, 202)
        run_id = queued.json()["run_id"]
        self.assertEqual(self.client.get(f"/demo/runs/{run_id}").status_code, 200)
        self.assertEqual(self.client.get(f"/runs/{run_id}", headers=self.headers).status_code, 404)

        os.environ["ENABLE_DEMO_MODE"] = "false"
        self.assertEqual(self.client.get("/demo/intake").status_code, 404)


class MigrationAndHealthTests(DatabaseHarness):
    migrate_on_setup = False

    def test_health_is_live_while_readiness_requires_current_migrations(self):
        self.assertEqual(self.client.get("/healthz").status_code, 200)
        self.assertEqual(self.client.get("/readyz").status_code, 503)
        blocked = self.client.post("/projects", headers=self.headers)
        self.assertEqual(blocked.status_code, 503)
        command.upgrade(self._alembic_config(), "head")
        ready = self.client.get("/readyz")
        self.assertEqual(ready.status_code, 200)
        self.assertEqual(ready.json()["database_revision"], "20260719_0003")

    def test_migration_upgrade_and_downgrade_are_complete(self):
        config = self._alembic_config()
        command.upgrade(config, "head")
        self.assertEqual(
            set(inspect(self.engine).get_table_names()),
            {"alembic_version", "intake_projects", "run_events", "runs"},
        )
        command.downgrade(config, "base")
        self.assertNotIn("runs", inspect(self.engine).get_table_names())


if __name__ == "__main__":
    unittest.main()
