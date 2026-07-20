import json
import re
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import BackgroundTasks, HTTPException

from intake.schema import SCHEMA
from web_api.app import GeneratePlanRequest, generate_plan, get_demo_intake, get_run


ROOT = Path(__file__).resolve().parents[1]
DEMO_INTAKE = ROOT / "sample_intake" / "fictional_bywater_grounds.json"
WEB_PAGE = ROOT / "web" / "app" / "intake" / "page.tsx"


class FakeRunStore:
    def __init__(self) -> None:
        self.run = None
        self.audit_events = []

    def create(self, *, run_id, client_slug, intake, artifact_path) -> None:
        now = datetime(2026, 7, 19, 12, 0, 0)
        self.run = SimpleNamespace(
            id=run_id,
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

    def test_user_entered_business_name_is_preserved_and_slugged(self) -> None:
        intake = json.loads(json.dumps(self.demo))
        intake["business_information"]["business_name"] = "Lena's Cakes & Co."
        store = FakeRunStore()

        with patch("web_api.app._store", return_value=store):
            response = generate_plan(GeneratePlanRequest(intake=intake), BackgroundTasks())

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
            generate_plan(
                GeneratePlanRequest(intake={"business_information": {"business_name": "Acme"}}),
                BackgroundTasks(),
            )

        self.assertEqual(caught.exception.status_code, 422)
        detail = caught.exception.detail
        self.assertEqual(detail["code"], "invalid_intake")
        self.assertTrue(any(item["field"] == "business_information.industry" for item in detail["fields"]))

    def test_demo_request_queue_poll_result_contract(self) -> None:
        store = FakeRunStore()
        background = BackgroundTasks()
        with patch("web_api.app._store", return_value=store):
            queued = generate_plan(GeneratePlanRequest(intake=self.demo), background)

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

            polled = get_run(queued["run_id"])

        self.assertEqual(polled["status"], "succeeded")
        self.assertEqual(polled["result"]["draft_markdown"], "# Bywater Grounds")
        self.assertTrue(all(item["status"] == "complete" for item in polled["progress"]))


if __name__ == "__main__":
    unittest.main()
