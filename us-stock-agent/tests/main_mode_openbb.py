import json
import tempfile
from pathlib import Path

from src.main import build_response, run_ingest, build_brief_from_db
from src.repository import get_connection, fetch_upcoming_earnings
from src.tossinvest_data import store_toss_index_snapshot, store_toss_news_items
from src.saveticker_data import store_saveticker_items

class OpenBBModeCases:
        def test_openbb_quote_mode_uses_runtime_context_payload(self) -> None:
            payload = build_response(
                '{"request":"RDDT OpenBB quote", "symbols":["RDDT"]}',
                runtime_context={
                    "openbb_quote": {
                        "status": "ok",
                        "symbol": "RDDT",
                        "name": "Reddit, Inc.",
                        "price": 161.46,
                        "previous_close": 166.56,
                        "pct_change": -3.06,
                        "open": 168.5,
                        "high": 169.1,
                        "low": 159.6,
                        "volume": 2726614,
                        "currency": "USD",
                        "source": "openbb:yfinance",
                    }
                },
            )

            self.assertEqual(payload["mode"], "openbb_quote")
            self.assertIn("openbb", payload["features"])
            self.assertTrue(any("RDDT" in item and "161.46" in item for item in payload["focus"]))

        def test_openbb_history_mode_uses_runtime_context_payload(self) -> None:
            payload = build_response(
                '{"request":"SPY OpenBB history", "symbols":["SPY"], "start_date":"2024-01-02", "end_date":"2024-01-05"}',
                runtime_context={
                    "openbb_history": {
                        "status": "ok",
                        "symbol": "SPY",
                        "source": "openbb:yfinance",
                        "rows": [
                            {"date": "2024-01-02", "open": 472.16, "high": 473.67, "low": 470.49, "close": 472.65, "volume": 123623700},
                            {"date": "2024-01-05", "open": 467.49, "high": 470.44, "low": 466.43, "close": 467.92, "volume": 86118900},
                        ],
                    }
                },
            )

            self.assertEqual(payload["mode"], "openbb_history")
            self.assertIn("openbb_history", payload["features"])
            self.assertTrue(any("SPY" in item and "2 rows" in item for item in payload["focus"]))

        def test_openbb_profile_mode_uses_runtime_context_payload(self) -> None:
            payload = build_response(
                '{"request":"NVDA OpenBB profile", "symbols":["NVDA"]}',
                runtime_context={
                    "openbb_profile": {
                        "status": "ok",
                        "symbol": "NVDA",
                        "name": "NVIDIA Corporation",
                        "sector": "Technology",
                        "industry": "Semiconductors",
                        "market_cap": 3000000000000,
                        "exchange": "NMS",
                        "source": "openbb:yfinance",
                    }
                },
            )

            self.assertEqual(payload["mode"], "openbb_profile")
            self.assertIn("openbb_profile", payload["features"])
            self.assertTrue(any("NVIDIA" in item for item in payload["focus"]))
