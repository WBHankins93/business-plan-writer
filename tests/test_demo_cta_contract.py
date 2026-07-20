import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_FIXTURE = ROOT / "sample_intake" / "fictional_bywater_grounds.json"
WEB_FIXTURE = ROOT / "web" / "fixtures" / "fictional_bywater_grounds.json"
CTA_SOURCE = ROOT / "web" / "components" / "intake-workspace.tsx"


class DemoCtaContractTests(unittest.TestCase):
    def test_bundled_web_fixture_matches_canonical_demo_intake(self) -> None:
        canonical = json.loads(CANONICAL_FIXTURE.read_text(encoding="utf-8"))
        bundled = json.loads(WEB_FIXTURE.read_text(encoding="utf-8"))

        self.assertEqual(bundled, canonical)

    def test_demo_cta_loads_the_bundled_fixture_without_fetching(self) -> None:
        source = CTA_SOURCE.read_text(encoding="utf-8")
        load_demo = source.split("const loadDemo", maxsplit=1)[1].split(
            "const pollRun", maxsplit=1
        )[0]

        self.assertIn("canonicalIntake(DEMO_INTAKE)", load_demo)
        self.assertNotIn("fetch(", load_demo)


if __name__ == "__main__":
    unittest.main()
