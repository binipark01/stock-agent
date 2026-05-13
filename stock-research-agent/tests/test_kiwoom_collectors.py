import unittest
from types import SimpleNamespace

from src.kiwoom_client import KiwoomTRResult
from src.kiwoom_collectors import TRCallResult, call_kiwoom_tr, call_market_tr
from src.kiwoom_api_catalog import KiwoomApiPermissionError


class FakeClient:
    def __init__(self, env="mock", payload=None, cont_yn="N", next_key=""):
        self.config = SimpleNamespace(normalized_env=env, rest_base_url="https://mockapi.kiwoom.com")
        self.payload = payload or {"return_code": 0, "return_msg": "정상적으로 처리되었습니다", "trde_prica_upper": [{"stk_cd": "005930"}]}
        self.cont_yn = cont_yn
        self.next_key = next_key
        self.calls = []

    def post_tr(self, api_id, endpoint, body, cont_yn="N", next_key=""):
        self.calls.append({"api_id": api_id, "endpoint": endpoint, "body": body, "cont_yn": cont_yn, "next_key": next_key})
        return KiwoomTRResult(data=self.payload, cont_yn=self.cont_yn, next_key=self.next_key, status_code=200)


class KiwoomCollectorsTest(unittest.TestCase):
    def test_call_market_tr_uses_catalog_endpoint_and_merges_default_body(self):
        client = FakeClient()

        result = call_market_tr(client, "ka10032", {"mrkt_tp": "101", "limit": "5"})

        self.assertIsInstance(result, TRCallResult)
        self.assertEqual("ok", result.status)
        self.assertEqual("kiwoom", result.source)
        self.assertEqual("mock", result.env)
        self.assertEqual("ka10032", result.api_id)
        self.assertEqual("/api/dostk/rkinfo", result.endpoint)
        self.assertEqual(0, result.return_code)
        self.assertEqual("정상적으로 처리되었습니다", result.return_msg)
        self.assertEqual(1, result.row_count)
        self.assertIn("collected_at", result.to_dict())
        self.assertEqual(
            {"mrkt_tp": "101", "mang_stk_incls": "0", "stex_tp": "1", "limit": "5"},
            client.calls[0]["body"],
        )

    def test_call_market_tr_marks_empty_payload_without_error(self):
        client = FakeClient(payload={"return_code": 0, "return_msg": "정상적으로 처리되었습니다", "prm_netprps_upper_50": []})

        result = call_market_tr(client, "ka90003")

        self.assertEqual("empty", result.status)
        self.assertEqual(0, result.row_count)
        self.assertEqual([], result.rows)

    def test_call_market_tr_preserves_safe_kiwoom_error_message(self):
        client = FakeClient(payload={"return_code": 2, "return_msg": "입력 값 오류입니다[1511:필수 입력 값]"})

        result = call_market_tr(client, "ka10032")

        self.assertEqual("error", result.status)
        self.assertEqual(2, result.return_code)
        self.assertIn("1511", result.return_msg)
        self.assertEqual(0, result.row_count)

    def test_safety_gate_blocks_account_and_order_trs_by_default(self):
        client = FakeClient(payload={"return_code": 0, "return_msg": "정상적으로 처리되었습니다"})

        with self.assertRaises(KiwoomApiPermissionError):
            call_kiwoom_tr(client, "kt00001")
        with self.assertRaises(KiwoomApiPermissionError):
            call_kiwoom_tr(client, "kt10000", allow_account=True)

        account = call_kiwoom_tr(client, "kt00001", allow_account=True)
        self.assertEqual("account_readonly", account.risk_tier)


if __name__ == "__main__":
    unittest.main()
