import unittest


class KrxConditionUniverseTest(unittest.TestCase):
    def test_builds_condition_universe_from_rank_scan_sections(self):
        from src.krx_condition_universe import build_condition_universe_from_rank_scan

        scan = {
            "source": "kiwoom",
            "source_environment": "mock",
            "base_url": "https://mockapi.kiwoom.com",
            "collected_at": "t",
            "sections": {
                "trade_value": {"rows": [
                    {"rank": 1, "code": "005380", "name": "현대차", "trade_value": 880000000000, "change_pct": 7.17, "current_price": 613000},
                    {"rank": 2, "code": "001440", "name": "대한전선", "trading_value": 550000000000, "change_pct": 12.7},
                ]},
                "investor_intraday": {"rows": [
                    {"rank": 1, "code": "005380", "name": "현대차", "net_buy_amount": 12000000000, "net_buy_quantity": 12000},
                ]},
                "foreign_institution": {"rows": [
                    {
                        "rank": 1,
                        "foreign_net_buy_code": "005380", "foreign_net_buy_name": "현대차",
                        "foreign_net_buy_amount": 22000000000, "foreign_net_buy_quantity": 523820,
                        "institution_net_buy_code": "000660", "institution_net_buy_name": "SK하이닉스",
                        "institution_net_buy_amount": 8000000000, "institution_net_buy_quantity": 181374,
                    }
                ]},
                "program_net_buy": {"rows": [
                    {"rank": 1, "code": "005380", "name": "현대차", "program_net_buy_amount": 5000000000, "program_net_buy_quantity": 462230},
                ]},
            },
        }
        universe = build_condition_universe_from_rank_scan(scan, limit=10)
        self.assertEqual("krx_condition_universe", universe["mode"])
        self.assertEqual("mock", universe["source_environment"])
        stocks = {row["code"]: row for row in universe["stocks"]}
        self.assertEqual(3, len(stocks))
        hyundai = stocks["005380"]
        self.assertEqual(1, hyundai["trade_value_rank"])
        self.assertEqual(880000000000, hyundai["trade_value"])
        self.assertEqual(523820, hyundai["foreign_net_buy"])
        self.assertEqual(462230, hyundai["program_net_buy"])
        self.assertIn("trade_value_top", hyundai["rank_signals"])
        hynix = stocks["000660"]
        self.assertEqual(181374, hynix["institution_net_buy"])

    def test_condition_scan_can_use_generated_universe(self):
        from src.krx_condition_universe import build_condition_universe_from_rank_scan
        from src.krx_condition_engine import run_krx_condition_scan

        scan = {
            "source": "kiwoom",
            "source_environment": "mock",
            "collected_at": "t",
            "sections": {
                "trade_value": {"rows": [{"rank": 5, "code": "005380", "name": "현대차", "trade_value": 1_000_000_000_000, "change_pct": 7.17}]},
                "investor_intraday": {"rows": [{"code": "005380", "name": "현대차", "net_buy_quantity": 10000}]},
                "foreign_institution": {"rows": [{"foreign_net_buy_code": "005380", "foreign_net_buy_name": "현대차", "foreign_net_buy_quantity": 523820, "institution_net_buy_code": "005380", "institution_net_buy_name": "현대차", "institution_net_buy_quantity": 439195}]},
                "program_net_buy": {"rows": [{"code": "005380", "name": "현대차", "program_net_buy_quantity": 462230}]},
            },
        }
        stocks = build_condition_universe_from_rank_scan(scan)["stocks"]
        report = run_krx_condition_scan(stocks, condition_names=["supply_accumulation"], collected_at="t")
        top = report["conditions"][0]["results"][0]
        self.assertEqual("005380", top["stock"]["code"])
        self.assertGreaterEqual(top["score"], 5)

    def test_mode_handler_auto_builds_universe_from_rank_scan_runtime(self):
        from src.krx_mode_handlers import build_krx_condition_scan_mode_response

        scan = {
            "source": "kiwoom",
            "source_environment": "mock",
            "base_url": "https://mockapi.kiwoom.com",
            "collected_at": "t",
            "sections": {
                "trade_value": {"rows": [{"rank": 1, "code": "005380", "name": "현대차", "trade_value": 900000000000, "change_pct": 7.17}]},
                "investor_intraday": {"rows": [{"code": "005380", "name": "현대차", "net_buy_quantity": 10000}]},
                "foreign_institution": {"rows": [{"foreign_net_buy_code": "005380", "foreign_net_buy_name": "현대차", "foreign_net_buy_quantity": 523820, "institution_net_buy_code": "005380", "institution_net_buy_name": "현대차", "institution_net_buy_quantity": 439195}]},
                "program_net_buy": {"status": "empty", "rows": []},
            },
        }
        response = build_krx_condition_scan_mode_response(
            {"condition_names": ["supply_accumulation"]},
            {"krx_flow_rank_scan": scan},
            "국장 검색식 돌려봐",
            [],
        )
        self.assertEqual("krx_condition_scan", response["mode"])
        raw = response["raw"]
        self.assertEqual("mock", raw["source_environment"])
        self.assertEqual(1, raw["condition_universe"]["stock_count"])
        self.assertIn("현대차(005380)", "\n".join(response["focus"]))


if __name__ == "__main__":
    unittest.main()
