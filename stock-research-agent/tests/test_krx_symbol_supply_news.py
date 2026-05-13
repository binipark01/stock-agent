import unittest

from src.krx_symbol_supply_news import (
    build_krx_symbol_supply_news_report,
    fetch_naver_stock_news,
    format_krx_symbol_supply_news_report,
    normalize_krx_code,
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload
    def raise_for_status(self):
        return None
    def json(self):
        return self.payload


class FakeSession:
    def get(self, url, **kwargs):
        return FakeResponse([
            {"items": [
                {"id": "1", "officeId": "001", "articleId": "0001", "officeName": "테스트뉴스", "datetime": "202605081530", "title": "현대차그룹 급등", "body": "본문"},
                {"id": "2", "officeName": "테스트뉴스", "datetime": "202605081400", "title": "관세 리스크 점검", "body": "본문"},
            ]}
        ])


class KrxSymbolSupplyNewsTest(unittest.TestCase):
    def test_normalize_krx_code_strips_suffixes(self):
        self.assertEqual("005380", normalize_krx_code("005380.KS"))
        self.assertEqual("005380", normalize_krx_code("A005380"))

    def test_fetch_naver_stock_news_flattens_items(self):
        rows = fetch_naver_stock_news("005380", session=FakeSession())
        self.assertEqual(2, len(rows))
        self.assertEqual("현대차그룹 급등", rows[0]["title"])
        self.assertIn("n.news.naver.com", rows[0]["url"])

    def test_report_template_includes_supply_price_and_news(self):
        snapshot = {
            "symbol": "005380",
            "env": "mock",
            "base_url": "https://mockapi.kiwoom.com",
            "requested_date": "20260508",
            "data_dates": {"ka10009": "20260508", "ka10045": "20260508"},
            "is_today_confirmed": True,
            "supply_signal": "동반순매수",
            "institution_net_buy_qty": 439195,
            "foreign_net_buy_qty": 523820,
            "program_net_buy_qty": 462230,
            "warnings": [],
        }
        integration = {
            "stockName": "현대차",
            "dealTrendInfos": [{
                "bizdate": "20260508",
                "closePrice": "613,000",
                "compareToPreviousClosePrice": "41,000",
                "accumulatedTradingVolume": "5,020,568",
                "organPureBuyQuant": "+439,195",
                "foreignerPureBuyQuant": "+309,580",
                "individualPureBuyQuant": "-745,834",
            }],
        }
        report = build_krx_symbol_supply_news_report(
            "005380",
            flow_snapshot=snapshot,
            integration=integration,
            news_items=[{"title": "현대차그룹 급등", "source": "YTN", "datetime": "202605082245"}],
        )
        lines = format_krx_symbol_supply_news_report(report)
        text = "\n".join(lines)
        self.assertIn("현대차(005380) 수급+뉴스 템플릿", text)
        self.assertIn("기관 +439,195주", text)
        self.assertIn("+7.17%", text)
        self.assertIn("현대차그룹 급등", text)


if __name__ == "__main__":
    unittest.main()
