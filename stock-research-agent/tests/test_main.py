import json
import tempfile
import unittest
from pathlib import Path

from src.main import build_response, run_ingest, build_brief_from_db
from src.repository import get_connection, fetch_upcoming_earnings
from src.tossinvest_data import store_toss_index_snapshot, store_toss_news_items
from src.saveticker_data import store_saveticker_items


class StockResearchAgentTest(unittest.TestCase):
    def test_sector_strength_mode_uses_runtime_quotes_for_intraday_alert(self) -> None:
        quotes = {
            "SPY": {"symbol": "SPY", "price": 500.0, "previous_close": 497.51, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "QQQ": {"symbol": "QQQ", "price": 430.0, "previous_close": 425.74, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "XLK": {"symbol": "XLK", "price": 210.0, "previous_close": 205.88, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "XLU": {"symbol": "XLU", "price": 70.0, "previous_close": 71.43, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "^VIX": {"symbol": "^VIX", "price": 17.0, "previous_close": 16.5, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
        }

        payload = build_response(
            json.dumps({"request": "장중 섹터 강약 5분 알림", "mode": "sector_strength"}, ensure_ascii=False),
            runtime_context={"sector_quotes": quotes, "collected_at": "2026-04-30T13:35:00+00:00"},
        )

        self.assertEqual(payload["mode"], "sector_strength")
        self.assertIn("섹터 강약", payload["summary"])
        self.assertTrue(any("ETF 시장 참고" in item and "XLK" in item and "XLU" in item for item in payload["focus"]))
        self.assertIn("sector_strength", payload["features"])
        self.assertEqual(payload["data"]["sector_strength"]["strong"][0]["symbol"], "XLK")

    def test_infers_sector_strength_from_korean_sector_prompt(self) -> None:
        payload = build_response(
            "장중 섹터별 강한 섹터 약한 섹터 알려줘",
            runtime_context={
                "sector_quotes": {
                    "SPY": {"symbol": "SPY", "price": 500.0, "previous_close": 500.0},
                    "QQQ": {"symbol": "QQQ", "price": 430.0, "previous_close": 430.0},
                    "XLK": {"symbol": "XLK", "price": 210.0, "previous_close": 207.92},
                }
            },
        )

        self.assertEqual(payload["mode"], "sector_strength")

    def test_saveticker_breaking_mode_returns_only_important_alerts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "stock_agent.db"
            conn = get_connection(db_path)
            store_saveticker_items(
                conn,
                [
                    {
                        "headline": "테슬라, 로보택시 생산 일정 앞당김",
                        "kind": "속보",
                        "published_text": "8분 전",
                        "tickers": ["TSLA"],
                        "popularity_text": "12.4K",
                        "source": "saveticker_api:SAVE:오선",
                        "collected_at": "2026-04-30T00:00:00+00:00",
                        "url": "https://www.saveticker.com/app/news/tsla",
                    },
                    {
                        "headline": "유럽 통신주 분기 실적 발표",
                        "kind": "정보",
                        "published_text": "6분 전",
                        "tickers": [],
                        "popularity_text": "1.0K",
                        "source": "saveticker_api:reuters",
                        "collected_at": "2026-04-30T00:01:00+00:00",
                        "url": "https://www.saveticker.com/app/news/eu",
                    },
                ],
            )
            conn.commit()
            conn.close()

            payload = build_response(
                json.dumps(
                    {
                        "mode": "saveticker_breaking",
                        "request": "SaveTicker 속보 중요한 것만 알려줘",
                        "symbols": ["TSLA"],
                        "watchlist": ["TSLA"],
                        "db_path": str(db_path),
                    },
                    ensure_ascii=False,
                )
            )

            self.assertEqual(payload["mode"], "saveticker_breaking")
            self.assertIn("중요 속보", payload["summary"])
            self.assertTrue(any("테슬라" in item and "중요도" in item for item in payload["focus"]))
            self.assertFalse(any("유럽 통신주" in item for item in payload["focus"]))
            self.assertTrue(any("루머" in item or "검증" in item for item in payload["next_actions"]))

    def test_symbol_review_defaults_to_known_symbols(self) -> None:
        payload = build_response("NVDA랑 TSLA 체크포인트 정리해줘")
        self.assertEqual(payload["agent"], "stock-research-agent")
        self.assertEqual(payload["mode"], "symbol_review")
        self.assertIn("NVDA", payload["symbols"])
        self.assertIn("TSLA", payload["symbols"])

    def test_brief_mode_from_json_request(self) -> None:
        raw = json.dumps(
            {
                "mode": "brief",
                "symbols": ["AAPL"],
                "portfolio": ["AAPL"],
                "request": "장전 브리핑 만들어줘",
            },
            ensure_ascii=False,
        )
        payload = build_response(raw)
        self.assertEqual(payload["mode"], "brief")
        self.assertEqual(payload["symbols"], ["AAPL"])
        self.assertTrue(any("AAPL" in item for item in payload["focus"]))

    def test_portfolio_guard_mode(self) -> None:
        payload = build_response(
            "TSLA 포트폴리오 리스크 봐줘",
            runtime_context={"portfolio": ["TSLA"]},
        )
        self.assertEqual(payload["mode"], "portfolio_guard")
        self.assertIn("TSLA", payload["symbols"])
        self.assertTrue(any("위험도" in item for item in payload["focus"]))

    def test_compare_mode_prioritizes_one_symbol_with_reason(self) -> None:
        payload = build_response(
            json.dumps(
                {
                    "request": "NVDA vs AMD 뭐 먼저 볼까",
                    "symbols": ["NVDA", "AMD"],
                },
                ensure_ascii=False,
            )
        )
        self.assertEqual(payload["mode"], "compare")
        self.assertEqual(payload["symbols"], ["NVDA", "AMD"])
        self.assertTrue(any(item.startswith("우선순위:") for item in payload["focus"]))
        self.assertTrue(any(item.startswith("NVDA 비교:") for item in payload["focus"]))
        self.assertTrue(any(item.startswith("AMD 비교:") for item in payload["focus"]))
        self.assertTrue(any("먼저" in item for item in payload["next_actions"]))

    def test_compare_mode_ranks_two_symbols(self) -> None:
        payload = build_response("NVDA vs AMD 뭐 먼저 볼까")
        self.assertEqual(payload["mode"], "compare")
        self.assertEqual(payload["symbols"], ["NVDA", "AMD"])
        self.assertTrue(any(item.startswith("우선순위:") for item in payload["focus"]))
        self.assertTrue(any("NVDA" in item and "AMD" in item for item in payload["focus"]))
        self.assertTrue(any("비교 결론" in item for item in payload["focus"]))

    def test_what_changed_mode_summarizes_latest_market_symbol_and_breaking_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "stock_agent.db"
            run_ingest(["NVDA", "PLTR"], db_path=db_path)
            conn = get_connection(db_path)
            store_toss_index_snapshot(
                conn,
                {
                    "index_code": "COMP.NAI",
                    "index_name": "나스닥",
                    "collected_at": "2026-04-24T00:00:00+00:00",
                    "close": 24438.50,
                    "change_value": 219.06,
                    "change_pct": 1.12,
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
                        "headline": "엔비디아, 데이터센터 투자 확대",
                        "source_name": "로이터",
                        "published_text": "35분 전",
                        "url": "https://www.tossinvest.com/feed/news?contentType=news&id=changed-1",
                        "source": "tossinvest_feed",
                        "collected_at": "2026-04-24T00:00:00+00:00",
                    }
                ],
            )
            store_saveticker_items(
                conn,
                [
                    {
                        "headline": "팔란티어, 신규 정부 계약 확대",
                        "kind": "속보",
                        "published_text": "12분 전",
                        "tickers": ["PLTR"],
                        "popularity_text": "8.4K",
                        "source": "saveticker",
                        "collected_at": "2026-04-24T00:05:00+00:00",
                        "url": "https://www.saveticker.com/app/news?id=changed-breaking",
                    }
                ],
            )
            conn.commit()
            conn.close()

            payload = build_response(
                json.dumps(
                    {
                        "request": "NVDA PLTR 뭐가 달라졌어",
                        "symbols": ["NVDA", "PLTR"],
                        "db_path": str(db_path),
                    },
                    ensure_ascii=False,
                )
            )
            self.assertEqual(payload["mode"], "what_changed")
            self.assertTrue(any(item.startswith("시장 변화:") for item in payload["focus"]))
            self.assertTrue(any(item.startswith("종목 변화:") for item in payload["focus"]))
            self.assertTrue(any(item.startswith("속보 변화:") for item in payload["focus"]))
            self.assertTrue(any(item.startswith("변화 결론:") for item in payload["focus"]))
            self.assertTrue(any("나스닥" in item for item in payload["focus"]))
            self.assertTrue(any("PLTR" in item for item in payload["focus"]))

    def test_overnight_recap_mode_summarizes_after_close_to_pre_market_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "stock_agent.db"
            run_ingest(["NVDA", "PLTR"], db_path=db_path)
            conn = get_connection(db_path)
            store_toss_index_snapshot(
                conn,
                {
                    "index_code": "SPX.CBI",
                    "index_name": "S&P 500",
                    "collected_at": "2026-04-24T00:00:00+00:00",
                    "close": 7108.40,
                    "change_value": 29.50,
                    "change_pct": 0.41,
                    "volume": 12345.0,
                    "trading_value_text": "-",
                    "open": 7120.0,
                    "high": 7130.0,
                    "low": 7090.0,
                    "source": "tossinvest",
                    "note": "test",
                },
            )
            store_toss_news_items(
                conn,
                [
                    {
                        "headline": "미국 증시, 장후 반도체 강세 지속",
                        "source_name": "로이터",
                        "published_text": "1시간 전",
                        "url": "https://www.tossinvest.com/feed/news?contentType=news&id=overnight-1",
                        "source": "tossinvest_feed",
                        "collected_at": "2026-04-24T00:00:00+00:00",
                    }
                ],
            )
            store_saveticker_items(
                conn,
                [
                    {
                        "headline": "엔비디아, 주요 고객사 AI 서버 주문 확대",
                        "kind": "속보",
                        "published_text": "18분 전",
                        "tickers": ["NVDA"],
                        "popularity_text": "7.9K",
                        "source": "saveticker",
                        "collected_at": "2026-04-24T00:05:00+00:00",
                        "url": "https://www.saveticker.com/app/news?id=overnight-breaking",
                    }
                ],
            )
            conn.commit()
            conn.close()

            payload = build_response(
                json.dumps(
                    {
                        "request": "NVDA PLTR overnight recap 해줘",
                        "symbols": ["NVDA", "PLTR"],
                        "db_path": str(db_path),
                    },
                    ensure_ascii=False,
                )
            )
            self.assertEqual(payload["mode"], "overnight_recap")
            self.assertTrue(any(item.startswith("야간 시장:") for item in payload["focus"]))
            self.assertTrue(any(item.startswith("야간 속보:") for item in payload["focus"]))
            self.assertTrue(any(item.startswith("장전 체크:") for item in payload["focus"]))
            self.assertTrue(any(item.startswith("야간 결론:") for item in payload["focus"]))
            self.assertTrue(any("NVDA" in item for item in payload["focus"]))

    def test_why_symbol_mode_explains_why_symbol_matters_now(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "stock_agent.db"
            run_ingest(["NVDA"], db_path=db_path)
            payload = build_response(
                json.dumps(
                    {
                        "request": "왜 NVDA 봐야 해?",
                        "symbols": ["NVDA"],
                        "db_path": str(db_path),
                    },
                    ensure_ascii=False,
                )
            )
            self.assertEqual(payload["mode"], "why_symbol")
            self.assertTrue(any(item.startswith("핵심 이유:") for item in payload["focus"]))
            self.assertTrue(any(item.startswith("뉴스 이유:") for item in payload["focus"]))
            self.assertTrue(any(item.startswith("실적 이유:") for item in payload["focus"]))
            self.assertTrue(any(item.startswith("차트 이유:") for item in payload["focus"]))
            self.assertTrue(any(item.startswith("한줄 결론:") for item in payload["focus"]))

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

    def test_infer_symbols_uses_watchlist_file_when_no_symbol_in_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            watchlist_path = Path(tmpdir) / "watchlist.json"
            watchlist_path.write_text(
                json.dumps(
                    {
                        "watchlist": ["PLTR", "ORCL", "TSM"],
                        "portfolio": ["PLTR"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            payload = build_response(
                json.dumps(
                    {
                        "mode": "brief",
                        "watchlist_path": str(watchlist_path),
                        "request": "오늘 뭐 봐야 해?",
                    },
                    ensure_ascii=False,
                )
            )
            self.assertEqual(payload["symbols"], ["PLTR", "ORCL", "TSM"])

    def test_run_ingest_stores_market_snapshot_and_earnings(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "stock_agent.db"
            result = run_ingest(["NVDA", "TSLA"], db_path=db_path)
            self.assertEqual(result["symbols"], 2)
            self.assertGreaterEqual(result["prices"], 2)
            self.assertEqual(result["stored_prices"], result["prices"])
            self.assertEqual(result["stored_earnings"], 2)
            self.assertTrue(db_path.exists())

            conn = get_connection(db_path)
            upcoming = fetch_upcoming_earnings(conn, limit=5)
            conn.close()
            self.assertGreaterEqual(len(upcoming), 2)

    def test_build_brief_from_db_uses_stored_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "stock_agent.db"
            run_ingest(["NVDA", "TSLA"], db_path=db_path)
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
            text = build_brief_from_db(["NVDA", "TSLA"], db_path=db_path)
            self.assertIn("[시장 브리핑]", text)
            self.assertIn("[Market Summary]", text)
            self.assertIn("Market Summary: 미국장은", text)
            self.assertIn("오늘 테마는 소프트웨어", text)
            self.assertIn("근거 2건 기준입니다.", text)
            self.assertIn("NVDA", text)
            self.assertIn("TSLA", text)
            self.assertIn("[가까운 실적 일정]", text)
            self.assertIn("[토스증권 미국장 보조지표]", text)
            self.assertIn("나스닥", text)

    def test_brief_mode_prepends_market_summary_with_source_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "stock_agent.db"
            run_ingest(["PLTR", "GOOGL"], db_path=db_path)
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
            store_toss_index_snapshot(
                conn,
                {
                    "index_code": "SPX.CBI",
                    "index_name": "S&P 500",
                    "collected_at": "2026-04-24T00:00:00+00:00",
                    "close": 7108.40,
                    "change_value": -29.50,
                    "change_pct": -0.41,
                    "volume": 12345.0,
                    "trading_value_text": "-",
                    "open": 7120.0,
                    "high": 7130.0,
                    "low": 7090.0,
                    "source": "tossinvest",
                    "note": "test",
                },
            )
            store_toss_news_items(
                conn,
                [
                    {
                        "headline": "(카더라) 팔란티어, 소프트웨어 비관론 여파 주가 7% 급락",
                        "source_name": "연합인포맥스",
                        "published_text": "3시간 전",
                        "url": "https://www.tossinvest.com/feed/news?contentType=news&id=pltr",
                        "source": "tossinvest_feed",
                        "collected_at": "2026-04-24T00:00:00+00:00",
                    },
                    {
                        "headline": "미국 증시, 협상 기대에 상승",
                        "source_name": "로이터",
                        "published_text": "2시간 전",
                        "url": "https://www.tossinvest.com/feed/news?contentType=news&id=macro",
                        "source": "tossinvest_feed",
                        "collected_at": "2026-04-24T00:10:00+00:00",
                    }
                ],
            )
            store_saveticker_items(
                conn,
                [
                    {
                        "headline": "(카더라) 구글, 앤트로픽에 최대 400억 달러 투자 계획",
                        "kind": "속보",
                        "published_text": "2시간 전",
                        "tickers": ["GOOGL", "AVGO"],
                        "popularity_text": "6.7K",
                        "source": "saveticker",
                        "collected_at": "2026-04-24T00:00:00+00:00",
                        "url": "https://www.saveticker.com/app/news?id=1",
                    },
                    {
                        "headline": "(카더라) 이란 협상 재개 기대",
                        "kind": "정보",
                        "published_text": "1시간 전",
                        "tickers": [],
                        "popularity_text": "5.1K",
                        "source": "saveticker",
                        "collected_at": "2026-04-24T00:30:00+00:00",
                        "url": "https://www.saveticker.com/app/news?id=2",
                    }
                ],
            )
            conn.commit()
            conn.close()

            payload = build_response(
                json.dumps(
                    {
                        "mode": "brief",
                        "symbols": ["PLTR", "GOOGL"],
                        "portfolio": ["PLTR"],
                        "db_path": str(db_path),
                        "request": "미국장 브리핑 만들어줘",
                    },
                    ensure_ascii=False,
                )
            )

            self.assertTrue(payload["focus"][0].startswith("Market Summary:"))
            self.assertIn("미국장은", payload["focus"][0])
            self.assertIn("오늘 테마는 소프트웨어(portfolio, 0.50), AI(watchlist, 0.30)", payload["focus"][0])
            self.assertNotIn("매크로(general, 0.20)", payload["focus"][0])
            self.assertIn("핵심 뉴스는 (카더라) 팔란티어, 소프트웨어 비관론 여파 주가 7% 급락 / (카더라) 구글, 앤트로픽에 최대 400억 달러 투자 계획", payload["focus"][0])
            self.assertIn("혼합 소스 기준입니다.", payload["focus"][0])
            self.assertIn("근거 4건 기준입니다.", payload["focus"][0])
            self.assertIn("나스닥", payload["focus"][0])
            self.assertIn("검증 필요", payload["focus"][0])
            self.assertNotIn("risk_on", payload["focus"][0])
            self.assertNotIn("risk_off", payload["focus"][0])
            self.assertNotIn("mixed", payload["focus"][0])
            movers_line = next(item for item in payload["focus"] if item.startswith("오늘 먼저 볼 종목:"))
            self.assertIn("PLTR(보유)", movers_line)
            self.assertIn("GOOGL(속보)", movers_line)
            portfolio_line = next(item for item in payload["focus"] if item.startswith("보유종목 브리핑:"))
            self.assertIn("PLTR", portfolio_line)
            self.assertNotIn("GOOGL", portfolio_line)
            catalyst_line = next(item for item in payload["focus"] if item.startswith("Catalyst Board:"))
            self.assertIn("상승", catalyst_line)
            self.assertIn("루머", catalyst_line)
            earnings_line = next(item for item in payload["focus"] if item.startswith("실적 임박:"))
            self.assertIn("PLTR", earnings_line)

    def test_watchlist_weight_promotes_related_theme_without_portfolio(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "stock_agent.db"
            watchlist_path = Path(tmpdir) / "watchlist.json"
            watchlist_path.write_text(
                json.dumps(
                    {
                        "watchlist": ["PLTR", "GOOGL"],
                        "portfolio": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
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
                        "url": "https://www.tossinvest.com/feed/news?contentType=news&id=pltr-watchlist",
                        "source": "tossinvest_feed",
                        "collected_at": "2026-04-24T00:00:00+00:00",
                    },
                    {
                        "headline": "미국 증시, 협상 기대에 상승",
                        "source_name": "로이터",
                        "published_text": "2시간 전",
                        "url": "https://www.tossinvest.com/feed/news?contentType=news&id=macro-watchlist",
                        "source": "tossinvest_feed",
                        "collected_at": "2026-04-24T00:10:00+00:00",
                    },
                ],
            )
            store_saveticker_items(
                conn,
                [
                    {
                        "headline": "(카더라) 이란 협상 재개 기대",
                        "kind": "정보",
                        "published_text": "1시간 전",
                        "tickers": [],
                        "popularity_text": "5.1K",
                        "source": "saveticker",
                        "collected_at": "2026-04-24T00:30:00+00:00",
                        "url": "https://www.saveticker.com/app/news?id=watchlist-macro-1",
                    },
                    {
                        "headline": "백악관 협상 기대에 증시 반등",
                        "kind": "정보",
                        "published_text": "50분 전",
                        "tickers": [],
                        "popularity_text": "4.9K",
                        "source": "saveticker",
                        "collected_at": "2026-04-24T00:40:00+00:00",
                        "url": "https://www.saveticker.com/app/news?id=watchlist-macro-2",
                    },
                ],
            )
            conn.commit()
            conn.close()

            payload = build_response(
                json.dumps(
                    {
                        "mode": "brief",
                        "db_path": str(db_path),
                        "watchlist_path": str(watchlist_path),
                        "request": "미국장 브리핑 만들어줘",
                    },
                    ensure_ascii=False,
                )
            )

            self.assertEqual(payload["symbols"], ["PLTR", "GOOGL"])
            self.assertIn("오늘 테마는 소프트웨어(watchlist, 0.50), 매크로(general, 0.50)", payload["focus"][0])
            self.assertIn("핵심 뉴스는 팔란티어, 소프트웨어 비관론 여파 주가 7% 급락 / 백악관 협상 기대에 증시 반등", payload["focus"][0])

    def test_headline_priority_prefers_related_news_across_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "stock_agent.db"
            watchlist_path = Path(tmpdir) / "watchlist.json"
            watchlist_path.write_text(
                json.dumps(
                    {
                        "watchlist": ["GOOGL"],
                        "portfolio": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
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
                        "headline": "미국 증시, 협상 기대에 상승",
                        "source_name": "로이터",
                        "published_text": "3시간 전",
                        "url": "https://www.tossinvest.com/feed/news?contentType=news&id=macro-priority",
                        "source": "tossinvest_feed",
                        "collected_at": "2026-04-24T00:00:00+00:00",
                    }
                ],
            )
            store_saveticker_items(
                conn,
                [
                    {
                        "headline": "구글, 앤트로픽에 최대 400억 달러 투자 계획",
                        "kind": "속보",
                        "published_text": "2시간 전",
                        "tickers": ["GOOGL", "AVGO"],
                        "popularity_text": "6.7K",
                        "source": "saveticker",
                        "collected_at": "2026-04-24T00:10:00+00:00",
                        "url": "https://www.saveticker.com/app/news?id=priority-1",
                    }
                ],
            )
            conn.commit()
            conn.close()

            payload = build_response(
                json.dumps(
                    {
                        "mode": "brief",
                        "db_path": str(db_path),
                        "watchlist_path": str(watchlist_path),
                        "request": "미국장 브리핑 만들어줘",
                    },
                    ensure_ascii=False,
                )
            )

            self.assertIn("핵심 뉴스는 구글, 앤트로픽에 최대 400억 달러 투자 계획 / 미국 증시, 협상 기대에 상승", payload["focus"][0])

    def test_market_summary_prioritizes_portfolio_breaking_headline_within_same_source(self) -> None:
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
                        "headline": "미국 증시, 협상 기대에 상승",
                        "source_name": "로이터",
                        "published_text": "2시간 전",
                        "url": "https://www.tossinvest.com/feed/news?contentType=news&id=portfolio-summary-macro",
                        "source": "tossinvest_feed",
                        "collected_at": "2026-04-24T00:00:00+00:00",
                    }
                ],
            )
            store_saveticker_items(
                conn,
                [
                    {
                        "headline": "엔비디아·마이크로소프트·아마존, AI 클라우드 투자 확대",
                        "kind": "속보",
                        "published_text": "7분 전",
                        "tickers": ["NVDA", "MSFT", "AMZN"],
                        "popularity_text": "11.2K",
                        "source": "saveticker",
                        "collected_at": "2026-04-24T00:07:00+00:00",
                        "url": "https://www.saveticker.com/app/news?id=portfolio-summary-broad",
                    },
                    {
                        "headline": "팔란티어, 미 국방 데이터 계약 확대",
                        "kind": "속보",
                        "published_text": "11분 전",
                        "tickers": ["PLTR"],
                        "popularity_text": "8.4K",
                        "source": "saveticker",
                        "collected_at": "2026-04-24T00:11:00+00:00",
                        "url": "https://www.saveticker.com/app/news?id=portfolio-summary-pltr",
                    }
                ],
            )
            conn.commit()
            conn.close()

            payload = build_response(
                json.dumps(
                    {
                        "mode": "brief",
                        "symbols": ["PLTR", "NVDA"],
                        "portfolio": ["PLTR"],
                        "db_path": str(db_path),
                        "request": "미국장 브리핑 만들어줘",
                    },
                    ensure_ascii=False,
                )
            )

            self.assertIn("핵심 뉴스는 팔란티어, 미 국방 데이터 계약 확대 / 미국 증시, 협상 기대에 상승", payload["focus"][0])
            self.assertNotIn("핵심 뉴스는 엔비디아·마이크로소프트·아마존, AI 클라우드 투자 확대 / 미국 증시, 협상 기대에 상승", payload["focus"][0])
            self.assertIn("혼합 소스 기준입니다.", payload["focus"][0])

    def test_market_summary_marks_wire_based_headlines_when_top_news_are_high_reliability(self) -> None:
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
                        "headline": "미국 증시, 협상 기대에 상승",
                        "source_name": "로이터",
                        "published_text": "20분 전",
                        "url": "https://www.tossinvest.com/feed/news?contentType=news&id=wire-1",
                        "source": "tossinvest_feed",
                        "collected_at": "2026-04-24T00:00:00+00:00",
                    },
                    {
                        "headline": "애플, 신형 칩 공급망 재점검",
                        "source_name": "블룸버그",
                        "published_text": "35분 전",
                        "url": "https://www.tossinvest.com/feed/news?contentType=news&id=wire-2",
                        "source": "tossinvest_feed",
                        "collected_at": "2026-04-24T00:05:00+00:00",
                    }
                ],
            )
            conn.commit()
            conn.close()

            payload = build_response(
                json.dumps(
                    {
                        "mode": "brief",
                        "symbols": ["AAPL"],
                        "db_path": str(db_path),
                        "request": "미국장 브리핑 만들어줘",
                    },
                    ensure_ascii=False,
                )
            )

            self.assertIn("주요 통신 기준입니다.", payload["focus"][0])

    def test_technical_snapshot_mode_returns_indicator_summary(self) -> None:
        payload = build_response(
            json.dumps(
                {
                    "mode": "technical_snapshot",
                    "symbols": ["NVDA"],
                    "request": "NVDA 차트 기술적 스냅샷 보여줘",
                },
                ensure_ascii=False,
            )
        )
        self.assertEqual(payload["mode"], "technical_snapshot")
        self.assertEqual(payload["symbols"], ["NVDA"])
        self.assertTrue(any("RSI" in item for item in payload["focus"]))
        self.assertTrue(any("MACD" in item for item in payload["focus"]))
        self.assertTrue(any("20일선" in item for item in payload["focus"]))
        self.assertTrue(any("지지" in item for item in payload["focus"]))
        self.assertTrue(any("해석" in item for item in payload["focus"]))
        self.assertTrue(any("action bias" in item for item in payload["focus"]))
        self.assertTrue(any("이벤트 태그" in item for item in payload["focus"]))
        self.assertTrue(any("손절 기준 가격" in item for item in payload["focus"]))
        self.assertTrue(any("손절 거리" in item for item in payload["focus"]))
        self.assertFalse(any(item.endswith(": ") for item in payload["focus"] if "이벤트 태그" in item))
        self.assertTrue(any("매수 관점" in item or "관망 관점" in item or "손절 경계" in item for item in payload["focus"]))
        self.assertTrue(any("TradingView 느낌" in item for item in payload["next_actions"]))

    def test_brief_mode_includes_technical_one_liner(self) -> None:
        payload = build_response(
            json.dumps(
                {
                    "mode": "brief",
                    "symbols": ["NVDA"],
                    "request": "미국장 브리핑 만들어줘",
                },
                ensure_ascii=False,
            )
        )
        self.assertEqual(payload["mode"], "brief")
        self.assertTrue(any("차트 한줄" in item for item in payload["focus"]))
        self.assertTrue(any("상승 추세" in item or "하락 추세" in item or "박스권/혼조" in item for item in payload["focus"]))
        self.assertTrue(any("매수 관점" in item or "관망 관점" in item or "손절 경계" in item for item in payload["focus"]))
        self.assertTrue(any("저항 돌파 시도" in item or "지지 이탈 위험" in item or "과열 경계" in item for item in payload["focus"]))
        self.assertTrue(any("손절" in item and "%" in item for item in payload["focus"] if "차트 한줄" in item))
        self.assertFalse(any("중립" in item for item in payload["focus"] if "차트 한줄" in item))
        self.assertFalse(any("Technical:" in item for item in payload["focus"]))
        self.assertFalse(any("action bias" in item for item in payload["focus"]))

    def test_after_market_brief_uses_post_close_tone(self) -> None:
        payload = build_response(
            json.dumps(
                {
                    "mode": "brief",
                    "symbols": ["NVDA"],
                    "request": "장후 브리핑 만들어줘",
                },
                ensure_ascii=False,
            )
        )
        self.assertEqual(payload["mode"], "brief")
        self.assertIn("장후 브리핑", payload["summary"])
        self.assertTrue(payload["focus"][0].startswith("장후 Market Summary:"))
        self.assertIn("마감 이후", payload["focus"][0])
        self.assertTrue(any("애프터마켓" in item or "마감 이후" in item for item in payload["next_actions"]))

    def test_brief_mode_prioritizes_fresh_breaking_news(self) -> None:
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
                        "headline": "엔비디아, 데이터센터 투자 확대",
                        "source_name": "로이터",
                        "published_text": "3시간 전",
                        "url": "https://www.tossinvest.com/feed/news?contentType=news&id=older",
                        "source": "tossinvest_feed",
                        "collected_at": "2026-04-24T00:00:00+00:00",
                    }
                ],
            )
            store_saveticker_items(
                conn,
                [
                    {
                        "headline": "(카더라) 구글, 앤트로픽 추가 투자 검토",
                        "kind": "속보",
                        "published_text": "12분 전",
                        "tickers": ["GOOGL"],
                        "popularity_text": "7.2K",
                        "source": "saveticker",
                        "collected_at": "2026-04-24T00:05:00+00:00",
                        "url": "https://www.saveticker.com/app/news?id=fresh-breaking",
                    }
                ],
            )
            conn.commit()
            conn.close()

            payload = build_response(
                json.dumps(
                    {
                        "mode": "brief",
                        "symbols": ["NVDA", "GOOGL"],
                        "db_path": str(db_path),
                        "request": "미국장 브리핑 만들어줘",
                    },
                    ensure_ascii=False,
                )
            )
            self.assertTrue(any(item.startswith("속보 우선:") for item in payload["focus"]))
            breaking_line = next(item for item in payload["focus"] if item.startswith("속보 우선:"))
            self.assertIn("[watchlist 관련][신속][신뢰도:낮음][루머 주의]", breaking_line)
            self.assertIn("12분 전", breaking_line)
            self.assertIn("구글, 앤트로픽 추가 투자 검토", breaking_line)
            self.assertLess(payload["focus"].index(breaking_line), payload["focus"].index(next(item for item in payload["focus"] if item.startswith("차트 한줄:"))))

    def test_brief_mode_adds_position_alert_for_portfolio_related_breaking_news(self) -> None:
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
            store_saveticker_items(
                conn,
                [
                    {
                        "headline": "팔란티어, 신규 정부 계약 확대",
                        "kind": "속보",
                        "published_text": "9분 전",
                        "tickers": ["PLTR"],
                        "popularity_text": "9.1K",
                        "source": "saveticker",
                        "collected_at": "2026-04-24T00:02:00+00:00",
                        "url": "https://www.saveticker.com/app/news?id=portfolio-breaking",
                    }
                ],
            )
            conn.commit()
            conn.close()

            payload = build_response(
                json.dumps(
                    {
                        "mode": "brief",
                        "symbols": ["PLTR", "NVDA"],
                        "portfolio": ["PLTR"],
                        "db_path": str(db_path),
                        "request": "미국장 브리핑 만들어줘",
                    },
                    ensure_ascii=False,
                )
            )
            self.assertTrue(any(item.startswith("포지션 경고:") for item in payload["focus"]))
            alert_line = next(item for item in payload["focus"] if item.startswith("포지션 경고:"))
            self.assertIn("[초신속][신뢰도:낮음]", alert_line)
            self.assertIn("PLTR", alert_line)
            self.assertIn("9분 전", alert_line)
            thesis_line = next(item for item in payload["focus"] if item.startswith("thesis break 이유:"))
            self.assertIn("PLTR", thesis_line)
            self.assertIn("기대 선반영", thesis_line)
            self.assertLess(payload["focus"].index(alert_line), payload["focus"].index(thesis_line))
            self.assertLess(payload["focus"].index(thesis_line), payload["focus"].index(next(item for item in payload["focus"] if item.startswith("차트 한줄:"))))

    def test_brief_mode_warns_when_source_specific_news_is_stale(self) -> None:
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
                        "headline": "미국 증시, 협상 기대에 상승",
                        "source_name": "로이터",
                        "published_text": "5시간 전",
                        "url": "https://www.tossinvest.com/feed/news?contentType=news&id=stale-toss",
                        "source": "tossinvest_feed",
                        "collected_at": "2026-04-24T00:00:00+00:00",
                    }
                ],
            )
            store_saveticker_items(
                conn,
                [
                    {
                        "headline": "엔비디아, AI 서버 공급 확대",
                        "kind": "속보",
                        "published_text": "2시간 전",
                        "tickers": ["NVDA"],
                        "popularity_text": "6.1K",
                        "source": "saveticker",
                        "collected_at": "2026-04-24T00:30:00+00:00",
                        "url": "https://www.saveticker.com/app/news?id=stale-save",
                    }
                ],
            )
            conn.commit()
            conn.close()

            payload = build_response(
                json.dumps(
                    {
                        "mode": "brief",
                        "symbols": ["NVDA"],
                        "db_path": str(db_path),
                        "request": "미국장 브리핑 만들어줘",
                    },
                    ensure_ascii=False,
                )
            )
            self.assertTrue(any(item.startswith("최신성 경고:") for item in payload["focus"]))
            stale_line = next(item for item in payload["focus"] if item.startswith("최신성 경고:"))
            self.assertIn("Toss 5시간 전", stale_line)
            self.assertIn("SaveTicker 2시간 전", stale_line)

    def test_brief_mode_normalizes_absolute_timestamp_in_staleness_warning(self) -> None:
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
                        "headline": "미국 증시, 협상 기대에 상승",
                        "source_name": "로이터",
                        "published_text": "5시간 전",
                        "url": "https://www.tossinvest.com/feed/news?contentType=news&id=stale-absolute-toss",
                        "source": "tossinvest_feed",
                        "collected_at": "2026-04-24T00:00:00+00:00",
                    }
                ],
            )
            store_saveticker_items(
                conn,
                [
                    {
                        "headline": "인텔 - 실적발표",
                        "kind": "속보",
                        "published_text": "2020. 01. 01. 00:00",
                        "tickers": ["INTC"],
                        "popularity_text": "2.1K",
                        "source": "saveticker",
                        "collected_at": "2026-04-24T00:30:00+00:00",
                        "url": "https://www.saveticker.com/app/news?id=stale-absolute-save",
                    }
                ],
            )
            conn.commit()
            conn.close()

            payload = build_response(
                json.dumps(
                    {
                        "mode": "brief",
                        "symbols": ["INTC"],
                        "db_path": str(db_path),
                        "request": "미국장 브리핑 만들어줘",
                    },
                    ensure_ascii=False,
                )
            )
            stale_line = next(item for item in payload["focus"] if item.startswith("최신성 경고:"))
            self.assertIn("Toss 5시간 전", stale_line)
            self.assertIn("SaveTicker ", stale_line)
            self.assertIn("전", stale_line)
            self.assertNotIn("2020. 01. 01. 00:00", stale_line)

    def test_earnings_mode_returns_schedule(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "stock_agent.db"
            run_ingest(["MSFT", "AMZN"], db_path=db_path)
            raw = json.dumps(
                {
                    "mode": "earnings",
                    "symbols": ["MSFT", "AMZN"],
                    "db_path": str(db_path),
                    "request": "미국 실적 일정 보여줘",
                },
                ensure_ascii=False,
            )
            payload = build_response(raw)
            self.assertEqual(payload["mode"], "earnings")
            self.assertTrue(any("실적 예정" in item for item in payload["focus"]))

    def test_toss_sync_mode_returns_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "stock_agent.db"
            conn = get_connection(db_path)
            store_toss_index_snapshot(
                conn,
                {
                    "index_code": "SPX.CBI",
                    "index_name": "S&P 500",
                    "collected_at": "2026-04-24T00:00:00+00:00",
                    "close": 7108.40,
                    "change_value": -29.50,
                    "change_pct": -0.41,
                    "volume": 12345.0,
                    "trading_value_text": "-",
                    "open": 7120.0,
                    "high": 7130.0,
                    "low": 7090.0,
                    "source": "tossinvest",
                    "note": "test",
                },
            )
            store_toss_news_items(
                conn,
                [
                    {
                        "headline": "미국 IPO 쓰나미 온다…AI 열풍 속 뉴욕증시 경고등",
                        "source_name": "뉴스1",
                        "published_text": "23분 전",
                        "url": "https://www.tossinvest.com/feed/news?contentType=news&id=2",
                        "source": "tossinvest_feed",
                        "collected_at": "2026-04-24T00:00:00+00:00",
                    }
                ],
            )
            conn.commit()
            conn.close()
            text = build_brief_from_db(["MSFT"], db_path=db_path)
            self.assertIn("S&P 500", text)
            self.assertIn("AI 열풍", text)
            payload = build_response(
                json.dumps(
                    {
                        "mode": "brief",
                        "symbols": ["MSFT"],
                        "db_path": str(db_path),
                        "request": "미국장 브리핑 만들어줘",
                    },
                    ensure_ascii=False,
                )
            )
            self.assertTrue(any("S&P 500" in item for item in payload["focus"]))
            self.assertTrue(any("AI 열풍" in item for item in payload["focus"]))

    def test_portfolio_relevance_prioritizes_mapped_news(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "stock_agent.db"
            conn = get_connection(db_path)
            store_toss_news_items(
                conn,
                [
                    {
                        "headline": "팔란티어, 소프트웨어 비관론 여파 주가 7% 급락",
                        "source_name": "연합인포맥스",
                        "published_text": "3시간 전",
                        "url": "https://www.tossinvest.com/feed/news?contentType=news&id=pltr",
                        "source": "tossinvest_feed",
                        "collected_at": "2026-04-24T00:00:00+00:00",
                    },
                    {
                        "headline": "미국 IPO 쓰나미 온다…AI 열풍 속 뉴욕증시 경고등",
                        "source_name": "뉴스1",
                        "published_text": "23분 전",
                        "url": "https://www.tossinvest.com/feed/news?contentType=news&id=macro",
                        "source": "tossinvest_feed",
                        "collected_at": "2026-04-24T00:00:00+00:00",
                    },
                ],
            )
            conn.commit()
            conn.close()
            payload = build_response(
                json.dumps(
                    {
                        "mode": "brief",
                        "symbols": ["PLTR"],
                        "portfolio": ["PLTR"],
                        "db_path": str(db_path),
                        "request": "미국장 브리핑 만들어줘",
                    },
                    ensure_ascii=False,
                )
            )
            news_lines = [item for item in payload["focus"] if "관련종목:" in item]
            self.assertGreaterEqual(len(news_lines), 2)
            self.assertIn("PLTR", news_lines[0])


if __name__ == "__main__":
    unittest.main()
