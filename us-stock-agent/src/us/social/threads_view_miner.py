from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

try:
    from .threads import DEFAULT_THREADS_CLASSIFIED_PATH, load_threads_view_targets
    from ...watchlists import SYMBOL_ALIASES
except ImportError:  # direct script execution
    from us.social.threads import DEFAULT_THREADS_CLASSIFIED_PATH, load_threads_view_targets
    from watchlists import SYMBOL_ALIASES


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data"
DEFAULT_THREADS_PROFILE_CACHE_DIR = DEFAULT_OUTPUT_DIR / "threads_profile_cache"
DEFAULT_THREADS_SLOW_STATE_PATH = DEFAULT_THREADS_PROFILE_CACHE_DIR / "slow_state.json"
JINA_PREFIX = "https://r.jina.ai/http://"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

EXTRA_SYMBOL_ALIASES: dict[str, tuple[str, ...]] = {
    "030530.KQ": ("030530", "원익홀딩스"),
    "093370.KQ": ("093370", "후성"),
    "SNDK": ("sndk", "sandisk", "샌디스크"),
    "STX": ("stx", "seagate", "씨게이트"),
    "MU": ("mu", "micron", "마이크론"),
    "SMH": ("smh",),
    "SOXL": ("soxl",),
    "IREN": ("iren",),
    "INTC": ("intc", "intel", "인텔"),
    "MRVL": ("mrvl", "marvell", "마벨"),
    "CGTX": ("cgtx", "cognition therapeutics"),
    "XNDU": ("xndu",),
    "BTC-USD": ("btc", "bitcoin", "비트코인"),
}

PROFILE_NOISE_PREFIXES = (
    "translate",
    "related threads",
    "log in",
    "sign up",
    "threads",
    "instagram",
    "meta",
)

BULLISH_TERMS = [
    "돌파",
    "상승",
    "강세",
    "좋",
    "살아",
    "타점",
    "추세 전환",
    "매집",
    "대장",
    "주도",
    "줍줍",
    "비중 추가",
    "수요",
    "성장",
    "호재",
    "beat",
    "strong",
    "breakout",
    "upside",
    "bullish",
    "buy",
]
RISK_TERMS = [
    "급락",
    "조심",
    "이탈",
    "하락",
    "악재",
    "둔화",
    "조정",
    "위험",
    "리스크",
    "손절",
    "무효",
    "과열",
    "압박",
    "cut",
    "miss",
    "slowdown",
    "bearish",
    "downside",
]
CHART_TERMS = ["차트", "지지", "저항", "타점", "추세", "돌파", "매집", "손익비", "캔들", "이평", "신고가", "눌림"]
RUMOR_TERMS = ["루머", "카더라", "썰", "rumor", "hearsay"]
FOMO_TERMS = ["좋아요", "우리끼리", "99%", "급등", "안사면", "세력", "숨겨진", "몇 배", "팔로우"]
MACRO_TERMS = ["금리", "fomc", "cpi", "고용", "달러", "채권", "10년", "유가", "vix", "파월"]
CATALYST_TERMS = ["실적", "계약", "승인", "fda", "임상", "가이던스", "공시", "sec", "earnings", "filing"]


def _normalize_handle(value: Any) -> str:
    return str(value or "").strip().lstrip("@")


def _clean_markdown_line(line: str) -> str:
    text = line.strip()
    if not text:
        return ""
    if text.startswith("!["):
        return ""
    text = re.sub(r"!\[[^\]]*\]\([^\)]*\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^\)]*\)", r"\1", text)
    text = re.sub(r"\s+", " ", text).strip(" -|\t")
    if text.lower() in PROFILE_NOISE_PREFIXES:
        return ""
    if any(text.lower().startswith(prefix) for prefix in PROFILE_NOISE_PREFIXES):
        return ""
    return text


def _extract_post_id(url: str) -> str:
    match = re.search(r"/post/([A-Za-z0-9_-]+)", url)
    return match.group(1) if match else url.rstrip("/").rsplit("/", 1)[-1]


def extract_threads_posts_from_markdown(markdown: str, account: dict[str, Any], max_posts: int = 20) -> list[dict[str, Any]]:
    """Extract recent public Threads post snippets from Jina/profile markdown.

    Public Threads/Jina output is partial and unstable, so this parser is deliberately
    conservative: it dedupes post URLs and keeps only nearby text snippets.
    """
    handle = _normalize_handle(account.get("handle"))
    if not handle or not markdown:
        return []

    post_url_pattern = re.compile(r"https://www\.threads\.com/@([^/\s\)]+)/post/([A-Za-z0-9_-]+)")
    lines = markdown.splitlines()
    posts: list[dict[str, Any]] = []
    seen: set[str] = set()

    for idx, raw_line in enumerate(lines):
        match = post_url_pattern.search(raw_line)
        if not match:
            continue
        url_handle = _normalize_handle(match.group(1))
        if url_handle.lower() != handle.lower():
            continue
        post_url = match.group(0)
        post_id = match.group(2)
        if post_id in seen:
            continue
        seen.add(post_id)

        date_match = re.search(r"\[([^\]]*(?:\d{1,2}/\d{1,2}/\d{2}|\d+\s*[hdwm]|\d+일|\d+시간)[^\]]*)\]", raw_line, flags=re.IGNORECASE)
        if not date_match:
            date_match = re.search(r"(\d{1,2}/\d{1,2}/\d{2}|\d+\s*[hdwm]|\d+일|\d+시간)", raw_line, flags=re.IGNORECASE)
        published_hint = date_match.group(1).strip() if date_match else None

        snippet_lines: list[str] = []
        same_line = _clean_markdown_line(raw_line.replace(post_url, " "))
        if same_line and not re.fullmatch(r"\d{1,2}/\d{1,2}/\d{2}|\d+\s*[hdwm]|\d+일|\d+시간", same_line, flags=re.IGNORECASE):
            snippet_lines.append(same_line)
        for next_line in lines[idx + 1 : idx + 12]:
            if post_url_pattern.search(next_line):
                break
            cleaned = _clean_markdown_line(next_line)
            if not cleaned:
                continue
            if cleaned in snippet_lines:
                continue
            snippet_lines.append(cleaned)
            if len(" ".join(snippet_lines)) >= 500 or len(snippet_lines) >= 5:
                break

        text = " ".join(snippet_lines).strip()
        if not text:
            continue
        posts.append(
            {
                "author_handle": handle,
                "author_name": str(account.get("display_name") or handle),
                "category": str(account.get("category") or "unknown"),
                "priority": str(account.get("priority") or "medium"),
                "post_id": post_id,
                "post_url": post_url,
                "published_hint": published_hint,
                "text": text,
                "source": "threads_jina_markdown",
            }
        )
        if max_posts and len(posts) >= max_posts:
            break
    return posts


def _combined_symbol_aliases() -> dict[str, tuple[str, ...]]:
    merged = {symbol: tuple(aliases) for symbol, aliases in SYMBOL_ALIASES.items()}
    for symbol, aliases in EXTRA_SYMBOL_ALIASES.items():
        merged.setdefault(symbol, ())
        merged[symbol] = tuple(dict.fromkeys([*merged[symbol], *aliases]))
    return merged


def _alias_matches(text: str, alias: str) -> bool:
    lowered = text.lower()
    alias_lower = alias.lower()
    if not alias_lower:
        return False
    if re.fullmatch(r"[a-z0-9._-]+", alias_lower):
        return bool(re.search(rf"(?<![A-Za-z0-9._-]){re.escape(alias_lower)}(?![A-Za-z0-9._-])", lowered))
    return alias_lower in lowered


def match_symbols(text: str) -> list[str]:
    matched: list[str] = []
    seen: set[str] = set()
    for symbol, aliases in _combined_symbol_aliases().items():
        if any(_alias_matches(text, alias) for alias in aliases):
            if symbol not in seen:
                seen.add(symbol)
                matched.append(symbol)
    return matched


def _infer_direction(text: str) -> str:
    lowered = text.lower()
    bullish = sum(1 for term in BULLISH_TERMS if term.lower() in lowered)
    risk = sum(1 for term in RISK_TERMS if term.lower() in lowered)
    if bullish and risk:
        return "bullish_with_risk"
    if bullish:
        return "bullish"
    if risk:
        return "bearish_or_risk"
    return "neutral"


def _infer_evidence_type(text: str) -> str:
    lowered = text.lower()
    if any(term in lowered for term in RUMOR_TERMS):
        return "rumor"
    if any(term in lowered for term in CHART_TERMS):
        return "chart"
    if any(term in lowered for term in CATALYST_TERMS):
        return "catalyst"
    if any(term in lowered for term in MACRO_TERMS):
        return "macro"
    return "opinion"


def _infer_horizon(text: str) -> str:
    lowered = text.lower()
    if any(term in lowered for term in ["단타", "장초", "intraday", "당일"]):
        return "intraday"
    if any(term in lowered for term in ["스윙", "swing", "며칠", "1~2주", "2주"]):
        return "swing"
    if any(term in lowered for term in ["중기", "중장기", "medium"]):
        return "medium"
    if any(term in lowered for term in ["장기", "long", "구조적"]):
        return "long"
    return "unspecified"


def _extract_key_levels_krw(text: str) -> list[int]:
    levels: list[int] = []
    for match in re.finditer(r"(\d{1,3}(?:,\d{3})+|\d{4,6})\s*원대?", text):
        value = int(match.group(1).replace(",", ""))
        if value not in levels:
            levels.append(value)
    for match in re.finditer(r"(\d{1,2})층\s*중반", text):
        value = int(match.group(1)) * 1000 + 500
        if value not in levels:
            levels.append(value)
    return levels


def _infer_themes(text: str, symbols: Iterable[str]) -> list[str]:
    lowered = text.lower()
    themes: list[str] = []
    symbol_set = set(symbols)
    if any(symbol.endswith((".KS", ".KQ")) for symbol in symbol_set) or any(term in text for term in ["국장", "국내주식", "코스닥", "코스피"]):
        themes.append("KRX")
    if any(term in lowered for term in ["반도체", "soxx", "soxl", "sndk", "memory", "dram", "hbm", "메모리"]) or symbol_set.intersection({"SOXX", "SOXL", "SMH", "NVDA", "TSM", "MU", "SNDK", "STX", "005930.KS", "000660.KS"}):
        themes.append("semiconductors")
    if any(term in lowered for term in ["ai", "인공지능", "데이터센터", "ai 인프라", "infra"]):
        themes.append("AI_infra")
    if any(term in lowered for term in ["코인", "비트코인", "btc", "crypto"]):
        themes.append("crypto")
    if any(term in lowered for term in MACRO_TERMS):
        themes.append("macro")
    if any(term in lowered for term in ["바이오", "임상", "fda", "health", "cgtx"]):
        themes.append("healthcare_biotech")
    if not themes:
        themes.append("general_market")
    return list(dict.fromkeys(themes))


def _short_claim(text: str, max_chars: int = 180) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 1].rstrip() + "…"


def analyze_threads_post(post: dict[str, Any]) -> dict[str, Any]:
    text = str(post.get("text") or "")
    symbols = match_symbols(text)
    direction = _infer_direction(text)
    evidence_type = _infer_evidence_type(text)
    horizon = _infer_horizon(text)
    themes = _infer_themes(text, symbols)
    key_levels_krw = _extract_key_levels_krw(text)
    priority = str(post.get("priority") or "medium")

    relevance = 20
    if priority == "high":
        relevance += 25
    elif priority == "medium":
        relevance += 12
    if symbols:
        relevance += 30
    if direction in {"bullish", "bearish_or_risk", "bullish_with_risk"}:
        relevance += 15
    if evidence_type in {"chart", "catalyst", "macro"}:
        relevance += 10
    if key_levels_krw:
        relevance += 10
    if "KRX" in themes:
        relevance += 5
    if evidence_type == "rumor":
        relevance -= 12
    if not symbols and any(term in text for term in FOMO_TERMS):
        relevance -= 25
    relevance = max(0, min(100, relevance))

    actionability = "actionable_research_input" if relevance >= 60 and symbols else "context_only"
    if evidence_type == "rumor" or (not symbols and any(term in text for term in FOMO_TERMS)):
        actionability = "ignore_or_downrank"

    return {
        "author_handle": post.get("author_handle"),
        "author_name": post.get("author_name"),
        "category": post.get("category"),
        "priority": priority,
        "post_id": post.get("post_id"),
        "post_url": post.get("post_url"),
        "published_hint": post.get("published_hint"),
        "claim_text": _short_claim(text),
        "symbols": symbols,
        "themes": themes,
        "direction": direction,
        "horizon": horizon,
        "evidence_type": evidence_type,
        "key_levels_krw": key_levels_krw,
        "requires_price_validation": bool(symbols or key_levels_krw),
        "relevance_score": relevance,
        "actionability": actionability,
        "source": post.get("source"),
    }


def fetch_threads_profile_markdown(handle: str, timeout: int = 30) -> str:
    url = f"{JINA_PREFIX}https://www.threads.com/@{handle}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def _safe_cache_filename(handle: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", _normalize_handle(handle)) + ".md"


def _read_fresh_cache(cache_dir: str | Path | None, handle: str, cache_ttl_seconds: int | float) -> str | None:
    if not cache_dir or cache_ttl_seconds <= 0:
        return None
    path = Path(cache_dir) / _safe_cache_filename(handle)
    if not path.exists():
        return None
    age_seconds = time.time() - path.stat().st_mtime
    if age_seconds > cache_ttl_seconds:
        return None
    return path.read_text(encoding="utf-8")


def _write_cache(cache_dir: str | Path | None, handle: str, markdown: str) -> None:
    if not cache_dir:
        return
    path = Path(cache_dir) / _safe_cache_filename(handle)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")


def _fetch_error_status(exc: BaseException) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        return str(exc.code)
    return type(exc).__name__


def _is_rate_limit_error(exc: BaseException) -> bool:
    return isinstance(exc, urllib.error.HTTPError) and exc.code == 429


def _load_classified_accounts(path: str | Path | None = None) -> list[dict[str, Any]]:
    classified_path = Path(path or DEFAULT_THREADS_CLASSIFIED_PATH)
    if not classified_path.exists():
        return []
    try:
        data = json.loads(classified_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    accounts = data.get("accounts", []) if isinstance(data, dict) else []
    return [item for item in accounts if isinstance(item, dict) and item.get("handle")]


def load_threads_scan_accounts(
    account_source: str = "seed_high_signal",
    max_accounts: int = 0,
    classified_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    if account_source == "view_targets":
        accounts = load_threads_view_targets()
    else:
        accounts = _load_classified_accounts(classified_path)
        if account_source == "seed_high_signal":
            allowed_categories = {"trader", "stocks", "macro_news", "crypto"}
            accounts = [item for item in accounts if item.get("priority") == "high" and item.get("category") in allowed_categories]
        elif account_source == "seed_stock_trader":
            allowed_categories = {"trader", "stocks", "macro_news"}
            accounts = [item for item in accounts if item.get("priority") == "high" and item.get("category") in allowed_categories]
    normalized = []
    seen: set[str] = set()
    for account in accounts:
        handle = _normalize_handle(account.get("handle"))
        if not handle or handle in seen:
            continue
        seen.add(handle)
        normalized.append({**account, "handle": handle, "display_name": str(account.get("display_name") or handle)})
    if max_accounts and max_accounts > 0:
        return normalized[:max_accounts]
    return normalized


def _cluster_counts(claims: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    authors: dict[str, set[str]] = defaultdict(set)
    for claim in claims:
        values = claim.get(key) or []
        if isinstance(values, str):
            values = [values]
        for value in values:
            counts[str(value)] += 1
            if claim.get("author_handle"):
                authors[str(value)].add(str(claim["author_handle"]))
    return [
        {"symbol" if key == "symbols" else "theme": value, "count": count, "authors": sorted(authors[value])}
        for value, count in counts.most_common()
    ]


def build_threads_view_scan_report(
    accounts: list[dict[str, Any]] | None = None,
    profile_markdown_by_handle: dict[str, str] | None = None,
    max_accounts: int = 0,
    account_offset: int = 0,
    max_posts_per_account: int = 8,
    fetch_live: bool = True,
    account_source: str = "seed_high_signal",
    cache_dir: str | Path | None = None,
    cache_ttl_seconds: int | float = 0,
    delay_seconds: int | float = 0,
    fetcher: Callable[[str, int], str] = fetch_threads_profile_markdown,
    sleeper: Callable[[float], Any] = time.sleep,
    max_consecutive_rate_limits: int = 2,
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    selected_accounts = accounts or load_threads_scan_accounts(account_source=account_source, max_accounts=0)
    # account_offset is the absolute resume cursor for full seed lists. If a caller
    # passes only a small pre-selected batch with an offset larger than that batch,
    # keep the accounts intact and use the offset only for state metadata.
    if account_offset and account_offset > 0 and int(account_offset) < len(selected_accounts):
        selected_accounts = selected_accounts[account_offset:]
    if max_accounts and max_accounts > 0:
        selected_accounts = selected_accounts[:max_accounts]
    markdown_by_handle = {_normalize_handle(k): v for k, v in (profile_markdown_by_handle or {}).items()}

    posts: list[dict[str, Any]] = []
    fetch_errors: list[dict[str, str]] = []
    skipped_accounts: list[str] = []
    cache_hits = 0
    live_fetch_count = 0
    consecutive_rate_limits = 0
    stopped_early = False
    stop_reason: str | None = None

    for index, account in enumerate(selected_accounts):
        handle = _normalize_handle(account.get("handle"))
        markdown = markdown_by_handle.get(handle, "")
        if not markdown:
            cached = _read_fresh_cache(cache_dir, handle, cache_ttl_seconds)
            if cached is not None:
                markdown = cached
                cache_hits += 1
        if not markdown and fetch_live:
            try:
                markdown = fetcher(handle, timeout_seconds)
                live_fetch_count += 1
                consecutive_rate_limits = 0
                _write_cache(cache_dir, handle, markdown)
                if delay_seconds and index < len(selected_accounts) - 1:
                    sleeper(float(delay_seconds))
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                status = _fetch_error_status(exc)
                fetch_errors.append({"handle": handle, "error": str(exc)[:180], "status": status})
                if _is_rate_limit_error(exc):
                    consecutive_rate_limits += 1
                    if max_consecutive_rate_limits and consecutive_rate_limits >= max_consecutive_rate_limits:
                        stopped_early = True
                        stop_reason = "rate_limited"
                        skipped_accounts = [_normalize_handle(item.get("handle")) for item in selected_accounts[index + 1 :]]
                        break
                else:
                    consecutive_rate_limits = 0
                continue
        extracted = extract_threads_posts_from_markdown(markdown, account, max_posts=max_posts_per_account) if markdown else []
        posts.extend(extracted)

    claims = [analyze_threads_post(post) for post in posts]
    actionable_claims = [claim for claim in claims if claim["actionability"] == "actionable_research_input"]
    ranked_claims = sorted(actionable_claims, key=lambda claim: (-int(claim["relevance_score"]), str(claim.get("author_handle") or ""), str(claim.get("post_id") or "")))
    symbol_clusters = _cluster_counts(actionable_claims, "symbols")
    theme_clusters = _cluster_counts(actionable_claims, "themes")

    focus_lines = [
        f"Threads 수집: {len(selected_accounts)}계정 / {len(posts)}글 / actionable {len(actionable_claims)}건 / fetch_errors {len(fetch_errors)}건 / cache_hits {cache_hits}건 / live_fetch {live_fetch_count}건",
    ]
    for idx, claim in enumerate(ranked_claims[:10], start=1):
        symbol_text = ",".join(claim.get("symbols") or ["no_symbol"])
        level_text = f" / levels={','.join(str(v) for v in claim['key_levels_krw'])}" if claim.get("key_levels_krw") else ""
        focus_lines.append(
            f"{idx}) {symbol_text} {claim['direction']} @{claim['author_handle']} / {claim['evidence_type']} / score {claim['relevance_score']}{level_text} / {claim['claim_text']}"
        )
    if symbol_clusters:
        focus_lines.append("종목 클러스터: " + ", ".join(f"{item['symbol']}({item['count']})" for item in symbol_clusters[:8]))
    if theme_clusters:
        focus_lines.append("테마 클러스터: " + ", ".join(f"{item['theme']}({item['count']})" for item in theme_clusters[:8]))
    if fetch_errors:
        focus_lines.append("접근 제한/실패: " + ", ".join(f"@{item['handle']}[{item.get('status', 'error')}]" for item in fetch_errors[:8]))
    if stopped_early:
        focus_lines.append(f"수집 중단: {stop_reason} / skipped {len(skipped_accounts)}계정 / 다음 배치에서 재시도")

    summary = f"Threads view scan: {len(selected_accounts)}계정 / {len(posts)}글 / actionable {len(actionable_claims)}건"
    next_actions = [
        "상위 actionable 종목은 현재가·거래량·뉴스/공시로 교차검증",
        "KRX 종목은 지지/타점 원화 가격대와 현재가 괴리부터 확인",
        "429가 나오면 같은 세션에서 즉시 재시도하지 말고 cache/retry queue 기준으로 다음 배치에서 재수집",
        "루머·숨은픽·좋아요 유도 글은 alert가 아니라 crowd/FOMO 노이즈로만 사용",
    ]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "account_source": account_source,
        "account_offset": int(account_offset or 0),
        "account_count": len(selected_accounts),
        "post_count": len(posts),
        "claim_count": len(claims),
        "actionable_count": len(actionable_claims),
        "cache_hits": cache_hits,
        "live_fetch_count": live_fetch_count,
        "cache_ttl_seconds": float(cache_ttl_seconds),
        "delay_seconds": float(delay_seconds),
        "stopped_early": stopped_early,
        "stop_reason": stop_reason,
        "skipped_accounts": skipped_accounts,
        "accounts": selected_accounts,
        "posts": posts,
        "claims": ranked_claims + [claim for claim in claims if claim not in ranked_claims],
        "symbol_clusters": symbol_clusters,
        "theme_clusters": theme_clusters,
        "fetch_errors": fetch_errors,
        "focus_lines": focus_lines,
        "next_actions": next_actions,
    }


def load_threads_slow_state(state_path: str | Path = DEFAULT_THREADS_SLOW_STATE_PATH) -> dict[str, Any]:
    path = Path(state_path)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def build_threads_slow_state(
    report: dict[str, Any],
    batch_size: int | None = None,
    accounts_total: int | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    offset = int(report.get("account_offset") or 0)
    account_count = int(report.get("account_count") or 0)
    skipped_count = len(report.get("skipped_accounts") or [])
    attempted_count = max(account_count - skipped_count, 0)
    next_offset = offset + attempted_count
    last_completed_offset = next_offset - 1 if attempted_count else offset - 1
    handles = [str(account.get("handle")) for account in report.get("accounts", []) if isinstance(account, dict) and account.get("handle")]
    artifact_paths = {str(key): Path(value).as_posix() for key, value in (report.get("artifact_paths") or {}).items()}
    last_batch = {
        "offset": offset,
        "next_offset": next_offset,
        "accounts": handles[:attempted_count] if attempted_count else [],
        "summary": report.get("summary"),
        "cache_hits": int(report.get("cache_hits") or 0),
        "live_fetch_count": int(report.get("live_fetch_count") or 0),
        "fetch_errors": len(report.get("fetch_errors") or []),
        "stopped_early": bool(report.get("stopped_early")),
        "stop_reason": report.get("stop_reason"),
        "artifact_paths": artifact_paths,
    }
    state = {
        "last_completed_offset": last_completed_offset,
        "next_offset": next_offset,
        "batch_size": int(batch_size or account_count or attempted_count or 0),
        "recommended_delay_seconds": float(report.get("delay_seconds") or 0),
        "cache_ttl_seconds": int(report.get("cache_ttl_seconds") or 0) if report.get("cache_ttl_seconds") is not None else 0,
        "account_source": report.get("account_source"),
        "accounts_total": int(accounts_total) if accounts_total is not None else None,
        "last_batch": last_batch,
    }
    if note:
        state["note"] = note
    return state


def save_threads_slow_state(
    report: dict[str, Any],
    state_path: str | Path = DEFAULT_THREADS_SLOW_STATE_PATH,
    batch_size: int | None = None,
    accounts_total: int | None = None,
    note: str | None = None,
) -> Path:
    state = build_threads_slow_state(report, batch_size=batch_size, accounts_total=accounts_total, note=note)
    path = Path(state_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def save_threads_view_scan_artifacts(report: dict[str, Any], output_dir: str | Path = DEFAULT_OUTPUT_DIR, date_label: str | None = None) -> dict[str, Path]:
    target_dir = Path(output_dir)
    references_dir = target_dir.parent / "docs" / "references" if target_dir.name == "data" else target_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    references_dir.mkdir(parents=True, exist_ok=True)
    label = date_label or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    json_path = target_dir / f"threads_view_scan_{label}.json"
    markdown_path = references_dir / f"threads-view-scan-{label}.md"

    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# Threads View Scan", "", report.get("summary", "Threads view scan"), "", "## 핵심 포인트"]
    for line in report.get("focus_lines", []):
        lines.append(f"- {line}")
    lines.extend(["", "## 다음 액션"])
    for line in report.get("next_actions", []):
        lines.append(f"- {line}")
    lines.extend(["", "## Claims"])
    for claim in report.get("claims", [])[:30]:
        symbols = ",".join(claim.get("symbols") or ["no_symbol"])
        lines.append(f"- @{claim.get('author_handle')} / {symbols} / {claim.get('direction')} / {claim.get('claim_text')}")
    markdown_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return {"json": json_path, "markdown": markdown_path}
