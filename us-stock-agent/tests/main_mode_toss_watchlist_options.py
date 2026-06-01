import json
import tempfile
from pathlib import Path

from src.main import build_response, run_ingest, build_brief_from_db
from src.repository import get_connection, fetch_upcoming_earnings
from src.tossinvest_data import store_toss_index_snapshot, store_toss_news_items
from src.saveticker_data import store_saveticker_items

class TossWatchlistOptionsModeCases:
        def test_day_market_mode_uses_runtime_toss_markdown_without_live_network(self) -> None:
            markdown = """
    팔란티어 PLTR
    212,133원
    $142.87
    데이마켓 -4,691원 (2.16%)
    애프터마켓에서 -5,879원 (2.71%) 마감
    13:27:54
    거래량 319,968
    """
            payload = build_response(
                json.dumps({"request": "PLTR 데이마켓 가격", "symbols": ["PLTR"], "mode": "day_market"}, ensure_ascii=False),
                runtime_context={"toss_day_market_markdown": {"PLTR": markdown}},
            )

            self.assertEqual(payload["mode"], "day_market")
            self.assertIn("PLTR $142.87", payload["summary"])
            self.assertTrue(any("PLTR 데이마켓" in item and "212,133원" in item for item in payload["focus"]))
            action_text = " ".join(payload["next_actions"])
            self.assertIn("호가·스프레드", action_text)
            self.assertIn("Yahoo", action_text)

        def test_toss_stock_snapshot_prompt_routes_and_extracts_symbol_without_live_network(self) -> None:
            markdown = """
    레드와이어 RDW
    13,719원 $9.33
    지난 정규장보다 +941원 (7.36%)
    01:30:10
    거래량 6,787,335
    """

            payload = build_response(
                "RDW 토스 정보",
                runtime_context={"toss_day_market_markdown": {"RDW": markdown}, "toss_code_cache_path": False},
            )

            self.assertEqual(payload["mode"], "day_market")
            self.assertEqual(payload["symbols"], ["RDW"])
            self.assertIn("RDW $9.33", payload["summary"])
            self.assertTrue(any("RDW 정규장" in item and "13,719원" in item for item in payload["focus"]))
            self.assertNotIn("community", json.dumps(payload, ensure_ascii=False).lower())

        def test_watchlist_scan_mode_uses_named_watchlists_and_runtime_quotes(self) -> None:
            with tempfile.TemporaryDirectory() as tmpdir:
                watchlist_path = Path(tmpdir) / "watchlist.json"
                watchlist_path.write_text(
                    json.dumps(
                        {
                            "watchlist": ["레딧", "NVDA"],
                            "portfolio": ["TSLA"],
                            "lists": {"optical": ["AAOI", "LITE"], "crypto": ["COIN", "MARA"]},
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                quotes = {
                    "SPY": {"price": 500.0, "previous_close": 500.0, "source": "unit", "timestamp": "2026-05-02T13:35:00+00:00"},
                    "RDDT": {"price": 162.0, "previous_close": 150.0, "source": "unit", "timestamp": "2026-05-02T13:35:00+00:00"},
                    "NVDA": {"price": 104.0, "previous_close": 100.0, "source": "unit", "timestamp": "2026-05-02T13:35:00+00:00"},
                    "TSLA": {"price": 190.0, "previous_close": 200.0, "source": "unit", "timestamp": "2026-05-02T13:35:00+00:00"},
                    "AAOI": {"price": 18.0, "previous_close": 16.0, "source": "unit", "timestamp": "2026-05-02T13:35:00+00:00"},
                    "LITE": {"price": 70.0, "previous_close": 69.0, "source": "unit", "timestamp": "2026-05-02T13:35:00+00:00"},
                    "COIN": {"price": 220.0, "previous_close": 210.0, "source": "unit", "timestamp": "2026-05-02T13:35:00+00:00"},
                    "MARA": {"price": 14.0, "previous_close": 14.2, "source": "unit", "timestamp": "2026-05-02T13:35:00+00:00"},
                }

                payload = build_response(
                    json.dumps({"request": "광통신 watchlist만 봐줘", "watchlist_path": str(watchlist_path)}, ensure_ascii=False),
                    runtime_context={"watchlist_quotes": quotes, "collected_at": "2026-05-02T13:35:00+00:00"},
                )

            self.assertEqual(payload["mode"], "watchlist_scan")
            self.assertEqual(payload["symbols"], ["AAOI", "LITE"])
            self.assertTrue(any("관심종목 범위: optical" in item for item in payload["focus"]))
            self.assertTrue(any("관심종목 스캔" in item and "AAOI" in item for item in payload["focus"]))
            self.assertTrue(any("리스트별 강도" in item and "optical" in item for item in payload["focus"]))
            self.assertEqual(payload["data"]["watchlist_scan"]["top_movers"][0]["symbol"], "AAOI")

        def test_options_flow_mode_returns_compact_options_focus(self) -> None:
            payload = build_response(
                json.dumps(
                    {
                        "request": "NVDA 옵션판 빡세게 봐줘",
                        "symbols": ["NVDA"],
                        "options_payload": {
                            "timestamp": "2026-05-01T15:30:00",
                            "data": {
                                "symbol": "NVDA",
                                "current_price": 152.0,
                                "options": [
                                    {"option": "NVDA260501C00150000", "volume": 5000, "open_interest": 1000, "iv": 0.65, "delta": 0.55, "gamma": 0.025},
                                    {"option": "NVDA260501P00140000", "volume": 2400, "open_interest": 600, "iv": 0.75, "delta": -0.30, "gamma": 0.018},
                                ],
                            },
                        },
                    },
                    ensure_ascii=False,
                )
            )

            self.assertEqual(payload["mode"], "options_flow")
            self.assertTrue(any("옵션판" in item for item in payload["focus"]))
            self.assertIn("options_flow", payload["features"])
            self.assertEqual(payload["data"]["options_flow"]["source"], "cboe_delayed")

        def test_options_sweep_mode_uses_watchlist_symbols_and_payload_map(self) -> None:
            with tempfile.TemporaryDirectory() as tmpdir:
                watchlist_path = Path(tmpdir) / "watchlist.json"
                watchlist_path.write_text(json.dumps({"watchlist": ["NVDA", "RDDT"], "portfolio": [], "lists": {}}, ensure_ascii=False), encoding="utf-8")
                payload = build_response(
                    json.dumps(
                        {
                            "request": "내 관심종목 옵션 스윕해줘",
                            "watchlist_path": str(watchlist_path),
                            "options_payloads": {
                                "NVDA": {
                                    "timestamp": "2026-05-01T15:30:00",
                                    "data": {
                                        "symbol": "NVDA",
                                        "current_price": 152.0,
                                        "options": [
                                            {"option": "NVDA260501C00150000", "volume": 5000, "open_interest": 1000, "iv": 0.65, "delta": 0.55, "gamma": 0.025},
                                            {"option": "NVDA260501P00140000", "volume": 500, "open_interest": 800, "iv": 0.75, "delta": -0.30, "gamma": 0.018},
                                        ],
                                    },
                                },
                                "RDDT": {"timestamp": "2026-05-01T15:30:00", "data": {"symbol": "RDDT", "current_price": 100.0, "options": []}},
                            },
                        },
                        ensure_ascii=False,
                    )
                )

            self.assertEqual(payload["mode"], "options_sweep")
            self.assertTrue(any("옵션 관심종목" in item and "NVDA" in item for item in payload["focus"]))
            self.assertEqual(payload["data"]["options_sweep"]["ranked"][0]["symbol"], "NVDA")

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
