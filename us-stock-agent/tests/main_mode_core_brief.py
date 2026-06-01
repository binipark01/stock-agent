import json
import tempfile
from pathlib import Path

from src.main import build_response, run_ingest, build_brief_from_db
from src.repository import get_connection, fetch_upcoming_earnings
from src.tossinvest_data import store_toss_index_snapshot, store_toss_news_items
from src.saveticker_data import store_saveticker_items

class CoreBriefModeCases:
        def test_symbol_review_defaults_to_known_symbols(self) -> None:
            payload = build_response("NVDA랑 TSLA 체크포인트 정리해줘")
            self.assertEqual(payload["agent"], "us-stock-agent")
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
            self.assertTrue(any("Slow Stoch" in item for item in payload["focus"]))
            self.assertTrue(any("BB" in item or "볼린저" in item for item in payload["focus"]))
            self.assertTrue(any("ATR" in item for item in payload["focus"]))
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
