import json
import tempfile
import unittest
from pathlib import Path

from src.threads_social import load_threads_view_targets


class ThreadsViewTargetsTest(unittest.TestCase):
    def test_loads_bullish_bee_view_target(self):
        targets = load_threads_view_targets()
        bullish_bee = next((target for target in targets if target["handle"] == "bullish_bee"), None)

        self.assertIsNotNone(bullish_bee)
        self.assertEqual(bullish_bee["display_name"], "양봉업자")
        self.assertEqual(bullish_bee["category"], "trader")
        self.assertEqual(bullish_bee["priority"], "high")
        self.assertIn("technical_analysis_style", bullish_bee["view_learning_focus"])

    def test_normalizes_at_prefixed_handles(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "targets.json"
            path.write_text(
                json.dumps(
                    {
                        "targets": [
                            {
                                "handle": "@bullish_bee",
                                "display_name": "양봉업자",
                                "category": "trader",
                                "priority": "high",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            targets = load_threads_view_targets(path)

        self.assertEqual(targets[0]["handle"], "bullish_bee")
        self.assertEqual(targets[0]["display_name"], "양봉업자")


if __name__ == "__main__":
    unittest.main()
