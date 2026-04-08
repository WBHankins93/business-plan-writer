import unittest

from agents.prompt_utils import compact_json, truncate_text


class PromptUtilsTests(unittest.TestCase):
    def test_truncate_text_keeps_bounds(self) -> None:
        text = "A" * 200
        truncated = truncate_text(text, max_chars=100)
        self.assertIn("TRUNCATED", truncated)
        self.assertTrue(truncated.startswith("A"))
        self.assertTrue(truncated.endswith("A" * 25))

    def test_compact_json_truncates_large_payload(self) -> None:
        payload = {"big": "x" * 5000}
        result = compact_json(payload, max_chars=200)
        self.assertLessEqual(len(result), 280)  # includes truncation marker overhead
        self.assertIn("TRUNCATED", result)


if __name__ == "__main__":
    unittest.main()

