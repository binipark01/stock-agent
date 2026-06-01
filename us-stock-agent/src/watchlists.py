from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

DEFAULT_SYMBOLS = ["NVDA", "TSLA", "AAPL", "MSFT", "AMZN", "META", "GOOGL", "AMD"]

SYMBOL_ALIASES: dict[str, tuple[str, ...]] = {
    "NVDA": ("nvda", "nvidia", "엔비디아"),
    "TSLA": ("tsla", "tesla", "테슬라"),
    "AAPL": ("aapl", "apple", "애플"),
    "MSFT": ("msft", "microsoft", "마이크로소프트"),
    "AMZN": ("amzn", "amazon", "아마존"),
    "META": ("meta", "facebook", "메타"),
    "GOOGL": ("googl", "google", "alphabet", "구글"),
    "AMD": ("amd",),
    "AVGO": ("avgo", "broadcom", "브로드컴"),
    "TSM": ("tsm", "tsmc"),
    "PLTR": ("pltr", "palantir", "팔란티어"),
    "RDDT": ("rddt", "reddit", "레딧", "레딧주식"),
    "OKLO": ("oklo", "오클로"),
    "CRWV": ("crwv", "coreweave", "코어위브"),
    "MSTR": ("mstr", "microstrategy", "마이크로스트래티지", "스트래티지"),
    "COIN": ("coin", "coinbase", "코인베이스"),
    "RGTI": ("rgti", "rigetti", "리게티"),
    "IONQ": ("ionq", "아이온큐"),
    "BMNR": ("bmnr", "bitmine", "비트마인"),
    "RKLB": ("rklb", "rocket lab", "로켓랩"),
    "LUNR": ("lunr", "intuitive machines", "인튜이티브머신"),
    "RDW": ("rdw", "redwire", "레드와이어"),
    "AAOI": ("aaoi",),
    "LITE": ("lite", "lumentum", "루멘텀"),
    "COHR": ("cohr", "coherent", "코히런트"),
    "QQQ": ("qqq", "나스닥 etf"),
    "SPY": ("spy", "s&p etf", "sp500 etf"),
    "SOXX": ("soxx", "반도체 etf"),
    "005930.KS": ("005930", "삼성전자", "samsung electronics", "samsung"),
    "000660.KS": ("000660", "sk hynix", "hynix", "하이닉스", "sk하이닉스"),
    "042700.KS": ("042700", "한미반도체"),
    "095340.KQ": ("095340", "isc"),
    "403870.KQ": ("403870", "hpsp"),
    "240810.KQ": ("240810", "원익ips", "원익아이피에스"),
    "007660.KS": ("007660", "이수페타시스"),
    "222800.KQ": ("222800", "심텍"),
    "399720.KQ": ("399720", "가온칩스"),
    "394280.KQ": ("394280", "오픈엣지테크놀로지", "오픈엣지"),
    "373220.KS": ("373220", "lg에너지솔루션", "엘지에너지솔루션"),
    "006400.KS": ("006400", "삼성sdi", "삼성에스디아이"),
    "247540.KQ": ("247540", "에코프로비엠"),
    "003670.KS": ("003670", "포스코퓨처엠"),
    "005380.KS": ("005380", "현대차", "현대자동차", "hyundai motor"),
    "012330.KS": ("012330", "현대모비스"),
    "000270.KS": ("000270", "기아", "kia"),
    "078600.KQ": ("078600", "대주전자재료"),
    "348370.KQ": ("348370", "엔켐"),
    "020150.KS": ("020150", "롯데에너지머티리얼즈"),
    "267260.KS": ("267260", "hd현대일렉트릭", "현대일렉트릭"),
    "298040.KS": ("298040", "효성중공업"),
    "006260.KS": ("006260", "ls"),
    "001440.KS": ("001440", "대한전선"),
    "010120.KS": ("010120", "ls electric", "ls일렉트릭"),
    "103590.KS": ("103590", "일진전기"),
    "034020.KS": ("034020", "두산에너빌리티"),
    "052690.KS": ("052690", "한전기술"),
    "012450.KS": ("012450", "한화에어로스페이스"),
    "064350.KS": ("064350", "현대로템"),
    "079550.KS": ("079550", "lig넥스원", "lig디펜스", "lig디펜스앤에어로스페이스"),
    "047810.KS": ("047810", "한국항공우주", "kai"),
    "272210.KS": ("272210", "한화시스템"),
    "329180.KS": ("329180", "hd현대중공업", "현대중공업"),
    "042660.KS": ("042660", "한화오션"),
    "010140.KS": ("010140", "삼성중공업"),
    "071970.KS": ("071970", "hd현대마린엔진", "현대마린엔진"),
    "014620.KQ": ("014620", "성광벤드"),
    "023160.KQ": ("023160", "태광"),
    "017960.KS": ("017960", "한국카본"),
    "033500.KQ": ("033500", "동성화인텍"),
    "454910.KS": ("454910", "두산로보틱스"),
    "277810.KQ": ("277810", "레인보우로보틱스"),
    "058610.KQ": ("058610", "에스피지", "spg"),
    "108490.KQ": ("108490", "로보티즈"),
    "117730.KQ": ("117730", "티로보틱스", "t-robotics"),
    "348340.KQ": ("348340", "뉴로메카"),
}

_ALIAS_TO_SYMBOL = {alias.lower(): symbol for symbol, aliases in SYMBOL_ALIASES.items() for alias in aliases}

LIST_ALIASES: dict[str, tuple[str, ...]] = {
    # KRX sub-theme aliases must stay before broad/global aliases like "반도체" and "국장".
    "krx_stockcrew_semiconductors": ("krx_stockcrew_semiconductors", "국장 반도체", "한국 반도체", "국장 hbm", "국장 pcb"),
    "krx_stockcrew_battery": ("krx_stockcrew_battery", "국장 이차전지", "국장 2차전지", "한국 이차전지", "한국 2차전지"),
    "krx_stockcrew_power_infra": ("krx_stockcrew_power_infra", "국장 전력", "국장 전력인프라", "한국 전력", "전력 인프라"),
    "krx_stockcrew_defense": ("krx_stockcrew_defense", "국장 방산", "한국 방산"),
    "krx_stockcrew_shipbuilding": ("krx_stockcrew_shipbuilding", "국장 조선", "한국 조선"),
    "krx_stockcrew_robotics": ("krx_stockcrew_robotics", "국장 로봇", "한국 로봇"),
    "krx_stockcrew_leaders": ("krx_stockcrew_leaders", "국장테마", "국장 테마", "한국장테마", "한국장 테마", "대장섹터", "대장 섹터", "주식크루", "stockcrew", "국장", "한국장"),
    "ai_infra": ("ai_infra", "ai infra", "ai", "ai인프라", "ai 인프라", "인공지능", "빅테크"),
    "optical": ("optical", "광통신", "광 통신", "광", "광모듈", "네트워크광"),
    "reddit_rddt": ("reddit_rddt", "reddit", "rddt", "레딧"),
    "crypto": ("crypto", "코인", "암호화", "비트코인", "크립토"),
    "nuclear": ("nuclear", "원전", "우라늄", "전력", "smr"),
    "semis": ("semis", "semi", "반도체", "ai칩", "ai 칩"),
    "space": ("space", "우주", "항공우주"),
    "quantum": ("quantum", "양자"),
    "healthcare": ("healthcare", "헬스케어", "glp", "디지털헬스"),
    "biotech_later": ("biotech_later", "바이오", "개잡주", "잡주"),
}


def infer_watchlist_scope(request_text: str, watchlist_data: dict[str, Any] | None = None) -> str | None:
    lowered = str(request_text or "").lower().replace("_", " ")
    available = set((watchlist_data or {}).get("lists", {}).keys()) if isinstance((watchlist_data or {}).get("lists"), dict) else set()
    for list_name in available:
        normalized = str(list_name).lower().replace("_", " ")
        if normalized and normalized in lowered:
            return str(list_name)
    for list_name, aliases in LIST_ALIASES.items():
        if available and list_name not in available:
            continue
        if any(alias.lower().replace("_", " ") in lowered for alias in aliases):
            return list_name
    if any(keyword in lowered for keyword in ["portfolio", "포트폴리오", "보유"]):
        return "portfolio"
    return None


def filter_watchlist_scope(watchlist_data: dict[str, Any], scope: str | None) -> dict[str, Any]:
    if not scope:
        return watchlist_data
    scope = str(scope)
    lists = watchlist_data.get("lists") if isinstance(watchlist_data.get("lists"), dict) else {}
    if scope == "watchlist":
        return {"watchlist": normalize_symbols(watchlist_data.get("watchlist") or []), "portfolio": [], "lists": {}}
    if scope == "portfolio":
        return {"watchlist": [], "portfolio": normalize_symbols(watchlist_data.get("portfolio") or []), "lists": {}}
    if scope in lists:
        return {"watchlist": [], "portfolio": [], "lists": {scope: normalize_symbols(lists.get(scope) or [])}}
    return watchlist_data


def normalize_symbol(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    lowered = text.lower()
    if lowered in _ALIAS_TO_SYMBOL:
        return _ALIAS_TO_SYMBOL[lowered]
    compact = text.replace(" ", "").upper()
    if compact in {"REDDIT", "레딧"}:
        return "RDDT"
    return text.upper()


def normalize_symbols(values: Iterable[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        symbol = normalize_symbol(value)
        if symbol and symbol not in seen:
            seen.add(symbol)
            result.append(symbol)
    return result


def _default_watchlist() -> dict[str, Any]:
    return {"watchlist": DEFAULT_SYMBOLS[:3], "portfolio": [], "lists": {}}


def load_watchlist(path: str | Path | None = None) -> dict[str, Any]:
    if path is None:
        return _default_watchlist()
    watchlist_path = Path(path)
    if not watchlist_path.exists():
        return _default_watchlist()
    try:
        data = json.loads(watchlist_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return _default_watchlist()
    if not isinstance(data, dict):
        return _default_watchlist()

    lists_raw = data.get("lists") if isinstance(data.get("lists"), dict) else {}
    return {
        "watchlist": normalize_symbols(data.get("watchlist") or DEFAULT_SYMBOLS[:3]),
        "portfolio": normalize_symbols(data.get("portfolio") or []),
        "lists": {str(name): normalize_symbols(symbols or []) for name, symbols in lists_raw.items()},
    }


def save_watchlist(
    path: str | Path,
    watchlist: Iterable[Any] | None = None,
    portfolio: Iterable[Any] | None = None,
    lists: dict[str, Iterable[Any]] | None = None,
) -> dict[str, Any]:
    watchlist_path = Path(path)
    watchlist_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "watchlist": normalize_symbols(watchlist or []),
        "portfolio": normalize_symbols(portfolio or []),
        "lists": {str(name): normalize_symbols(symbols or []) for name, symbols in (lists or {}).items()},
    }
    watchlist_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"saved": True, "path": str(watchlist_path), **payload}


def flatten_watchlist_symbols(watchlist_data: dict[str, Any]) -> list[str]:
    symbols: list[Any] = []
    symbols.extend(watchlist_data.get("watchlist") or [])
    symbols.extend(watchlist_data.get("portfolio") or [])
    lists = watchlist_data.get("lists") if isinstance(watchlist_data.get("lists"), dict) else {}
    for values in lists.values():
        symbols.extend(values or [])
    return normalize_symbols(symbols)


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        numeric = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None
    if numeric != numeric or numeric in (float("inf"), float("-inf")):
        return None
    return numeric


def _pct_change(quote: dict[str, Any]) -> float | None:
    direct = _to_float(quote.get("pct_change") or quote.get("change_pct") or quote.get("regularMarketChangePercent"))
    if direct is not None:
        return round(direct, 2)
    price = _to_float(quote.get("price") or quote.get("last") or quote.get("last_price") or quote.get("regularMarketPrice"))
    previous = _to_float(quote.get("previous_close") or quote.get("previousClose") or quote.get("regularMarketPreviousClose"))
    if price is None or previous in (None, 0):
        return None
    return round(((price - float(previous)) / float(previous)) * 100, 2)


def _fmt_pct(value: Any) -> str:
    numeric = _to_float(value)
    return "n/a" if numeric is None else f"{numeric:+.2f}%"


def _symbol_membership(watchlist_data: dict[str, Any]) -> dict[str, list[str]]:
    membership: dict[str, list[str]] = {}
    for symbol in normalize_symbols(watchlist_data.get("watchlist") or []):
        membership.setdefault(symbol, []).append("watchlist")
    for symbol in normalize_symbols(watchlist_data.get("portfolio") or []):
        membership.setdefault(symbol, []).append("portfolio")
    lists = watchlist_data.get("lists") if isinstance(watchlist_data.get("lists"), dict) else {}
    for list_name, values in lists.items():
        for symbol in normalize_symbols(values or []):
            membership.setdefault(symbol, []).append(str(list_name))
    return membership


def _list_summary(list_name: str, symbols: list[str], quotes: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    rows = []
    for symbol in symbols:
        quote = quotes.get(symbol) or {}
        pct = _pct_change(quote)
        if pct is None:
            continue
        rows.append({"symbol": symbol, "pct_change": pct, "price": quote.get("price"), "source": quote.get("source"), "timestamp": quote.get("timestamp")})
    if not rows:
        return None
    values = [float(row["pct_change"]) for row in rows]
    leaders = sorted(rows, key=lambda row: row["pct_change"], reverse=True)[:3]
    laggards = sorted(rows, key=lambda row: row["pct_change"])[:3]
    return {
        "name": list_name,
        "symbols": symbols,
        "covered_symbols": [row["symbol"] for row in rows],
        "average_pct_change": round(sum(values) / len(values), 2),
        "breadth_positive_pct": round((sum(1 for value in values if value > 0) / len(values)) * 100, 1),
        "leaders": leaders,
        "laggards": laggards,
    }


def build_watchlist_scan(watchlist_data: dict[str, Any], quotes: dict[str, Any], collected_at: str | None = None, top_n: int = 5) -> dict[str, Any]:
    normalized_quotes = {str(symbol).upper(): dict(quote or {}) for symbol, quote in (quotes or {}).items() if isinstance(quote, dict)}
    collected_at = collected_at or next((str(q.get("timestamp") or q.get("collected_at")) for q in normalized_quotes.values() if q.get("timestamp") or q.get("collected_at")), None) or datetime.now(timezone.utc).isoformat()
    membership = _symbol_membership(watchlist_data)
    all_symbols = list(membership.keys())
    spy_pct = _pct_change(normalized_quotes.get("SPY", {})) or 0.0

    movers: list[dict[str, Any]] = []
    for symbol in all_symbols:
        quote = normalized_quotes.get(symbol) or {}
        pct = _pct_change(quote)
        if pct is None:
            continue
        rel_spy = round(pct - spy_pct, 2)
        movers.append(
            {
                "symbol": symbol,
                "pct_change": round(pct, 2),
                "relative_to_spy_pct": rel_spy,
                "mover_score": round(abs(pct) + max(rel_spy, 0.0), 3),
                "direction": "강세" if pct >= 0 else "약세",
                "lists": membership.get(symbol, []),
                "price": quote.get("price"),
                "source": quote.get("source"),
                "timestamp": quote.get("timestamp") or quote.get("collected_at"),
            }
        )

    top_movers = sorted((row for row in movers if row["pct_change"] >= 0), key=lambda row: (row["pct_change"], row["mover_score"]), reverse=True)[:top_n]
    weak_movers = sorted((row for row in movers if row["pct_change"] < 0), key=lambda row: row["pct_change"])[:top_n]
    all_ranked = sorted(movers, key=lambda row: row["mover_score"], reverse=True)

    list_inputs = {"watchlist": normalize_symbols(watchlist_data.get("watchlist") or []), "portfolio": normalize_symbols(watchlist_data.get("portfolio") or [])}
    lists = watchlist_data.get("lists") if isinstance(watchlist_data.get("lists"), dict) else {}
    list_inputs.update({str(name): normalize_symbols(values or []) for name, values in lists.items()})
    list_summaries = [summary for name, symbols in list_inputs.items() if (summary := _list_summary(name, symbols, normalized_quotes))]
    list_summaries.sort(key=lambda row: row["average_pct_change"], reverse=True)

    if not movers:
        return {
            "available": False,
            "summary": "관심종목 스캔: quote 데이터 부족",
            "collected_at": collected_at,
            "focus_lines": ["관심종목 스캔: watchlist quote 데이터가 부족합니다"],
            "next_actions": ["watchlist 심볼과 Yahoo quote 수집 상태를 먼저 확인"],
            "top_movers": [],
            "weak_movers": [],
            "list_summaries": [],
            "quotes": normalized_quotes,
        }

    top_line = " | ".join(f"{row['symbol']} {_fmt_pct(row['pct_change'])}({','.join(row['lists'])})" for row in top_movers[:top_n]) or "없음"
    weak_line = " | ".join(f"{row['symbol']} {_fmt_pct(row['pct_change'])}({','.join(row['lists'])})" for row in weak_movers[:top_n]) or "없음"
    list_line = " | ".join(f"{row['name']} 평균 {_fmt_pct(row['average_pct_change'])} / 상승비율 {row['breadth_positive_pct']:.1f}%" for row in list_summaries[:3]) or "데이터 부족"
    leader = top_movers[0]["symbol"] if top_movers else all_ranked[0]["symbol"]
    laggard = weak_movers[0]["symbol"] if weak_movers else "약세 제한"

    return {
        "available": True,
        "summary": f"관심종목 스캔: {leader} 강세 / {laggard} 약세 / {len(movers)}개 quote 확인",
        "collected_at": collected_at,
        "focus_lines": [
            f"관심종목 스캔: 강한 종목 {top_line}",
            f"약한 종목: {weak_line}",
            f"리스트별 강도: {list_line}",
            f"벤치마크: SPY {_fmt_pct(spy_pct)} / 기준시각 {collected_at}",
        ],
        "next_actions": [
            "강한 종목은 해당 리스트/테마가 같이 강한지 확인",
            "약한 보유종목은 뉴스/공시/지지선 순서로 재점검",
            "동일 테마 안에서 강한 종목만 추리고 약한 종목은 추격 제외",
        ],
        "top_movers": top_movers,
        "weak_movers": weak_movers,
        "movers": all_ranked,
        "list_summaries": list_summaries,
        "quotes": normalized_quotes,
    }
