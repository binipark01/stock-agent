import json
import unittest
from unittest.mock import patch

from src.main import build_response, infer_mode


class SecFilingsModeTest(unittest.TestCase):
    def test_infer_mode_routes_sec_and_filing_requests(self) -> None:
        self.assertEqual(infer_mode("BMNR 최근 8-K 공시 봐줘"), "sec_filings")
        self.assertEqual(infer_mode("NVDA SEC filings 요약"), "sec_filings")

    def test_sec_filings_mode_surfaces_recent_filing_focus_lines(self) -> None:
        fake_pack = {
            "symbol": "BMNR",
            "source": "sec_company_submissions",
            "cik": "0001234567",
            "filings": [
                {
                    "form": "8-K",
                    "filing_date": "2026-04-24",
                    "accession_number": "0001234567-26-000001",
                    "primary_document": "form8-k.htm",
                    "headline": "8-K / 2026-04-24 / Current report / exhibit likely",
                    "url": "https://www.sec.gov/Archives/edgar/data/1234567/000123456726000001/form8-k.htm",
                    "interpretation": "공식 이벤트 공시: press release/exhibit를 확인해야 합니다.",
                },
                {
                    "form": "S-3",
                    "filing_date": "2026-04-22",
                    "accession_number": "0001234567-26-000002",
                    "primary_document": "s-3.htm",
                    "headline": "S-3 / 2026-04-22 / Registration statement",
                    "url": "https://www.sec.gov/Archives/edgar/data/1234567/000123456726000002/s-3.htm",
                    "interpretation": "등록신고서: primary issuance인지 resale인지 원문 확인 필요.",
                },
            ],
            "error": None,
        }
        with patch("src.main.fetch_sec_filings_pack", return_value=fake_pack):
            payload = build_response(
                json.dumps({"request": "BMNR 최근 8-K 공시 봐줘", "symbols": ["BMNR"]}, ensure_ascii=False)
            )

        self.assertEqual(payload["mode"], "sec_filings")
        self.assertEqual(payload["symbols"], ["BMNR"])
        self.assertTrue(any(item.startswith("SEC BMNR:") for item in payload["focus"]))
        self.assertTrue(any("8-K" in item and "공식 이벤트" in item for item in payload["focus"]))
        self.assertTrue(any("S-3" in item and "primary issuance" in item for item in payload["focus"]))
        self.assertTrue(any("ex99-1" in item or "exhibit" in item.lower() for item in payload["next_actions"]))


if __name__ == "__main__":
    unittest.main()
