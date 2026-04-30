import unittest

from src import request_modes
from src.main import infer_mode as main_infer_mode


class RequestModesTest(unittest.TestCase):
    def test_infer_mode_lives_in_dedicated_request_modes_module_and_stays_reexported(self):
        examples = {
            "장중 섹터별 강한 섹터 약한 섹터 알려줘": "sector_strength",
            "NVDA 최근 8-K 공시 봐줘": "sec_filings",
            "NVDA 데이터허브 topic 보여줘": "topic_hub",
            "NVDA technical RSI MACD": "technical_snapshot",
            "NVDA 실적 프리뷰": "earnings_preview",
        }
        for request, expected in examples.items():
            self.assertEqual(request_modes.infer_mode(request), expected)
            self.assertEqual(main_infer_mode(request), expected)


if __name__ == "__main__":
    unittest.main()
