import unittest

from src.kiwoom_api_catalog import (
    KIWOOM_CATEGORIES,
    KIWOOM_TRS,
    KiwoomApiPermissionError,
    assert_tr_allowed,
    get_category,
    get_tr,
    p0_market_trs,
)


class KiwoomApiCatalogTest(unittest.TestCase):
    def test_catalog_contains_all_domestic_categories_with_risk_tiers(self):
        self.assertEqual(16, len(KIWOOM_CATEGORIES))
        expected = {
            "acnt": ("계좌", "/api/dostk/acnt", "account_readonly"),
            "rkinfo": ("순위정보", "/api/dostk/rkinfo", "market_readonly"),
            "mrkcond": ("시세", "/api/dostk/mrkcond", "market_readonly"),
            "frgnistt": ("기관/외국인", "/api/dostk/frgnistt", "market_readonly"),
            "slb": ("대차거래", "/api/dostk/slb", "market_readonly"),
            "shsa": ("공매도", "/api/dostk/shsa", "market_readonly"),
            "ordr": ("주문", "/api/dostk/ordr", "order_mutation"),
            "crdordr": ("신용주문", "/api/dostk/crdordr", "order_mutation"),
            "websocket": ("실시간시세", "/api/dostk/websocket", "market_readonly"),
            "thme": ("테마", "/api/dostk/thme", "market_readonly"),
            "etf": ("ETF", "/api/dostk/etf", "market_readonly"),
        }
        for key, (label, endpoint, risk_tier) in expected.items():
            category = get_category(key)
            self.assertEqual(label, category.label)
            self.assertEqual(endpoint, category.endpoint)
            self.assertEqual(risk_tier, category.risk_tier)

    def test_p0_market_trs_capture_first_implementation_scope(self):
        expected = {
            "ka10032": ("거래대금상위요청", "/api/dostk/rkinfo"),
            "ka10023": ("거래량급증요청", "/api/dostk/rkinfo"),
            "ka10065": ("장중투자자별매매상위요청", "/api/dostk/rkinfo"),
            "ka90009": ("외국인기관매매상위요청", "/api/dostk/rkinfo"),
            "ka90003": ("프로그램순매수상위50요청", "/api/dostk/stkinfo"),
            "ka10001": ("주식기본정보요청", "/api/dostk/stkinfo"),
            "ka10004": ("주식호가요청", "/api/dostk/mrkcond"),
            "ka10046": ("체결강도추이시간별요청", "/api/dostk/mrkcond"),
            "ka10063": ("장중투자자별매매요청", "/api/dostk/mrkcond"),
            "ka10008": ("주식외국인종목별매매동향", "/api/dostk/frgnistt"),
            "ka10009": ("주식기관요청", "/api/dostk/frgnistt"),
            "ka90008": ("종목시간별프로그램매매추이요청", "/api/dostk/mrkcond"),
            "ka90004": ("종목별프로그램매매현황", "/api/dostk/stkinfo"),
            "ka10014": ("공매도추이요청", "/api/dostk/shsa"),
            "ka10013": ("신용매매동향요청", "/api/dostk/stkinfo"),
            "ka10068": ("대차거래추이요청", "/api/dostk/slb"),
            "ka10069": ("대차거래상위10종목요청", "/api/dostk/slb"),
            "ka20068": ("대차거래추이요청(종목별)", "/api/dostk/slb"),
            "ka90012": ("대차거래내역요청", "/api/dostk/slb"),
            "ka90001": ("테마그룹별요청", "/api/dostk/thme"),
            "ka90002": ("테마구성종목요청", "/api/dostk/thme"),
            "ka10051": ("업종별투자자순매수요청", "/api/dostk/sect"),
            "ka10010": ("업종프로그램요청", "/api/dostk/sect"),
            "ka20003": ("전업종지수요청", "/api/dostk/sect"),
            "ka40004": ("ETF전체시세요청", "/api/dostk/etf"),
            "ka40002": ("ETF종목정보요청", "/api/dostk/etf"),
        }
        for api_id, (name, endpoint) in expected.items():
            tr = get_tr(api_id)
            self.assertEqual(name, tr.name)
            self.assertEqual(endpoint, tr.endpoint)
            self.assertEqual("market_readonly", tr.risk_tier)
            self.assertIn(tr.priority, {"p0", "p1"})

        p0_ids = {tr.api_id for tr in p0_market_trs()}
        self.assertTrue({"ka10032", "ka10023", "ka90009", "ka10001", "ka90001"}.issubset(p0_ids))

    def test_default_bodies_keep_known_required_inputs(self):
        self.assertEqual("0", get_tr("ka10032").default_body["mang_stk_incls"])
        self.assertEqual("9000", get_tr("ka10065").default_body["orgn_tp"])
        self.assertEqual("0", get_tr("ka90009").default_body["qry_dt_tp"])
        self.assertEqual("1", get_tr("ka90003").default_body["trde_upper_tp"])
        self.assertIn("trde_tp", get_tr("ka10021").default_body)
        self.assertIn("base_dt_tp", get_tr("ka10035").default_body)
        self.assertIn("updown_incls", get_tr("ka10033").default_body)
        self.assertIn("crd_cnd", get_tr("ka10033").default_body)

    def test_order_and_account_apis_are_blocked_by_default(self):
        self.assertEqual("account_readonly", get_tr("kt00001").risk_tier)
        self.assertEqual("order_mutation", get_tr("kt10000").risk_tier)

        assert_tr_allowed("ka10032")
        with self.assertRaises(KiwoomApiPermissionError):
            assert_tr_allowed("kt00001")
        with self.assertRaises(KiwoomApiPermissionError):
            assert_tr_allowed("kt10000")

        assert_tr_allowed("kt00001", allow_account=True)
        with self.assertRaises(KiwoomApiPermissionError):
            assert_tr_allowed("kt10000", allow_account=True)
        assert_tr_allowed("kt10000", allow_order=True)


if __name__ == "__main__":
    unittest.main()
