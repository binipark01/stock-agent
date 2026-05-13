import unittest
from types import SimpleNamespace

from src.kiwoom_client import KiwoomTRResult
from src.krx_symbol_flow_kiwoom import build_krx_symbol_flow_snapshot_v2, format_krx_symbol_flow_snapshot_v2


class FakeConfig:
    normalized_env = "mock"
    rest_base_url = "https://mockapi.kiwoom.com"


class FakeClient:
    config = FakeConfig()

    def __init__(self):
        self.calls = []

    def post_tr(self, api_id, endpoint, body, cont_yn="N", next_key=""):
        self.calls.append((api_id, endpoint, dict(body)))
        payloads = {
            "ka10009": {"date": "20260508", "orgn_daly_nettrde": "-138096", "frgnr_daly_nettrde": "-1584", "return_code": 0, "return_msg": "정상"},
            "ka10045": {"stk_orgn_trde_trnsn": [
                {"dt": "20260508", "orgn_daly_nettrde_qty": "-138096", "for_daly_nettrde_qty": "-1584", "trde_qty": "1000000"}
            ], "return_code": 0, "return_msg": "정상"},
            "ka90008": {"stk_tm_prm_trde_trnsn": [
                {"tm": "153939", "prm_netprps_qty": "--913990", "prm_netprps_amt": "--1479223", "base_pric_tm": "153900"}
            ], "return_code": 0, "return_msg": "정상"},
            "ka10008": {"stk_frgnr": [
                {"dt": "20260508", "chg_qty": "-1584", "limit_exh_rt": "+26.14"}
            ], "return_code": 0, "return_msg": "정상"},
        }
        return KiwoomTRResult(data=payloads[api_id], status_code=200)


class StaleClient(FakeClient):
    def post_tr(self, api_id, endpoint, body, cont_yn="N", next_key=""):
        if api_id == "ka10009":
            self.calls.append((api_id, endpoint, dict(body)))
            return KiwoomTRResult(data={"date": "20260507", "orgn_daly_nettrde": "293", "frgnr_daly_nettrde": "-1584", "return_code": 0, "return_msg": "정상"}, status_code=200)
        if api_id == "ka10045":
            self.calls.append((api_id, endpoint, dict(body)))
            return KiwoomTRResult(data={"stk_orgn_trde_trnsn": [{"dt": "20260507", "orgn_daly_nettrde_qty": "293", "for_daly_nettrde_qty": "-1584"}], "return_code": 0, "return_msg": "정상"}, status_code=200)
        return super().post_tr(api_id, endpoint, body, cont_yn, next_key)


class KrxSymbolFlowKiwoomTest(unittest.TestCase):
    def test_symbol_flow_uses_dated_individual_trs_not_ranking_buckets(self):
        client = FakeClient()
        snapshot = build_krx_symbol_flow_snapshot_v2(client, "000660", as_of_date="20260508")

        self.assertEqual(["ka10009", "ka10045", "ka90008", "ka10008"], [call[0] for call in client.calls])
        self.assertEqual("20260508", snapshot["requested_date"])
        self.assertTrue(snapshot["is_today_confirmed"])
        self.assertEqual(-138096, snapshot["institution_net_buy_qty"])
        self.assertEqual(-1584, snapshot["foreign_net_buy_qty"])
        self.assertEqual(-913990, snapshot["program_net_buy_qty"])
        self.assertEqual("기관매도", snapshot["supply_signal"])

    def test_symbol_flow_warns_when_latest_rows_are_stale_or_tiny(self):
        snapshot = build_krx_symbol_flow_snapshot_v2(StaleClient(), "000660", as_of_date="20260508")

        self.assertFalse(snapshot["is_today_confirmed"])
        self.assertEqual(293, snapshot["institution_net_buy_qty"])
        self.assertEqual("기준일미확인", snapshot["supply_signal"])
        text = "\n".join(format_krx_symbol_flow_snapshot_v2(snapshot))
        self.assertIn("당일 기관/외인 데이터 미확인", text)
        self.assertIn("materiality threshold", text)
        self.assertIn("env=mock", text)


if __name__ == "__main__":
    unittest.main()
