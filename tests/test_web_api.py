import json
import hashlib
import hmac
import os
import tempfile
import time
import unittest
import uuid
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
from web_api.billing import CheckoutSessionResult
from web_api.db import RunStore
from web_api.execution import (
    ExecutionFailed,
    ExecutionResult,
    ExecutionTimedOut,
    SubprocessExecutor,
)
from web_api.models import Entitlement, Payment, Profile


ROOT = Path(__file__).resolve().parents[1]
VALID_INTAKE = json.loads(
    (ROOT / "sample_intake" / "fictional_bywater_grounds.json").read_text(encoding="utf-8")
)
USER_ID = "11111111-1111-1111-1111-111111111111"


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
    seed_on_setup = True

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.database_path = root / "api.db"
        self.artifact_root = root / "artifacts"
        self.original_environment = {
            name: os.environ.get(name)
            for name in (
                "DATABASE_URL",
                "ARTIFACT_ROOT",
                "BUSINESS_PLAN_API_KEY",
                "TRUST_AUTH_PROXY_HEADERS",
                "STRIPE_SECRET_KEY",
                "STRIPE_WEBHOOK_SECRET",
            )
        }
        os.environ["DATABASE_URL"] = f"sqlite:///{self.database_path}"
        os.environ["ARTIFACT_ROOT"] = str(self.artifact_root)
        os.environ["BUSINESS_PLAN_API_KEY"] = "beta-key"
        os.environ["TRUST_AUTH_PROXY_HEADERS"] = "true"
        os.environ["STRIPE_SECRET_KEY"] = "sk_test_local"
        os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_local"

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
        self.headers = {
            "X-API-Key": "beta-key",
            "X-Authenticated-User-Id": USER_ID,
        }
        if self.migrate_on_setup:
            with db_module.SessionLocal() as session:
                session.add(Profile(id=USER_ID))
                session.commit()
            if self.seed_on_setup:
                self.seed_entitlement()

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

    def seed_entitlement(self):
        payment_id = str(uuid.uuid4())
        with db_module.SessionLocal() as session:
            session.add(
                Payment(
                    id=payment_id,
                    owner_id=USER_ID,
                    package_code="funding_ready_v1",
                    provider="stripe",
                    status="paid",
                    amount_total=49700,
                    currency="usd",
                    provider_livemode=False,
                    provider_checkout_session_id=f"cs_test_{payment_id}",
                )
            )
            session.add(
                Entitlement(
                    owner_id=USER_ID,
                    payment_id=payment_id,
                    package_code="funding_ready_v1",
                    status="available",
                    revision_limit=2,
                    revisions_used=0,
                )
            )
            session.commit()


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
        with db_module.SessionLocal() as session:
            self.assertEqual(
                session.get(Entitlement, RunStore().get(run_id).entitlement_id).status,
                "consumed",
            )
        self.assertEqual(
            {artifact.artifact_type for artifact in RunStore().artifacts(run_id)},
            {"draft", "docx", "pdf"},
        )

    def test_two_runs_for_same_business_have_distinct_artifact_directories(self):
        self.seed_entitlement()
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
        with db_module.SessionLocal() as session:
            entitlement = session.get(Entitlement, stored.entitlement_id)
            self.assertEqual(entitlement.status, "available")
            self.assertIsNone(entitlement.reserved_run_id)

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


class BillingFlowTests(DatabaseHarness):
    seed_on_setup = False

    def checkout(self):
        def fake_checkout(_gateway, *, payment_id, package):
            self.assertEqual(package.code, "funding_ready_v1")
            return CheckoutSessionResult(
                id=f"cs_test_{payment_id}",
                url="https://checkout.stripe.test/session",
                livemode=False,
            )

        with patch.object(app_module.StripeGateway, "create_checkout_session", fake_checkout):
            response = self.client.post(
                "/billing/checkout-sessions", headers=self.headers
            )
        self.assertEqual(response.status_code, 201)
        return response.json()

    def webhook(self, event):
        event = json.loads(json.dumps(event))
        event.setdefault("object", "event")
        event["data"]["object"].setdefault(
            "object", "refund" if event["type"].startswith("refund.") else "checkout.session"
        )
        payload = json.dumps(event, separators=(",", ":")).encode()
        timestamp = int(time.time())
        signature = hmac.new(
            b"whsec_local",
            f"{timestamp}.".encode() + payload,
            hashlib.sha256,
        ).hexdigest()
        return self.client.post(
            "/billing/webhooks/stripe",
            content=payload,
            headers={"Stripe-Signature": f"t={timestamp},v1={signature}"},
        )

    def checkout_event(self, checkout, *, event_id="evt_checkout_paid"):
        payment_id = checkout["payment_id"]
        return {
            "id": event_id,
            "type": "checkout.session.completed",
            "livemode": False,
            "data": {
                "object": {
                    "id": f"cs_test_{payment_id}",
                    "client_reference_id": payment_id,
                    "payment_status": "paid",
                    "amount_total": 49700,
                    "currency": "usd",
                    "payment_intent": f"pi_test_{payment_id}",
                }
            },
        }

    def test_successful_checkout_grants_exactly_one_credit_and_duplicate_is_safe(self):
        checkout = self.checkout()
        before = self.client.get(checkout["status_url"], headers=self.headers).json()
        self.assertEqual(before["payment_status"], "checkout_pending")
        self.assertIsNone(before["entitlement"])

        event = self.checkout_event(checkout)
        first = self.webhook(event)
        duplicate = self.webhook(event)

        self.assertEqual(first.status_code, 200)
        self.assertFalse(first.json()["duplicate"])
        self.assertTrue(duplicate.json()["duplicate"])
        status_body = self.client.get(checkout["status_url"], headers=self.headers).json()
        self.assertEqual(status_body["payment_status"], "paid")
        self.assertEqual(status_body["entitlement"]["status"], "available")
        summary = self.client.get("/billing/entitlements", headers=self.headers).json()
        self.assertEqual(summary["available_credits"], 1)
        self.assertEqual(len(summary["entitlements"]), 1)
        generated = self.generate(SuccessfulExecutor)
        self.assertEqual(generated.status_code, 202)
        completed = self.client.get(checkout["status_url"], headers=self.headers).json()
        self.assertEqual(completed["payment_status"], "paid")
        self.assertEqual(completed["entitlement"]["status"], "consumed")
        run_id = generated.json()["run_id"]
        for revision_number in (1, 2):
            RunStore().create_revision(
                run_id=run_id,
                owner_id=USER_ID,
                storage_provider="filesystem",
                storage_key=f"{run_id}/paid-revision-{revision_number}.md",
            )
        with self.assertRaisesRegex(ValueError, "revision limit"):
            RunStore().create_revision(
                run_id=run_id,
                owner_id=USER_ID,
                storage_provider="filesystem",
                storage_key=f"{run_id}/paid-revision-3.md",
            )

    def test_failed_payment_never_grants_generation_access(self):
        checkout = self.checkout()
        payment_id = checkout["payment_id"]
        failed = {
            "id": "evt_checkout_failed",
            "type": "checkout.session.async_payment_failed",
            "livemode": False,
            "data": {
                "object": {
                    "id": f"cs_test_{payment_id}",
                    "client_reference_id": payment_id,
                }
            },
        }
        self.assertEqual(self.webhook(failed).status_code, 200)
        status_body = self.client.get(checkout["status_url"], headers=self.headers).json()
        self.assertEqual(status_body["payment_status"], "failed")
        self.assertIsNone(status_body["entitlement"])
        blocked = self.client.post(
            "/generate-plan", json={"intake": VALID_INTAKE}, headers=self.headers
        )
        self.assertEqual(blocked.status_code, 402)

    def test_abandoned_checkout_never_grants_generation_access(self):
        checkout = self.checkout()
        payment_id = checkout["payment_id"]
        expired = {
            "id": "evt_checkout_expired",
            "type": "checkout.session.expired",
            "livemode": False,
            "data": {
                "object": {
                    "id": f"cs_test_{payment_id}",
                    "client_reference_id": payment_id,
                }
            },
        }
        self.assertEqual(self.webhook(expired).status_code, 200)
        body = self.client.get(checkout["status_url"], headers=self.headers).json()
        self.assertEqual(body["payment_status"], "abandoned")
        self.assertIsNone(body["entitlement"])

    def test_full_refund_revokes_credit_and_support_request_is_traceable(self):
        checkout = self.checkout()
        payment_id = checkout["payment_id"]
        self.assertEqual(self.webhook(self.checkout_event(checkout)).status_code, 200)
        refund = {
            "id": "evt_refund_created",
            "type": "refund.created",
            "livemode": False,
            "data": {
                "object": {
                    "id": "re_test_full",
                    "payment_intent": f"pi_test_{payment_id}",
                    "charge": "ch_test_full",
                    "status": "succeeded",
                    "amount": 49700,
                    "currency": "usd",
                    "reason": "requested_by_customer",
                }
            },
        }
        self.assertEqual(self.webhook(refund).status_code, 200)
        body = self.client.get(checkout["status_url"], headers=self.headers).json()
        self.assertEqual(body["payment_status"], "refunded")
        self.assertEqual(body["entitlement"]["status"], "refunded")

        support_body = {
            "client_request_id": "refund-help-1",
            "kind": "refund",
            "message": "Please confirm the status of my refund.",
            "payment_id": payment_id,
        }
        first = self.client.post(
            "/billing/support-requests", json=support_body, headers=self.headers
        )
        repeated = self.client.post(
            "/billing/support-requests", json=support_body, headers=self.headers
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.json()["status"], "open")
        self.assertEqual(
            first.json()["support_request_id"], repeated.json()["support_request_id"]
        )

    def test_failed_generation_releases_reserved_credit(self):
        checkout = self.checkout()
        self.assertEqual(self.webhook(self.checkout_event(checkout)).status_code, 200)
        response = self.generate(FailedExecutor)
        self.assertEqual(response.status_code, 202)
        payment = self.client.get(checkout["status_url"], headers=self.headers).json()
        self.assertEqual(payment["payment_status"], "paid")
        self.assertEqual(payment["entitlement"]["status"], "available")

    def test_invalid_webhook_signature_is_rejected(self):
        response = self.client.post(
            "/billing/webhooks/stripe",
            content=b'{}',
            headers={"Stripe-Signature": "t=1,v1=invalid"},
        )
        self.assertEqual(response.status_code, 400)


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
        self.assertEqual(ready.json()["database_revision"], "20260719_0004")

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
                "payments",
                "entitlements",
                "webhook_events",
                "refunds",
                "support_requests",
            },
        )

        command.downgrade(config, "base")
        self.assertNotIn("runs", inspect(self.engine).get_table_names())


if __name__ == "__main__":
    unittest.main()
