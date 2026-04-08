import subprocess
import sys
import unittest


class CLITests(unittest.TestCase):
    def test_main_help_returns_success(self) -> None:
        proc = subprocess.run(
            [sys.executable, "main.py", "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("--allow-unready", proc.stdout)


if __name__ == "__main__":
    unittest.main()

