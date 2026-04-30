import unittest
from unittest.mock import patch


class SectorStrengthTest(unittest.TestCase):
    def test_ranks_sector_etfs_by_absolute_and_relative_strength(self) -> None:
        from src.sector_strength import build_sector_strength_report

        quotes = {
            "SPY": {"symbol": "SPY", "price": 500.0, "previous_close": 497.51, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},  # +0.50%
            "QQQ": {"symbol": "QQQ", "price": 430.0, "previous_close": 425.74, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},  # +1.00%
            "XLK": {"symbol": "XLK", "price": 210.0, "previous_close": 205.88, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},  # +2.00%
            "XLE": {"symbol": "XLE", "price": 98.0, "previous_close": 97.03, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},  # +1.00%
            "XLU": {"symbol": "XLU", "price": 70.0, "previous_close": 71.43, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},  # -2.00%
        }

        report = build_sector_strength_report(quotes, collected_at="2026-04-30T13:35:00+00:00")

        self.assertEqual(report["available"], True)
        self.assertEqual(report["strong"][0]["symbol"], "XLK")
        self.assertGreater(report["strong"][0]["relative_to_spy_pct"], 1.0)
        self.assertGreater(report["strong"][0]["relative_to_qqq_pct"], 0.5)
        self.assertEqual(report["weak"][0]["symbol"], "XLU")
        self.assertLess(report["weak"][0]["relative_to_spy_pct"], -2.0)
        self.assertTrue(any("ETF 시장 참고" in line and "XLK" in line and "XLU" in line for line in report["focus_lines"]))

    def test_classifies_risk_off_when_vix_oil_yields_and_dxy_jump(self) -> None:
        from src.sector_strength import build_sector_strength_report

        quotes = {
            "SPY": {"symbol": "SPY", "price": 500.0, "previous_close": 500.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "QQQ": {"symbol": "QQQ", "price": 430.0, "previous_close": 430.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "XLK": {"symbol": "XLK", "price": 210.0, "previous_close": 210.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "XLE": {"symbol": "XLE", "price": 98.0, "previous_close": 96.08, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "^VIX": {"symbol": "^VIX", "price": 24.0, "previous_close": 20.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "CL=F": {"symbol": "CL=F", "price": 84.0, "previous_close": 80.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "^TNX": {"symbol": "^TNX", "price": 46.0, "previous_close": 45.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "DX-Y.NYB": {"symbol": "DX-Y.NYB", "price": 107.0, "previous_close": 105.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
        }

        report = build_sector_strength_report(quotes, collected_at="2026-04-30T13:35:00+00:00")

        self.assertEqual(report["regime"]["label"], "risk_off")
        self.assertTrue(any("VIX" in signal for signal in report["regime"]["signals"]))
        self.assertTrue(any("WTI" in signal or "오일" in signal for signal in report["regime"]["signals"]))
        self.assertTrue(any("고베타" in action or "추격" in action for action in report["next_actions"]))
        self.assertTrue(any("시장 레짐" in line and "리스크오프" in line for line in report["focus_lines"]))

    def test_returns_unavailable_report_when_benchmarks_are_missing(self) -> None:
        from src.sector_strength import build_sector_strength_report

        report = build_sector_strength_report({"XLK": {"symbol": "XLK", "price": 210.0, "previous_close": 205.0}})

        self.assertFalse(report["available"])
        self.assertIn("SPY", report["summary"])
        self.assertEqual(report["focus_lines"][0], "섹터 강약: SPY/QQQ 기준 데이터가 부족합니다")

    def test_user_watchlist_theme_baskets_rank_space_and_show_internal_leaders(self) -> None:
        from src.sector_strength import build_sector_strength_report

        quotes = {
            "SPY": {"price": 500.0, "previous_close": 497.51, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "QQQ": {"price": 430.0, "previous_close": 428.28, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "RKLB": {"price": 29.0, "previous_close": 27.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "LUNR": {"price": 12.4, "previous_close": 11.8, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "RDW": {"price": 9.4, "previous_close": 9.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "ASTS": {"price": 52.0, "previous_close": 50.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "HIMS": {"price": 48.0, "previous_close": 47.5, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "LLY": {"price": 780.0, "previous_close": 778.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
        }

        report = build_sector_strength_report(quotes, collected_at="2026-04-30T13:35:00+00:00")

        self.assertEqual(report["strong_themes"][0]["key"], "space_aerospace")
        self.assertEqual(report["strong_themes"][0]["name"], "우주/항공우주")
        self.assertGreater(report["strong_themes"][0]["breadth_positive_pct"], 70.0)
        self.assertEqual(report["strong_themes"][0]["leaders"][0]["symbol"], "RKLB")
        self.assertTrue(any("강한 테마" in line and "우주/항공우주" in line and "RKLB" in line for line in report["focus_lines"]))

    def test_theme_lines_use_clear_rising_ratio_label_instead_of_bullish_candle(self) -> None:
        from src.sector_strength import build_sector_strength_report

        quotes = {
            "SPY": {"price": 500.0, "previous_close": 500.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "QQQ": {"price": 430.0, "previous_close": 430.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "RKLB": {"price": 30.0, "previous_close": 27.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "LUNR": {"price": 12.6, "previous_close": 12.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "RDW": {"price": 8.8, "previous_close": 9.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
        }

        report = build_sector_strength_report(quotes, collected_at="2026-04-30T13:35:00+00:00")
        focus_text = "\n".join(report["focus_lines"])

        self.assertIn("상승비율", focus_text)
        self.assertNotIn("양봉", focus_text)

    def test_leveraged_single_stock_products_do_not_dominate_theme_basket_score(self) -> None:
        from src.sector_strength import build_sector_strength_report

        quotes = {
            "SPY": {"price": 500.0, "previous_close": 500.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "QQQ": {"price": 430.0, "previous_close": 430.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "RKLX": {"price": 28.0, "previous_close": 20.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "RKLZ": {"price": 29.0, "previous_close": 20.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "RKLB": {"price": 25.0, "previous_close": 25.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "LUNR": {"price": 11.9, "previous_close": 12.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "HIMS": {"price": 51.5, "previous_close": 50.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "LLY": {"price": 803.0, "previous_close": 790.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "NVO": {"price": 82.0, "previous_close": 80.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
        }

        report = build_sector_strength_report(quotes, collected_at="2026-04-30T13:35:00+00:00")

        self.assertEqual(report["strong_themes"][0]["key"], "healthcare_glp1_digital")
        space = next(row for row in report["theme_baskets"] if row["key"] == "space_aerospace")
        self.assertIn("RKLX", space["excluded_symbols"])
        self.assertIn("RKLZ", space["excluded_symbols"])

    def test_watchlist_movers_rank_theme_constituents_for_today_first_list(self) -> None:
        from src.sector_strength import build_sector_strength_report

        quotes = {
            "SPY": {"price": 500.0, "previous_close": 500.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "QQQ": {"price": 430.0, "previous_close": 430.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "RKLB": {"price": 30.0, "previous_close": 27.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "LUNR": {"price": 12.6, "previous_close": 12.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "COIN": {"price": 220.0, "previous_close": 211.54, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "HIMS": {"price": 45.0, "previous_close": 50.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
        }

        report = build_sector_strength_report(quotes, collected_at="2026-04-30T13:35:00+00:00")

        self.assertEqual(report["watchlist_movers"][0]["symbol"], "RKLB")
        self.assertEqual(report["watchlist_movers"][0]["theme"], "우주/항공우주")
        self.assertTrue(any("오늘 먼저 볼 종목" in line and "RKLB" in line and "COIN" in line for line in report["focus_lines"]))

    def test_photo_theme_baskets_drive_primary_summary_not_broad_etfs(self) -> None:
        from src.sector_strength import build_sector_strength_report

        quotes = {
            "SPY": {"price": 500.0, "previous_close": 500.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "QQQ": {"price": 430.0, "previous_close": 430.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "XLE": {"price": 100.0, "previous_close": 95.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "XLU": {"price": 50.0, "previous_close": 51.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "RKLB": {"price": 30.0, "previous_close": 27.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "LUNR": {"price": 12.6, "previous_close": 12.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "COIN": {"price": 180.0, "previous_close": 181.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "MARA": {"price": 10.0, "previous_close": 10.5, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
        }

        report = build_sector_strength_report(quotes, collected_at="2026-04-30T13:35:00+00:00")

        self.assertTrue(report["summary"].startswith("장중 테마 강약: 우주/항공우주 주도"))
        self.assertNotIn("XLE 주도", report["summary"])
        self.assertTrue(report["focus_lines"][1].startswith("강한 테마"))
        self.assertTrue(any("ETF 시장 참고" in line and "XLE" in line for line in report["focus_lines"]))

    def test_sub_theme_baskets_split_semiconductors_and_power_into_actionable_groups(self) -> None:
        from src.sector_strength import USER_SUB_THEME_BASKETS

        self.assertIn("semis_memory_storage", USER_SUB_THEME_BASKETS)
        self.assertIn("semis_ai_accelerators", USER_SUB_THEME_BASKETS)
        self.assertIn("semis_equipment", USER_SUB_THEME_BASKETS)
        self.assertIn("power_utilities_generation", USER_SUB_THEME_BASKETS)
        self.assertIn("nuclear_smr", USER_SUB_THEME_BASKETS)
        self.assertEqual(USER_SUB_THEME_BASKETS["semis_memory_storage"]["parent"], "semiconductors")
        self.assertIn("MU", USER_SUB_THEME_BASKETS["semis_memory_storage"]["symbols"])
        self.assertIn("NVDA", USER_SUB_THEME_BASKETS["semis_ai_accelerators"]["symbols"])
        self.assertIn("AMAT", USER_SUB_THEME_BASKETS["semis_equipment"]["symbols"])
        self.assertIn("VST", USER_SUB_THEME_BASKETS["power_utilities_generation"]["symbols"])
        self.assertIn("OKLO", USER_SUB_THEME_BASKETS["nuclear_smr"]["symbols"])

    def test_sub_theme_strength_detects_semiconductor_memory_rotation(self) -> None:
        from src.sector_strength import build_sector_strength_report

        quotes = {
            "SPY": {"price": 500.0, "previous_close": 500.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "QQQ": {"price": 430.0, "previous_close": 430.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "MU": {"price": 106.0, "previous_close": 100.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "SNDK": {"price": 53.0, "previous_close": 50.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "STX": {"price": 104.0, "previous_close": 100.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "NVDA": {"price": 99.0, "previous_close": 100.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "AMD": {"price": 98.0, "previous_close": 100.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "INTC": {"price": 102.0, "previous_close": 100.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "QCOM": {"price": 101.0, "previous_close": 100.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
        }

        report = build_sector_strength_report(quotes, collected_at="2026-04-30T13:35:00+00:00")

        self.assertEqual(report["strong_sub_themes"][0]["key"], "semis_memory_storage")
        self.assertEqual(report["strong_sub_themes"][0]["parent_key"], "semiconductors")
        self.assertEqual(report["weak_sub_themes"][0]["key"], "semis_ai_accelerators")
        self.assertTrue(any("강한 세부테마" in line and "메모리/스토리지" in line and "MU" in line for line in report["focus_lines"]))
        self.assertTrue(any("약한 세부테마" in line and "AI 가속기/GPU" in line for line in report["focus_lines"]))
        self.assertEqual(report["watchlist_movers"][0]["sub_theme"], "메모리/스토리지")

    def test_rotation_alert_explains_internal_sub_theme_shift(self) -> None:
        from src.sector_strength import build_sector_strength_report

        quotes = {
            "SPY": {"price": 500.0, "previous_close": 500.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "QQQ": {"price": 430.0, "previous_close": 430.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "MU": {"price": 106.0, "previous_close": 100.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "SNDK": {"price": 53.0, "previous_close": 50.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "STX": {"price": 104.0, "previous_close": 100.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "NVDA": {"price": 97.0, "previous_close": 100.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "AMD": {"price": 97.0, "previous_close": 100.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "AVGO": {"price": 97.0, "previous_close": 100.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "ARM": {"price": 97.0, "previous_close": 100.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "INTC": {"price": 104.0, "previous_close": 100.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "QCOM": {"price": 104.0, "previous_close": 100.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "SNPS": {"price": 105.0, "previous_close": 100.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "TSM": {"price": 101.0, "previous_close": 100.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
        }

        report = build_sector_strength_report(quotes, collected_at="2026-04-30T13:35:00+00:00")

        self.assertEqual(report["rotation_alerts"][0]["parent_key"], "semiconductors")
        self.assertEqual(report["rotation_alerts"][0]["into_sub_theme"], "메모리/스토리지")
        self.assertEqual(report["rotation_alerts"][0]["out_of_sub_theme"], "AI 가속기/GPU")
        self.assertTrue(
            any(
                "로테이션 해석" in line
                and "반도체/AI칩 내부" in line
                and "메모리/스토리지로 자금 이동" in line
                and "AI 가속기/GPU 약세" in line
                and "MU" in line
                and "NVDA" in line
                for line in report["focus_lines"]
            )
        )
        self.assertTrue(any("메모리/스토리지 추격은" in action for action in report["next_actions"]))

    def test_photo_watchlist_theme_baskets_include_ai_semis_power_quantum_and_updated_crypto(self) -> None:
        from src.sector_strength import USER_THEME_BASKETS

        self.assertIn("ai_bigtech_infra", USER_THEME_BASKETS)
        self.assertIn("semiconductors", USER_THEME_BASKETS)
        self.assertIn("nuclear_power_uranium", USER_THEME_BASKETS)
        self.assertIn("quantum", USER_THEME_BASKETS)
        self.assertIn("NVDA", USER_THEME_BASKETS["semiconductors"]["symbols"])
        self.assertIn("SOXL", USER_THEME_BASKETS["semiconductors"]["excluded_from_score"])
        self.assertIn("OKLO", USER_THEME_BASKETS["nuclear_power_uranium"]["symbols"])
        self.assertIn("IONQ", USER_THEME_BASKETS["quantum"]["symbols"])
        self.assertIn("PLTR", USER_THEME_BASKETS["ai_bigtech_infra"]["symbols"])
        self.assertIn("BMNU", USER_THEME_BASKETS["crypto_equities"]["symbols"])
        self.assertIn("BMNU", USER_THEME_BASKETS["crypto_equities"]["excluded_from_score"])

    def test_fetch_sector_strength_quotes_uses_yahoo_chart_quote_first_for_intraday_alerts(self) -> None:
        from src.sector_strength import fetch_sector_strength_quotes

        def fake_chart_pack(symbol: str) -> dict:
            return {
                "available": True,
                "source": "chart-quote-test",
                "collected_at": "2026-04-30T12:22:37+00:00",
                "quote": {"price": 66.1, "previous_close": 64.98, "pct_change": 1.72},
            }

        with patch("src.yfinance_data.fetch_yfinance_market_pack", side_effect=AssertionError("must not use full market pack")), patch(
            "src.yfinance_data.fetch_yahoo_chart_quote_pack", side_effect=fake_chart_pack
        ) as chart_pack, patch("src.yfinance_data.fetch_yfinance_quote_pack", side_effect=AssertionError("must not use fallback when chart quote is available")):
            quotes = fetch_sector_strength_quotes(["OKLO", "SMR"])

        self.assertEqual(chart_pack.call_count, 2)
        self.assertEqual(quotes["OKLO"]["source"], "chart-quote-test")
        self.assertEqual(quotes["OKLO"]["pct_change"], 1.72)

    def test_fetch_sector_strength_quotes_falls_back_to_yfinance_quote_only_helper(self) -> None:
        from src.sector_strength import fetch_sector_strength_quotes

        def fake_chart_pack(symbol: str) -> dict:
            return {"available": False, "source": "yahoo_chart_quote_error", "warning": "chart unavailable"}

        def fake_quote_pack(symbol: str) -> dict:
            return {
                "available": True,
                "source": "quote-only-test",
                "collected_at": "2026-04-30T13:35:00+00:00",
                "quote": {"price": 101.0, "previous_close": 100.0, "pct_change": 1.0},
            }

        with patch("src.yfinance_data.fetch_yfinance_market_pack", side_effect=AssertionError("must not use full market pack")), patch(
            "src.yfinance_data.fetch_yahoo_chart_quote_pack", side_effect=fake_chart_pack
        ), patch("src.yfinance_data.fetch_yfinance_quote_pack", side_effect=fake_quote_pack) as quote_pack:
            quotes = fetch_sector_strength_quotes(["SPY", "RKLB"])

        self.assertEqual(quote_pack.call_count, 2)
        self.assertEqual(quotes["SPY"]["source"], "quote-only-test")
        self.assertEqual(quotes["RKLB"]["pct_change"], 1.0)


if __name__ == "__main__":
    unittest.main()
