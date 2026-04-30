import json
import tempfile
import unittest
from pathlib import Path

from src.main import build_response, run_ingest
from src.repository import get_connection, insert_news_item
from src.earnings_preview import build_earnings_preview


class EarningsPreviewTest(unittest.TestCase):
    def test_build_earnings_preview_for_nvda(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "stock_agent.db"
            run_ingest(["NVDA"], db_path=db_path)
            conn = get_connection(db_path)
            insert_news_item(
                conn,
                symbol="NVDA",
                headline="엔비디아, hyperscaler capex 기대 유지",
                url="https://example.com/nvda-news",
                source="test",
                collected_at="2026-04-24T00:00:00+00:00",
            )
            conn.commit()
            conn.close()

            preview = build_earnings_preview("NVDA", db_path=db_path)

            self.assertEqual(preview["symbol"], "NVDA")
            self.assertIn("bull_case", preview)
            self.assertIn("bear_case", preview)
            self.assertIn("key_metrics", preview)
            self.assertIn("questions_for_call", preview)
            self.assertGreaterEqual(len(preview["questions_for_call"]), 5)
            self.assertTrue(any("data center" in item.lower() or "hyperscaler" in item.lower() for item in preview["key_metrics"] + preview["questions_for_call"]))

    def test_build_response_earnings_preview_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "stock_agent.db"
            run_ingest(["MSFT", "AMZN"], db_path=db_path)
            raw = json.dumps(
                {
                    "mode": "earnings_preview",
                    "symbols": ["MSFT", "AMZN"],
                    "db_path": str(db_path),
                    "request": "실적 프리뷰 만들어줘",
                },
                ensure_ascii=False,
            )

            payload = build_response(raw)

            self.assertEqual(payload["mode"], "earnings_preview")
            self.assertTrue(any("Bull case" in item or "Bear case" in item for item in payload["focus"]))
            self.assertTrue(any("Questions" in item or "질문" in item for item in payload["focus"]))


if __name__ == "__main__":
    unittest.main()
