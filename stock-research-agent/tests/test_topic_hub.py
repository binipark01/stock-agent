import json
import tempfile
import unittest
from pathlib import Path

from src.main import build_response, infer_mode, run_ingest
from src.repository import get_connection, insert_earnings_event, insert_news_item, insert_price_snapshot
from src.topic_hub import list_stock_topics, peek_topic


class TopicHubModeTest(unittest.TestCase):
    def test_list_stock_topics_builds_fincept_style_topic_names(self) -> None:
        topics = list_stock_topics(["NVDA"])
        self.assertIn("market:quote:NVDA", topics)
        self.assertIn("news:symbol:NVDA", topics)
        self.assertIn("filing:sec:NVDA", topics)
        self.assertIn("options:chain:NVDA", topics)
        self.assertIn("social:threads:NVDA", topics)
        self.assertIn("earnings:calendar:NVDA", topics)

    def test_peek_topic_returns_cached_quote_news_and_earnings(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "stock_agent.db"
            conn = get_connection(db_path)
            insert_price_snapshot(conn, "NVDA", "2026-04-29T00:00:00+00:00", 900.0, 1.2, "test", "good tape")
            insert_news_item(conn, "NVDA", "엔비디아 데이터센터 수요 확대", "https://example.com/nvda", "test", "2026-04-29T00:01:00+00:00")
            insert_earnings_event(conn, "NVDA", "2026-05-20", "after_close", "test", "시간 확정", "2026-04-29T00:02:00+00:00")
            conn.commit()
            conn.close()

            quote = peek_topic("market:quote:NVDA", db_path=db_path)
            news = peek_topic("news:symbol:NVDA", db_path=db_path)
            earnings = peek_topic("earnings:calendar:NVDA", db_path=db_path)

        self.assertEqual(quote["value"]["price"], 900.0)
        self.assertEqual(news["value"]["headline"], "엔비디아 데이터센터 수요 확대")
        self.assertEqual(earnings["value"]["earnings_date"], "2026-05-20")

    def test_topic_hub_mode_outputs_topics_and_peek_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "stock_agent.db"
            run_ingest(["NVDA"], db_path=db_path)
            payload = build_response(
                json.dumps({"request": "NVDA 데이터허브 topic 보여줘", "symbols": ["NVDA"], "db_path": str(db_path)}, ensure_ascii=False)
            )
        self.assertEqual(payload["mode"], "topic_hub")
        self.assertTrue(any("market:quote:NVDA" in item for item in payload["focus"]))
        self.assertTrue(any("news:symbol:NVDA" in item for item in payload["focus"]))
        self.assertTrue(any("peek" in item.lower() or "age" in item.lower() for item in payload["focus"]))

    def test_infer_mode_routes_topic_hub_requests(self) -> None:
        self.assertEqual(infer_mode("NVDA 데이터허브 topic 보여줘"), "topic_hub")
        self.assertEqual(infer_mode("NVDA list topics"), "topic_hub")


if __name__ == "__main__":
    unittest.main()
