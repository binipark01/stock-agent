from __future__ import annotations

import json
import re
from typing import Any


class AgentJsonError(ValueError):
    """Raised when an agent response cannot be recovered as a JSON object."""


def _json_loads_object(text: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    if isinstance(payload, dict):
        return payload
    return None


def _balanced_json_candidates(text: str) -> list[str]:
    starts = [idx for idx, char in enumerate(text) if char == "{"]
    candidates: list[str] = []
    for start in starts:
        depth = 0
        in_string = False
        escaped = False
        for idx in range(start, len(text)):
            char = text[idx]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    candidates.append(text[start : idx + 1])
                    break
    return candidates


def parse_agent_json(text: str, *, expected_agent: str | None = None) -> dict[str, Any]:
    """Parse direct, fenced, or prose-wrapped JSON from an LLM response."""

    raw = str(text or "").strip()
    if not raw:
        raise AgentJsonError("empty agent response")

    direct = _json_loads_object(raw)
    if direct is not None:
        return _validate_expected_agent(direct, expected_agent)

    fenced_blocks = re.findall(r"```(?:json)?\s*(.*?)```", raw, flags=re.IGNORECASE | re.DOTALL)
    for block in fenced_blocks:
        parsed = _json_loads_object(block.strip())
        if parsed is not None:
            return _validate_expected_agent(parsed, expected_agent)

    for candidate in _balanced_json_candidates(raw):
        parsed = _json_loads_object(candidate)
        if parsed is not None:
            return _validate_expected_agent(parsed, expected_agent)

    raise AgentJsonError("agent response did not contain a valid JSON object")


def _validate_expected_agent(payload: dict[str, Any], expected_agent: str | None) -> dict[str, Any]:
    if expected_agent is None:
        return payload
    actual = str(payload.get("agent") or "").strip()
    if actual and actual != expected_agent:
        raise AgentJsonError(f"unexpected agent '{actual}', expected '{expected_agent}'")
    return payload


def require_list(payload: dict[str, Any], key: str) -> list[Any]:
    value = payload.get(key)
    if isinstance(value, list):
        return value
    raise AgentJsonError(f"'{key}' must be a list")


def require_dict(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if isinstance(value, dict):
        return value
    raise AgentJsonError(f"'{key}' must be an object")
