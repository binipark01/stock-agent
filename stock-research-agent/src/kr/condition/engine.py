"""Rule-based KRX condition-search engine.

Read-only screening helpers for Korean stock condition searches.  The engine is
pure and testable: callers provide already-collected stock snapshots.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any
import json

CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "krx_conditions.json"


def _load_default_condition_sets() -> dict[str, dict[str, Any]]:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


DEFAULT_CONDITION_SETS: dict[str, dict[str, Any]] = _load_default_condition_sets()


def _to_number(value: Any) -> float | int | None:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        cleaned = value.strip().replace(",", "").replace("%", "")
        if cleaned in {"", "n/a", "None"}:
            return None
        neg = cleaned.startswith("--") or cleaned.startswith("-")
        cleaned = cleaned.lstrip("+-")
        try:
            num = float(cleaned) if "." in cleaned else int(cleaned)
            return -num if neg else num
        except ValueError:
            return value
    return value


def _compare(left: Any, op: str, right: Any) -> bool:
    left = _to_number(left)
    right = _to_number(right)
    if op == "exists":
        return left is not None
    if left is None:
        return False
    if op == "==":
        return left == right
    if op == "!=":
        return left != right
    try:
        if op == ">":
            return left > right
        if op == ">=":
            return left >= right
        if op == "<":
            return left < right
        if op == "<=":
            return left <= right
        if op == "in":
            return left in right
    except TypeError:
        return False
    raise ValueError(f"unsupported operator: {op}")


def _eval_rule(rule: dict[str, Any], stock: dict[str, Any]) -> tuple[bool, list[str], list[str]]:
    if "any" in rule:
        passed_labels: list[str] = []
        failed_labels: list[str] = []
        any_passed = False
        for child in rule["any"]:
            passed, matched, failed = _eval_rule(child, stock)
            if passed:
                any_passed = True
                passed_labels.extend(matched)
            else:
                failed_labels.extend(failed)
        return any_passed, passed_labels, [] if any_passed else failed_labels
    if "all" in rule:
        matched: list[str] = []
        failed: list[str] = []
        all_passed = True
        for child in rule["all"]:
            passed, child_matched, child_failed = _eval_rule(child, stock)
            all_passed = all_passed and passed
            matched.extend(child_matched)
            failed.extend(child_failed)
        return all_passed, matched if all_passed else [], failed
    label = str(rule.get("label") or rule.get("field") or "condition")
    passed = _compare(stock.get(rule.get("field")), str(rule.get("op", "==")), rule.get("value"))
    return passed, [label] if passed else [], [] if passed else [label]


def _label_for_score(condition_set: dict[str, Any], score: int, excluded: bool) -> str:
    if excluded and condition_set.get("name") == "위험 제외":
        return "위험제외"
    if excluded:
        return "제외"
    for item in sorted(condition_set.get("labels", []), key=lambda x: x.get("min_score", 0), reverse=True):
        if score >= int(item.get("min_score", 0)):
            return str(item.get("label", "관찰"))
    return "관찰"


def evaluate_condition_set(condition_set: dict[str, Any], stock: dict[str, Any]) -> dict[str, Any]:
    matched: list[str] = []
    failed: list[str] = []
    for rule in condition_set.get("filters", []):
        passed, rule_matched, rule_failed = _eval_rule(rule, stock)
        matched.extend(rule_matched)
        failed.extend(rule_failed)
    filters_passed = not failed

    excluded_by: list[str] = []
    for rule in condition_set.get("exclude", []):
        passed, rule_matched, _ = _eval_rule(rule, stock)
        if passed:
            excluded_by.extend(rule_matched)

    score = 0
    score_reasons: list[str] = []
    for rule in condition_set.get("score", []):
        passed, rule_matched, _ = _eval_rule(rule, stock)
        if passed:
            points = int(rule.get("points", 0))
            score += points
            for label in rule_matched:
                score_reasons.append(f"{label} +{points}")

    excluded = bool(excluded_by)
    label = _label_for_score(condition_set, score, excluded)
    passed = filters_passed and not excluded
    return {
        "condition": condition_set.get("name", "검색식"),
        "passed": passed,
        "excluded": excluded,
        "label": label,
        "score": score,
        "matched": matched,
        "failed": failed,
        "excluded_by": excluded_by,
        "score_reasons": score_reasons,
        "stock": deepcopy(stock),
    }


def run_krx_condition_scan(
    stocks: list[dict[str, Any]],
    condition_names: list[str] | None = None,
    collected_at: str | None = None,
    condition_sets: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    condition_sets = condition_sets or DEFAULT_CONDITION_SETS
    selected = condition_names or list(condition_sets.keys())
    sections: list[dict[str, Any]] = []
    for condition_id in selected:
        condition = condition_sets[condition_id]
        rows = []
        for stock in stocks:
            result = evaluate_condition_set(condition, stock)
            # For normal screens, show passed candidates. For risk screen, show excluded/risky rows too.
            if result["passed"] or result["excluded"] or result["score"] > 0:
                rows.append(result)
        rows.sort(key=lambda item: (not item["passed"], -int(item["score"]), item["stock"].get("trade_value_rank") or 999999))
        sections.append({
            "id": condition_id,
            "name": condition.get("name", condition_id),
            "description": condition.get("description", ""),
            "results": rows[:10],
        })
    return {
        "mode": "krx_condition_scan",
        "summary": f"국장 검색식 {len(selected)}개 / 후보 {len(stocks)}개 평가",
        "stock_count": len(stocks),
        "condition_count": len(selected),
        "collected_at": collected_at,
        "conditions": sections,
        "caveats": ["검색식은 리서치/감시 보조용이며 주문/자동매매를 수행하지 않음"],
    }


def _stock_title(stock: dict[str, Any]) -> str:
    code = stock.get("code") or stock.get("symbol") or ""
    name = stock.get("name") or code or "종목"
    return f"{name}({code})" if code else str(name)


def format_krx_condition_scan_report(report: dict[str, Any], max_rows_per_condition: int = 3) -> list[str]:
    lines = [f"[국장 검색식] {report.get('condition_count', 0)}개 / 후보 {report.get('stock_count', 0)}개"]
    if report.get("collected_at"):
        lines.append(f"기준시각={report['collected_at']}")
    for section in report.get("conditions", []):
        lines.append(f"[{section.get('name')}] {section.get('description', '')}".rstrip())
        rows = section.get("results", [])[:max_rows_per_condition]
        if not rows:
            lines.append("- 후보 없음")
            continue
        for idx, row in enumerate(rows, 1):
            stock = row.get("stock", {})
            reasons = row.get("excluded_by") or row.get("matched") or row.get("score_reasons") or []
            reason_text = ",".join(map(str, reasons[:4])) if reasons else "근거부족"
            lines.append(f"{idx}. {_stock_title(stock)} 라벨={row.get('label')} 점수={row.get('score')} 근거={reason_text}")
    for caveat in report.get("caveats", []):
        lines.append(f"[주의] {caveat}")
    return lines


def build_krx_condition_scan_response(report: dict[str, Any]) -> dict[str, Any]:
    focus = format_krx_condition_scan_report(report)
    return {
        "mode": "krx_condition_scan",
        "summary": report.get("summary") or "국장 검색식 평가",
        "focus": focus,
        "features": ["krx_condition_scan", "rule_based_screens", "read_only_monitoring"],
        "next_actions": [
            "검색식 후보는 krx_session_flow_watch로 NXT/시간외 이탈 여부를 이어서 감시",
            "실전 후보는 개별종목 수급/프로그램/뉴스 기준일을 재확인",
        ],
        "raw": report,
    }
