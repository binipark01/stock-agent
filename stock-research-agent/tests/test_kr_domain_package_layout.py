import unittest
from unittest.mock import patch

from src import (
    kiwoom_api_catalog,
    kiwoom_client,
    kiwoom_collectors,
    kiwoom_realtime,
    krx_condition_engine,
    krx_condition_universe,
    krx_flow_common,
    krx_flow_rank_scan,
    krx_flow_snapshot,
    krx_flows_kiwoom,
    krx_session_flow_watch,
    krx_symbol_flow_kiwoom,
    krx_symbol_supply_news,
    krx_theme_leader_scan,
)
from src.kr.condition import engine as kr_condition_engine
from src.kr.condition import universe as kr_condition_universe
from src.kr.flow import common as kr_flow_common
from src.kr.flow import kiwoom as kr_flow_kiwoom
from src.kr.flow import rank_scan as kr_flow_rank_scan
from src.kr.flow import snapshot as kr_flow_snapshot
from src.kr.flow import symbol_flow as kr_flow_symbol_flow
from src.kr.kiwoom import api_catalog as kr_kiwoom_api_catalog
from src.kr.kiwoom import client as kr_kiwoom_client
from src.kr.kiwoom import collectors as kr_kiwoom_collectors
from src.kr.kiwoom import realtime as kr_kiwoom_realtime
from src.kr.news import symbol_supply_news as kr_symbol_supply_news
from src.kr.session import flow_watch as kr_session_flow_watch
from src.kr.theme import leader_scan as kr_theme_leader_scan


class KrDomainPackageLayoutTest(unittest.TestCase):
    def test_kiwoom_modules_moved_and_old_paths_alias(self) -> None:
        self.assertIs(kiwoom_client.KiwoomRestClient, kr_kiwoom_client.KiwoomRestClient)
        self.assertIs(kiwoom_api_catalog.get_tr, kr_kiwoom_api_catalog.get_tr)
        self.assertIs(kiwoom_collectors.call_market_tr, kr_kiwoom_collectors.call_market_tr)
        self.assertIs(kiwoom_realtime.build_register_message, kr_kiwoom_realtime.build_register_message)

    def test_krx_flow_condition_theme_modules_moved_and_old_paths_alias(self) -> None:
        self.assertIs(krx_flow_common.normalize_krx_code, kr_flow_common.normalize_krx_code)
        self.assertIs(krx_flow_snapshot.build_krx_flow_snapshot, kr_flow_snapshot.build_krx_flow_snapshot)
        self.assertIs(krx_flow_rank_scan.build_krx_flow_rank_scan, kr_flow_rank_scan.build_krx_flow_rank_scan)
        self.assertIs(krx_flows_kiwoom.build_krx_flow_response, kr_flow_kiwoom.build_krx_flow_response)
        self.assertIs(krx_symbol_flow_kiwoom.build_krx_symbol_flow_snapshot_v2, kr_flow_symbol_flow.build_krx_symbol_flow_snapshot_v2)
        self.assertIs(krx_condition_engine.run_krx_condition_scan, kr_condition_engine.run_krx_condition_scan)
        self.assertIs(krx_condition_universe.build_condition_universe_from_rank_scan, kr_condition_universe.build_condition_universe_from_rank_scan)
        self.assertIs(krx_session_flow_watch.build_krx_session_flow_watch_report, kr_session_flow_watch.build_krx_session_flow_watch_report)
        self.assertIs(krx_theme_leader_scan.build_krx_theme_leader_report, kr_theme_leader_scan.build_krx_theme_leader_report)
        self.assertIs(krx_symbol_supply_news.build_krx_symbol_supply_news_report, kr_symbol_supply_news.build_krx_symbol_supply_news_report)

    def test_theme_leader_old_patch_path_still_hits_implementation(self) -> None:
        watchlist_data = {"lists": {"krx_stockcrew_power_infra": ["001440.KS"]}}
        quotes = {"001440.KS": {"price": 18000, "previous_close": 16000, "volume": 8000000}}
        with patch('src.krx_theme_leader_scan.load_watchlist', return_value=watchlist_data) as load_watchlist:
            report = kr_theme_leader_scan.build_krx_theme_leader_report(None, quotes, collected_at="t")
        load_watchlist.assert_called_once_with()
        self.assertEqual(report["themes"][0]["theme_key"], "krx_stockcrew_power_infra")


if __name__ == '__main__':
    unittest.main()
