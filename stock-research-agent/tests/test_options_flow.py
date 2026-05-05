import unittest


class OptionsFlowTest(unittest.TestCase):
    def test_analyze_options_chain_computes_ratios_walls_max_pain_and_unusuals(self) -> None:
        from src.options_flow import analyze_options_chain, parse_occ_option_symbol

        parsed = parse_occ_option_symbol("NVDA260501C00150000", underlying="NVDA")
        self.assertEqual(parsed["expiration"], "2026-05-01")
        self.assertEqual(parsed["option_type"], "call")
        self.assertEqual(parsed["strike"], 150.0)

        rows = [
            {"option": "NVDA260501C00150000", "volume": 5000, "open_interest": 1000, "iv": 0.65, "delta": 0.55, "gamma": 0.025, "last_trade_price": 6.2},
            {"option": "NVDA260501C00160000", "volume": 3000, "open_interest": 8000, "iv": 0.7, "delta": 0.35, "gamma": 0.021, "last_trade_price": 2.4},
            {"option": "NVDA260501P00140000", "volume": 2400, "open_interest": 600, "iv": 0.75, "delta": -0.30, "gamma": 0.018, "last_trade_price": 1.8},
            {"option": "NVDA260501P00130000", "volume": 700, "open_interest": 9000, "iv": 0.8, "delta": -0.15, "gamma": 0.012, "last_trade_price": 0.9},
        ]

        report = analyze_options_chain("NVDA", rows, current_price=152.0, collected_at="2026-05-01T15:30:00+00:00")

        self.assertTrue(report["available"])
        self.assertEqual(report["nearest_expiration"], "2026-05-01")
        self.assertEqual(report["totals"]["call_volume"], 8000)
        self.assertEqual(report["totals"]["put_volume"], 3100)
        self.assertEqual(report["ratios"]["put_call_volume_ratio"], 0.39)
        self.assertEqual(report["walls"]["call_wall"]["strike"], 160.0)
        self.assertEqual(report["walls"]["put_wall"]["strike"], 130.0)
        self.assertIsNotNone(report["max_pain"])
        self.assertEqual(report["unusual_volume"][0]["strike"], 150.0)
        self.assertIn("call_volume_bullish", report["alerts"])
        self.assertIn("unusual_options_activity", report["alerts"])
        self.assertTrue(report["expiration_summaries"])
        self.assertTrue(any("옵션 트리거" in line and "call_volume_bullish" in line for line in report["focus_lines"]))
        self.assertTrue(any("만기별" in line and "2026-05-01" in line for line in report["focus_lines"]))
        self.assertTrue(any("옵션판" in line and "P/C vol" in line for line in report["focus_lines"]))
        self.assertTrue(any("콜월" in line and "풋월" in line for line in report["focus_lines"]))

    def test_build_watchlist_options_sweep_ranks_symbols_by_alert_pressure(self) -> None:
        from src.options_flow import build_watchlist_options_sweep

        payloads = {
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
            "RDDT": {
                "timestamp": "2026-05-01T15:30:00",
                "data": {"symbol": "RDDT", "current_price": 100.0, "options": []},
            },
        }

        sweep = build_watchlist_options_sweep(["RDDT", "NVDA"], payloads=payloads)

        self.assertTrue(sweep["available"])
        self.assertEqual(sweep["ranked"][0]["symbol"], "NVDA")
        self.assertTrue(any("옵션 관심종목" in line and "NVDA" in line for line in sweep["focus_lines"]))

    def test_build_options_flow_report_accepts_cboe_payload_shape(self) -> None:
        from src.options_flow import build_options_flow_report

        payload = {
            "timestamp": "2026-05-01T15:30:00",
            "data": {
                "symbol": "NVDA",
                "current_price": 152.0,
                "options": [
                    {"option": "NVDA260501C00150000", "volume": 5000, "open_interest": 1000, "iv": 0.65, "delta": 0.55, "gamma": 0.025},
                    {"option": "NVDA260501P00140000", "volume": 2400, "open_interest": 600, "iv": 0.75, "delta": -0.30, "gamma": 0.018},
                ],
            },
        }

        report = build_options_flow_report("NVDA", cboe_payload=payload)

        self.assertTrue(report["available"])
        self.assertEqual(report["source"], "cboe_delayed")
        self.assertEqual(report["underlying_price"], 152.0)
        self.assertTrue(any("NVDA" in line for line in report["focus_lines"]))


if __name__ == "__main__":
    unittest.main()
