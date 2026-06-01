import json
import tempfile
from pathlib import Path

from src.main import build_response, run_ingest, build_brief_from_db
from src.repository import get_connection, fetch_upcoming_earnings
from src.tossinvest_data import store_toss_index_snapshot, store_toss_news_items
from src.saveticker_data import store_saveticker_items

class SocialModeCases:
            def test_social_search_mode_uses_seed_accounts_and_returns_recent_hits(self) -> None:
                from unittest.mock import patch

                fake_hits = [
                    {
                        "handle": "fintwt",
                        "display_name": "Fintwit",
                        "date": "04/25/26",
                        "days_ago": 2,
                        "post_url": "https://www.threads.com/@fintwt/post/demo",
                        "text": "BMNR 최근 수급이 다시 붙는 중",
                        "query": "BMNR",
                    }
                ]
                with patch("src.main.search_threads_seed_accounts", return_value=fake_hits):
                    payload = build_response(
                        json.dumps(
                            {
                                "request": "BMNR 스레드 찾아줘",
                            },
                            ensure_ascii=False,
                        )
                    )
                self.assertEqual(payload["mode"], "social_search")
                self.assertTrue(any(item.startswith("최근 Threads 반응:") for item in payload["focus"]))
                self.assertTrue(any("fintwt" in item for item in payload["focus"]))
                self.assertIn("seed 계정", payload["summary"])

            def test_social_search_mode_reports_when_no_recent_hits_exist(self) -> None:
                from unittest.mock import patch

                with patch("src.main.search_threads_seed_accounts", return_value=[]):
                    payload = build_response(
                        json.dumps(
                            {
                                "request": "BMNR 스레드 찾아줘",
                            },
                            ensure_ascii=False,
                        )
                    )
                self.assertEqual(payload["mode"], "social_search")
                self.assertTrue(any(item.startswith("최근 Threads 반응:") for item in payload["focus"]))
                self.assertTrue(any("최근 14일" in item for item in payload["focus"]))

            def test_stock_news_request_includes_threads_seed_social_signal(self) -> None:
                from unittest.mock import patch

                fake_hits = [
                    {
                        "handle": "fintwt",
                        "display_name": "Fintwit",
                        "date": "04/25/26",
                        "days_ago": 2,
                        "post_url": "https://www.threads.com/@fintwt/post/demo-news",
                        "text": "BMNR 최근 수급이 다시 붙는 중",
                        "query": "BMNR",
                    }
                ]
                with patch("src.main.search_threads_seed_accounts", return_value=fake_hits):
                    payload = build_response("비트마인 소식알려줘")

                self.assertEqual(payload["mode"], "brief")
                self.assertEqual(payload["symbols"], ["BMNR"])
                self.assertTrue(any(item.startswith("Social Signal:") for item in payload["focus"]))
                self.assertTrue(any("@fintwt" in item for item in payload["focus"]))

            def test_stock_news_request_reports_empty_threads_seed_social_signal(self) -> None:
                from unittest.mock import patch

                with patch("src.main.search_threads_seed_accounts", return_value=[]):
                    payload = build_response("비트마인 소식알려줘")

                self.assertEqual(payload["mode"], "brief")
                self.assertTrue(any(item == "Social Signal: seed 계정 최근 14일 BMNR 언급 없음" for item in payload["focus"]))
