"""Scrape/cache Kiwoom official REST API guide implementation examples.

The official site exposes each TR detail as HTML at:
  /guide/apiGuideContents?jobTpCode=<job>&apiId=<api>
This module extracts request/response examples, body fields, row keys and
endpoint metadata so the local catalog can be checked against the source docs.
It never touches credentials or live trading endpoints.
"""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Mapping

import requests
from bs4 import BeautifulSoup

GUIDE_CONTENTS_URL = "https://openapi.kiwoom.com/guide/apiGuideContents"


@dataclass
class KiwoomApiDoc:
    api_id: str
    job_tp_code: str
    name: str = ""
    method: str = ""
    real_domain: str = ""
    mock_domain: str = ""
    endpoint: str = ""
    request_example: dict[str, Any] | None = None
    response_example: dict[str, Any] | None = None
    request_body_fields: list[str] | None = None
    response_fields: list[str] | None = None
    row_keys: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _clean(text: str) -> str:
    return " ".join((text or "").split())


def _parse_example(text: str) -> dict[str, Any] | None:
    text = (text or "").strip()
    if not text.startswith("{"):
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            value = ast.literal_eval(text)
        except (SyntaxError, ValueError):
            return None
        return value if isinstance(value, dict) else None


def _table_rows(table: Any) -> list[list[str]]:
    rows: list[list[str]] = []
    for tr in table.find_all("tr"):
        cells = [_clean(c.get_text(" ", strip=True)) for c in tr.find_all(["th", "td"])]
        if cells:
            rows.append(cells)
    return rows


def _field_ids_from_rows(rows: list[list[str]]) -> list[str]:
    fields: list[str] = []
    for row in rows:
        if not row:
            continue
        field = row[0].strip()
        if field and field.lower() != "element":
            fields.append(field.removeprefix("- ").strip())
    return fields


def parse_api_guide_contents(html: str, *, api_id: str, job_tp_code: str) -> KiwoomApiDoc:
    soup = BeautifulSoup(html, "html.parser")
    doc = KiwoomApiDoc(api_id=api_id, job_tp_code=job_tp_code)

    # Basic metadata table.
    for table in soup.find_all("table"):
        rows = _table_rows(table)
        for row in rows:
            if len(row) < 2:
                continue
            key, value = row[0], row[1]
            if key == "Method":
                doc.method = value
            elif key.startswith("운영 도메인"):
                doc.real_domain = value.split()[0]
            elif key == "모의투자 도메인":
                doc.mock_domain = value.split("(")[0].strip()
            elif key == "URL":
                doc.endpoint = value

    examples = []
    for pre in soup.find_all("pre"):
        parsed = _parse_example(pre.get_text("\n", strip=True))
        if parsed is not None:
            examples.append(parsed)
    if examples:
        doc.request_example = examples[0]
    if len(examples) > 1:
        doc.response_example = examples[1]
        doc.row_keys = [k for k, v in examples[1].items() if isinstance(v, list)]

    request_fields: list[str] = []
    response_fields: list[str] = []
    for table in soup.find_all("table"):
        rows = _table_rows(table)
        joined = " ".join(" ".join(row) for row in rows)
        fields = _field_ids_from_rows(rows)
        if "Required" not in joined or not fields:
            continue
        if any(field in (doc.request_example or {}) for field in fields):
            request_fields.extend(fields)
        if doc.response_example and any(field in doc.response_example for field in fields):
            response_fields.extend(fields)

    doc.request_body_fields = list(dict.fromkeys(request_fields))
    doc.response_fields = list(dict.fromkeys(response_fields))
    return doc


def fetch_api_doc(api_id: str, job_tp_code: str, *, timeout: int = 30) -> KiwoomApiDoc:
    response = requests.get(
        GUIDE_CONTENTS_URL,
        params={"jobTpCode": job_tp_code, "apiId": api_id},
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": f"https://openapi.kiwoom.com/guide/apiguide?jobTpCode={job_tp_code}",
            "X-Requested-With": "XMLHttpRequest",
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return parse_api_guide_contents(response.text, api_id=api_id, job_tp_code=job_tp_code)


def cache_api_docs(specs: Mapping[str, str], cache_path: str | Path) -> dict[str, Any]:
    docs = {api_id: fetch_api_doc(api_id, job).to_dict() for api_id, job in specs.items()}
    path = Path(cache_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(docs, ensure_ascii=False, indent=2), encoding="utf-8")
    return docs


__all__ = ["GUIDE_CONTENTS_URL", "KiwoomApiDoc", "cache_api_docs", "fetch_api_doc", "parse_api_guide_contents"]
