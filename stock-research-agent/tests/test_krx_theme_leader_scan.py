import unittest


class KrxThemeLeaderScanTest(unittest.TestCase):
    def test_ranks_themes_by_money_flow_and_identifies_leader_stock(self):
        from src.krx_theme_leader_scan import build_krx_theme_leader_report

        watchlist_data = {
            "lists": {
                "krx_stockcrew_semiconductors": ["005930.KS", "000660.KS"],
                "krx_stockcrew_power_infra": ["001440.KS", "267260.KS"],
            }
        }
        quotes = {
            "005930.KS": {"price": 70000, "previous_close": 69000, "volume": 1_000_000},
            "000660.KS": {"price": 190000, "previous_close": 188000, "volume": 500_000},
            "001440.KS": {"price": 18000, "previous_close": 16000, "volume": 8_000_000, "foreign_net_buy": 250000, "program_net_buy": 120000},
            "267260.KS": {"price": 420000, "previous_close": 400000, "volume": 200_000, "institution_net_buy": 50000},
        }

        report = build_krx_theme_leader_report(watchlist_data, quotes, collected_at="t")

        self.assertEqual(report["mode"], "krx_theme_leader_scan")
        self.assertEqual(report["themes"][0]["theme_key"], "krx_stockcrew_power_infra")
        self.assertEqual(report["themes"][0]["leader"]["symbol"], "001440.KS")
        self.assertGreater(report["themes"][0]["money_flow_score"], report["themes"][1]["money_flow_score"])
        self.assertIn("어느 테마에 돈", "\n".join(report["focus_lines"]))

    def test_build_response_returns_theme_first_format_from_runtime_quotes(self):
        from src.main import build_response

        watchlist_data = {
            "watchlist": [],
            "portfolio": [],
            "lists": {
                "krx_stockcrew_robotics": ["454910.KS", "277810.KQ"],
                "krx_stockcrew_shipbuilding": ["329180.KS", "042660.KS"],
            },
        }
        quotes = {
            "454910.KS": {"price": 100000, "previous_close": 95000, "volume": 900000, "program_net_buy": 50000},
            "277810.KQ": {"price": 300000, "previous_close": 294000, "volume": 300000},
            "329180.KS": {"price": 200000, "previous_close": 198000, "volume": 150000},
            "042660.KS": {"price": 90000, "previous_close": 89500, "volume": 100000},
        }

        payload = build_response(
            "국장 어느 테마에 돈 들어오고 대장주 뭐야",
            runtime_context={"watchlist_data": watchlist_data, "krx_theme_quotes": quotes, "collected_at": "t"},
        )

        self.assertEqual(payload["mode"], "krx_theme_leader_scan")
        text = "\n".join([payload["summary"], *payload["focus"]])
        self.assertIn("주도테마", text)
        self.assertIn("로봇", text)
        self.assertIn("454910.KS", text)


if __name__ == "__main__":
    unittest.main()
