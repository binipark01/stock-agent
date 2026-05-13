import unittest
from unittest.mock import patch

from src.main import build_technical_snapshot as main_build_technical_snapshot
from src.technical_snapshot import build_technical_snapshot


class TechnicalSnapshotModuleTest(unittest.TestCase):
    def test_technical_snapshot_lives_in_dedicated_module_and_stays_reexported(self):
        closes = [100 + idx for idx in range(60)]
        with patch("src.technical_snapshot.fetch_price_ohlcv_history", return_value=[], create=True), patch("src.technical_snapshot.fetch_price_history", return_value=closes):
            direct = build_technical_snapshot("NVDA")
        with patch("src.technical_snapshot.fetch_price_ohlcv_history", return_value=[], create=True), patch("src.technical_snapshot.fetch_price_history", return_value=closes):
            reexported = main_build_technical_snapshot("NVDA")

        self.assertEqual(direct, reexported)
        self.assertEqual(direct["symbol"], "NVDA")
        self.assertIn("차트 한줄", direct["brief_line"])
        self.assertIn("RSI", direct["brief_line"])
        self.assertIn(direct["action_bias"], direct["brief_line"])

    def test_technical_snapshot_uses_rsi_25_75_momentum_bounds(self):
        def closes_from_changes(changes):
            closes = [100.0]
            for change in changes:
                closes.append(closes[-1] + change)
            return closes

        closes_for_rsi_70 = closes_from_changes([1] * 7 + [-1] * 3 + [0] * 4)
        with patch("src.technical_snapshot.fetch_price_ohlcv_history", return_value=[], create=True), patch("src.technical_snapshot.fetch_price_history", return_value=closes_for_rsi_70):
            not_overbought = build_technical_snapshot("NVDA")
        self.assertEqual(not_overbought["rsi14"], 70.0)
        self.assertEqual(not_overbought["momentum"], "중립 구간")
        self.assertNotIn("과열 경계", not_overbought["event_tags"])

        closes_for_rsi_80 = closes_from_changes([1] * 8 + [-1] * 2 + [0] * 4)
        with patch("src.technical_snapshot.fetch_price_ohlcv_history", return_value=[], create=True), patch("src.technical_snapshot.fetch_price_history", return_value=closes_for_rsi_80):
            overbought = build_technical_snapshot("NVDA")
        self.assertEqual(overbought["rsi14"], 80.0)
        self.assertEqual(overbought["momentum"], "과열 구간")

        closes_for_rsi_20 = closes_from_changes([1] * 2 + [-1] * 8 + [0] * 4)
        with patch("src.technical_snapshot.fetch_price_ohlcv_history", return_value=[], create=True), patch("src.technical_snapshot.fetch_price_history", return_value=closes_for_rsi_20):
            oversold = build_technical_snapshot("NVDA")
        self.assertEqual(oversold["rsi14"], 20.0)
        self.assertEqual(oversold["momentum"], "과매도 구간")

    def test_technical_snapshot_adds_tradingview_style_indicator_stack(self):
        records = []
        price = 100.0
        for idx in range(60):
            price += 0.7 if idx < 35 else (-0.35 if idx < 48 else 1.15)
            records.append(
                {
                    "open": price - 0.4,
                    "high": price + 1.6 + (idx % 3) * 0.15,
                    "low": price - 1.3 - (idx % 2) * 0.1,
                    "close": price,
                    "volume": 1_000_000 + idx * 20_000,
                }
            )

        with patch("src.technical_snapshot.fetch_price_ohlcv_history", return_value=records, create=True):
            snapshot = build_technical_snapshot("NVDA")

        for key in [
            "ema12",
            "ema26",
            "macd_direction",
            "stoch_k",
            "stoch_d",
            "stoch_signal",
            "bb_upper",
            "bb_middle",
            "bb_lower",
            "bb_percent_b",
            "bb_width_pct",
            "atr14",
            "atr_pct",
            "volume_ratio20",
            "risk_note",
        ]:
            self.assertIn(key, snapshot)

        self.assertNotEqual(snapshot["signal"], round(snapshot["macd"] * 0.8, 2))
        self.assertGreater(snapshot["bb_upper"], snapshot["bb_middle"])
        self.assertGreater(snapshot["bb_middle"], snapshot["bb_lower"])
        self.assertGreaterEqual(snapshot["bb_percent_b"], 0.0)
        self.assertGreater(snapshot["atr14"], 0.0)
        self.assertGreater(snapshot["volume_ratio20"], 0.0)
        self.assertIn("Stoch", snapshot["brief_line"])
        self.assertIn("BB", snapshot["brief_line"])


if __name__ == "__main__":
    unittest.main()
