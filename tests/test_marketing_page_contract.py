import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MARKETING_PAGE = ROOT / "web" / "app" / "page.tsx"
ANALYTICS_LINK = ROOT / "web" / "app" / "components" / "AnalyticsLink.tsx"
SAMPLE_SOURCE = ROOT / "web" / "public" / "samples" / "bywater-grounds-sample-plan.md"


class MarketingPageContractTests(unittest.TestCase):
    def test_public_page_has_required_offer_and_trust_sections(self) -> None:
        source = MARKETING_PAGE.read_text(encoding="utf-8")

        for section_id in ["sample", "process", "pricing", "trust", "privacy", "support"]:
            self.assertIn(f'id="{section_id}"', source)

        self.assertIn("$497", source)
        self.assertIn("One consolidated revision round", source)
        self.assertIn("not reviewed by a human expert", source)
        self.assertIn("does not guarantee financing", source)

    def test_account_start_url_defaults_to_intake_without_adding_auth(self) -> None:
        source = MARKETING_PAGE.read_text(encoding="utf-8")

        self.assertIn('NEXT_PUBLIC_ACCOUNT_START_URL || "/intake"', source)
        self.assertNotIn("signIn(", source)
        self.assertNotIn("checkout", source.lower())

    def test_required_analytics_events_are_emitted(self) -> None:
        page_source = MARKETING_PAGE.read_text(encoding="utf-8")
        analytics_source = ANALYTICS_LINK.read_text(encoding="utf-8")

        for event_name in ["cta_click", "sample_download", "account_start"]:
            self.assertIn(f'"{event_name}"', page_source + analytics_source)

        self.assertIn("window.dataLayer?.push(payload)", analytics_source)
        self.assertIn("business-plan-writer:analytics", analytics_source)

    def test_public_sample_is_explicitly_fictional(self) -> None:
        source = SAMPLE_SOURCE.read_text(encoding="utf-8")

        self.assertIn("entirely fictional", source)
        self.assertIn("not based on external research", source)
        self.assertIn("was not reviewed by a human", source)


if __name__ == "__main__":
    unittest.main()
