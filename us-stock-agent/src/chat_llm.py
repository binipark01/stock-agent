from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any


DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_BASE_URL = "https://api.openai.com/v1"
MAX_HISTORY_MESSAGES = 12

CHAT_HINTS = (
    "야",
    "안녕",
    "ㅎㅇ",
    "하이",
    "hello",
    "hi",
    "고마워",
    "뭐해",
    "누구",
    "너 뭐",
    "너는 뭐",
    "뭘 할 수",
    "도와줘",
    "llm",
    "gpt",
    "챗",
    "대화",
)

STOCK_HINTS = (
    "주식",
    "미국장",
    "시장",
    "종목",
    "체크포인트",
    "브리핑",
    "장전",
    "장후",
    "프리장",
    "마감",
    "나스닥",
    "다우",
    "s&p",
    "etf",
    "섹터",
    "옵션",
    "공시",
    "실적",
    "어닝",
    "차트",
    "기술적",
    "rsi",
    "macd",
    "가격",
    "주가",
    "매수",
    "매도",
    "보유",
    "포트폴리오",
    "뭐 봐",
    "봐야",
    "비교",
    "vs",
)

NON_TICKER_UPPERCASE = {
    "AI",
    "API",
    "GPT",
    "JSON",
    "LLM",
    "UI",
    "URL",
}


def _has_ticker_like_token(text: str) -> bool:
    tokens = re.findall(r"\b[A-Z][A-Z0-9.-]{1,5}\b", text)
    return any(token not in NON_TICKER_UPPERCASE for token in tokens)


def should_use_llm_chat(request_text: str, explicit_mode: str | None = None) -> bool:
    if explicit_mode and explicit_mode != "auto":
        return False
    text = str(request_text or "").strip()
    if not text:
        return True
    lowered = text.lower()
    if _has_ticker_like_token(text):
        return False
    if any(hint in lowered for hint in STOCK_HINTS):
        return False
    if any(hint in lowered for hint in CHAT_HINTS):
        return True
    return len(text) <= 24


def _configured() -> tuple[str | None, str, str]:
    api_key = os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("OPENAI_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    model = os.environ.get("OPENAI_MODEL", DEFAULT_MODEL)
    return api_key, base_url, model


def _chat_response(content: str, *, configured: bool, model: str | None = None) -> dict[str, Any]:
    return {
        "agent": "llm",
        "mode": "chat",
        "summary": content,
        "message": content,
        "symbols": [],
        "focus": [],
        "next_actions": [],
        "features": ["llm_chat"] + ([] if configured else ["llm_unconfigured"]),
        "model": model,
    }


def _normalize_history(history: Any) -> list[dict[str, str]]:
    if not isinstance(history, list):
        return []
    messages: list[dict[str, str]] = []
    for item in history[-MAX_HISTORY_MESSAGES:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip()
        content = str(item.get("content") or "").strip()
        if role not in {"user", "assistant"} or not content:
            continue
        messages.append({"role": role, "content": content})
    return messages


def _build_messages(request_text: str, history: Any) -> list[dict[str, str]]:
    messages = [
        {
            "role": "system",
            "content": (
                "너는 US Stock Agent 안에 들어있는 대화형 LLM이다. "
                "일반 대화에는 짧고 자연스럽게 한국어로 답한다. "
                "주식 분석이 필요한 질문이면 실시간 데이터는 별도 stock agent가 처리한다고 안내한다."
            ),
        }
    ]
    normalized_history = _normalize_history(history)
    messages.extend(normalized_history)
    if not normalized_history or normalized_history[-1] != {"role": "user", "content": request_text}:
        messages.append({"role": "user", "content": request_text})
    return messages


def build_llm_chat_response(request_text: str, history: Any = None, timeout: int = 30) -> dict[str, Any]:
    api_key, base_url, model = _configured()
    if not api_key:
        return _chat_response(
            "지금은 LLM API key가 설정되어 있지 않아서 실제 LLM 답변을 만들 수 없습니다. "
            "OPENAI_API_KEY를 설정하면 이런 일반 대화는 주식 watchlist로 빠지지 않고 LLM이 바로 답합니다.",
            configured=False,
            model=model,
        )

    payload = {
        "model": model,
        "messages": _build_messages(request_text, history),
        "temperature": 0.7,
    }
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"LLM API error {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"LLM API connection failed: {exc.reason}") from exc

    content = (
        data.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
        .strip()
    )
    if not content:
        raise RuntimeError("LLM API returned an empty response")
    return _chat_response(content, configured=True, model=model)
