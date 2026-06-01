from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from typing import Any, Callable

DEFAULT_OPENBB_PYTHON = "/mnt/d/Workspace/openbb-quick/.venv-openbb/bin/python"
Runner = Callable[..., subprocess.CompletedProcess]


def _openbb_python_path(python_path: str | None = None) -> str:
    return python_path or os.environ.get("OPENBB_PYTHON") or DEFAULT_OPENBB_PYTHON


def _extract_marked_json(stdout: str) -> Any:
    marker = "OPENBB_JSON="
    for line in reversed(stdout.splitlines()):
        if line.startswith(marker):
            return json.loads(line[len(marker):])
    stripped = stdout.strip()
    if stripped:
        return json.loads(stripped)
    raise ValueError("OpenBB subprocess did not emit OPENBB_JSON marker")


def _run_openbb_script(
    script: str,
    *,
    python_path: str | None = None,
    runner: Runner | None = None,
    timeout: int = 75,
) -> Any:
    runner = runner or subprocess.run
    python = _openbb_python_path(python_path)
    completed = runner(
        [python, "-"],
        input=script,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        stdout = (completed.stdout or "").strip()
        message = stderr or stdout or f"OpenBB subprocess failed with exit code {completed.returncode}"
        raise RuntimeError(message[-1200:])
    return _extract_marked_json(completed.stdout or "")


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _pct_change(price: float | None, previous_close: float | None) -> float | None:
    if price is None or previous_close in (None, 0):
        return None
    return round(((price - previous_close) / previous_close) * 100, 2)


def build_openbb_quote(
    symbol: str,
    *,
    provider: str = "yfinance",
    python_path: str | None = None,
    runner: Runner | None = None,
    timeout: int = 75,
) -> dict[str, Any]:
    normalized_symbol = symbol.upper().strip()
    script = f'''
import json
from openbb import obb
res = obb.equity.price.quote({normalized_symbol!r}, provider={provider!r})
df = res.to_df()
row = df.iloc[0].where(df.notna().iloc[0], None).to_dict() if len(df) else {{}}
print("OPENBB_JSON=" + json.dumps(row, default=str, ensure_ascii=False))
'''
    try:
        row = _run_openbb_script(script, python_path=python_path, runner=runner, timeout=timeout)
    except (FileNotFoundError, subprocess.TimeoutExpired, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        return {
            "status": "unavailable",
            "symbol": normalized_symbol,
            "source": f"openbb:{provider}",
            "error": str(exc),
            "collected_at": datetime.now(timezone.utc).isoformat(),
        }

    price = _to_float(row.get("last_price") or row.get("price") or row.get("close"))
    previous_close = _to_float(row.get("prev_close") or row.get("previous_close"))
    return {
        "status": "ok",
        "symbol": str(row.get("symbol") or normalized_symbol).upper(),
        "name": row.get("name"),
        "price": price,
        "previous_close": previous_close,
        "pct_change": _pct_change(price, previous_close),
        "open": _to_float(row.get("open")),
        "high": _to_float(row.get("high")),
        "low": _to_float(row.get("low")),
        "volume": _to_int(row.get("volume")),
        "currency": row.get("currency"),
        "exchange": row.get("exchange"),
        "bid": _to_float(row.get("bid")),
        "ask": _to_float(row.get("ask")),
        "source": f"openbb:{provider}",
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }


def build_openbb_history(
    symbol: str,
    *,
    start_date: str,
    end_date: str | None = None,
    provider: str = "yfinance",
    python_path: str | None = None,
    runner: Runner | None = None,
    timeout: int = 75,
) -> dict[str, Any]:
    normalized_symbol = symbol.upper().strip()
    script = f'''
import json
from openbb import obb
kwargs = {{"start_date": {start_date!r}, "provider": {provider!r}}}
if {end_date!r} is not None:
    kwargs["end_date"] = {end_date!r}
res = obb.equity.price.historical({normalized_symbol!r}, **kwargs)
df = res.to_df().reset_index()
records = []
for row in df.where(df.notna(), None).to_dict(orient="records"):
    if "date" not in row and "index" in row:
        row["date"] = row.pop("index")
    records.append(row)
print("OPENBB_JSON=" + json.dumps(records, default=str, ensure_ascii=False))
'''
    try:
        rows = _run_openbb_script(script, python_path=python_path, runner=runner, timeout=timeout)
    except (FileNotFoundError, subprocess.TimeoutExpired, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        return {
            "status": "unavailable",
            "symbol": normalized_symbol,
            "source": f"openbb:{provider}",
            "error": str(exc),
            "rows": [],
            "collected_at": datetime.now(timezone.utc).isoformat(),
        }

    normalized_rows: list[dict[str, Any]] = []
    for row in rows or []:
        normalized_rows.append(
            {
                "date": str(row.get("date") or row.get("timestamp") or ""),
                "open": _to_float(row.get("open")),
                "high": _to_float(row.get("high")),
                "low": _to_float(row.get("low")),
                "close": _to_float(row.get("close")),
                "volume": _to_int(row.get("volume")),
            }
        )
    return {
        "status": "ok",
        "symbol": normalized_symbol,
        "source": f"openbb:{provider}",
        "rows": normalized_rows,
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }


def build_openbb_profile(
    symbol: str,
    *,
    provider: str = "yfinance",
    python_path: str | None = None,
    runner: Runner | None = None,
    timeout: int = 75,
) -> dict[str, Any]:
    normalized_symbol = symbol.upper().strip()
    script = f"""
import json
from openbb import obb
res = obb.equity.profile({normalized_symbol!r}, provider={provider!r})
df = res.to_df()
row = df.iloc[0].where(df.notna().iloc[0], None).to_dict() if len(df) else {{}}
print("OPENBB_JSON=" + json.dumps(row, default=str, ensure_ascii=False))
"""
    try:
        row = _run_openbb_script(script, python_path=python_path, runner=runner, timeout=timeout)
    except (FileNotFoundError, subprocess.TimeoutExpired, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        return {
            "status": "unavailable",
            "symbol": normalized_symbol,
            "source": f"openbb:{provider}",
            "error": str(exc),
            "collected_at": datetime.now(timezone.utc).isoformat(),
        }

    return {
        "status": "ok",
        "symbol": str(row.get("symbol") or normalized_symbol).upper(),
        "name": row.get("name") or row.get("company_name") or row.get("long_name"),
        "sector": row.get("sector"),
        "industry": row.get("industry"),
        "market_cap": _to_float(row.get("market_cap") or row.get("market_capitalization")),
        "exchange": row.get("exchange"),
        "currency": row.get("currency"),
        "country": row.get("country"),
        "website": row.get("website"),
        "description": row.get("description") or row.get("long_business_summary"),
        "source": f"openbb:{provider}",
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }


def build_openbb_history_response(history: dict[str, Any]) -> dict[str, Any]:
    symbol = history.get("symbol") or "UNKNOWN"
    source = history.get("source") or "openbb"
    rows = history.get("rows") or []
    if history.get("status") != "ok":
        error = history.get("error") or "OpenBB unavailable"
        focus = [f"{symbol} OpenBB history: 사용 불가 / {error}"]
        summary = f"OpenBB history 호출이 실패했습니다: {symbol}"
        next_actions = ["OPENBB_PYTHON 경로와 OpenBB quick venv 상태 확인", "기존 Yahoo history 경로로 fallback 확인"]
    else:
        first = rows[0] if rows else {}
        last = rows[-1] if rows else {}
        focus = [f"{symbol} OpenBB history: {len(rows)} rows / source={source}"]
        if rows:
            focus.append(f"기간: {first.get('date')} close={first.get('close')} → {last.get('date')} close={last.get('close')}")
            focus.append(f"최근 row: open={last.get('open')} high={last.get('high')} low={last.get('low')} volume={last.get('volume')}")
        summary = f"OpenBB로 {symbol} history를 확인했습니다."
        next_actions = ["필요하면 이 OHLCV를 기술지표/백테스트 입력으로 연결", "가격 판단은 기존 Yahoo chart 경로와 교차확인"]
    return {
        "agent": "us-stock-agent",
        "mode": "openbb_history",
        "summary": summary,
        "symbols": [symbol],
        "focus": focus,
        "next_actions": next_actions,
        "features": ["openbb", "openbb_history"],
        "data": {"openbb_history": history},
    }


def build_openbb_profile_response(profile: dict[str, Any]) -> dict[str, Any]:
    symbol = profile.get("symbol") or "UNKNOWN"
    source = profile.get("source") or "openbb"
    if profile.get("status") != "ok":
        error = profile.get("error") or "OpenBB unavailable"
        focus = [f"{symbol} OpenBB profile: 사용 불가 / {error}"]
        summary = f"OpenBB profile 호출이 실패했습니다: {symbol}"
        next_actions = ["OPENBB_PYTHON 경로와 OpenBB quick venv 상태 확인", "기존 profile/fundamental provider로 fallback 확인"]
    else:
        name = profile.get("name") or symbol
        focus = [
            f"{symbol} profile: {name} / sector={profile.get('sector') or 'unknown'} / industry={profile.get('industry') or 'unknown'} / source={source}",
            f"거래소/통화: exchange={profile.get('exchange') or 'unknown'} / currency={profile.get('currency') or 'unknown'} / country={profile.get('country') or 'unknown'}",
            f"market_cap={profile.get('market_cap')} / website={profile.get('website') or 'unknown'}",
        ]
        description = profile.get("description")
        if description:
            focus.append(f"사업 설명: {str(description)[:220]}")
        summary = f"OpenBB로 {symbol} profile을 확인했습니다."
        next_actions = ["다음 확장은 fundamentals/financials를 profile 옆에 붙이기", "핵심 가격 판단은 기존 quote/technical과 함께 확인"]
    return {
        "agent": "us-stock-agent",
        "mode": "openbb_profile",
        "summary": summary,
        "symbols": [symbol],
        "focus": focus,
        "next_actions": next_actions,
        "features": ["openbb", "openbb_profile"],
        "data": {"openbb_profile": profile},
    }


def build_openbb_quote_response(quote: dict[str, Any]) -> dict[str, Any]:
    symbol = quote.get("symbol") or "UNKNOWN"
    source = quote.get("source") or "openbb"
    if quote.get("status") != "ok":
        error = quote.get("error") or "OpenBB unavailable"
        focus = [f"{symbol} OpenBB: 사용 불가 / {error}"]
        summary = f"OpenBB quote 호출이 실패했습니다: {symbol}"
        next_actions = ["OPENBB_PYTHON 경로와 OpenBB quick venv 상태 확인", "Yahoo 기본 provider로 fallback해서 가격 확인"]
    else:
        price = quote.get("price")
        previous = quote.get("previous_close")
        pct = quote.get("pct_change")
        name = quote.get("name") or symbol
        if price is not None and previous is not None and pct is not None:
            focus = [f"{symbol} OpenBB quote: {price:.2f} {quote.get('currency') or ''} / 전일종가 {previous:.2f} / {pct:+.2f}% / source={source}"]
        else:
            focus = [f"{symbol} OpenBB quote: price={price} / source={source}"]
        focus.extend(
            [
                f"{symbol} 장중 범위: open {quote.get('open')} / high {quote.get('high')} / low {quote.get('low')} / volume {quote.get('volume')}",
                f"{symbol} 프로필: {name} / exchange={quote.get('exchange') or 'unknown'}",
            ]
        )
        summary = f"OpenBB로 {symbol} quote를 확인했습니다."
        next_actions = [
            "기본 가격 판단은 기존 Yahoo chart와 교차확인",
            "OpenBB는 fundamentals/macro/options/news 보조 provider로 확장",
        ]
    return {
        "agent": "us-stock-agent",
        "mode": "openbb_quote",
        "summary": summary,
        "symbols": [symbol],
        "focus": focus,
        "next_actions": next_actions,
        "features": ["openbb", "openbb_quote"],
        "data": {"openbb_quote": quote},
    }
