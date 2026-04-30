import unittest
from unittest.mock import patch

from src.main import build_technical_snapshot as main_build_technical_snapshot
from src.technical_snapshot import build_technical_snapshot


class TechnicalSnapshotModuleTest(unittest.TestCase):
    def test_technical_snapshot_lives_in_dedicated_module_and_stays_reexported(self):
        closes = [100 + idx for idx in range(60)]
        with patch("src.technical_snapshot.fetch_price_history", return_value=closes):
            direct = build_technical_snapshot("NVDA")
        with patch("src.technical_snapshot.fetch_price_history", return_value=closes):
            reexported = main_build_technical_snapshot("NVDA")

        self.assertEqual(direct, reexported)
        self.assertEqual(direct["symbol"], "NVDA")
        self.assertIn("차트 한줄", direct["brief_line"])
        self.assertIn("RSI", direct["brief_line"])
        self.assertIn(direct["action_bias"], direct["brief_line"])


if __name__ == "__main__":
    unittest.main()
