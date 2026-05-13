import unittest

from src.krx_flows_kiwoom import (
    build_krx_flow_rank_scan,
    build_krx_flow_rank_watch_report,
    build_krx_flow_trade_candidates,
    build_krx_flow_watch_report,
    build_krx_flow_snapshot,
    format_krx_flow_focus,
    format_krx_flow_rank_focus,
    format_krx_flow_trade_candidate_focus,
    format_krx_flow_watch_focus,
    normalize_krx_code,
)


class FakeKiwoomClient:
    def __init__(self):
        self.calls = []

    def post_tr(self, api_id, endpoint, body, **kwargs):
        self.calls.append((api_id, endpoint, body))
        payloads = {
            "ka10032": {
                "trde_prica_upper": [
                    {
                        "rank": "1",
                        "stk_cd": "005930",
                        "stk_nm": "삼성전자",
                        "cur_prc": "+71500",
                        "flu_rt": "+0.70",
                        "acc_trde_prica": "8580000000",
                        "trde_qty": "120000",
                    }
                ]
            },
            "ka10065": {
                "opmr_invsr_trde_upper": [
                    {
                        "stk_cd": "000660",
                        "stk_nm": "SK하이닉스",
                        "sel_qty": "-911330",
                        "buy_qty": "+1006623",
                        "netslmt": "+95293",
                    }
                ]
            },
            "ka90009": {
                "frgnr_orgn_trde_upper": [
                    {
                        "for_netslmt_stk_cd": "402340",
                        "for_netslmt_stk_nm": "SK스퀘어",
                        "for_netslmt_amt": "-49383",
                        "for_netslmt_qty": "-454",
                        "for_netprps_stk_cd": "005930",
                        "for_netprps_stk_nm": "삼성전자",
                        "for_netprps_amt": "366597",
                        "for_netprps_qty": "13782",
                        "orgn_netslmt_stk_cd": "005930",
                        "orgn_netslmt_stk_nm": "삼성전자",
                        "orgn_netslmt_amt": "-12000",
                        "orgn_netslmt_qty": "-700",
                        "orgn_netprps_stk_cd": "000660",
                        "orgn_netprps_stk_nm": "SK하이닉스",
                        "orgn_netprps_amt": "16198",
                        "orgn_netprps_qty": "900",
                    }
                ]
            },
            "ka10001": {
                "stk_cd": "005930",
                "stk_nm": "삼성전자",
                "cur_prc": "+71500",
                "pred_pre": "+500",
                "flu_rt": "+0.70",
                "mac": "4260000",
            },
            "ka10004": {
                "bid_req_base_tm": "093001",
                "sel_1th_pre_req_pre": "71600",
                "buy_1th_pre_req_pre": "71500",
                "sel_1th_pre_req": "12000",
                "buy_1th_pre_req": "15000",
            },
            "ka10046": {
                "stk_cd": "005930",
                "cntr_str_tm": [
                    {
                        "cntr_tm": "093000",
                        "cur_prc": "+71500",
                        "trde_qty": "120000",
                        "acc_trde_prica": "8580000000",
                        "cntr_str": "152.3",
                        "cntr_str_5min": "148.0",
                    }
                ],
            },
            "ka10063": {
                "netprps_amt": "+12500",
                "netprps_qty": "+180000",
                "buy_amt": "42000",
                "sell_amt": "29500",
            },
            "ka90003": {
                "prm_netprps_upper_50": [
                    {
                        "rank": "1",
                        "stk_cd": "005930",
                        "stk_nm": "삼성전자",
                        "prm_sell_amt": "10000",
                        "prm_buy_amt": "15500",
                        "prm_netprps_amt": "+5500",
                    }
                ]
            },
            "ka90008": {
                "stk_prm_tm_trde_trnsn": [
                    {
                        "tm": "093000",
                        "prm_sell_amt": "10000",
                        "prm_buy_amt": "15500",
                        "prm_netprps_amt": "+5500",
                        "prm_netprps_qty": "+90000",
                    }
                ]
            },
        }
        return type("Result", (), {"data": payloads[api_id], "cont_yn": "N", "next_key": ""})()


class KrxFlowsKiwoomTest(unittest.TestCase):
    def test_normalize_krx_code_accepts_korean_alias_and_symbol_forms(self):
        self.assertEqual(normalize_krx_code("삼성전자"), "005930")
        self.assertEqual(normalize_krx_code("005930"), "005930")
        self.assertEqual(normalize_krx_code("A005930"), "005930")
        self.assertEqual(normalize_krx_code("005930.KS"), "005930")
        self.assertEqual(normalize_krx_code("000660.KS"), "000660")

    def test_build_krx_flow_snapshot_calls_high_value_trs_and_labels_source_time(self):
        client = FakeKiwoomClient()

        snapshot = build_krx_flow_snapshot(["삼성전자"], client=client, collected_at="2026-05-07T19:40:00+09:00")

        self.assertEqual(snapshot["source"], "kiwoom")
        self.assertEqual(snapshot["collected_at"], "2026-05-07T19:40:00+09:00")
        self.assertEqual(snapshot["symbols"], ["005930"])
        stock = snapshot["stocks"][0]
        self.assertEqual(stock["code"], "005930")
        self.assertEqual(stock["name"], "삼성전자")
        self.assertEqual(stock["basic"]["current_price"], 71500)
        self.assertEqual(stock["orderbook"]["best_ask"], 71600)
        self.assertEqual(stock["execution_strength"]["latest"]["execution_strength"], 152.3)
        self.assertEqual(stock["intraday_investor_flow"]["net_buy_quantity"], 180000)
        self.assertEqual(stock["program_intraday"]["latest"]["program_net_buy_amount"], 5500)
        self.assertIn(("ka10001", "/api/dostk/stkinfo", {"stk_cd": "005930"}), client.calls)
        self.assertIn(("ka90008", "/api/dostk/mrkcond", {"stk_cd": "005930", "amt_qty_tp": "1", "date": ""}), client.calls)

    def test_format_krx_flow_focus_is_compact_and_includes_tr_labels(self):
        snapshot = build_krx_flow_snapshot(["삼성전자"], client=FakeKiwoomClient(), collected_at="2026-05-07T19:40:00+09:00")

        focus = format_krx_flow_focus(snapshot)

        joined = "\n".join(focus)
        self.assertIn("삼성전자(005930)", joined)
        self.assertIn("현재가 71,500", joined)
        self.assertIn("체결강도 152.3", joined)
        self.assertIn("장중 투자자 순매수", joined)
        self.assertIn("프로그램 순매수", joined)
        self.assertIn("ka10001", joined)
        self.assertIn("ka90008", joined)

    def test_build_krx_flow_rank_scan_combines_trade_value_investor_and_program_sections(self):
        client = FakeKiwoomClient()

        scan = build_krx_flow_rank_scan(client=client, collected_at="2026-05-07T10:00:00+09:00", limit=5)

        self.assertEqual(scan["mode"], "krx_flow_rank_scan")
        self.assertEqual(scan["source"], "kiwoom")
        self.assertEqual(scan["sections"]["trade_value"]["tr"], "ka10032")
        self.assertEqual(scan["sections"]["trade_value"]["rows"][0]["code"], "005930")
        self.assertEqual(scan["sections"]["trade_value"]["rows"][0]["trading_value"], 8580000000)
        self.assertEqual(scan["sections"]["investor_intraday"]["rows"][0]["code"], "000660")
        self.assertEqual(scan["sections"]["investor_intraday"]["rows"][0]["buy_quantity"], 1006623)
        self.assertEqual(scan["sections"]["investor_intraday"]["rows"][0]["net_buy_quantity"], 95293)
        self.assertEqual(scan["sections"]["foreign_institution"]["rows"][0]["code"], "005930")
        self.assertEqual(scan["sections"]["foreign_institution"]["rows"][0]["name"], "삼성전자")
        self.assertEqual(scan["sections"]["foreign_institution"]["rows"][0]["foreign_net_buy_amount"], 366597)
        self.assertEqual(scan["sections"]["foreign_institution"]["rows"][0]["institution_net_buy_amount"], 16198)
        self.assertEqual(scan["sections"]["program_net_buy"]["rows"][0]["program_net_buy_amount"], 5500)
        called_api_ids = [call[0] for call in client.calls]
        self.assertIn("ka10032", called_api_ids)
        self.assertIn("ka10065", called_api_ids)
        self.assertIn("ka90009", called_api_ids)
        self.assertIn("ka90003", called_api_ids)
        lines = format_krx_flow_rank_focus(scan)
        joined = "\n".join(lines)
        self.assertIn("거래대금 상위", joined)
        self.assertIn("외국인/기관", joined)
        self.assertIn("프로그램", joined)

    def test_build_krx_flow_trade_candidates_merges_rank_sections_into_buying_triage(self):
        scan = build_krx_flow_rank_scan(client=FakeKiwoomClient(), collected_at="2026-05-07T10:00:00+09:00", limit=5)

        candidates = build_krx_flow_trade_candidates(scan)

        self.assertEqual(candidates[0]["code"], "005930")
        self.assertEqual(candidates[0]["name"], "삼성전자")
        self.assertGreaterEqual(candidates[0]["score"], 7)
        self.assertIn("trade_value_top", candidates[0]["signals"])
        self.assertIn("foreign_net_buy_top", candidates[0]["signals"])
        self.assertIn("program_net_buy_top", candidates[0]["signals"])
        self.assertEqual(candidates[0]["judgment"], "눌림 대기")
        sk = next(candidate for candidate in candidates if candidate["code"] == "000660")
        self.assertIn("investor_intraday_net_buy", sk["signals"])
        self.assertIn("institution_net_buy_top", sk["signals"])
        self.assertIn(sk["judgment"], {"관찰", "눌림 대기"})
        lines = format_krx_flow_trade_candidate_focus(candidates, limit=3)
        joined = "\n".join(lines)
        self.assertIn("매매 후보", joined)
        self.assertIn("추격", joined)
        self.assertIn("삼성전자(005930)", joined)

    def test_build_krx_flow_rank_watch_report_flags_new_and_strengthening_candidates(self):
        previous = {
            "mode": "krx_flow_rank_scan",
            "collected_at": "2026-05-07T09:55:00+09:00",
            "sections": {
                "trade_value": {"rows": [{"rank": 3, "code": "005930", "name": "삼성전자", "trading_value": 1000}]},
                "investor_intraday": {"rows": []},
                "foreign_institution": {"rows": []},
                "program_net_buy": {"rows": []},
            },
        }
        current = build_krx_flow_rank_scan(client=FakeKiwoomClient(), collected_at="2026-05-07T10:00:00+09:00", limit=5)

        report = build_krx_flow_rank_watch_report(previous, current)

        self.assertEqual(report["mode"], "krx_flow_rank_watch")
        samsung = next(item for item in report["changes"] if item["code"] == "005930")
        self.assertGreaterEqual(samsung["score_delta"], 5)
        self.assertIn("signal_strengthening", samsung["alerts"])
        self.assertIn("foreign_net_buy_top", samsung["new_signals"])
        self.assertIn("program_net_buy_top", samsung["new_signals"])
        hynix = next(item for item in report["changes"] if item["code"] == "000660")
        self.assertIn("new_candidate", hynix["alerts"])

    def test_build_krx_flow_watch_report_flags_program_execution_and_trading_value_changes(self):
        previous = {
            "collected_at": "2026-05-07T09:55:00+09:00",
            "stocks": [
                {
                    "code": "005930",
                    "name": "삼성전자",
                    "basic": {"current_price": 70000},
                    "execution_strength": {"latest": {"execution_strength": 101.0, "accumulated_trading_value": 1000000}},
                    "intraday_investor_flow": {"net_buy_quantity": 1000, "net_buy_amount": 100},
                    "program_intraday": {"latest": {"program_net_buy_quantity": 1000, "program_net_buy_amount": 1000}},
                }
            ],
        }
        current = {
            "collected_at": "2026-05-07T10:00:00+09:00",
            "stocks": [
                {
                    "code": "005930",
                    "name": "삼성전자",
                    "basic": {"current_price": 71500},
                    "execution_strength": {"latest": {"execution_strength": 152.3, "accumulated_trading_value": 8580000000}},
                    "intraday_investor_flow": {"net_buy_quantity": 180000, "net_buy_amount": 12500},
                    "program_intraday": {"latest": {"program_net_buy_quantity": 90000, "program_net_buy_amount": 5500}},
                }
            ],
        }

        report = build_krx_flow_watch_report(previous, current)

        self.assertEqual(report["mode"], "krx_flow_watch")
        diff = report["diffs"][0]
        self.assertEqual(diff["code"], "005930")
        self.assertEqual(diff["price_delta"], 1500)
        self.assertEqual(diff["program_net_buy_amount_delta"], 4500)
        self.assertIn("program_net_buy_acceleration", diff["alerts"])
        self.assertIn("execution_strength_spike", diff["alerts"])
        self.assertIn("trading_value_surge", diff["alerts"])
        self.assertIn("investor_net_buy_acceleration", diff["alerts"])
        lines = format_krx_flow_watch_focus(report)
        self.assertIn("프로그램", "\n".join(lines))


if __name__ == "__main__":
    unittest.main()
