import unittest

from src import request_modes
from src.main import infer_mode as main_infer_mode


class RequestModesTest(unittest.TestCase):
    def test_infer_mode_lives_in_dedicated_request_modes_module_and_stays_reexported(self):
        examples = {
            "장중 섹터별 강한 섹터 약한 섹터 알려줘": "sector_strength",
            "오늘 주도 테마 랭킹 보여줘": "sector_strength",
            "내 관심종목 훑어봐": "watchlist_scan",
            "광통신 watchlist만 봐줘": "watchlist_scan",
            "주식크루 국장 테마 리스트만 봐줘": "watchlist_scan",
            "지금 시장 레짐 판단해줘": "market_regime",
            "유가랑 vix 좀 봐줘": "oil_vix",
            "PLTR 데이마켓 가격": "day_market",
            "지금 주간거래 가격": "day_market",
            "데이장 주가": "day_market",
            "토스 데이마켓": "day_market",
            "RDW 토스 정보": "day_market",
            "레드와이어 토스나": "day_market",
            "NVDA 토스 주가": "day_market",
            "PLTR 토스 스냅샷": "day_market",
            "토스 지수 뉴스 수집": "ingest",
            "NVDA 옵션판 빡세게 봐줘": "options_flow",
            "내 관심종목 옵션 스윕해줘": "options_sweep",
            "NVDA 최근 8-K 공시 봐줘": "sec_filings",
            "NVDA 데이터허브 topic 보여줘": "topic_hub",
            "NVDA technical RSI MACD": "technical_snapshot",
            "RDDT OpenBB quote": "openbb_quote",
            "NVDA 오픈비비로 봐줘": "openbb_quote",
            "SPY OpenBB history 2024-01-02": "openbb_history",
            "NVDA OpenBB profile": "openbb_profile",
            "AAPL 오픈비비 프로필": "openbb_profile",
            "NVDA 실적 프리뷰": "earnings_preview",
            "삼성전자 수급 봐줘": "krx_symbol_flow_v2",
            "하이닉스 외인 기관 순매수": "krx_symbol_flow_v2",
            "현대차 어때": "krx_symbol_brief",
            "삼성전자 뉴스랑 수급": "krx_symbol_brief",
            "국장 프로그램 순매수 확인": "krx_flow_snapshot",
            "국장 수급 랭킹 5분마다 감시": "krx_flow_rank_watch",
            "국장 수급 상위 보여줘": "krx_flow_rank_scan",
            "프로그램 순매수 상위 국장": "krx_flow_rank_scan",
            "외국인 기관 매매 상위": "krx_flow_rank_scan",
            "거래대금 상위 국장": "krx_flow_rank_scan",
            "수급 랭킹": "krx_flow_rank_scan",
            "삼성전자 5분마다 수급 확인": "krx_flow_watch",
            "하이닉스 실시간 프로그램 매매 모니터": "krx_flow_watch",
            "NXT까지 수급 감시": "krx_session_flow_watch",
            "nxt 장까지 수급 변화": "krx_session_flow_watch",
            "종가 이후 수급 감시": "krx_session_flow_watch",
            "장끝나고 수급 변화 봐줘": "krx_session_flow_watch",
        }
        for request, expected in examples.items():
            self.assertEqual(request_modes.infer_mode(request), expected)
            self.assertEqual(main_infer_mode(request), expected)



class KrxConditionScanRoutingTest(unittest.TestCase):
    def test_krx_condition_scan_routes_condition_search_prompts(self):
        self.assertEqual("krx_condition_scan", request_modes.infer_mode("국장 검색식 여러개 돌려봐"))
        self.assertEqual("krx_condition_scan", request_modes.infer_mode("만쥬식 종가배팅 검색식"))
        self.assertEqual("krx_condition_scan", request_modes.infer_mode("수급 검색식으로 후보 찾아줘"))

if __name__ == "__main__":
    unittest.main()
