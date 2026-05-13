import unittest

from src.krx_condition_engine import (
    DEFAULT_CONDITION_SETS,
    evaluate_condition_set,
    run_krx_condition_scan,
    format_krx_condition_scan_report,
)


class KrxConditionEngineTest(unittest.TestCase):
    def test_default_condition_sets_include_practical_krx_screens(self):
        expected = {
            "manju_close_bet",
            "supply_accumulation",
            "theme_leader",
            "theme_pairing",
            "momentum_continuation",
            "risk_avoid",
        }
        self.assertTrue(expected.issubset(DEFAULT_CONDITION_SETS.keys()))

    def test_manju_close_bet_scores_strong_supply_candidate(self):
        stock = {
            "code": "005380",
            "name": "현대차",
            "change_pct": 7.17,
            "trade_value_rank": 5,
            "close_position_pct": 88,
            "theme_strength_score": 3,
            "theme_leader_rank": 1,
            "foreign_net_buy": 523820,
            "institution_net_buy": 439195,
            "program_net_buy": 462230,
            "news_momentum": 2,
            "is_management_stock": False,
            "is_investment_warning": False,
        }
        result = evaluate_condition_set(DEFAULT_CONDITION_SETS["manju_close_bet"], stock)
        self.assertTrue(result["passed"])
        self.assertFalse(result["excluded"])
        self.assertEqual("종가베팅 후보", result["label"])
        self.assertGreaterEqual(result["score"], 15)
        self.assertIn("거래대금 100위 이내", result["matched"])
        self.assertIn("프로그램 순매수", result["matched"])

    def test_risk_and_divergence_candidate_is_excluded(self):
        stock = {
            "code": "000660",
            "name": "SK하이닉스",
            "change_pct": 2.8,
            "trade_value_rank": 3,
            "close_position_pct": 81,
            "foreign_net_buy": -980000,
            "program_net_buy": -760000,
            "price_up_flow_divergence": True,
            "is_investment_warning": False,
            "is_management_stock": False,
        }
        result = evaluate_condition_set(DEFAULT_CONDITION_SETS["risk_avoid"], stock)
        self.assertTrue(result["excluded"])
        self.assertEqual("위험제외", result["label"])
        self.assertIn("가격상승/수급이탈", result["excluded_by"])

    def test_scan_runs_multiple_conditions_and_formats_reasons(self):
        stocks = [
            {
                "code": "005380", "name": "현대차", "change_pct": 7.17, "trade_value_rank": 5,
                "close_position_pct": 88, "theme_strength_score": 3, "theme_leader_rank": 1,
                "foreign_net_buy": 523820, "institution_net_buy": 439195, "program_net_buy": 462230,
                "news_momentum": 2, "is_management_stock": False, "is_investment_warning": False,
            },
            {
                "code": "000660", "name": "SK하이닉스", "change_pct": 2.8, "trade_value_rank": 3,
                "close_position_pct": 81, "foreign_net_buy": -980000, "program_net_buy": -760000,
                "price_up_flow_divergence": True, "is_management_stock": False, "is_investment_warning": False,
            },
        ]
        report = run_krx_condition_scan(stocks, condition_names=["manju_close_bet", "risk_avoid"], collected_at="t")
        self.assertEqual("krx_condition_scan", report["mode"])
        self.assertEqual(2, report["stock_count"])
        self.assertEqual("manju_close_bet", report["conditions"][0]["id"])
        text = "\n".join(format_krx_condition_scan_report(report))
        self.assertIn("만쥬식 종가배팅", text)
        self.assertIn("현대차(005380)", text)
        self.assertIn("SK하이닉스(000660)", text)
        self.assertIn("위험제외", text)


if __name__ == "__main__":
    unittest.main()
