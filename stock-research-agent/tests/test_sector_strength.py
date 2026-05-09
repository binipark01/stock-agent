import unittest
from unittest.mock import patch


class SectorStrengthTest(unittest.TestCase):
    def test_rsi_interpretation_uses_25_75_extremes(self) -> None:
        from src.sector_strength import _technical_suffix

        high_but_not_extreme = _technical_suffix({"rsi14": 74.0, "rsi14_delta": 5.0})
        self.assertIn("RSI 74(+5)", high_but_not_extreme)
        self.assertIn("50선 위에서 재가속", high_but_not_extreme)
        self.assertNotIn("과열권", high_but_not_extreme)

        overbought = _technical_suffix({"rsi14": 76.0, "rsi14_delta": 2.0})
        self.assertIn("RSI 76(+2)", overbought)
        self.assertIn("과열권", overbought)

        oversold = _technical_suffix({"rsi14": 24.0, "rsi14_delta": -2.0})
        self.assertIn("RSI 24(-2)", oversold)
        self.assertIn("과매도권", oversold)

    def test_report_includes_current_strength_against_previous_regular_close(self) -> None:
        from src.sector_strength import build_sector_strength_report

        quotes = {
            "SPY": {"symbol": "SPY", "price": 500.0, "previous_close": 500.0, "source": "yahoo_chart_quote", "price_source": "yahoo_chart_quote", "pct_change_basis": "정규장 종가 대비", "timestamp": "2026-05-08T13:35:00+00:00"},
            "^IXIC": {"symbol": "^IXIC", "price": 17000.0, "previous_close": 16900.0, "source": "yahoo_chart_quote", "timestamp": "2026-05-08T13:35:00+00:00"},
            "SOXX": {"symbol": "SOXX", "price": 220.0, "previous_close": 218.0, "source": "yahoo_chart_quote", "timestamp": "2026-05-08T13:35:00+00:00"},
            "BTC-USD": {"symbol": "BTC-USD", "price": 100000.0, "previous_close": 99000.0, "source": "yahoo_chart_quote", "timestamp": "2026-05-08T13:35:00+00:00"},
            "CL=F": {"symbol": "CL=F", "price": 70.0, "previous_close": 71.0, "source": "yahoo_chart_quote", "timestamp": "2026-05-08T13:35:00+00:00"},
            "^VIX": {"symbol": "^VIX", "price": 17.0, "previous_close": 18.0, "source": "yahoo_chart_quote", "timestamp": "2026-05-08T13:35:00+00:00"},
            "RKLB": {"symbol": "RKLB", "price": 110.0, "previous_close": 100.0, "source": "yahoo_chart_quote", "price_source": "yahoo_chart_quote", "pct_change_basis": "정규장 종가 대비", "timestamp": "2026-05-08T13:35:00+00:00"},
            "MU": {"symbol": "MU", "price": 109.0, "previous_close": 100.0, "source": "yahoo_chart_quote", "price_source": "yahoo_chart_quote", "pct_change_basis": "정규장 종가 대비", "timestamp": "2026-05-08T13:35:00+00:00"},
            "COIN": {"symbol": "COIN", "price": 103.0, "previous_close": 100.0, "source": "yahoo_chart_quote", "price_source": "yahoo_chart_quote", "pct_change_basis": "정규장 종가 대비", "timestamp": "2026-05-08T13:35:00+00:00"},
        }

        report = build_sector_strength_report(quotes, collected_at="2026-05-08T13:35:00+00:00")
        focus_text = "\n".join(report["focus_lines"])

        self.assertIn("전일종가 대비 현재 강세:", focus_text)
        self.assertIn("기준 전일 정규장 종가 대비 현재가", focus_text)
        self.assertIn("Yahoo chart 1m includePrePost", focus_text)
        self.assertRegex(focus_text, r"RKLB \+10\.00%.*가격 110")
        self.assertRegex(focus_text, r"MU \+9\.00%.*가격 109")
        self.assertLess(focus_text.find("RKLB +10.00%"), focus_text.find("MU +9.00%"))

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
        self.assertEqual(report["weak"][0]["symbol"], "XLU")
        self.assertLess(report["weak"][0]["relative_to_spy_pct"], -2.0)
        self.assertTrue(any("ETF 시장 참고" in line and "XLK" in line and "XLU" in line for line in report["focus_lines"]))
        self.assertNotIn("QQQ", "\n".join(report["focus_lines"] + report["next_actions"]))

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
        self.assertTrue(any("장 분위기" in line and "리스크오프" in line for line in report["focus_lines"]))

    def test_oil_vix_report_detects_vol_backwardation_and_oil_shock(self) -> None:
        from src.sector_strength import build_oil_vix_report

        quotes = {
            "SPY": {"symbol": "SPY", "price": 500.0, "previous_close": 500.0, "source": "unit", "timestamp": "2026-05-03T13:35:00+00:00"},
            "QQQ": {"symbol": "QQQ", "price": 430.0, "previous_close": 430.0, "source": "unit", "timestamp": "2026-05-03T13:35:00+00:00"},
            "^VIX": {"symbol": "^VIX", "price": 27.0, "previous_close": 22.5, "source": "unit", "timestamp": "2026-05-03T13:35:00+00:00"},
            "^VIX9D": {"symbol": "^VIX9D", "price": 30.0, "previous_close": 23.0, "source": "unit", "timestamp": "2026-05-03T13:35:00+00:00"},
            "^VIX3M": {"symbol": "^VIX3M", "price": 24.0, "previous_close": 24.5, "source": "unit", "timestamp": "2026-05-03T13:35:00+00:00"},
            "CL=F": {"symbol": "CL=F", "price": 85.0, "previous_close": 80.0, "source": "unit", "timestamp": "2026-05-03T13:35:00+00:00"},
            "BZ=F": {"symbol": "BZ=F", "price": 89.0, "previous_close": 85.0, "source": "unit", "timestamp": "2026-05-03T13:35:00+00:00"},
            "XLE": {"symbol": "XLE", "price": 100.0, "previous_close": 98.0, "source": "unit", "timestamp": "2026-05-03T13:35:00+00:00"},
            "OIH": {"symbol": "OIH", "price": 330.0, "previous_close": 320.0, "source": "unit", "timestamp": "2026-05-03T13:35:00+00:00"},
            "XOP": {"symbol": "XOP", "price": 150.0, "previous_close": 145.0, "source": "unit", "timestamp": "2026-05-03T13:35:00+00:00"},
        }

        report = build_oil_vix_report(quotes, collected_at="2026-05-03T13:35:00+00:00")

        self.assertEqual(report["vix"]["structure"], "backwardation")
        self.assertEqual(report["oil"]["state"], "oil_shock")
        self.assertIn("vix_backwardation", report["alerts"])
        self.assertIn("oil_shock", report["alerts"])
        self.assertTrue(any("트리거" in line and "oil_shock" in line for line in report["focus_lines"]))
        self.assertTrue(any("VIX 구조" in line and "백워데이션" in line for line in report["focus_lines"]))
        self.assertTrue(any("유가" in line and "WTI" in line and "Brent" in line for line in report["focus_lines"]))
        self.assertTrue(any("에너지 주식" in line and "OIH" in line and "XOP" in line for line in report["focus_lines"]))
        self.assertTrue(any("헤지" in action or "추격" in action for action in report["next_actions"]))

    def test_oil_vix_report_detects_intraday_minute_spikes(self) -> None:
        from src.sector_strength import build_oil_vix_report

        quotes = {
            "^VIX": {"symbol": "^VIX", "price": 19.2, "previous_close": 18.9, "pct_change_5m": 5.8, "pct_change_15m": 8.4, "source": "unit", "timestamp": "2026-05-03T13:35:00+00:00"},
            "^VIX9D": {"symbol": "^VIX9D", "price": 19.5, "previous_close": 19.0, "source": "unit", "timestamp": "2026-05-03T13:35:00+00:00"},
            "^VIX3M": {"symbol": "^VIX3M", "price": 22.0, "previous_close": 22.0, "source": "unit", "timestamp": "2026-05-03T13:35:00+00:00"},
            "CL=F": {"symbol": "CL=F", "price": 81.2, "previous_close": 80.8, "pct_change_5m": 1.3, "pct_change_15m": 2.2, "source": "unit", "timestamp": "2026-05-03T13:35:00+00:00"},
            "BZ=F": {"symbol": "BZ=F", "price": 84.0, "previous_close": 83.8, "pct_change_5m": 0.8, "pct_change_15m": 1.4, "source": "unit", "timestamp": "2026-05-03T13:35:00+00:00"},
        }

        report = build_oil_vix_report(quotes, collected_at="2026-05-03T13:35:00+00:00")

        self.assertIn("vix_5m_spike", report["alerts"])
        self.assertIn("wti_5m_spike", report["alerts"])
        self.assertTrue(any("분봉 급등" in line and "VIX 5m +5.80%" in line and "WTI 5m +1.30%" in line for line in report["focus_lines"]))

    def test_market_regime_report_includes_score_and_trading_difficulty(self) -> None:
        from src.sector_strength import build_market_regime_report

        quotes = {
            "SPY": {"price": 500.0, "previous_close": 500.0},
            "QQQ": {"price": 426.0, "previous_close": 430.0},
            "^VIX": {"price": 27.0, "previous_close": 22.5},
            "^VIX9D": {"price": 30.0, "previous_close": 23.0},
            "^VIX3M": {"price": 24.0, "previous_close": 24.5},
            "CL=F": {"price": 85.0, "previous_close": 80.0},
            "BZ=F": {"price": 89.0, "previous_close": 85.0},
        }

        report = build_market_regime_report(quotes, collected_at="2026-05-03T13:35:00+00:00")

        self.assertEqual(report["trading_difficulty"]["label"], "어려움")
        self.assertGreaterEqual(report["scores"]["vol_stress_score"], 3)
        self.assertGreaterEqual(report["scores"]["oil_pressure_score"], 2)
        self.assertTrue(any("오늘 매매 난이도" in line and "어려움" in line for line in report["focus_lines"]))

    def test_returns_unavailable_report_when_benchmarks_are_missing(self) -> None:
        from src.sector_strength import build_sector_strength_report

        report = build_sector_strength_report({"XLK": {"symbol": "XLK", "price": 210.0, "previous_close": 205.0}})

        self.assertFalse(report["available"])
        self.assertIn("SPY", report["summary"])
        self.assertEqual(report["focus_lines"][0], "섹터 강약: SPY 기준 데이터가 부족합니다")

    def test_sector_strength_report_does_not_require_or_compare_qqq(self) -> None:
        from src.sector_strength import build_sector_strength_report

        quotes = {
            "SPY": {"price": 500.0, "previous_close": 500.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "^IXIC": {"price": 16000.0, "previous_close": 15840.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "SOXX": {"price": 220.0, "previous_close": 215.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "BTC-USD": {"price": 65000.0, "previous_close": 64000.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "CL=F": {"price": 80.0, "previous_close": 81.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "^VIX": {"price": 18.0, "previous_close": 18.5, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "RKLB": {"price": 30.0, "previous_close": 27.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "LUNR": {"price": 12.6, "previous_close": 12.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
        }

        report = build_sector_strength_report(quotes, collected_at="2026-04-30T13:35:00+00:00")

        self.assertTrue(report["available"])
        focus_text = "\n".join(report["focus_lines"] + report["next_actions"])
        self.assertIn("장 분위기", focus_text)
        self.assertIn("NASDAQ", focus_text)
        self.assertIn("BTCUSDT", focus_text)
        self.assertIn("WTI", focus_text)
        self.assertNotIn("QQQ", focus_text)
        self.assertNotIn("QQQ", report["benchmarks"])

    def test_sector_strength_report_keeps_benchmark_labels_when_one_quote_is_missing(self) -> None:
        from src.sector_strength import build_sector_strength_report

        quotes = {
            "SPY": {"price": 500.0, "previous_close": 499.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "SOXX": {"price": 220.0, "previous_close": 219.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "BTC-USD": {"price": 65000.0, "previous_close": 65000.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "CL=F": {"price": 80.0, "previous_close": 81.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "^VIX": {"price": 18.0, "previous_close": 18.5, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "RKLB": {"price": 30.0, "previous_close": 27.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "LUNR": {"price": 12.6, "previous_close": 12.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
        }

        report = build_sector_strength_report(quotes, collected_at="2026-04-30T13:35:00+00:00")
        focus_text = "\n".join(report["focus_lines"])

        self.assertIn("NASDAQ n/a / SPY", focus_text)
        self.assertIn("SOXX", focus_text)
        self.assertIn("BTCUSDT", focus_text)
        self.assertIn("WTI", focus_text)
        self.assertIn("VIX", focus_text)
        self.assertNotIn("QQQ", focus_text)

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
            "RKLB": {"price": 30.0, "previous_close": 27.0, "rsi14": 64.2, "rsi14_delta": 5.1, "bollinger_position_pct": 92.0, "bollinger_position_delta": 8.4, "bollinger_bandwidth_pct": 12.5, "bollinger_bandwidth_delta": 1.8, "bollinger_state": "상단권", "ichimoku_conversion": 29.5, "ichimoku_base": 28.0, "ichimoku_cloud_top": 29.0, "ichimoku_cloud_bottom": 25.0, "ichimoku_cloud_distance_pct": 3.3, "ichimoku_conversion_base_spread": 1.5, "ichimoku_cloud_state": "구름 위", "macd_line": 0.72, "macd_signal": 0.41, "macd_histogram": 0.31, "macd_histogram_delta": 0.09, "macd_state": "상방", "stochastic_k": 88.0, "stochastic_d": 82.0, "stochastic_k_delta": 4.2, "stochastic_d_delta": 2.7, "stochastic_state": "과열", "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "LUNR": {"price": 12.6, "previous_close": 12.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "COIN": {"price": 220.0, "previous_close": 211.54, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "HIMS": {"price": 45.0, "previous_close": 50.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
        }

        report = build_sector_strength_report(quotes, collected_at="2026-04-30T13:35:00+00:00")

        self.assertEqual(report["watchlist_movers"][0]["symbol"], "RKLB")
        self.assertEqual(report["watchlist_movers"][0]["theme"], "우주/항공우주")
        self.assertEqual(report["watchlist_movers"][0]["rsi14"], 64.2)
        self.assertEqual(report["watchlist_movers"][0]["bollinger_state"], "상단권")
        self.assertEqual(report["watchlist_movers"][0]["ichimoku_cloud_state"], "구름 위")
        self.assertEqual(report["watchlist_movers"][0]["macd_state"], "상방")
        self.assertEqual(report["watchlist_movers"][0]["stochastic_state"], "과열")
        expected_fragments = (
            "RSI 64(+5): 50선 위에서 재가속",
            "MACD 0.72/0.41 h+0.31(+0.09): 신호선 위·히스토그램 확대",
            "스토캐스틱 Slow 88/82(+4): 과열권 K>D 유지",
            "BB 92%(+8) 상단권: 상단 확장",
            "종합: 모멘텀 개선 중",
        )
        self.assertTrue(any("오늘 먼저 볼 종목" in line and "RKLB" in line and "COIN" in line for line in report["focus_lines"]))
        focus_text = "\n".join(report["focus_lines"])
        for fragment in expected_fragments:
            self.assertIn(fragment, focus_text)
        self.assertNotIn("Stoch ", focus_text)
        self.assertNotIn("구름", focus_text)
        self.assertNotIn("전환선", focus_text)

    def test_theme_basket_lines_include_trading_value_when_quote_has_volume(self) -> None:
        from src.sector_strength import build_sector_strength_report

        quotes = {
            "SPY": {"price": 500.0, "previous_close": 500.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "QQQ": {"price": 430.0, "previous_close": 430.0, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "RKLB": {"price": 30.0, "previous_close": 27.0, "volume": 1_000_000, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
            "LUNR": {"price": 12.6, "previous_close": 12.0, "volume": 500_000, "source": "unit", "timestamp": "2026-04-30T13:35:00+00:00"},
        }

        report = build_sector_strength_report(quotes, collected_at="2026-04-30T13:35:00+00:00")
        space = next(row for row in report["theme_baskets"] if row["key"] == "space_aerospace")

        self.assertEqual(space["trading_value"], 36300000.0)
        self.assertTrue(any("강한 테마" in line and "거래대금" in line for line in report["focus_lines"]))

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
            "src.yfinance_data.fetch_toss_wts_quote_packs", return_value={}
        ), patch(
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
            "src.yfinance_data.fetch_toss_wts_quote_packs", return_value={}
        ), patch(
            "src.yfinance_data.fetch_yahoo_chart_quote_pack", side_effect=fake_chart_pack
        ), patch("src.yfinance_data.fetch_yfinance_quote_pack", side_effect=fake_quote_pack) as quote_pack:
            quotes = fetch_sector_strength_quotes(["SPY", "RKLB"])

        self.assertEqual(quote_pack.call_count, 2)
        self.assertEqual(quotes["SPY"]["source"], "quote-only-test")
        self.assertEqual(quotes["RKLB"]["pct_change"], 1.0)

    def test_fetch_sector_strength_quotes_prefers_toss_display_price_but_keeps_yahoo_technicals(self) -> None:
        from src.sector_strength import fetch_sector_strength_quotes

        def fake_chart_pack(symbol: str) -> dict:
            return {
                "available": True,
                "source": "yahoo_chart_quote",
                "collected_at": "2026-04-30T20:05:00+00:00",
                "quote": {
                    "price": 26.5,
                    "previous_close": 26.5,
                    "pct_change": 0.0,
                    "session_label": "애프터장",
                    "is_stale_regular_close": True,
                    "rsi14": 61.2,
                },
            }

        def fake_toss_packs(symbols) -> dict:
            return {
                "RKLB": {
                    "available": True,
                    "source": "toss_wts_stock_prices",
                    "collected_at": "2026-04-30T20:06:00+00:00",
                    "quote": {
                        "price": 27.2,
                        "previous_close": 26.5,
                        "pct_change": 2.64,
                        "session_label": "토스 데이마켓/주간거래",
                        "pct_change_basis": "Toss base 대비",
                        "price_source": "toss_wts_stock_prices",
                        "is_stale_regular_close": False,
                    },
                }
            }

        with patch("src.yfinance_data.fetch_toss_wts_quote_packs", side_effect=fake_toss_packs), patch(
            "src.yfinance_data.fetch_yahoo_chart_quote_pack", side_effect=fake_chart_pack
        ), patch("src.yfinance_data.fetch_yfinance_quote_pack", side_effect=AssertionError("chart quote should be enough")):
            quotes = fetch_sector_strength_quotes(["RKLB"])

        self.assertEqual(quotes["RKLB"]["price"], 27.2)
        self.assertEqual(quotes["RKLB"]["pct_change"], 2.64)
        self.assertEqual(quotes["RKLB"]["session_label"], "토스 데이마켓/주간거래")
        self.assertEqual(quotes["RKLB"]["pct_change_basis"], "Toss base 대비")
        self.assertFalse(quotes["RKLB"]["is_stale_regular_close"])
        self.assertEqual(quotes["RKLB"]["rsi14"], 61.2)


if __name__ == "__main__":
    unittest.main()
