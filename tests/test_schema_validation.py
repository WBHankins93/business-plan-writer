import unittest

from intake.schema import validate_intake


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


if __name__ == "__main__":
    unittest.main()

