"""US technical-analysis mode handlers."""
from __future__ import annotations

from typing import Any

try:
    from .technical.snapshot import build_technical_snapshot
except ImportError:  # direct script execution
    from us.technical.snapshot import build_technical_snapshot


def build_us_technical_response(
    mode: str,
    runtime_context: dict[str, Any],
    symbols: list[str],
) -> dict[str, Any] | None:
    if mode == "technical_snapshot":
        snapshots = [build_technical_snapshot(symbol) for symbol in symbols]
        focus = []
        for snap in snapshots:
            focus.append(f"{snap['symbol']} 추세: {snap['trend']} / 현재가 {snap['latest']:.2f} / 20일선 {snap['sma20']:.2f} / 50일선 {snap['sma50']:.2f} / 200일선 {snap['sma200']:.2f}")
            focus.append(f"{snap['symbol']} RSI: {snap['rsi14']:.2f} / 모멘텀: {snap['momentum']}")
            focus.append(
                f"{snap['symbol']} MACD: {snap['macd']:+.2f} / Signal: {snap['signal']:+.2f} / "
                f"Histogram: {snap['hist']:+.2f} / {snap.get('macd_direction', 'hist 방향 미확인')}"
            )
            focus.append(
                f"{snap['symbol']} Slow Stoch: %K {snap.get('stoch_k', 50.0):.2f} / "
                f"%D {snap.get('stoch_d', 50.0):.2f} / {snap.get('stoch_signal', '중립')}"
            )
            focus.append(
                f"{snap['symbol']} BB: 하단 {snap.get('bb_lower', 0.0):.2f} / 중단 {snap.get('bb_middle', 0.0):.2f} / "
                f"상단 {snap.get('bb_upper', 0.0):.2f} / %B {snap.get('bb_percent_b', 0.5):.2f} / 폭 {snap.get('bb_width_pct', 0.0):.2f}%"
            )
            focus.append(
                f"{snap['symbol']} ATR: {snap.get('atr14', 0.0):.2f} / ATR% {snap.get('atr_pct', 0.0):.2f}% / "
                f"거래량비 {snap['volume_ratio20']:.2f}x" if snap.get('volume_ratio20') is not None else
                f"{snap['symbol']} ATR: {snap.get('atr14', 0.0):.2f} / ATR% {snap.get('atr_pct', 0.0):.2f}% / 거래량비 데이터 없음"
            )
            focus.append(f"{snap['symbol']} 지지/저항: 지지 {snap['support']:.2f} / 저항 {snap['resistance']:.2f}")
            focus.append(f"{snap['symbol']} 손절 기준 가격: {snap['stop_price']:.2f}")
            focus.append(f"{snap['symbol']} 손절 거리: {snap['stop_distance_pct']:+.2f}%")
            focus.append(f"{snap['symbol']} 리스크: {snap.get('risk_note', '변동성/거래량 확인 필요')}")
            focus.append(f"{snap['symbol']} 해석: {snap['interpretation']}")
            focus.append(f"{snap['symbol']} action bias: {snap['action_bias']}")
            if snap['event_tags']:
                focus.append(f"{snap['symbol']} 이벤트 태그: {', '.join(snap['event_tags'])}")
        return {
            "agent": "stock-research-agent",
            "mode": mode,
            "summary": f"TradingView 느낌의 technical snapshot을 준비했습니다: {', '.join(symbols)}",
            "symbols": symbols,
            "focus": focus,
            "next_actions": [
                "TradingView 느낌으로 보면 20일선/50일선 위아래 위치를 먼저 확인",
                "RSI(25/75) → MACD hist 방향 → Slow Stoch 교차 순서로 모멘텀 확인",
                "BB %B가 0.9 이상이면 추격보다 눌림, 0.1 이하면 반등 확인",
                "ATR%가 높으면 손절폭과 포지션 크기를 먼저 줄이고 거래량 동반 여부 확인",
            ],
            "features": runtime_context.get("features", []),
        }



    return None
