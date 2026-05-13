import unittest

from src.krx_session_flow_watch import (
    build_krx_session_flow_watch_report,
    build_krx_session_flow_watch_response,
    format_krx_session_flow_watch_report,
)


class KrxSessionFlowWatchTest(unittest.TestCase):
    def test_detects_nxt_continuation_and_flow_acceleration(self) -> None:
        snapshots = [
            {
                "session": "regular",
                "collected_at": "2026-05-08T15:20:00+09:00",
                "env": "mock",
                "source": "kiwoom",
                "stocks": [
                    {
                        "code": "005380",
                        "name": "현대차",
                        "price": 613000,
                        "change_pct": 7.17,
                        "foreign_net_buy": 523820,
                        "institution_net_buy": 439195,
                        "program_net_buy": 462230,
                        "volume": 5020568,
                    }
                ],
            },
            {
                "session": "nxt",
                "collected_at": "2026-05-08T18:10:00+09:00",
                "env": "mock",
                "source": "nxt_quote+latest_kiwoom_flow",
                "stocks": [
                    {
                        "code": "005380",
                        "name": "현대차",
                        "price": 620000,
                        "change_pct": 8.39,
                        "foreign_net_buy": 610000,
                        "institution_net_buy": 470000,
                        "program_net_buy": 540000,
                        "volume": 5520000,
                    }
                ],
            },
        ]

        report = build_krx_session_flow_watch_report(snapshots)

        self.assertEqual(report["session_path"], ["regular", "nxt"])
        item = report["items"][0]
        self.assertEqual(item["code"], "005380")
        self.assertIn("session_continuation", item["alerts"])
        self.assertIn("program_buy_acceleration", item["alerts"])
        self.assertIn("foreign_buy_acceleration", item["alerts"])
        self.assertTrue(report["nxt_caveat"])

    def test_detects_price_up_flow_divergence_and_session_reversal(self) -> None:
        snapshots = [
            {
                "session": "regular",
                "collected_at": "2026-05-08T15:20:00+09:00",
                "stocks": [{"code": "000660", "name": "SK하이닉스", "price": 1686000, "change_pct": 1.93, "foreign_net_buy": -500000, "program_net_buy": -300000, "volume": 4200000}],
            },
            {
                "session": "nxt",
                "collected_at": "2026-05-08T18:10:00+09:00",
                "stocks": [{"code": "000660", "name": "SK하이닉스", "price": 1700000, "change_pct": 2.78, "foreign_net_buy": -980000, "program_net_buy": -760000, "volume": 4600000}],
            },
        ]

        report = build_krx_session_flow_watch_report(snapshots)
        item = report["items"][0]

        self.assertIn("foreign_sell_acceleration", item["alerts"])
        self.assertIn("program_sell_acceleration", item["alerts"])
        self.assertIn("price_up_flow_divergence", item["alerts"])
        self.assertIn("session_reversal", item["alerts"])
        self.assertEqual(item["judgment"], "수급이탈주의")

    def test_response_formats_korean_nxt_caveat(self) -> None:
        report = build_krx_session_flow_watch_report([
            {"session": "regular", "collected_at": "t1", "stocks": [{"code": "001440", "name": "대한전선", "price": 70000, "change_pct": 8, "program_net_buy": 1000, "volume": 100000}]},
            {"session": "nxt", "collected_at": "t2", "stocks": [{"code": "001440", "name": "대한전선", "price": 72000, "change_pct": 10, "program_net_buy": 4000, "volume": 130000}]},
        ])

        focus = "\n".join(format_krx_session_flow_watch_report(report))
        response = build_krx_session_flow_watch_response(report)

        self.assertIn("NXT", focus)
        self.assertIn("가격/거래량 변화 감시 중심", focus)
        self.assertEqual(response["mode"], "krx_session_flow_watch")
        self.assertIn("수급 변화", response["summary"])


if __name__ == "__main__":
    unittest.main()
