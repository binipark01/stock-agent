from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from typing import Any

DEFAULT_SUBREDDITS = ("stocks", "wallstreetbets", "investing", "SecurityAnalysis", "ValueInvesting")


def _clean_query(request_text: str, symbols: list[str] | None = None) -> str:
    if symbols:
        return symbols[0]
    query = request_text
    for token in ["레딧", "reddit", "Reddit", "에서", "반응", "찾아줘", "검색", "알려줘", "여론"]:
        query = query.replace(token, " ")
    query = re.sub(r"\s+", " ", query).strip()
    return query or request_text.strip() or "NVDA"


def parse_reddit_listing(listing: dict[str, Any], query: str) -> list[dict[str, Any]]:
    children = (((listing or {}).get("data") or {}).get("children") or [])
    posts: list[dict[str, Any]] = []
    for child in children:
        data = (child or {}).get("data") or {}
        title = str(data.get("title") or "").strip()
        if not title:
            continue
        subreddit = str(data.get("subreddit") or "unknown").strip()
        score = int(data.get("score") or 0)
        comments = int(data.get("num_comments") or 0)
        permalink = str(data.get("permalink") or "").strip()
        url = str(data.get("url") or "").strip()
        if permalink:
            url = "https://www.reddit.com" + permalink
        text = str(data.get("selftext") or "").strip()
        text_preview = re.sub(r"\s+", " ", text)[:220]
        posts.append(
            {
                "source": "reddit_public_search",
                "query": query,
                "subreddit": subreddit,
                "title": title,
                "text": text_preview,
                "score": score,
                "comments": comments,
                "created_utc": data.get("created_utc"),
                "url": url,
                "engagement_score": score + (comments * 2),
            }
        )
    return sorted(posts, key=lambda row: row["engagement_score"], reverse=True)


def search_reddit_public(query: str, subreddits: tuple[str, ...] = DEFAULT_SUBREDDITS, limit: int = 5) -> list[dict[str, Any]]:
    encoded = urllib.parse.quote(query)
    joined_subreddits = "+".join(subreddits)
    url = f"https://www.reddit.com/r/{joined_subreddits}/search.json?q={encoded}&restrict_sr=1&sort=new&t=week&limit={max(limit, 10)}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "stock-research-agent/0.1 public research assistant",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return parse_reddit_listing(payload, query=query)[:limit]


def build_reddit_search_payload(request_text: str, symbols: list[str], limit: int = 5) -> tuple[str, list[str], list[str]]:
    query = _clean_query(request_text, symbols)
    try:
        posts = search_reddit_public(query, limit=limit)
    except Exception as exc:
        summary = f"Reddit 공개 검색을 시도했지만 접근이 실패했습니다: {query}"
        focus = [f"Reddit 검색 실패: {type(exc).__name__} / public endpoint 제한 가능"]
        next_actions = [
            "Reddit은 공식 API/로그인/레이트리밋 제한이 있을 수 있으니 뉴스·공시와 먼저 교차검증",
            "필요하면 관심 subreddit 또는 수동 URL을 좁혀 재시도",
            "소셜 반응은 매매 신호가 아니라 분위기/논점 확인용으로만 사용",
        ]
        return summary, focus, next_actions

    focus = [f"Reddit 공개 검색: 최근 1주 / query={query} / subreddits={', '.join(DEFAULT_SUBREDDITS)}"]
    if not posts:
        summary = f"Reddit 공개 검색에서 {query} 관련 최근 게시물을 찾지 못했습니다."
        focus.append("Reddit 최근 게시물 없음 또는 public search 제한")
    else:
        summary = f"Reddit 공개 검색 기준 주요 반응을 정리했습니다: {query}"
        for post in posts[:limit]:
            snippet = f" / {post['text']}" if post.get("text") else ""
            focus.append(f"Reddit r/{post['subreddit']} / score {post['score']} / comments {post['comments']} / {post['title']}{snippet}")
    next_actions = [
        "Reddit 반응은 retail sentiment/논점 확인용이며 뉴스·공시·가격 반응으로 교차검증",
        "r/wallstreetbets류 고노이즈 게시물은 과대해석 금지",
        "반복 언급되는 리스크/촉매만 브리핑 또는 포트폴리오 guard에 반영",
    ]
    return summary, focus, next_actions
