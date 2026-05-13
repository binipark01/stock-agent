import unittest


class KrxFlowModuleSplitTest(unittest.TestCase):
    def test_snapshot_module_exports_legacy_snapshot_and_watch_api(self):
        from src import krx_flow_snapshot
        from src import krx_flows_kiwoom

        self.assertIs(krx_flow_snapshot.build_krx_flow_snapshot, krx_flows_kiwoom.build_krx_flow_snapshot)
        self.assertIs(krx_flow_snapshot.build_krx_flow_response, krx_flows_kiwoom.build_krx_flow_response)
        self.assertIs(krx_flow_snapshot.build_krx_flow_watch_report, krx_flows_kiwoom.build_krx_flow_watch_report)

    def test_rank_module_exports_legacy_rank_and_candidate_api(self):
        from src import krx_flow_rank_scan
        from src import krx_flows_kiwoom

        self.assertIs(krx_flow_rank_scan.build_krx_flow_rank_scan, krx_flows_kiwoom.build_krx_flow_rank_scan)
        self.assertIs(krx_flow_rank_scan.build_krx_flow_trade_candidates, krx_flows_kiwoom.build_krx_flow_trade_candidates)
        self.assertIs(krx_flow_rank_scan.build_krx_flow_rank_watch_report, krx_flows_kiwoom.build_krx_flow_rank_watch_report)

    def test_common_module_keeps_code_normalization_shared(self):
        from src import krx_flow_common
        from src import krx_flows_kiwoom

        self.assertIs(krx_flow_common.normalize_krx_code, krx_flows_kiwoom.normalize_krx_code)
        self.assertEqual("005930", krx_flow_common.normalize_krx_code("삼성전자"))
        self.assertEqual("000660", krx_flow_common.normalize_krx_code("000660.KS"))


if __name__ == "__main__":
    unittest.main()
