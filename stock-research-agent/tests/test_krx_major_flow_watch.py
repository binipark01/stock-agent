import unittest

from src.kr.flow.major_watch import build_krx_major_flow_watch_report, build_krx_major_flow_watch_response
from src.main import build_response
from src.request_modes import infer_mode


class KrxMajorFlowWatchTest(unittest.TestCase):
    def _snapshot(self, symbol, inst=0, foreign=0, program=0, today=True):
        return {
            "symbol": symbol,
            "env": "mock",
            "base_url": "https://mockapi.kiwoom.com",
            "collected_at": "2026-05-13T09:10:00+09:00",
            "requested_date": "20260513",
            "data_dates": {"ka10009": "20260513"},
            "is_today_confirmed": today,
            "institution_net_buy_qty": inst,
            "foreign_net_buy_qty": foreign,
            "program_net_buy_qty": program,
            "program_net_buy_amt": program * 1000,
            "warnings": [],
        }

    def test_scores_fixed_major_symbols_without_rank_scan(self):
        report = build_krx_major_flow_watch_report(
            snapshots=[
                self._snapshot("005930", inst=220000, foreign=130000, program=450000),
                self._snapshot("000660", inst=-180000, foreign=-210000, program=-330000),
            ],
            symbols=["005930", "000660"],
            collected_at="2026-05-13T09:10:00+09:00",
            as_of_date="20260513",
        )
        self.assertEqual(report["mode"], "krx_major_flow_watch")
        self.assertEqual(report["watched_count"], 2)
        self.assertEqual(report["env"], "mock")
        self.assertEqual(report["top_candidates"][0]["code"], "005930")
        self.assertEqual(report["top_candidates"][0]["action"], "추적")
        weak = [row for row in report["results"] if row["code"] == "000660"][0]
        self.assertEqual(weak["action"], "버림")

    def test_response_is_mobile_action_oriented(self):
        report = build_krx_major_flow_watch_report(
            snapshots=[self._snapshot("005930", inst=220000, foreign=130000, program=450000)],
            symbols=["005930"],
            collected_at="2026-05-13T09:10:00+09:00",
        )
        response = build_krx_major_flow_watch_response(report)
        self.assertEqual(response["mode"], "krx_major_flow_watch")
        self.assertIn("주요종목 고정 수급 감시", response["summary"])
        self.assertTrue(any("결론:" in line for line in response["focus"]))
        self.assertIn("major_flow_watch", response["features"])

    def test_request_mode_routes_major_flow_watch(self):
        self.assertEqual(infer_mode("국장 주요종목 수급 고정 감시"), "krx_major_flow_watch")
        self.assertEqual(infer_mode("랭킹 누락 대비 대형주 수급 모니터"), "krx_major_flow_watch")

    def test_main_response_uses_runtime_snapshots_without_live_client(self):
        payload = build_response(
            "국장 주요종목 수급 고정 감시",
            runtime_context={
                "krx_major_flow_snapshots": [self._snapshot("005930", inst=220000, foreign=130000, program=450000)],
                "krx_major_symbols": ["005930"],
                "collected_at": "2026-05-13T09:10:00+09:00",
            },
            explicit_mode="krx_major_flow_watch",
        )
        self.assertEqual(payload["mode"], "krx_major_flow_watch")
        self.assertIn("주요종목 고정 수급 감시", payload["summary"])
        self.assertEqual(payload["raw"]["krx_major_flow_watch"]["top_candidates"][0]["code"], "005930")


if __name__ == "__main__":
    unittest.main()
