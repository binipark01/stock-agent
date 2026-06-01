import json
import tempfile
from pathlib import Path

from src.main import build_response, run_ingest, build_brief_from_db
from src.repository import get_connection, fetch_upcoming_earnings
from src.tossinvest_data import store_toss_index_snapshot, store_toss_news_items
from src.saveticker_data import store_saveticker_items

class SectorModeCases:
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

        def test_market_regime_mode_returns_regime_only_focus(self) -> None:
            payload = build_response(
                "지금 시장 레짐 판단해줘",
                runtime_context={
                    "sector_quotes": {
                        "SPY": {"symbol": "SPY", "price": 500.0, "previous_close": 500.0},
                        "QQQ": {"symbol": "QQQ", "price": 430.0, "previous_close": 430.0},
                        "^VIX": {"symbol": "^VIX", "price": 25.0, "previous_close": 22.0},
                        "CL=F": {"symbol": "CL=F", "price": 84.0, "previous_close": 80.0},
                        "^TNX": {"symbol": "^TNX", "price": 46.0, "previous_close": 45.0},
                        "DX-Y.NYB": {"symbol": "DX-Y.NYB", "price": 107.0, "previous_close": 105.0},
                    },
                    "collected_at": "2026-05-02T13:35:00+00:00",
                },
            )

            self.assertEqual(payload["mode"], "market_regime")
            self.assertIn("리스크오프", payload["summary"])
            self.assertTrue(any("장 분위기" in item and "리스크오프" in item for item in payload["focus"]))
            self.assertIn("market_regime", payload["features"])

        def test_oil_vix_mode_returns_oil_and_vix_focus(self) -> None:
            payload = build_response(
                "유가랑 vix 좀 봐줘",
                runtime_context={
                    "sector_quotes": {
                        "SPY": {"symbol": "SPY", "price": 500.0, "previous_close": 500.0},
                        "QQQ": {"symbol": "QQQ", "price": 430.0, "previous_close": 430.0},
                        "^VIX": {"symbol": "^VIX", "price": 27.0, "previous_close": 22.5},
                        "^VIX9D": {"symbol": "^VIX9D", "price": 30.0, "previous_close": 23.0},
                        "^VIX3M": {"symbol": "^VIX3M", "price": 24.0, "previous_close": 24.5},
                        "CL=F": {"symbol": "CL=F", "price": 85.0, "previous_close": 80.0},
                        "BZ=F": {"symbol": "BZ=F", "price": 89.0, "previous_close": 85.0},
                        "XLE": {"symbol": "XLE", "price": 100.0, "previous_close": 98.0},
                        "OIH": {"symbol": "OIH", "price": 330.0, "previous_close": 320.0},
                        "XOP": {"symbol": "XOP", "price": 150.0, "previous_close": 145.0},
                    },
                    "collected_at": "2026-05-03T13:35:00+00:00",
                },
            )

            self.assertEqual(payload["mode"], "oil_vix")
            self.assertIn("VIX", payload["summary"])
            self.assertTrue(any("VIX 구조" in item for item in payload["focus"]))
            self.assertTrue(any("유가" in item and "WTI" in item for item in payload["focus"]))
