import tempfile
import unittest
from pathlib import Path

from src.repository import get_connection
from src.tossinvest_data import (
    build_toss_day_market_quote_report,
    build_toss_market_brief,
    extract_toss_stock_code_from_markdown,
    fetch_toss_day_market_quote,
    map_toss_news_item,
    parse_toss_day_market_markdown,
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

DAY_MARKET_SAMPLE = """
팔란티어 PLTR
212,133원
$142.87
데이마켓 -4,691원 (2.16%)
애프터마켓에서 -5,879원 (2.71%) 마감
13:27:54
거래량 319,968
"""

RDW_STOCK_PAGE_SAMPLE = """
Title: 레드와이어(RDW) 실시간 주가를 확인해보세요
# 13,719원 +7.36% | 레드와이어
레드와이어 RDW
13,719원 $9.33
지난 정규장보다 +941원 (7.36%)
01:30:10
거래량 6,787,335
"""

RDW_SEARCH_SAMPLE = """
[레드와이어(RDW) 실시간 주가](https://www.tossinvest.com/stocks/US20210903005)
[레드와이어 커뮤니티](https://www.tossinvest.com/stocks/US20210903005/community?feedSortType=POPULAR)
"""

ACME_SEARCH_SAMPLE = """
[에이씨미(ACME) 실시간 주가](https://www.tossinvest.com/stocks/US20260101001)
[에이씨미 커뮤니티](https://www.tossinvest.com/stocks/US20260101001/community?feedSortType=POPULAR)
"""


class TossinvestParserTest(unittest.TestCase):
    def test_parse_toss_index_markdown(self) -> None:
        payload = parse_toss_index_markdown("KGG01P", INDEX_SAMPLE)
        self.assertEqual(payload["index_code"], "KGG01P")
        self.assertEqual(payload["close"], 6475.63)
        self.assertEqual(payload["change_pct"], 0.0)
        self.assertEqual(payload["trading_value_text"], "29.8조")

    def test_parse_toss_day_market_markdown(self) -> None:
        payload = parse_toss_day_market_markdown(DAY_MARKET_SAMPLE, symbol="PLTR", source_url="https://www.tossinvest.com/stocks/US20200930014/order")
        self.assertEqual(payload["symbol"], "PLTR")
        self.assertEqual(payload["session_label"], "데이마켓")
        self.assertEqual(payload["usd_price"], 142.87)
        self.assertEqual(payload["krw_price"], 212133)
        self.assertEqual(payload["change_krw"], -4691)
        self.assertEqual(payload["change_pct"], -2.16)
        self.assertEqual(payload["last_trade_time"], "13:27:54")
        self.assertEqual(payload["volume"], 319968)

    def test_fetch_toss_day_market_quote_uses_known_stock_code(self) -> None:
        seen_urls = []

        def fake_fetch(url: str) -> str:
            seen_urls.append(url)
            return DAY_MARKET_SAMPLE

        quote = fetch_toss_day_market_quote("PLTR", fetcher=fake_fetch)
        self.assertTrue(quote["available"])
        self.assertIn("US20200930014", seen_urls[0])
        self.assertEqual(quote["usd_price"], 142.87)

    def test_extract_toss_stock_code_from_search_markdown(self) -> None:
        self.assertEqual(extract_toss_stock_code_from_markdown(RDW_SEARCH_SAMPLE, "RDW"), "US20210903005")

    def test_fetch_toss_day_market_quote_resolves_unknown_stock_code(self) -> None:
        seen_quote_urls = []
        seen_resolver_urls = []

        def fake_quote_fetch(url: str) -> str:
            seen_quote_urls.append(url)
            return RDW_STOCK_PAGE_SAMPLE

        def fake_resolver_fetch(url: str) -> str:
            seen_resolver_urls.append(url)
            return ACME_SEARCH_SAMPLE

        quote = fetch_toss_day_market_quote("ACME", fetcher=fake_quote_fetch, resolver_fetcher=fake_resolver_fetch, cache_path=False)

        self.assertTrue(quote["available"])
        self.assertEqual(quote["symbol"], "ACME")
        self.assertEqual(quote["toss_code"], "US20260101001")
        self.assertEqual(quote["usd_price"], 9.33)
        self.assertEqual(quote["krw_price"], 13719)
        self.assertEqual(quote["change_pct"], 7.36)
        self.assertEqual(quote["last_trade_time"], "01:30:10")
        self.assertIn("stocks/US20260101001", seen_quote_urls[0])
        self.assertTrue(seen_resolver_urls)

    def test_build_toss_day_market_quote_report_from_runtime_markdown(self) -> None:
        report = build_toss_day_market_quote_report(
            "PLTR 데이마켓 가격",
            symbols=["PLTR"],
            runtime_context={"toss_day_market_markdown": {"PLTR": DAY_MARKET_SAMPLE}},
        )
        self.assertIn("PLTR $142.87", report["summary"])
        self.assertIn("호가·스프레드", " ".join(report["next_actions"]))
        self.assertIn("Yahoo", " ".join(report["next_actions"]))

    def test_build_toss_day_market_quote_report_can_resolve_multiple_symbols(self) -> None:
        def fake_quote_fetch(url: str) -> str:
            if "US20210903005" in url:
                return RDW_STOCK_PAGE_SAMPLE
            if "US20200930014" in url:
                return DAY_MARKET_SAMPLE
            raise AssertionError(url)

        def fake_resolver_fetch(url: str) -> str:
            return RDW_SEARCH_SAMPLE

        report = build_toss_day_market_quote_report(
            "RDW PLTR 토스 주가",
            symbols=["RDW", "PLTR"],
            runtime_context={"toss_fetcher": fake_quote_fetch, "toss_resolver_fetcher": fake_resolver_fetch, "toss_code_cache_path": False},
        )

        self.assertIn("RDW $9.33", report["summary"])
        self.assertEqual([quote["symbol"] for quote in report["quotes"]], ["RDW", "PLTR"])
        self.assertTrue(any("RDW" in line and "13,719원" in line for line in report["focus_lines"]))
        self.assertTrue(any("PLTR" in line and "$142.87" in line for line in report["focus_lines"]))

    def test_build_toss_day_market_quote_report_uses_resolver_fetcher_for_unknown_symbols(self) -> None:
        seen_resolver_urls = []

        def fake_quote_fetch(url: str) -> str:
            self.assertIn("US20260101001", url)
            return RDW_STOCK_PAGE_SAMPLE

        def fake_resolver_fetch(url: str) -> str:
            seen_resolver_urls.append(url)
            return ACME_SEARCH_SAMPLE

        report = build_toss_day_market_quote_report(
            "ACME 토스 스냅샷",
            symbols=["ACME"],
            runtime_context={"toss_fetcher": fake_quote_fetch, "toss_resolver_fetcher": fake_resolver_fetch, "toss_code_cache_path": False},
        )

        self.assertIn("ACME $9.33", report["summary"])
        self.assertEqual(report["quotes"][0]["toss_code"], "US20260101001")
        self.assertTrue(seen_resolver_urls)

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
