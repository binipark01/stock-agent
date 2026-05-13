import unittest
from types import SimpleNamespace

from src.kiwoom_client import KiwoomTRResult
from src.krx_rankings_kiwoom import build_krx_ranking_scan_v2, format_krx_ranking_scan_v2_focus


class FakeClient:
    def __init__(self):
        self.config = SimpleNamespace(normalized_env="mock", rest_base_url="https://mockapi.kiwoom.com")
        self.calls = []

    def post_tr(self, api_id, endpoint, body, cont_yn="N", next_key=""):
        self.calls.append((api_id, endpoint, body))
        payloads = {
            "ka10032": {"return_code": 0, "return_msg": "정상", "trde_prica_upper": [
                {"stk_cd": "005930", "stk_nm": "삼성전자", "acc_trde_prica": "11101719", "cur_prc": "+72000", "flu_rt": "+1.2"},
                {"stk_cd": "000660", "stk_nm": "SK하이닉스", "acc_trde_prica": "9481164", "cur_prc": "+221000", "flu_rt": "+2.1"},
            ]},
            "ka10023": {"return_code": 0, "return_msg": "정상", "trde_qty_sdnin": [
                {"stk_cd": "000660", "stk_nm": "SK하이닉스", "cur_prc": "+221000", "flu_rt": "+2.1", "prev_trde_qty": "100000", "now_trde_qty": "350000"}
            ]},
            "ka10065": {"return_code": 0, "return_msg": "정상", "opmr_invsr_trde_upper": [
                {"stk_cd": "000660", "stk_nm": "SK하이닉스", "netslmt": "+95293"}
            ]},
            "ka90009": {"return_code": 0, "return_msg": "정상", "frgnr_orgn_trde_upper": [
                {"for_netprps_stk_cd": "005930", "for_netprps_stk_nm": "삼성전자", "for_netprps_amt": "366597", "orgn_netprps_stk_cd": "000660", "orgn_netprps_stk_nm": "SK하이닉스", "orgn_netprps_amt": "47483"}
            ]},
            "ka90003": {"return_code": 0, "return_msg": "정상", "prm_netprps_upper_50": [
                {"stk_cd": "000660", "stk_nm": "SK하이닉스", "netprps_amt": "88000"}
            ]},
            "ka10021": {"return_code": 0, "return_msg": "정상", "bid_req_upper": [
                {"stk_cd": "005930", "stk_nm": "삼성전자", "bid_req": "2100000", "ask_req": "900000"}
            ]},
            "ka10035": {"return_code": 0, "return_msg": "정상", "frgn_cont_nettrde_upper": [
                {"stk_cd": "005930", "stk_nm": "삼성전자", "cont_netprps_dys": "3", "netprps_qty": "180000"}
            ]},
            "ka10033": {"return_code": 0, "return_msg": "정상", "crd_rt_upper": [
                {"stk_cd": "000660", "stk_nm": "SK하이닉스", "crd_rt": "8.5"}
            ]},
            "ka10069": {"return_code": 0, "return_msg": "정상", "slb_upper": [
                {"stk_cd": "005930", "stk_nm": "삼성전자", "loan_balance": "1200000"}
            ]},
        }
        return KiwoomTRResult(data=payloads[api_id], status_code=200)


class KrxRankingsKiwoomTest(unittest.TestCase):
    def test_rank_scan_v2_collects_multi_source_sections_with_metadata(self):
        client = FakeClient()

        scan = build_krx_ranking_scan_v2(client, limit=3)

        self.assertEqual("kiwoom", scan["source"])
        self.assertEqual("mock", scan["env"])
        self.assertEqual("https://mockapi.kiwoom.com", scan["base_url"])
        self.assertEqual(8, len(scan["sections"]))
        self.assertEqual([
            "ka10032", "ka10023", "ka10065", "ka90009", "ka90003", "ka10021", "ka10035", "ka10033",
        ], [call[0] for call in client.calls])
        self.assertEqual("ok", scan["sections"]["volume_surge"]["status"])
        self.assertEqual("ka10023", scan["sections"]["volume_surge"]["api_id"])
        self.assertEqual("000660", scan["sections"]["volume_surge"]["rows"][0]["code"])
        self.assertEqual(350000, scan["sections"]["volume_surge"]["rows"][0]["current_volume"])

    def test_rank_scan_v2_scores_candidates_from_confirmed_signals_and_risks(self):
        scan = build_krx_ranking_scan_v2(FakeClient(), limit=3)

        by_code = {candidate["code"]: candidate for candidate in scan["candidates"]}
        self.assertEqual("눌림대기", by_code["000660"]["bucket"])
        self.assertIn("trade_value_top", by_code["000660"]["signals"])
        self.assertIn("volume_surge", by_code["000660"]["signals"])
        self.assertNotIn("institution_net_buy_top", by_code["000660"]["signals"])
        self.assertIn("institution_net_buy_ignored_tiny", by_code["000660"]["evidence"])
        self.assertIn("program_net_buy_top", by_code["000660"]["signals"])
        self.assertIn("credit_ratio_high_risk", by_code["000660"]["risks"])
        self.assertNotIn("institution_net_buy_top", by_code["000660"]["signals"])
        self.assertNotIn("foreign_net_buy_top", by_code["005930"]["signals"])
        self.assertIn("foreign_net_buy_rank_bucket", by_code["005930"]["evidence"])
        self.assertIn("foreign_buy_streak", by_code["005930"]["signals"])

    def test_focus_format_makes_mock_domain_and_prod_switch_explicit(self):
        scan = build_krx_ranking_scan_v2(FakeClient(), limit=2)

        lines = format_krx_ranking_scan_v2_focus(scan)
        text = "\n".join(lines)

        self.assertIn("env=mock", text)
        self.assertIn("mockapi.kiwoom.com", text)
        self.assertIn("모의투자 도메인 실호출", text)
        self.assertIn("prod 전환", text)
        self.assertIn("주문 API 비활성", text)


if __name__ == "__main__":
    unittest.main()
