from __future__ import annotations

import json
from datetime import datetime

from krx_alert_review_packet_common import main


def should_wake_afterhours(now: datetime | None = None) -> bool:
    """장후 알림은 평일 16:00~20:00까지만 실제 발송한다."""
    current = now or datetime.now()
    if current.weekday() >= 5:
        return False
    if 16 <= current.hour <= 19:
        return True
    return current.hour == 20 and current.minute == 0

if __name__ == '__main__':
    if not should_wake_afterhours():
        print(json.dumps({'wakeAgent': False, 'reason': 'outside KRX afterhours alert window'}, ensure_ascii=False), flush=True)
        raise SystemExit(0)
    raise SystemExit(main('afterhours', 'krx_afterhours_alert_text.py'))
