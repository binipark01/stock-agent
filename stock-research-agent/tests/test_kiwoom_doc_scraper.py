import unittest

from src.kiwoom_doc_scraper import parse_api_guide_contents


HTML = '\n<section><h3>기본 정보</h3>\n<table><tr><th>Method</th><td>POST</td></tr><tr><th>운영 도메인</th><td>https://api.kiwoom.com</td></tr><tr><th>모의투자 도메인</th><td>https://mockapi.kiwoom.com<span>(KRX만 지원가능)</span></td></tr><tr><th>URL</th><td>/api/dostk/mrkcond</td></tr></table>\n<table><tr><th>Element</th><th>한글명</th><th>type</th><th>Required</th></tr><tr><td>stk_cd</td><td>종목코드</td><td>String</td><td>Y</td></tr><tr><td>strt_dt</td><td>시작일자</td><td>String</td><td>Y</td></tr></table>\n<pre>{"stk_cd":"005930","strt_dt":"20241007","end_dt":"20241107","orgn_prsm_unp_tp":"1","for_prsm_unp_tp":"1"}</pre>\n<table><tr><th>Element</th><th>한글명</th><th>type</th></tr><tr><td>stk_orgn_trde_trnsn</td><td>종목별기관매매추이</td><td>LIST</td></tr><tr><td>- orgn_daly_nettrde_qty</td><td>기관일별순매매수량</td><td>String</td></tr></table>\n<pre>{"stk_orgn_trde_trnsn":[{"dt":"20241107","orgn_daly_nettrde_qty":"-138096","for_daly_nettrde_qty":"-1584"}],"return_code":0,"return_msg":"정상"}</pre>\n</section>\n'


class KiwoomDocScraperTest(unittest.TestCase):
    def test_parse_api_guide_contents_extracts_examples_and_row_keys(self):
        doc = parse_api_guide_contents(HTML, api_id="ka10045", job_tp_code="02")

        self.assertEqual("POST", doc.method)
        self.assertEqual("https://api.kiwoom.com", doc.real_domain)
        self.assertEqual("https://mockapi.kiwoom.com", doc.mock_domain)
        self.assertEqual("/api/dostk/mrkcond", doc.endpoint)
        self.assertEqual("005930", doc.request_example["stk_cd"])
        self.assertIn("stk_orgn_trde_trnsn", doc.row_keys)
        self.assertIn("stk_cd", doc.request_body_fields)


if __name__ == "__main__":
    unittest.main()
