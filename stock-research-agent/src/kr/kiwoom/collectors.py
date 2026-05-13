"""Safe Kiwoom TR collector layer.

The transport client knows how to call Kiwoom. The catalog knows which TRs are
allowed. This module combines both and returns a uniform, metadata-rich result
without domain-specific scoring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Mapping

try:
    from .api_catalog import KiwoomTR, assert_tr_allowed, get_tr
except ImportError:  # direct script execution via src/main.py
    from kr.kiwoom.api_catalog import KiwoomTR, assert_tr_allowed, get_tr

KST = timezone(timedelta(hours=9))


@dataclass
class TRCallResult:
    source: str
    env: str
    base_url: str
    api_id: str
    endpoint: str
    risk_tier: str
    status: str
    collected_at: str
    data: dict[str, Any] = field(default_factory=dict)
    rows: list[Any] = field(default_factory=list)
    row_count: int = 0
    return_code: int | str | None = None
    return_msg: str = ""
    cont_yn: str = "N"
    next_key: str = ""
    status_code: int = 200

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "env": self.env,
            "base_url": self.base_url,
            "api_id": self.api_id,
            "endpoint": self.endpoint,
            "risk_tier": self.risk_tier,
            "status": self.status,
            "collected_at": self.collected_at,
            "return_code": self.return_code,
            "return_msg": self.return_msg,
            "cont_yn": self.cont_yn,
            "next_key": self.next_key,
            "status_code": self.status_code,
            "row_count": self.row_count,
            "rows": self.rows,
            "data": self.data,
        }


def _now_kst_iso() -> str:
    return datetime.now(KST).replace(microsecond=0).isoformat()


def _normalize_return_code(value: Any) -> int | str | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return str(value)


def _is_success_return_code(value: int | str | None) -> bool:
    return value in (None, 0, "0")


def _extract_rows(data: Mapping[str, Any], tr: KiwoomTR) -> list[Any]:
    for key in tr.row_keys:
        value = data.get(key)
        if isinstance(value, list):
            return value
    return []


def _build_status(data: Mapping[str, Any], tr: KiwoomTR, rows: list[Any], return_code: int | str | None) -> str:
    if not _is_success_return_code(return_code):
        return "error"
    if tr.row_keys and not rows:
        return "empty"
    return "ok"


def _client_env_and_base(client: Any) -> tuple[str, str]:
    config = getattr(client, "config", None)
    env = getattr(config, "normalized_env", "unknown")
    base_url = getattr(config, "rest_base_url", "")
    return env, base_url


def call_kiwoom_tr(
    client: Any,
    api_id: str,
    body_override: Mapping[str, Any] | None = None,
    *,
    allow_account: bool = False,
    allow_order: bool = False,
    cont_yn: str = "N",
    next_key: str = "",
) -> TRCallResult:
    tr = assert_tr_allowed(api_id, allow_account=allow_account, allow_order=allow_order)
    body = dict(tr.default_body)
    if body_override:
        body.update(dict(body_override))

    env, base_url = _client_env_and_base(client)
    collected_at = _now_kst_iso()
    result = client.post_tr(api_id=tr.api_id, endpoint=tr.endpoint, body=body, cont_yn=cont_yn, next_key=next_key)
    data = dict(getattr(result, "data", {}) or {})
    return_code = _normalize_return_code(data.get("return_code"))
    return_msg = str(data.get("return_msg") or "")
    rows = _extract_rows(data, tr)
    status = _build_status(data, tr, rows, return_code)

    return TRCallResult(
        source="kiwoom",
        env=env,
        base_url=base_url,
        api_id=tr.api_id,
        endpoint=tr.endpoint,
        risk_tier=tr.risk_tier,
        status=status,
        collected_at=collected_at,
        data=data,
        rows=rows,
        row_count=len(rows),
        return_code=return_code,
        return_msg=return_msg,
        cont_yn=getattr(result, "cont_yn", "N") or "N",
        next_key=getattr(result, "next_key", "") or "",
        status_code=getattr(result, "status_code", 200),
    )


def call_market_tr(client: Any, api_id: str, body_override: Mapping[str, Any] | None = None, **kwargs: Any) -> TRCallResult:
    tr = get_tr(api_id)
    if tr.risk_tier != "market_readonly":
        # Reuse the shared safety gate for consistent exceptions.
        assert_tr_allowed(api_id, **kwargs)
    return call_kiwoom_tr(client, api_id, body_override, **kwargs)


__all__ = ["TRCallResult", "call_kiwoom_tr", "call_market_tr"]
