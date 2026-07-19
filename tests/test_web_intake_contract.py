import json
import re
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import BackgroundTasks, HTTPException

from intake.schema import SCHEMA
from web_api.app import _queue_plan, _run_payload, get_demo_intake


ROOT = Path(__file__).resolve().parents[1]
DEMO_INTAKE = ROOT / "sample_intake" / "fictional_bywater_grounds.json"
WEB_PAGE = ROOT / "web" / "components" / "intake-workspace.tsx"
WEB_AUTH_MIDDLEWARE = ROOT / "web" / "lib" / "supabase" / "middleware.ts"


class FakeRunStore:
    def __init__(self) -> None:
        self.run = None
        self.audit_events = []

    def create(
        self, *, run_id, client_slug, intake, artifact_path, owner_id=None, project_id=None
    ) -> None:
        now = datetime(2026, 7, 19, 12, 0, 0)
        self.run = SimpleNamespace(
            id=run_id,
            owner_id=owner_id,
            project_id=project_id,
            client_slug=client_slug,
            status="queued",
            intake_json=intake,
            artifact_path=artifact_path,
            progress_json=[],
            result_json=None,
            error_code=None,
            error_message=None,
            started_at=None,
            finished_at=None,
            created_at=now,
            updated_at=now,
        )

    def get(self, _run_id):
        return self.run

    def events(self, _run_id):
        return self.audit_events


class WebIntakeContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.demo = json.loads(DEMO_INTAKE.read_text(encoding="utf-8"))

    def test_demo_endpoint_returns_complete_fixture(self) -> None:
        self.assertEqual(get_demo_intake(), self.demo)

    def test_web_question_map_matches_schema_paths_and_tiers(self) -> None:
        source = WEB_PAGE.read_text(encoding="utf-8")
        mapped_fields = {
            (section, name): int(tier)
            for section, name, tier in re.findall(
                r'\{ section: "([^"]+)", name: "([^"]+)"[^\n]+?tier: ([123])',
                source,
            )
        }
        schema_fields = {(field.section, field.name): field.tier for field in SCHEMA}

        self.assertEqual(mapped_fields, schema_fields)

    def test_web_autosave_has_visible_retry_and_no_shared_api_key(self) -> None:
        source = WEB_PAGE.read_text(encoding="utf-8")
        self.assertIn('method: "PUT"', source)
        self.assertIn("Retry save", source)
        self.assertIn("Changes are still on this page", source)
        self.assertNotIn("NEXT_PUBLIC_API_KEY", source)

    def test_private_page_guard_validates_claims(self) -> None:
        source = WEB_AUTH_MIDDLEWARE.read_text(encoding="utf-8")
        self.assertIn('const PRIVATE_PATHS = ["/projects"]', source)
        self.assertIn("supabase.auth.getClaims()", source)
        self.assertNotIn("auth.getSession()", source)

    def test_user_entered_business_name_is_preserved_and_slugged(self) -> None:
        intake = json.loads(json.dumps(self.demo))
        intake["business_information"]["business_name"] = "Lena's Cakes & Co."
        store = FakeRunStore()

        with patch("web_api.app._store", return_value=store):
            response = _queue_plan(
                intake=intake,
                background_tasks=BackgroundTasks(),
                owner_id="user-a",
                project_id="project-a",
                status_prefix="/runs",
            )

        self.assertEqual(response["client_slug"], "lena-s-cakes-co")
        self.assertEqual(store.run.intake_json["business_information"]["business_name"], "Lena's Cakes & Co.")
        self.assertNotIn("_meta", store.run.intake_json)
        self.assertEqual(
            {(field.section, field.name) for field in SCHEMA},
            {
                (section, name)
                for section, values in store.run.intake_json.items()
                for name in values
            },
        )

    def test_validation_errors_prevent_incomplete_request_from_queueing(self) -> None:
        with self.assertRaises(HTTPException) as caught:
            _queue_plan(
                intake={"business_information": {"business_name": "Acme"}},
                background_tasks=BackgroundTasks(),
                owner_id="user-a",
                project_id="project-a",
                status_prefix="/runs",
            )

        self.assertEqual(caught.exception.status_code, 422)
        detail = caught.exception.detail
        self.assertEqual(detail["code"], "invalid_intake")
        self.assertTrue(any(item["field"] == "business_information.industry" for item in detail["fields"]))

    def test_demo_request_queue_poll_result_contract(self) -> None:
        store = FakeRunStore()
        background = BackgroundTasks()
        with patch("web_api.app._store", return_value=store):
            queued = _queue_plan(
                intake=self.demo,
                background_tasks=background,
                owner_id="user-a",
                project_id="project-a",
                status_prefix="/runs",
            )

            self.assertEqual(queued["status"], "queued")
            self.assertEqual(len(queued["progress"]), 5)
            self.assertEqual(len(background.tasks), 1)

            store.run.status = "succeeded"
            store.run.progress_json = [
                {"step": index + 1, "name": name, "status": "complete"}
                for index, name in enumerate(["Validation", "Market", "Financials", "Draft", "Review"])
            ]
            store.run.result_json = {
                "status": "succeeded",
                "draft_markdown": "# Bywater Grounds",
                "progress": store.run.progress_json,
            }
            store.run.created_at = datetime(2026, 7, 19, 12, 0, 0)
            store.run.updated_at = datetime(2026, 7, 19, 12, 1, 0)

            polled = _run_payload(store.run, export_prefix=f"/runs/{queued['run_id']}/artifacts")

        self.assertEqual(polled["status"], "succeeded")
        self.assertEqual(polled["result"]["draft_markdown"], "# Bywater Grounds")
        self.assertTrue(all(item["status"] == "complete" for item in polled["progress"]))


if __name__ == "__main__":
    unittest.main()
