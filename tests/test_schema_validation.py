import json
import unittest
from pathlib import Path

from intake.schema import SCHEMA, intake_request_errors, validate_intake


ROOT = Path(__file__).resolve().parents[1]
DEMO_INTAKE = ROOT / "sample_intake" / "fictional_bywater_grounds.json"


def _base_intake() -> dict:
    return {
        "business_information": {
            "business_name": "Acme Health",
            "owner_name": "A. Owner",
            "ownership_structure": "LLC",
            "industry": "Healthcare",
            "funding_amount": "$120,000",
        },
        "management_details": {"owner_background": "10 years in care delivery"},
        "product_service_summary": {"services_offered": "Outpatient therapy services"},
        "market_analysis": {"geographic_market": "Austin, TX", "target_customer": "Adults 25-55"},
        "advertising_strategy": {"initial_marketing": "Referral network", "marketing_budget": "$2,500"},
        "competition": {"main_competitors": "Local clinics", "competitive_edge": "Faster access"},
        "strategy_and_implementation": {"business_strategy": "Neighborhood-focused model"},
        "milestones": {"twelve_month_goals": "Open clinic and reach 80 active clients"},
        "financial_information": {
            "cash_flow_narrative": "Receivables clear in <30 days",
            "financial_plan_summary": "Conservative ramp",
        },
        "income": {
            "beginning_balance": "$50,000",
            "client_volume": "40 clients/month",
            "monthly_revenue_projection": "$20,000",
            "annual_revenue_projection": "$240,000",
        },
        "expenses": {
            "payroll": "$8,000",
            "rent_utilities": "$2,500",
            "advertising_expense": "$1,200",
            "taxes": "$1,000",
        },
    }


class SchemaValidationTests(unittest.TestCase):
    def test_complete_demo_intake_matches_canonical_contract(self) -> None:
        intake = json.loads(DEMO_INTAKE.read_text(encoding="utf-8"))

        _, report = validate_intake(intake)

        self.assertEqual(intake_request_errors(intake), [])
        self.assertEqual(report.missing_tier1, [])
        self.assertEqual(report.typed_issues, [])
        self.assertEqual(report.cross_field_issues, [])
        for field_def in SCHEMA:
            self.assertIn(field_def.section, intake)
            self.assertIn(field_def.name, intake[field_def.section])

    def test_incomplete_intake_returns_human_readable_field_errors(self) -> None:
        errors = intake_request_errors({"business_information": {"business_name": "Acme"}})

        by_field = {error["field"]: error for error in errors}
        self.assertEqual(by_field["business_information.owner_name"]["label"], "Owner Name")
        self.assertEqual(
            by_field["product_service_summary.services_offered"]["message"],
            "Services / Products is required.",
        )

    def test_numeric_financial_fields_accept_numbers(self) -> None:
        intake = _base_intake()
        intake["business_information"]["funding_amount"] = 120000
        intake["income"]["beginning_balance"] = 50000.50
        intake["income"]["monthly_revenue_projection"] = 20000
        intake["income"]["annual_revenue_projection"] = 240000

        _, report = validate_intake(intake)

        self.assertEqual(report.typed_issues, [])
        self.assertEqual(report.cross_field_issues, [])

    def test_typed_validation_detects_non_numeric_values(self) -> None:
        intake = _base_intake()
        intake["income"]["monthly_revenue_projection"] = "high soon"

        _, report = validate_intake(intake)

        self.assertTrue(
            any("income.monthly_revenue_projection" in issue for issue in report.typed_issues)
        )

    def test_cross_field_validation_detects_large_mismatch(self) -> None:
        intake = _base_intake()
        intake["income"]["monthly_revenue_projection"] = "$50,000"
        intake["income"]["annual_revenue_projection"] = "$240,000"

        _, report = validate_intake(intake)

        self.assertTrue(any("appear inconsistent" in issue for issue in report.cross_field_issues))

    def test_month_by_month_projection_does_not_create_false_mismatch(self) -> None:
        intake = _base_intake()
        intake["income"]["monthly_revenue_projection"] = "M1 $10,000; M2 $12,000; M12 $30,000"
        intake["income"]["annual_revenue_projection"] = "$240,000"

        _, report = validate_intake(intake)

        self.assertEqual(report.cross_field_issues, [])

    def test_year_label_is_not_treated_as_the_annual_amount(self) -> None:
        intake = _base_intake()
        intake["income"]["monthly_revenue_projection"] = "$20,000"
        intake["income"]["annual_revenue_projection"] = "Year 1: $240,000; Year 2: $360,000"

        _, report = validate_intake(intake)

        self.assertEqual(report.typed_issues, [])
        self.assertEqual(report.cross_field_issues, [])


if __name__ == "__main__":
    unittest.main()
