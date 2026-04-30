import tempfile
import unittest
from pathlib import Path

from src.repository import get_connection
from src.tossinvest_data import (
    build_toss_market_brief,
    map_toss_news_item,
    parse_toss_index_markdown,
    parse_toss_news_feed_markdown,
    store_toss_index_snapshot,
    store_toss_news_items,
)


INDEX_SAMPLE = """
일별시세

| 일자 | 종가 | 전일대비 | 등락률 | 거래량 | 거래대금 | 시가 | 고가 | 저가 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 04.24 | 6,475.63 | -0.18 | -0.00% | 871,049,000 | 29.8조 | 6,496.10 | 6,516.54 | 6,403.74 |

투자자별 매매 동향 04.24. 16:13 기준
"""

NEWS_SAMPLE = """
인기뉴스 주요뉴스 최신뉴스 급상승뉴스

[![Image 14](https://example.com/a.png) 골드만삭스, SK하닉 목표가 135만→180만원\"주주환원 과소평가\" [SK하이닉스-0.16%](https://www.tossinvest.com/stocks/A000660/order) 뉴스1 ・ 3시간 전](https://www.tossinvest.com/feed/news?contentType=news&contentParams=%7B%22id%22%3A%22news1_6147725%22%7D)
[![Image 15](https://example.com/b.png) 팔란티어, 소프트웨어 비관론 여파 주가 7% 급락 [팔란티어+1.33%](https://www.tossinvest.com/stocks/US20200930014/order) 연합인포맥스 ・ 3시간 전](https://www.tossinvest.com/feed/news?contentType=news&contentParams=%7B%22id%22%3A%22infomax_123%22%7D)
"""


class TossinvestParserTest(unittest.TestCase):
    def test_parse_toss_index_markdown(self) -> None:
        payload = parse_toss_index_markdown("KGG01P", INDEX_SAMPLE)
        self.assertEqual(payload["index_code"], "KGG01P")
        self.assertEqual(payload["close"], 6475.63)
        self.assertEqual(payload["change_pct"], 0.0)
        self.assertEqual(payload["trading_value_text"], "29.8조")

    def test_parse_toss_news_feed_markdown(self) -> None:
        items = parse_toss_news_feed_markdown(NEWS_SAMPLE)
        self.assertGreaterEqual(len(items), 2)
        self.assertIn("골드만삭스", items[0]["headline"])
        self.assertEqual(items[0]["source_name"], "뉴스1")
        self.assertIn("feed/news", items[0]["url"])

    def test_map_toss_news_item_for_us_stock(self) -> None:
        mapped = map_toss_news_item(
            {
                "headline": "팔란티어, 소프트웨어 비관론 여파 주가 7% 급락",
                "source_name": "연합인포맥스",
                "published_text": "3시간 전",
                "url": "https://www.tossinvest.com/feed/news?contentType=news&id=1",
                "source": "tossinvest_feed",
                "collected_at": "2026-04-24T00:00:00+00:00",
            }
        )
        self.assertIn("PLTR", mapped["mapped_symbols"])
        self.assertIn("software", mapped["mapped_themes"])

    def test_map_toss_news_item_expands_theme_keywords(self) -> None:
        mapped = map_toss_news_item(
            {
                "headline": "오라클, 데이터센터 전력·보안 투자 확대",
                "source_name": "로이터",
                "published_text": "1시간 전",
                "url": "https://www.tossinvest.com/feed/news?contentType=news&id=2",
                "source": "tossinvest_feed",
                "collected_at": "2026-04-24T00:00:00+00:00",
            }
        )
        self.assertIn("ai_infra", mapped["mapped_themes"])
        self.assertIn("security", mapped["mapped_themes"])
        self.assertIn("power", mapped["mapped_themes"])

    def test_map_toss_news_item_marks_rumor(self) -> None:
        mapped = map_toss_news_item(
            {
                "headline": "(카더라) 오라클, 슈퍼마이크로 계약 취소설",
                "source_name": "블루핀",
                "published_text": "1시간 전",
                "url": "https://www.tossinvest.com/feed/news?contentType=news&id=rumor",
                "source": "tossinvest_feed",
                "collected_at": "2026-04-24T00:00:00+00:00",
            }
        )
        self.assertTrue(mapped["is_rumor"])

    def test_build_toss_market_brief_from_stored_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "stock_agent.db"
            conn = get_connection(db_path)
            store_toss_index_snapshot(
                conn,
                {
                    "index_code": "COMP.NAI",
                    "index_name": "나스닥",
                    "collected_at": "2026-04-24T00:00:00+00:00",
                    "close": 24438.50,
                    "change_value": -219.06,
                    "change_pct": -0.88,
                    "volume": 6705087891.0,
                    "trading_value_text": "-",
                    "open": 24553.74,
                    "high": 24664.86,
                    "low": 24209.73,
                    "source": "tossinvest",
                    "note": "test",
                },
            )
            store_toss_news_items(
                conn,
                [
                    {
                        "headline": "팔란티어, 소프트웨어 비관론 여파 주가 7% 급락",
                        "source_name": "연합인포맥스",
                        "published_text": "3시간 전",
                        "url": "https://www.tossinvest.com/feed/news?contentType=news&id=1",
                        "source": "tossinvest_feed",
                        "collected_at": "2026-04-24T00:00:00+00:00",
                    }
                ],
            )
            conn.commit()
            conn.close()

            text = build_toss_market_brief(db_path)
            self.assertIn("[토스증권 미국장 보조지표]", text)
            self.assertIn("나스닥", text)
            self.assertIn("팔란티어", text)
            self.assertIn("관련종목: PLTR", text)


if __name__ == "__main__":
    unittest.main()
