from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_CANDIDATES = [
    Path('/mnt/d/Agents/kr-stock-agent'),
    Path('D:/Agents/kr-stock-agent'),
    Path('/mnt/d/Agents/stock-research-agent'),
    Path('D:/Agents/stock-research-agent'),
    Path('D:/Workspace/stock-research-agent'),
]
ROOT = next((p for p in ROOT_CANDIDATES if p.exists()), ROOT_CANDIDATES[0])
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

KIWOOM_ENV_CANDIDATES = [
    Path('D:/Agents/stock-research-agent/config/kiwoom.env'),
    Path('/mnt/d/Agents/stock-research-agent/config/kiwoom.env'),
    Path('D:/Workspace/stock-research-agent/config/kiwoom.env'),
    Path('/mnt/d/Workspace/stock-research-agent/config/kiwoom.env'),
]
for _kiwoom_env_path in KIWOOM_ENV_CANDIDATES:
    if _kiwoom_env_path.exists():
        os.environ.setdefault('KIWOOM_ENV_FILE', str(_kiwoom_env_path))
        break

PROHIBITED_TERMS = [
    '| 눌림대기',
    '| 관망',
    '| 추격금지',
    '대응:',
    '액션',
    '후보 n개',
    '확산 약함',
    '단독 후보',
    '내일 볼 것',
    '죽은 후보',
    '수급 caveat',
    '매매 관점',
    '한줄판단',
    'stale=true',
    'env=unknown',
    'collected_at=unavailable',
    'data_date=unavailable',
]

ZERO_FOREIGN_INST_RE = re.compile(r'외인\s*\+?0주\s*/\s*기관\s*\+?0주')


def _now_hhmm() -> str:
    return datetime.now().strftime('%H:%M')


def _safe_block_body(kind: str, reasons: list[str]) -> str:
    now = _now_hhmm()
    head = '장후/SOR' if kind == 'afterhours' else '국장'
    clean_reasons = reasons[:3] or ['검수 조건 불충족']
    lines = [
        f'{head} {now}',
        '',
        '검수 실패',
        '- 이전 캐시 재전송 안 함',
    ]
    for reason in clean_reasons:
        lines.append(f'- 원인: {reason}')
    return '\n'.join(lines).strip()


def _header_age_minutes(first_line: str) -> int | None:
    m = re.match(r'^(국장|장후(?:/SOR)?)\s+(\d{2}):(\d{2})$', first_line.strip())
    if not m:
        return None
    now = datetime.now()
    hh, mm = int(m.group(2)), int(m.group(3))
    reported = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    age = int((now - reported).total_seconds() // 60)
    if age < -720:
        age += 24 * 60
    elif age < 0:
        age = 0
    return age


def _load_data_env() -> dict[str, Any]:
    info: dict[str, Any] = {
        'data_env': 'unknown',
        'data_base_url': '',
        'data_purpose': '',
        'has_data_credentials': False,
        'env_error': None,
    }
    try:
        from src.kr.kiwoom.client import load_kiwoom_data_env
        cfg = load_kiwoom_data_env()
        info.update({
            'data_env': getattr(cfg, 'normalized_env', None) or getattr(cfg, 'env', None) or 'unknown',
            'data_base_url': getattr(cfg, 'rest_base_url', '') or '',
            'data_purpose': getattr(cfg, 'purpose', '') or '',
            'has_data_credentials': bool(getattr(cfg, 'appkey', None) and getattr(cfg, 'secretkey', None)),
        })
    except Exception as exc:
        info['env_error'] = f'{type(exc).__name__}: {str(exc)[:200]}'
    return info



def _load_issue_candidates() -> dict[str, Any]:
    path = SCRIPT_DIR / 'regular.issue_candidates.json'
    if not path.exists():
        return {'items': [], 'error': 'issue candidate sidecar missing'}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            return {'items': [], 'error': 'issue candidate sidecar invalid'}
        items = data.get('items') if isinstance(data.get('items'), list) else []
        compact_items = []
        for row in items[:40]:
            if not isinstance(row, dict):
                continue
            candidates = []
            for item in row.get('candidates') or []:
                if not isinstance(item, dict):
                    continue
                title = str(item.get('title') or '').strip()
                if not title:
                    continue
                candidates.append({
                    'title': title[:260],
                    'source': str(item.get('source') or '').strip()[:80],
                    'datetime': str(item.get('datetime') or '').strip()[:60],
                    'url': str(item.get('url') or '').strip()[:220],
                })
                if len(candidates) >= 10:
                    break
            compact_items.append({
                'code': str(row.get('code') or '').strip(),
                'name': str(row.get('name') or '').strip(),
                'themes': list(row.get('themes') or [])[:4],
                'current_issue_line': str(row.get('current_issue_line') or '').strip()[:260],
                'candidates': candidates,
            })
        return {
            'generated_at': str(data.get('generated_at') or ''),
            'body_hash': str(data.get('body_hash') or ''),
            'items': compact_items,
        }
    except Exception as exc:
        return {'items': [], 'error': f'{type(exc).__name__}: {str(exc)[:200]}'}

def build_packet(kind: str, text_script_name: str) -> dict[str, Any]:
    expected_head = '장후' if kind == 'afterhours' else '국장'
    text_script = SCRIPT_DIR / text_script_name
    state_path = SCRIPT_DIR / f'krx_{kind}_alert_review_state.json'

    cp = subprocess.run(
        [sys.executable, str(text_script)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=150,
    )
    body = (cp.stdout or '').strip()
    stderr = (cp.stderr or '').strip()
    first_line = body.splitlines()[0].strip() if body else ''
    body_hash = hashlib.sha1(body.encode('utf-8', 'replace')).hexdigest() if body else ''
    issue_candidates = _load_issue_candidates()

    previous_hash = None
    if state_path.exists():
        try:
            previous_hash = json.loads(state_path.read_text(encoding='utf-8')).get('body_hash')
        except Exception:
            previous_hash = None

    expected_head_pattern = r'장후(?:/SOR)?' if expected_head == '장후' else re.escape(expected_head)
    header_ok = bool(re.match(rf'^{expected_head_pattern}\s+\d{{2}}:\d{{2}}$', first_line))
    header_age = _header_age_minutes(first_line)
    prohibited_found = [term for term in PROHIBITED_TERMS if term in body]
    env_info = _load_data_env()
    zero_foreign_inst_count = len(ZERO_FOREIGN_INST_RE.findall(body))
    rate_limit_count = body.count('rate-limit')
    failure_body = '데이터 갱신 실패' in body or '검수 실패' in body
    same_as_previous = bool(previous_hash and body_hash and previous_hash == body_hash)

    block_reasons: list[str] = []
    if cp.returncode != 0:
        block_reasons.append(f'렌더러 종료코드 {cp.returncode}')
    if not body:
        block_reasons.append('렌더러 본문 없음')
    if not header_ok:
        block_reasons.append('헤더 형식 불일치')
    if header_age is not None and header_age > 20:
        block_reasons.append(f'본문 시각 {header_age}분 지연')
    if same_as_previous:
        block_reasons.append('직전 본문과 동일')
    if prohibited_found:
        block_reasons.append('금지 문구 포함: ' + ', '.join(prohibited_found[:5]))
    if failure_body:
        block_reasons.append('렌더러 실패 본문')
    if env_info.get('data_env') != 'prod':
        block_reasons.append(f"Kiwoom 조회환경={env_info.get('data_env')} / 실전 수급 미확정")
    if body.count('- 없음') >= 3:
        block_reasons.append('유효 후보 없음 또는 DATA 조회 실패')
    if '외인/기관 확인 보류(TR필드 미확정)' in body:
        block_reasons.append('외인/기관 TR 필드 미확정')
    if zero_foreign_inst_count:
        suffix = 'mock row 가능성' if env_info.get('data_env') == 'mock' else '외인/기관 TR 필드 미확정'
        block_reasons.append(f'외인/기관 +0 단정 {zero_foreign_inst_count}건({suffix})')

    diagnostics = {
        'kind': kind,
        'reviewed_at': datetime.now().isoformat(timespec='seconds'),
        'script': text_script_name,
        'script_returncode': cp.returncode,
        'stderr_tail': stderr[-500:] if stderr else '',
        'first_line': first_line,
        'header_ok': header_ok,
        'header_age_minutes': header_age,
        'body_hash': body_hash[:12],
        'previous_hash': (previous_hash or '')[:12],
        'same_as_previous': same_as_previous,
        'prohibited_found': prohibited_found,
        'rate_limit_count': rate_limit_count,
        'zero_foreign_inst_count': zero_foreign_inst_count,
        **env_info,
        'block_reasons': block_reasons,
        'safe_block_body': _safe_block_body(kind, block_reasons),
    }

    try:
        state_path.write_text(
            json.dumps({
                'updated_at': diagnostics['reviewed_at'],
                'body_hash': body_hash,
                'first_line': first_line,
                'blocked': bool(block_reasons),
            }, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )
    except Exception as exc:
        diagnostics['state_write_error'] = f'{type(exc).__name__}: {str(exc)[:200]}'

    return {'body': body, 'diagnostics': diagnostics, 'issue_candidates': issue_candidates}


def main(kind: str, text_script_name: str) -> int:
    packet = build_packet(kind, text_script_name)
    print(json.dumps(packet, ensure_ascii=False, indent=2), flush=True)
    return 0
