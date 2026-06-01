from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import tomllib
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TIMEOUT_SECONDS = 120
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_LMSTUDIO_BASE_URL = "http://127.0.0.1:1234/v1"
DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434/v1"
OMX_DEFAULT_FRONTIER_MODEL_ENV = "OMX_DEFAULT_FRONTIER_MODEL"
OMX_DEFAULT_STANDARD_MODEL_ENV = "OMX_DEFAULT_STANDARD_MODEL"
OMX_DEFAULT_SPARK_MODEL_ENV = "OMX_DEFAULT_SPARK_MODEL"
OMX_SPARK_MODEL_ENV = "OMX_SPARK_MODEL"
DEFAULT_FRONTIER_MODEL = "gpt-5.5"
DEFAULT_STANDARD_MODEL = "gpt-5.4-mini"
DEFAULT_SPARK_MODEL = "gpt-5.3-codex-spark"
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


@dataclass(frozen=True)
class LLMSettings:
    provider: str = "codex"
    model: str = ""
    timeout: int = DEFAULT_TIMEOUT_SECONDS
    api_key: str = ""
    base_url: str = ""
    api_mode: str = "codex"
    codex_bin: str = ""
    model_provider: str = ""
    model_source: str = ""
    reasoning_effort: str = ""
    temperature: float | None = None
    max_tokens: int | None = None


@dataclass(frozen=True)
class LLMResult:
    ok: bool
    text: str = ""
    provider: str = "codex"
    error: str = ""
    command: str = ""
    model: str = ""


def _env(env: Mapping[str, str] | None = None) -> dict[str, str]:
    data = dict(os.environ)
    if env:
        data.update({str(k): str(v) for k, v in env.items()})
    return data


def _flag(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def llm_disabled(env: Mapping[str, str] | None = None) -> bool:
    env_map = _env(env)
    return _flag(env_map.get("DISCORD_AGENT_LLM_DISABLE", "0")) or _flag(env_map.get("US_STOCK_AGENT_LLM_DISABLE", "0"))


def normalize_provider(value: str | None) -> str:
    key = str(value or "codex").strip().lower().replace("_", "-")
    aliases = {
        "": "codex",
        "codex-cli": "codex",
        "omx": "codex",
        "omx-codex": "codex",
        "openai-api": "openai",
        "open-router": "openrouter",
        "openrouter-api": "openrouter",
        "api": "openai-compatible",
        "compatible": "openai-compatible",
        "generic": "openai-compatible",
        "generic-openai": "openai-compatible",
        "openai-compatible-api": "openai-compatible",
        "local": "openai-compatible",
        "local-openai": "openai-compatible",
        "lm-studio": "lmstudio",
        "lm_studio": "lmstudio",
    }
    return aliases.get(key, key)


def resolve_timeout(env: Mapping[str, str] | None = None) -> int:
    env_map = _env(env)
    for key in ("US_STOCK_AGENT_LLM_TIMEOUT", "DISCORD_AGENT_LLM_TIMEOUT"):
        try:
            value = str(env_map.get(key, "")).strip()
            if value:
                return max(15, min(300, int(value)))
        except Exception:
            return DEFAULT_TIMEOUT_SECONDS
    return DEFAULT_TIMEOUT_SECONDS


def resolve_codex_executable(env: Mapping[str, str] | None = None) -> str | None:
    env_map = _env(env)
    configured = str(env_map.get("US_STOCK_AGENT_CODEX_BIN") or env_map.get("DISCORD_AGENT_CODEX_BIN") or "").strip()
    if configured:
        return configured
    return shutil.which("codex")


def _first_env(env_map: Mapping[str, str], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = str(env_map.get(key, "")).strip()
        if value:
            return value
    return ""


def _normalize_configured_value(value: Any) -> str:
    return value.strip() if isinstance(value, str) and value.strip() else ""


def _codex_home(env_map: Mapping[str, str]) -> Path:
    configured = _normalize_configured_value(env_map.get("CODEX_HOME"))
    return Path(configured).expanduser() if configured else Path.home() / ".codex"


def _read_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _read_toml_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _read_omx_config(env_map: Mapping[str, str]) -> dict[str, Any]:
    return _read_json_file(_codex_home(env_map) / ".omx-config.json")


def _read_codex_config(env_map: Mapping[str, str]) -> dict[str, Any]:
    return _read_toml_file(_codex_home(env_map) / "config.toml")


def _omx_config_env_value(env_map: Mapping[str, str], key: str) -> str:
    config = _read_omx_config(env_map)
    env_block = config.get("env")
    if not isinstance(env_block, dict):
        return ""
    return _normalize_configured_value(env_block.get(key))


def _omx_models_block(env_map: Mapping[str, str]) -> dict[str, Any]:
    config = _read_omx_config(env_map)
    models = config.get("models")
    return models if isinstance(models, dict) else {}


def _codex_config_root_value(env_map: Mapping[str, str], key: str) -> str:
    return _normalize_configured_value(_read_codex_config(env_map).get(key))


def _team_low_complexity_model(env_map: Mapping[str, str]) -> str:
    models = _omx_models_block(env_map)
    for key in ("team_low_complexity", "team-low-complexity", "teamLowComplexity"):
        value = _normalize_configured_value(models.get(key))
        if value:
            return value
    return ""


def _resolve_omx_main_model(env_map: Mapping[str, str]) -> tuple[str, str]:
    value = _normalize_configured_value(env_map.get(OMX_DEFAULT_FRONTIER_MODEL_ENV))
    if value:
        return value, OMX_DEFAULT_FRONTIER_MODEL_ENV
    value = _omx_config_env_value(env_map, OMX_DEFAULT_FRONTIER_MODEL_ENV)
    if value:
        return value, f".omx-config.json env.{OMX_DEFAULT_FRONTIER_MODEL_ENV}"
    value = _codex_config_root_value(env_map, "model")
    if value:
        return value, "config.toml model"
    return DEFAULT_FRONTIER_MODEL, "OMX default frontier"


def _resolve_omx_standard_model(env_map: Mapping[str, str]) -> tuple[str, str]:
    value = _normalize_configured_value(env_map.get(OMX_DEFAULT_STANDARD_MODEL_ENV))
    if value:
        return value, OMX_DEFAULT_STANDARD_MODEL_ENV
    value = _omx_config_env_value(env_map, OMX_DEFAULT_STANDARD_MODEL_ENV)
    if value:
        return value, f".omx-config.json env.{OMX_DEFAULT_STANDARD_MODEL_ENV}"
    return _resolve_omx_main_model(env_map)


def _resolve_omx_spark_model(env_map: Mapping[str, str]) -> tuple[str, str]:
    for key in (OMX_DEFAULT_SPARK_MODEL_ENV, OMX_SPARK_MODEL_ENV):
        value = _normalize_configured_value(env_map.get(key))
        if value:
            return value, key
    for key in (OMX_DEFAULT_SPARK_MODEL_ENV, OMX_SPARK_MODEL_ENV):
        value = _omx_config_env_value(env_map, key)
        if value:
            return value, f".omx-config.json env.{key}"
    value = _team_low_complexity_model(env_map)
    if value:
        return value, ".omx-config.json models.team_low_complexity"
    return DEFAULT_SPARK_MODEL, "OMX default spark"


def resolve_omx_model(env: Mapping[str, str] | None = None, model_class: str | None = None) -> tuple[str, str]:
    env_map = _env(env)
    lane = str(model_class or env_map.get("US_STOCK_AGENT_LLM_MODEL_CLASS") or env_map.get("DISCORD_AGENT_LLM_MODEL_CLASS") or "frontier").strip().lower()
    if lane in {"spark", "fast", "low", "low-complexity"}:
        return _resolve_omx_spark_model(env_map)
    if lane in {"standard", "std"}:
        return _resolve_omx_standard_model(env_map)
    return _resolve_omx_main_model(env_map)


def resolve_omx_model_provider(env: Mapping[str, str] | None = None) -> str:
    env_map = _env(env)
    return _first_env(
        env_map,
        (
            "US_STOCK_AGENT_CODEX_MODEL_PROVIDER",
            "US_STOCK_AGENT_LLM_MODEL_PROVIDER",
            "DISCORD_AGENT_CODEX_MODEL_PROVIDER",
            "DISCORD_AGENT_LLM_MODEL_PROVIDER",
        ),
    ) or _codex_config_root_value(env_map, "model_provider")


def resolve_omx_reasoning_effort(env: Mapping[str, str] | None = None) -> str:
    env_map = _env(env)
    configured = _first_env(
        env_map,
        (
            "US_STOCK_AGENT_LLM_REASONING_EFFORT",
            "US_STOCK_AGENT_CODEX_REASONING_EFFORT",
            "DISCORD_AGENT_LLM_REASONING_EFFORT",
            "DISCORD_AGENT_CODEX_REASONING_EFFORT",
        ),
    )
    value = configured or _codex_config_root_value(env_map, "model_reasoning_effort")
    normalized = value.strip().lower()
    return normalized if normalized in {"low", "medium", "high", "xhigh"} else ""


def _model_for_provider(env_map: Mapping[str, str], provider: str) -> str:
    provider_keys: dict[str, tuple[str, ...]] = {
        "openai": ("US_STOCK_AGENT_OPENAI_MODEL", "DISCORD_AGENT_OPENAI_MODEL", "OPENAI_MODEL"),
        "openrouter": ("US_STOCK_AGENT_OPENROUTER_MODEL", "DISCORD_AGENT_OPENROUTER_MODEL", "OPENROUTER_MODEL"),
        "ollama": ("US_STOCK_AGENT_OLLAMA_MODEL", "DISCORD_AGENT_OLLAMA_MODEL", "OLLAMA_MODEL"),
        "lmstudio": ("US_STOCK_AGENT_LMSTUDIO_MODEL", "DISCORD_AGENT_LMSTUDIO_MODEL", "LMSTUDIO_MODEL"),
        "openai-compatible": ("US_STOCK_AGENT_COMPATIBLE_MODEL", "DISCORD_AGENT_COMPATIBLE_MODEL"),
    }
    return _first_env(env_map, provider_keys.get(provider, ()) + ("US_STOCK_AGENT_LLM_MODEL", "DISCORD_AGENT_LLM_MODEL"))


def _api_key_for_provider(env_map: Mapping[str, str], provider: str) -> str:
    provider_keys: dict[str, tuple[str, ...]] = {
        "openai": ("US_STOCK_AGENT_OPENAI_API_KEY", "DISCORD_AGENT_OPENAI_API_KEY", "OPENAI_API_KEY"),
        "openrouter": ("US_STOCK_AGENT_OPENROUTER_API_KEY", "DISCORD_AGENT_OPENROUTER_API_KEY", "OPENROUTER_API_KEY"),
        "ollama": ("US_STOCK_AGENT_OLLAMA_API_KEY", "DISCORD_AGENT_OLLAMA_API_KEY", "OLLAMA_API_KEY"),
        "lmstudio": ("US_STOCK_AGENT_LMSTUDIO_API_KEY", "DISCORD_AGENT_LMSTUDIO_API_KEY", "LMSTUDIO_API_KEY"),
        "openai-compatible": ("US_STOCK_AGENT_COMPATIBLE_API_KEY", "DISCORD_AGENT_COMPATIBLE_API_KEY"),
    }
    return _first_env(env_map, provider_keys.get(provider, ()) + ("US_STOCK_AGENT_LLM_API_KEY", "DISCORD_AGENT_LLM_API_KEY"))


def _base_url_for_provider(env_map: Mapping[str, str], provider: str) -> str:
    provider_keys: dict[str, tuple[str, ...]] = {
        "openai": ("US_STOCK_AGENT_OPENAI_BASE_URL", "DISCORD_AGENT_OPENAI_BASE_URL", "OPENAI_BASE_URL"),
        "openrouter": ("US_STOCK_AGENT_OPENROUTER_BASE_URL", "DISCORD_AGENT_OPENROUTER_BASE_URL", "OPENROUTER_BASE_URL"),
        "ollama": ("US_STOCK_AGENT_OLLAMA_BASE_URL", "DISCORD_AGENT_OLLAMA_BASE_URL", "OLLAMA_BASE_URL"),
        "lmstudio": ("US_STOCK_AGENT_LMSTUDIO_BASE_URL", "DISCORD_AGENT_LMSTUDIO_BASE_URL", "LMSTUDIO_BASE_URL"),
        "openai-compatible": ("US_STOCK_AGENT_COMPATIBLE_BASE_URL", "DISCORD_AGENT_COMPATIBLE_BASE_URL"),
    }
    return _first_env(env_map, provider_keys.get(provider, ()) + ("US_STOCK_AGENT_LLM_BASE_URL", "DISCORD_AGENT_LLM_BASE_URL")).rstrip("/")


def _resolve_float(env_map: Mapping[str, str], key: str) -> float | None:
    value = str(env_map.get(key, "")).strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _resolve_int(env_map: Mapping[str, str], key: str) -> int | None:
    value = str(env_map.get(key, "")).strip()
    if not value:
        return None
    try:
        return max(1, int(value))
    except ValueError:
        return None


def resolve_settings(env: Mapping[str, str] | None = None) -> LLMSettings:
    env_map = _env(env)
    provider = normalize_provider(env_map.get("US_STOCK_AGENT_LLM_PROVIDER") or env_map.get("DISCORD_AGENT_LLM_PROVIDER") or "codex")
    timeout = resolve_timeout(env_map)
    model = _model_for_provider(env_map, provider)
    api_key = _api_key_for_provider(env_map, provider)
    base_url = _base_url_for_provider(env_map, provider)
    api_mode = str(env_map.get("US_STOCK_AGENT_LLM_API_MODE") or env_map.get("DISCORD_AGENT_LLM_API_MODE") or "").strip().lower()
    codex_bin = str(env_map.get("US_STOCK_AGENT_CODEX_BIN") or env_map.get("DISCORD_AGENT_CODEX_BIN") or "").strip()
    model_provider = ""
    model_source = "explicit env" if model else ""
    reasoning_effort = ""
    temperature = _resolve_float(env_map, "US_STOCK_AGENT_LLM_TEMPERATURE") or _resolve_float(env_map, "DISCORD_AGENT_LLM_TEMPERATURE")
    max_tokens = _resolve_int(env_map, "US_STOCK_AGENT_LLM_MAX_TOKENS") or _resolve_int(env_map, "DISCORD_AGENT_LLM_MAX_TOKENS")

    if provider == "openai":
        base_url = base_url or DEFAULT_OPENAI_BASE_URL
        api_mode = api_mode or "responses"
    elif provider == "openrouter":
        base_url = base_url or DEFAULT_OPENROUTER_BASE_URL
        api_mode = "chat"
    elif provider == "ollama":
        base_url = base_url or DEFAULT_OLLAMA_BASE_URL
        api_mode = "chat"
    elif provider == "lmstudio":
        base_url = base_url or DEFAULT_LMSTUDIO_BASE_URL
        api_mode = "chat"
    elif provider == "openai-compatible":
        base_url = base_url or DEFAULT_LMSTUDIO_BASE_URL
        api_mode = api_mode or "chat"
    else:
        provider = "codex"
        api_mode = "codex"
        if not model:
            model, model_source = resolve_omx_model(env_map)
        model_provider = resolve_omx_model_provider(env_map)
        reasoning_effort = resolve_omx_reasoning_effort(env_map)

    return LLMSettings(
        provider=provider,
        model=model,
        timeout=timeout,
        api_key=api_key,
        base_url=base_url,
        api_mode=api_mode,
        codex_bin=codex_bin,
        model_provider=model_provider,
        model_source=model_source,
        reasoning_effort=reasoning_effort,
        temperature=temperature,
        max_tokens=max_tokens,
    )


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


def _chat_response(content: str, *, settings: LLMSettings, result: LLMResult | None = None) -> dict[str, Any]:
    features = ["llm_chat", f"llm_provider:{settings.provider}"]
    if settings.provider == "codex":
        features.append("omx_codex")
    return {
        "agent": "llm",
        "mode": "chat",
        "summary": content,
        "message": content,
        "symbols": [],
        "focus": [],
        "next_actions": [],
        "features": features,
        "model": settings.model,
        "reasoning_effort": settings.reasoning_effort,
        "provider": settings.provider,
        "command": result.command if result else "",
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


def _build_chat_prompt(request_text: str, history: Any) -> str:
    normalized_history = _normalize_history(history)
    transcript = "\n".join(f"{item['role']}: {item['content']}" for item in normalized_history)
    if not normalized_history or normalized_history[-1] != {"role": "user", "content": request_text}:
        transcript = "\n".join(part for part in [transcript, f"user: {request_text}"] if part)
    return f"""너는 US Stock Agent UI 안에 들어있는 대화형 LLM이다.

규칙:
- 사용자의 입력을 반드시 읽고 답한다.
- 일반 대화에는 짧고 자연스럽게 한국어로 답한다.
- 주식/시장과 무관한 잡담이면 억지로 시장 분석하지 않는다.
- 주식 분석이 필요한 질문이면 실시간 데이터는 별도 stock agent 경로가 처리한다고 안내한다.
- 고정 템플릿을 쓰지 않는다.

대화:
{transcript}

assistant:"""


def call_codex_llm(prompt: str, *, env: Mapping[str, str] | None = None, cwd: str | Path = ROOT) -> LLMResult:
    env_map = _env(env)
    settings = resolve_settings(env_map)
    if llm_disabled(env_map):
        return LLMResult(ok=False, provider="codex", error="llm_disabled", model=settings.model)

    codex = resolve_codex_executable(env_map)
    if not codex:
        return LLMResult(ok=False, provider="codex", error="codex_not_found", model=settings.model)

    output_path = Path(tempfile.gettempdir()) / f"us_stock_agent_llm_{os.getpid()}_{next(tempfile._get_candidate_names())}.txt"
    cmd = [
        codex,
        "exec",
        "--skip-git-repo-check",
        "--sandbox",
        "read-only",
        "--ephemeral",
        "-C",
        str(cwd),
        "--output-last-message",
        str(output_path),
    ]
    if settings.model:
        cmd.extend(["--model", settings.model])
    if settings.model_provider:
        provider = settings.model_provider.replace("\\", "\\\\").replace('"', '\\"')
        cmd.extend(["-c", f'model_provider="{provider}"'])
    if settings.reasoning_effort:
        cmd.extend(["-c", f'model_reasoning_effort="{settings.reasoning_effort}"'])
    cmd.append("-")

    try:
        proc = subprocess.run(
            cmd,
            input=prompt,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=resolve_timeout(env_map),
            cwd=str(cwd),
            env=env_map,
        )
    except subprocess.TimeoutExpired:
        return LLMResult(ok=False, provider="codex", error="llm_timeout", command=" ".join(cmd[:4]), model=settings.model)
    except Exception as exc:
        return LLMResult(ok=False, provider="codex", error=f"{type(exc).__name__}: {exc}", command=" ".join(cmd[:4]), model=settings.model)

    text = ""
    if output_path.exists():
        try:
            text = output_path.read_text(encoding="utf-8", errors="replace").strip()
        finally:
            try:
                output_path.unlink()
            except Exception:
                pass
    if not text:
        text = (proc.stdout or "").strip()

    command = " ".join(cmd[:4])
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip().splitlines()
        detail = err[-1] if err else f"codex_exit_{proc.returncode}"
        return LLMResult(ok=False, provider="codex", text=text, error=detail, command=command, model=settings.model)
    if not text:
        return LLMResult(ok=False, provider="codex", error="empty_llm_response", command=command, model=settings.model)
    return LLMResult(ok=True, provider="codex", text=text, command=command, model=settings.model)


def _http_post_json(url: str, payload: dict[str, Any], settings: LLMSettings) -> tuple[int, dict[str, Any] | str]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if settings.api_key:
        headers["Authorization"] = f"Bearer {settings.api_key}"
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=settings.timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return resp.status, json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return exc.code, raw[:500]


def _extract_responses_text(data: dict[str, Any]) -> str:
    direct = data.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    parts: list[str] = []
    for item in data.get("output", []) or []:
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []) or []:
            if isinstance(content, dict):
                text = content.get("text") or content.get("content")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
    return "\n".join(parts).strip()


def _extract_chat_text(data: dict[str, Any]) -> str:
    choices = data.get("choices") or []
    if not choices or not isinstance(choices, list):
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message") or {}
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str):
            return content.strip()
    text = first.get("text")
    return text.strip() if isinstance(text, str) else ""


def call_api_llm(prompt: str, *, env: Mapping[str, str] | None = None, settings: LLMSettings | None = None) -> LLMResult:
    settings = settings or resolve_settings(env)
    if llm_disabled(env):
        return LLMResult(ok=False, provider=settings.provider, error="llm_disabled", model=settings.model)
    if settings.provider in {"openai", "openrouter"} and not settings.api_key:
        return LLMResult(ok=False, provider=settings.provider, error="missing_api_key", model=settings.model)
    if not settings.base_url:
        return LLMResult(ok=False, provider=settings.provider, error="missing_base_url", model=settings.model)
    if not settings.model:
        return LLMResult(ok=False, provider=settings.provider, error="missing_model", model=settings.model)

    if settings.api_mode == "responses":
        url = f"{settings.base_url}/responses"
        payload: dict[str, Any] = {"model": settings.model, "input": prompt}
        extractor: Callable[[dict[str, Any]], str] = _extract_responses_text
    else:
        url = f"{settings.base_url}/chat/completions"
        payload = {"model": settings.model, "messages": [{"role": "user", "content": prompt}]}
        extractor = _extract_chat_text
    if settings.temperature is not None:
        payload["temperature"] = settings.temperature
    if settings.max_tokens is not None:
        payload["max_output_tokens" if settings.api_mode == "responses" else "max_tokens"] = settings.max_tokens

    try:
        status, data = _http_post_json(url, payload, settings)
    except TimeoutError:
        return LLMResult(ok=False, provider=settings.provider, error="llm_timeout", model=settings.model)
    except Exception as exc:
        return LLMResult(ok=False, provider=settings.provider, error=f"{type(exc).__name__}: {exc}", model=settings.model)

    if status < 200 or status >= 300:
        detail = data.get("error") if isinstance(data, dict) else data
        return LLMResult(ok=False, provider=settings.provider, error=f"http_{status}: {str(detail)[:300]}", model=settings.model)
    if not isinstance(data, dict):
        return LLMResult(ok=False, provider=settings.provider, error="invalid_json_response", model=settings.model)
    text = extractor(data)
    if not text:
        return LLMResult(ok=False, provider=settings.provider, error="empty_llm_response", model=settings.model)
    return LLMResult(ok=True, provider=settings.provider, text=text, command=settings.api_mode, model=settings.model)


def call_llm(prompt: str, *, env: Mapping[str, str] | None = None, cwd: str | Path = ROOT) -> LLMResult:
    settings = resolve_settings(env)
    if settings.provider == "codex":
        return call_codex_llm(prompt, env=env, cwd=cwd)
    return call_api_llm(prompt, env=env, settings=settings)


def build_llm_chat_response(
    request_text: str,
    history: Any = None,
    env: Mapping[str, str] | None = None,
    llm_func: Callable[..., LLMResult] = call_llm,
) -> dict[str, Any]:
    settings = resolve_settings(env)
    prompt = _build_chat_prompt(request_text, history)
    result = llm_func(prompt, cwd=ROOT, env=env)
    if not result.ok:
        text = f"LLM 호출에 실패했습니다: {result.error}"
        return _chat_response(text, settings=settings, result=result)
    return _chat_response(result.text, settings=settings, result=result)
