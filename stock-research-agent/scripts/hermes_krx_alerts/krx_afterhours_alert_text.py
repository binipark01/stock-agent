#!/usr/bin/env python3
from __future__ import annotations
import importlib.util
import os
from datetime import datetime
from pathlib import Path

REGULAR = Path(__file__).with_name('krx_regular_alert_text.py')
CACHE = Path(__file__).with_name('krx_afterhours_alert_text.last.txt')

def _load_regular():
    spec = importlib.util.spec_from_file_location('krx_regular_alert_text', REGULAR)
    if spec is None or spec.loader is None:
        raise RuntimeError('cannot load krx_regular_alert_text')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def build_afterhours_text() -> str:
    mod = _load_regular()
    previous_market = os.environ.get('KRX_QUOTE_MARKET')
    previous_suffix = os.environ.get('KRX_QUOTE_SUFFIX')
    os.environ['KRX_QUOTE_MARKET'] = 'SOR'
    os.environ.pop('KRX_QUOTE_SUFFIX', None)
    try:
        text = mod.build_regular_text()
    finally:
        if previous_market is None:
            os.environ.pop('KRX_QUOTE_MARKET', None)
        else:
            os.environ['KRX_QUOTE_MARKET'] = previous_market
        if previous_suffix is None:
            os.environ.pop('KRX_QUOTE_SUFFIX', None)
        else:
            os.environ['KRX_QUOTE_SUFFIX'] = previous_suffix
    lines = text.splitlines()
    if lines:
        lines[0] = lines[0].replace('국장 ', '장후/SOR ', 1).replace('장후/NXT ', '장후/SOR ', 1).replace('장후 ', '장후/SOR ', 1)
    return chr(10).join(lines).strip()

def main() -> int:
    try:
        text = build_afterhours_text()
        CACHE.write_text(text, encoding="utf-8")
        print(text, flush=True)
    except Exception as exc:
        now = datetime.now().strftime("%H:%M")
        print(
            chr(10).join([
                f"장후 {now}",
                "",
                f"데이터 갱신 실패: {type(exc).__name__}",
                "- 이전 캐시 재전송 안 함",
            ]),
            flush=True,
        )
        return 0
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
