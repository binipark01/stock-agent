from __future__ import annotations

import json
import os
import urllib.request
from typing import Any

COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik_padded}.json"
ARCHIVES_BASE = "https://www.sec.gov/Archives/edgar/data"


def _sec_headers() -> dict[str, str]:
    # SEC asks automated clients to identify themselves. Keep this configurable.
    return {
        "User-Agent": os.environ.get("SEC_USER_AGENT", "stock-research-agent/0.1 contact=local@example.com"),
        "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
    }


def _fetch_json(url: str, timeout: int = 30) -> Any:
    req = urllib.request.Request(url, headers=_sec_headers())
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def lookup_cik(symbol: str) -> str | None:
    symbol_upper = symbol.upper().strip()
    try:
        data = _fetch_json(COMPANY_TICKERS_URL)
    except Exception:
        return None
    rows = data.values() if isinstance(data, dict) else data
    for row in rows:
        if str(row.get("ticker", "")).upper() == symbol_upper:
            return str(row.get("cik_str", "")).strip()
    return None


def build_sec_archive_url(cik: str, accession_number: str, primary_document: str) -> str:
    cik_int = str(int(cik)) if str(cik).strip().isdigit() else str(cik).lstrip("0")
    accession_clean = accession_number.replace("-", "")
    return f"{ARCHIVES_BASE}/{cik_int}/{accession_clean}/{primary_document}"


def interpret_filing(form: str, primary_document: str = "", description: str = "") -> str:
    form_upper = form.upper()
    text = f"{primary_document} {description}".lower()
    if form_upper == "8-K":
        return "공식 이벤트 공시: press release/exhibit를 확인해야 합니다."
    if form_upper in {"10-Q", "10-K"}:
        return "정기 보고서: 매출/마진/리스크 요인 변화와 MD&A를 확인해야 합니다."
    if form_upper in {"S-3", "S-1", "424B5", "424B3"}:
        if any(word in text for word in ["resale", "selling stockholder", "selling shareholder"]):
            return "등록/증권신고서: selling-stockholder resale 가능성이 있어 회사 유입 현금 여부를 구분해야 합니다."
        return "등록신고서: primary issuance인지 resale인지 원문 확인 필요."
    if form_upper in {"13F-HR", "SC 13G", "SC 13D"}:
        return "보유지분/기관 포지션 공시: 수급 주체 변화 여부를 확인해야 합니다."
    return "공식 SEC 공시: 제목보다 원문 이벤트/재무 영향 확인이 필요합니다."


def _recent_filings_from_submissions(submissions: dict[str, Any], cik: str, limit: int = 5) -> list[dict[str, Any]]:
    recent = submissions.get("filings", {}).get("recent", {}) if isinstance(submissions, dict) else {}
    forms = recent.get("form", [])
    filing_dates = recent.get("filingDate", [])
    accession_numbers = recent.get("accessionNumber", [])
    primary_docs = recent.get("primaryDocument", [])
    descriptions = recent.get("primaryDocDescription", [])
    filings: list[dict[str, Any]] = []
    interesting_forms = {"8-K", "10-Q", "10-K", "S-3", "S-1", "424B5", "424B3", "13F-HR", "SC 13G", "SC 13D"}
    for idx, form in enumerate(forms):
        if len(filings) >= limit:
            break
        form_text = str(form)
        if form_text.upper() not in interesting_forms:
            continue
        filing_date = filing_dates[idx] if idx < len(filing_dates) else ""
        accession = accession_numbers[idx] if idx < len(accession_numbers) else ""
        primary_doc = primary_docs[idx] if idx < len(primary_docs) else ""
        description = descriptions[idx] if idx < len(descriptions) else ""
        url = build_sec_archive_url(cik, accession, primary_doc) if accession and primary_doc else ""
        interpretation = interpret_filing(form_text, primary_doc, description)
        headline = f"{form_text} / {filing_date} / {description or primary_doc or 'SEC filing'}"
        if form_text.upper() == "8-K" and "exhibit" not in headline.lower():
            headline = f"{headline} / exhibit likely"
        filings.append(
            {
                "form": form_text,
                "filing_date": filing_date,
                "accession_number": accession,
                "primary_document": primary_doc,
                "description": description,
                "headline": headline,
                "url": url,
                "interpretation": interpretation,
            }
        )
    return filings


def fetch_sec_filings_pack(symbol: str, limit: int = 5) -> dict[str, Any]:
    symbol_upper = symbol.upper().strip()
    cik = lookup_cik(symbol_upper)
    if not cik:
        return {"symbol": symbol_upper, "source": "sec_company_submissions", "cik": None, "filings": [], "error": "cik_not_found"}
    cik_padded = str(cik).zfill(10)
    try:
        submissions = _fetch_json(SUBMISSIONS_URL.format(cik_padded=cik_padded))
    except Exception as exc:
        return {"symbol": symbol_upper, "source": "sec_company_submissions", "cik": cik_padded, "filings": [], "error": f"sec_fetch_failed:{type(exc).__name__}"}
    return {
        "symbol": symbol_upper,
        "source": "sec_company_submissions",
        "cik": cik_padded,
        "filings": _recent_filings_from_submissions(submissions, cik, limit=limit),
        "error": None,
    }


def build_sec_focus_lines(pack: dict[str, Any], max_lines: int = 5) -> list[str]:
    symbol = pack.get("symbol") or "UNKNOWN"
    if pack.get("error"):
        return [f"SEC {symbol}: 조회 실패 / {pack['error']}"]
    filings = pack.get("filings") or []
    if not filings:
        return [f"SEC {symbol}: 최근 주요 8-K/10-Q/10-K/S-3 공시 없음"]
    lines = []
    for filing in filings[:max_lines]:
        lines.append(
            f"SEC {symbol}: {filing['form']} / {filing['filing_date']} / {filing['interpretation']} / {filing.get('url') or 'url 없음'}"
        )
    return lines
