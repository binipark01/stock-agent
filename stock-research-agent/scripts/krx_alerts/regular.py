#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, os, re, subprocess, sys, time
from datetime import datetime
from pathlib import Path

ROOT_CANDIDATES = [
    Path('/mnt/d/Agents/kr-stock-agent'),
    Path('D:/Agents/kr-stock-agent'),
    Path('/mnt/d/Agents/stock-research-agent'),
    Path('D:/Agents/stock-research-agent'),
    Path('D:/Workspace/stock-research-agent'),
]
def _valid_root(p: Path) -> bool:
    try:
        return (p / 'src' / 'main.py').exists()
    except Exception:
        return False

ROOT = next((p for p in ROOT_CANDIDATES if _valid_root(p)), ROOT_CANDIDATES[0])
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
CACHE = Path(__file__).with_name('regular.last.txt')
ERRLOG = Path(__file__).with_name('regular.err.txt')
ISSUE_CANDIDATES = Path(__file__).with_name('regular.issue_candidates.json')
SKIP_NAME_TOKENS = ('KODEX','TIGER','ACE','SOL','KBSTAR','HANARO','레버리지','인버스','ETN','ETF')
MAX_STRONG_THEMES = 5
MAX_WEAK_THEMES = 3
# 테마 내부 상세를 중간에 자르지 않도록 충분히 크게 둔다.
# 텔레그램 4096자 제한은 Hermes 전송 레이어가 메시지 단위로 분할한다.
STRONG_SECTION_LINE_LIMIT = 10_000
WEAK_SECTION_LINE_LIMIT = 10_000

FALLBACK_THEME_RULES = [
    ('반도체', ('삼성전자','SK하이닉스','한미반도체','리노공업','HPSP','ISC','이수페타시스','DB하이텍','원익IPS','주성엔지니어링')),
    ('IT부품/전기전자', ('LG전자','삼성전기','LG이노텍','비에이치','대덕전자','심텍')),
    ('철강/소재', ('POSCO','포스코','고려아연','현대제철','풍산','금양')),
    ('자동차/물류', ('현대차','기아','현대모비스','현대글로비스','HL만도')),
    ('통신', ('SK텔레콤','KT','LG유플러스')),
    ('바이오', ('알테오젠','셀트리온','삼성바이오','리가켐','HLB','유한양행')),
    ('조선/방산', ('HD현대중공업','한화오션','삼성중공업','HD한국조선해양','LIG넥스원','한화에어로')),
    ('전력/전선', ('HD현대일렉트릭','LS ELECTRIC','LS','대한전선','일진전기','제룡전기')),
    ('2차전지/화학', ('LG에너지솔루션','삼성SDI','에코프로','포스코퓨처엠','LG화학')),
    ('금융', ('KB금융','신한지주','하나금융','우리금융','삼성생명','메리츠금융')),
]
FALLBACK_CODE_THEMES = {
    '005930':['반도체'],'000660':['반도체'],'009150':['IT부품/전기전자'],'066570':['IT부품/전기전자'],
    '005490':['철강/소재'],'017670':['통신'],'086280':['자동차/물류'],'196170':['바이오'],'329180':['조선/방산'],
}
THEME_UNIVERSE_PATH = ROOT / 'config' / 'krx_theme_universe.json'

def load_theme_universe() -> tuple[dict[str, list[str]], dict[str, int], list[tuple[str, tuple[str, ...]]]]:
    """Load durable KRX theme universe config used for breadth scoring.

    A code can intentionally belong to multiple themes. That means one
    runtime stock can contribute to each relevant theme's breadth count.
    """
    try:
        data = json.loads(THEME_UNIVERSE_PATH.read_text(encoding='utf-8'))
        themes = data.get('themes') if isinstance(data, dict) else None
        if not isinstance(themes, list):
            raise ValueError('missing themes')
        code_themes: dict[str, list[str]] = {}
        universe_size: dict[str, int] = {}
        name_rules: list[tuple[str, tuple[str, ...]]] = []
        for theme in themes:
            if not isinstance(theme, dict):
                continue
            theme_name = str(theme.get('name') or '').strip()
            members = theme.get('members')
            if not theme_name or not isinstance(members, list):
                continue
            seen_codes: set[str] = set()
            names: list[str] = []
            for member in members:
                if not isinstance(member, dict):
                    continue
                digits = re.sub(r'\D', '', str(member.get('code') or ''))
                code = digits.zfill(6) if digits else ''
                name = str(member.get('name') or '').strip()
                if code and code not in seen_codes:
                    code_themes.setdefault(code, []).append(theme_name)
                    seen_codes.add(code)
                if name:
                    names.append(name)
            universe_size[theme_name] = len(seen_codes)
            if names:
                name_rules.append((theme_name, tuple(names)))
        if not universe_size:
            raise ValueError('empty theme universe')
        return code_themes, universe_size, name_rules
    except Exception:
        return FALLBACK_CODE_THEMES, {theme: len(tokens) for theme, tokens in FALLBACK_THEME_RULES}, FALLBACK_THEME_RULES

CODE_THEMES, THEME_UNIVERSE_SIZE, THEME_RULES = load_theme_universe()

def load_theme_members() -> dict[str, list[dict[str, str]]]:
    try:
        data = json.loads(THEME_UNIVERSE_PATH.read_text(encoding='utf-8'))
        themes = data.get('themes') if isinstance(data, dict) else None
        if not isinstance(themes, list):
            return {}
        result: dict[str, list[dict[str, str]]] = {}
        for theme in themes:
            if not isinstance(theme, dict):
                continue
            theme_name = str(theme.get('name') or '').strip()
            members = theme.get('members')
            if not theme_name or not isinstance(members, list):
                continue
            rows=[]; seen=set()
            for member in members:
                if not isinstance(member, dict):
                    continue
                digits = re.sub(r'\D', '', str(member.get('code') or ''))
                code = digits.zfill(6) if digits else ''
                name = str(member.get('name') or '').strip()
                if not code or code in seen or any(tok in name for tok in SKIP_NAME_TOKENS):
                    continue
                seen.add(code)
                rows.append({'code': code, 'name': name})
            if rows:
                result[theme_name]=rows
        return result
    except Exception:
        return {}

THEME_MEMBERS = load_theme_members()

def theme_majority_required(theme: str) -> int | None:
    universe = THEME_UNIVERSE_SIZE.get(theme)
    if not universe:
        return None
    return universe // 2 + 1

def run_mode(mode: str, request: str) -> dict:
    cp = subprocess.run([sys.executable, 'src/main.py', '--mode', mode, '--json', request], cwd=str(ROOT), capture_output=True, text=True, timeout=90)
    if cp.returncode != 0:
        raise RuntimeError((cp.stderr or cp.stdout)[-500:])
    return json.loads(cp.stdout)

def fmt_int(v):
    try:
        if v is None: return '확인불가'
        return f'{int(v):,}'
    except Exception:
        return '확인불가'

def clean_code(v):
    s = re.sub(r'\D', '', str(v or ''))
    return s.zfill(6) if s else ''

def parse_signed_qty(v):
    s = str(v or '').strip().replace(',', '')
    if not s:
        return None
    # Kiwoom/Naver can emit +123, -123, or double-minus style values.
    neg = s.startswith('-') or s.startswith('--')
    digits = re.sub(r'\D', '', s)
    if not digits:
        return None
    n = int(digits)
    return -n if neg else n


def themes_of(code: str, name: str) -> list[str]:
    themes = CODE_THEMES.get(code)
    if themes:
        return list(dict.fromkeys(themes))
    for theme, toks in THEME_RULES:
        if any(tok and tok in name for tok in toks):
            return [theme]
    return ['기타']

def metric_bits(metrics: dict) -> list[str]:
    bits=[]
    if metrics.get('trade_value_rank'): bits.append(f"거래대금 {metrics.get('trade_value_rank')}위")
    if metrics.get('foreign_rank'): bits.append(f"외인순매수 {metrics.get('foreign_rank')}위")
    if metrics.get('institution_rank'): bits.append(f"기관순매수 {metrics.get('institution_rank')}위")
    if metrics.get('investor_rank'): bits.append(f"장중수급 {metrics.get('investor_rank')}위")
    return bits

def build_foreign_inst_top_map(client) -> dict:
    """Build symbol -> foreign/institution intraday top flow from ka90009.

    Kiwoom ka90009 quantity fields are displayed in thousand shares in the
    ranking table, so convert to shares for Telegram display. This is a
    top-list supplement only; missing symbols remain n/a rather than 0.
    """
    result = {}
    try:
        payload = client.post_tr('ka90009', '/api/dostk/rkinfo', {
            'mrkt_tp': '000', 'qry_dt_tp': '0', 'date': '',
            'trde_tp': '1', 'sort_tp': '1', 'amt_qty_tp': '1', 'stex_tp': '1',
        }).data
        rows = payload.get('frgnr_orgn_trde_upper') or []
    except Exception:
        return result

    def put(row, kind, code_key, qty_key, sell=False):
        code = clean_code(row.get(code_key))
        if not code:
            return
        qty = parse_signed_qty(row.get(qty_key))
        if qty is None:
            return
        qty = qty * 1000
        if sell:
            qty = -abs(qty)
        else:
            qty = abs(qty)
        bucket = result.setdefault(code, {})
        bucket.setdefault(kind, qty)

    for row in rows:
        put(row, 'foreign', 'for_netprps_stk_cd', 'for_netprps_qty', sell=False)
        put(row, 'foreign', 'for_netslmt_stk_cd', 'for_netslmt_qty', sell=True)
        put(row, 'institution', 'orgn_netprps_stk_cd', 'orgn_netprps_qty', sell=False)
        put(row, 'institution', 'orgn_netslmt_stk_cd', 'orgn_netslmt_qty', sell=True)
    return result


def direct_investor_flow(client, code: str) -> dict:
    """Direct per-symbol foreign/institution flow via ka10059.

    This is preferred over top-list tables because it queries one stock code
    directly and returns current date investor buckets (, ).
    Quantities are shares, not thousand-share table units.
    """
    code = clean_code(code)
    if not code:
        return {}
    today = datetime.now().strftime('%Y%m%d')
    payload = client.post_tr('ka10059', '/api/dostk/stkinfo', {
        'dt': today, 'stk_cd': code, 'amt_qty_tp': '1', 'trde_tp': '0', 'unit_tp': '1'
    }).data
    rows = payload.get('stk_invsr_orgn') or []
    if not rows:
        return {}
    row = rows[0]
    return {
        'date': str(row.get('dt') or ''),
        'foreign': parse_signed_qty(row.get('frgnr_invsr')),
        'institution': parse_signed_qty(row.get('orgn')),
        'source': 'ka10059',
    }


def direct_symbol_flow(client, code: str) -> dict:
    from src.kr.flow.symbol_flow import build_krx_symbol_flow_snapshot_v2
    return build_krx_symbol_flow_snapshot_v2(client, code)

def decide_action(inst, foreign, program, score):
    if program is not None and program < 0:
        return '추격금지'
    if (program or 0) > 0 and ((inst or 0) > 0 or (foreign or 0) > 0):
        return '눌림대기'
    if score >= 5:
        return '확인대기'
    return '관찰'

def verdict_from_leaders(actions):
    if '눌림대기' in actions: return '눌림대기'
    if '확인대기' in actions: return '확인대기'
    return '관망'


def _index_number(raw):
    s = str(raw or '').strip().replace(',', '')
    if not s:
        return None
    m = re.search(r'[-+]?\d+(?:\.\d+)?', s)
    if not m:
        return None
    try:
        return float(m.group(0))
    except Exception:
        return None


def _format_index_value(raw):
    value = _index_number(raw)
    if value is None:
        return '확인불가'
    return f'{abs(value):,.2f}'


def _format_index_pct(raw):
    value = _index_number(raw)
    if value is None:
        return '등락률 확인불가'
    return f'{value:+.2f}%'


def _fetch_index_payload(client, mrkt_tp: str, inds_cd: str) -> dict:
    try:
        result = client.post_tr('ka20001', '/api/dostk/sect', {'mrkt_tp': mrkt_tp, 'inds_cd': inds_cd})
        data = result.data if hasattr(result, 'data') else result
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def market_index_line(client=None) -> str:
    """Render KOSPI200/KOSDAQ150 value and percentage change for the Telegram header."""
    try:
        if client is None:
            from src.kr.kiwoom.client import build_kiwoom_data_client
            client = build_kiwoom_data_client()
        specs = [
            ('KOSPI200', '2', '201'),
            ('KOSDAQ150', '1', '150'),
        ]
        parts=[]
        for label, mrkt_tp, inds_cd in specs:
            data = _fetch_index_payload(client, mrkt_tp, inds_cd)
            value = _format_index_value(data.get('cur_prc'))
            pct = _format_index_pct(data.get('flu_rt'))
            parts.append(f'{label} {value} {pct}')
        return '지수: ' + ' / '.join(parts)
    except Exception:
        return '지수: KOSPI200 확인불가 / KOSDAQ150 확인불가'


ISSUE_TOPIC_RULES = [
    ('노사', ('파업','조업중단','생산차질','긴급조정')),
    ('수주/계약', ('수주','계약','공급','납품','협력','파트너십','체결','선정')),
    ('투자/사업', ('투자','증설','공장','새만금','인수','합병','M&A','신사업','진출','출시','개발')),
    ('실적', ('실적','영업이익','매출','순이익','흑자','적자','컨센서스')),
    ('주주환원', ('배당','자사주','소각','주주환원')),
    ('증권가', ('목표가','투자의견','상향','하향','리포트')),
    ('리스크', ('리콜','소송','과징금','규제','관세','조사','제재')),
    ('테마', ('HBM','반도체','AI','원전','수소','로봇','전력','전선','자동차','방산','조선','바이오')),
]
ISSUE_SIGNAL_KEYWORDS = tuple(k for _, keys in ISSUE_TOPIC_RULES for k in keys) + (
    '수혜','호재','악재','기대','우려','전망','관측','발표','확대','승인','허가','인증','공시',
    '외국인','기관','순매수','순매도','시총','시가총액','왕좌','추격','맹추격','최대','최초',
)
ISSUE_NOISE_PATTERNS = [
    r'무료.?추천', r'추천주', r'리딩방', r'종목상담', r'종목토론', r'오늘의\s*종목',
    r'관심종목', r'급등주\s*발굴', r'상한가\s*따라잡기', r'매수\s*신호',
    r'VI\s*발동', r'시간외\s*특징주', r'장중\s*특징주',
    r'임금\s*협상', r'임단협', r'잠정\s*합의안', r'노조.*투표',
]
ISSUE_PRICE_ONLY_PATTERNS = [
    r'^(?:특징주\s*)?[^,，]{2,18}[,，]?\s*(?:장중\s*)?(?:급등|급락|상승|하락|강세|약세|보합|신고가|최고가|최저가)\s*$',
    r'^[^,，]{2,18}\s*주가\s*(?:급등|급락|상승|하락|강세|약세|보합).*$'
]
AMBIGUOUS_SHORT_NAME_AFFILIATES = {
    'SK': ('SK하이닉스','SK스퀘어','SK이노베이션','SK텔레콤','SK바이오팜','SK바이오사이언스','SKC','SK 하이닉스'),
    'LG': ('LG전자','LG화학','LG에너지솔루션','LG이노텍','LG유플러스','LG생활건강','LG 전자'),
    'LS': ('LS ELECTRIC','LS일렉트릭','LS에코에너지'),
    'CJ': ('CJ제일제당','CJ ENM','CJ대한통운','CJ CGV'),
    'KT': ('KT&G','케이티앤지'),
}


def clean_issue_title(title):
    try:
        import html
        title=html.unescape(str(title or ''))
    except Exception:
        title=str(title or '')
    title=re.sub(r'<[^>]+>', '', title)
    title=title.replace('…', ' ').replace('...', ' ')
    title=re.sub(r'\s+', ' ', title).strip()
    title=re.sub(r'^\[[^\]]{1,12}\]\s*', '', title)
    title=re.sub(r'^\([^)]{1,12}\)\s*', '', title)
    return title


def issue_topic(title):
    t=str(title or '')
    for label, keys in ISSUE_TOPIC_RULES:
        if any(k in t for k in keys):
            return label
    return '최신뉴스'


def issue_tokens(x):
    name=str(x.get('name') or '').strip()
    toks=[]
    def add(v):
        v=str(v or '').strip()
        if len(v) >= 2 and v not in toks:
            toks.append(v)
    add(name)
    compact=name.replace(' ', '')
    if compact != name:
        add(compact)
    if name.endswith('우'):
        add(name[:-1])
    aliases={
        '삼성전자우':['삼성전자'],
        '현대차':['현대차','현대자동차'],
        '기아':['기아'],
        'SK하이닉스':['SK하이닉스','하이닉스'],
        'SK스퀘어':['SK스퀘어'],
        '현대건설':['현대건설'],
        'LG전자':['LG전자'],
        'LG에너지솔루션':['LG에너지솔루션','LG엔솔'],
        'POSCO홀딩스':['POSCO홀딩스','포스코홀딩스'],
        'LS ELECTRIC':['LS ELECTRIC','LS일렉트릭','엘에스일렉트릭'],
    }
    for alias in aliases.get(name, []):
        add(alias)
    return toks


def _ascii_short_token_match(title, token):
    return re.search(r'(?<![A-Za-z0-9가-힣]){}(?![A-Za-z0-9가-힣])'.format(re.escape(token)), title) is not None


def _token_matches_issue_title(title, token):
    if not token:
        return False
    if re.fullmatch(r'[A-Z0-9&]{1,3}', token):
        return _ascii_short_token_match(title, token)
    return token in title


def _ambiguous_affiliate_conflict(name, title):
    for affiliate in AMBIGUOUS_SHORT_NAME_AFFILIATES.get(str(name or '').strip(), ()):
        if affiliate and affiliate in title:
            return True
    return False


def issue_matches(x, title):
    title=str(title or '')
    name=str(x.get('name') or '').strip()
    for tok in issue_tokens(x):
        if not _token_matches_issue_title(title, tok):
            continue
        if tok == name and _ambiguous_affiliate_conflict(name, title):
            continue
        return True
    return False


def issue_title_score(title):
    t=clean_issue_title(title)
    if not t:
        return 0
    if any(re.search(p, t, re.IGNORECASE) for p in ISSUE_NOISE_PATTERNS):
        return 0
    signal_count=sum(1 for k in ISSUE_SIGNAL_KEYWORDS if k in t)
    if signal_count <= 0:
        if any(re.search(p, t) for p in ISSUE_PRICE_ONLY_PATTERNS):
            return 0
        return 0
    score=signal_count * 3
    if re.search(r'\d+(?:조|억|만|%|원)', t):
        score += 1
    if issue_topic(t) != '최신뉴스':
        score += 2
    return score


def select_issue_item(x, items):
    best=None
    best_rank=None
    for idx, item in enumerate(items or []):
        if not isinstance(item, dict):
            continue
        raw_title=clean_issue_title(item.get('title'))
        if not raw_title or not issue_matches(x, raw_title):
            continue
        score=issue_title_score(raw_title)
        if score <= 0:
            continue
        rank=(score, -idx)
        if best_rank is None or rank > best_rank:
            best=item
            best_rank=rank
    return best


def format_issue(item):
    title=clean_issue_title(item.get('title')) if isinstance(item, dict) else ''
    if not title:
        return ''
    source=clean_issue_title(item.get('source')) if isinstance(item, dict) else ''
    prefix=issue_topic(title)
    suffix=f' ({source})' if source else ''
    if prefix == '최신뉴스':
        return f'{title}{suffix}'
    return f'{prefix}: {title}{suffix}'

def build_regular_text() -> str:
    now = datetime.now().strftime('%H:%M')
    rank = run_mode('krx_flow_rank_scan', '국장 테마별 수급 랭킹')
    data = rank.get('data') if isinstance(rank.get('data'), dict) else {}
    candidates = list(data.get('trade_candidates') or [])
    focus = [str(x) for x in rank.get('focus') or []]
    collected_at = 'unavailable'; env = 'unknown'
    for line in focus:
        if '수집시각:' in line:
            m = re.search(r'수집시각:\s*([^/]+)', line); e = re.search(r'env=([^\s/]+)', line)
            if m: collected_at = m.group(1).strip()
            if e: env = e.group(1).strip()
            break
    usable=[]; seen=set()
    for c in candidates:
        if not isinstance(c, dict):
            continue
        code=clean_code(c.get('code')); name=str(c.get('name') or code)
        if not code or code in seen or any(tok in name for tok in SKIP_NAME_TOKENS):
            continue
        seen.add(code)
        score=int(c.get('score') or 0)
        metrics=c.get('metrics') if isinstance(c.get('metrics'),dict) else {}
        bits=metric_bits(metrics)
        themes=themes_of(code,name)
        usable.append({'raw':c,'code':code,'name':name,'score':score,'metrics':metrics,'bits':bits,'themes':themes})
        if len(usable) >= 18:
            break
    groups={}
    for x in usable:
        for theme in x.get('themes') or ['기타']:
            g=groups.setdefault(theme, {'theme':theme, 'score':0, 'count':0, 'members':[], 'codes':set()})
            if x['code'] in g['codes']:
                continue
            g['codes'].add(x['code'])
            g['score'] += max(0, x['score'])
            g['count'] += 1
            g['members'].append(x)
    for g in groups.values():
        g['members'].sort(key=lambda z: (z['score'], len(z['bits'])), reverse=True)
        codes=set(g.pop('codes', set())) or {m['code'] for m in g['members'] if m.get('code')}
        universe=THEME_UNIVERSE_SIZE.get(g['theme'], 0)
        required=theme_majority_required(g['theme'])
        g['breadth_count']=len(codes)
        g['universe_count']=universe
        g['majority_required']=required
        g['is_broad_theme']=bool(required and len(codes) >= required)
        g['score'] += min(3, g['count'])
    ranked=sorted(groups.values(), key=lambda g:(g['score'], g['count']), reverse=True)
    broad=[g for g in ranked if g.get('is_broad_theme')]
    meaningful_strong=[g for g in broad if (g.get('breadth_count') or 0) >= 3 and (g.get('universe_count') or 0) >= 5]
    leader_focus_mode=not meaningful_strong
    strong=(meaningful_strong if meaningful_strong else [])[:MAX_STRONG_THEMES]
    strong_codes={m.get('code') for g in strong for m in g.get('members', []) if m.get('code')}
    weak=[]
    for g in ranked:
        if g.get('is_broad_theme'):
            continue
        members=[m for m in g.get('members', []) if m.get('code') not in strong_codes]
        if not members:
            continue
        gg=dict(g)
        gg['members']=members
        gg['count']=len(members)
        weak.append(gg)
        if len(weak) >= MAX_WEAK_THEMES:
            break

    from src.kr.kiwoom.client import build_kiwoom_data_client, load_kiwoom_data_env
    client=build_kiwoom_data_client()
    index_line=market_index_line(client)
    try:
        data_cfg = load_kiwoom_data_env()
        data_env = getattr(data_cfg, 'normalized_env', None) or getattr(data_cfg, 'env', None) or env
    except Exception:
        data_env = env
    live_data = data_env == 'prod'
    top_flow_map = build_foreign_inst_top_map(client) if live_data else {}
    flow_cache={}; quote_cache={}; issue_cache={}; issue_news_candidates={}; caution=[]; attempts=0; price_attempts=0; issue_attempts=0; max_attempts=18; max_price_attempts=220; max_issue_attempts=18

    def fmt_signed(v):
        try:
            if v is None:
                return '확인불가'
            return f'{int(v):+,}'
        except Exception:
            return '확인불가'

    def fmt_qty(v):
        s = fmt_signed(v)
        return '확인불가' if s == '확인불가' else f'{s}주'

    def parse_pct_value(raw):
        try:
            return None if raw in (None, '') else float(str(raw).replace('%','').replace('+','').replace(',','').strip())
        except Exception:
            return None

    def parse_int_value(raw):
        try:
            if raw in (None, ''):
                return None
            s = str(raw).replace(',', '').replace('+', '').strip()
            s = re.sub(r'[^0-9.\-]', '', s)
            if not s or s in ('-', '.', '-.'):
                return None
            return int(float(s))
        except Exception:
            return None

    def parse_price_value(raw):
        value = parse_int_value(raw)
        if value is None:
            return None
        value = abs(value)
        return value if value > 0 else None

    quote_market = os.environ.get('KRX_QUOTE_MARKET', '').strip().upper()
    quote_suffix = os.environ.get('KRX_QUOTE_SUFFIX', '').strip().upper()
    if not quote_suffix:
        quote_suffix = {'NXT': '_NX', 'SOR': '_AL', 'KRX': ''}.get(quote_market, '')
    if quote_suffix and not quote_suffix.startswith('_'):
        quote_suffix = '_' + quote_suffix

    def quote_request_code(code: str) -> str:
        clean = str(code or '').strip().upper()
        if not clean or '_' in clean or not quote_suffix:
            return clean
        return clean + quote_suffix

    def quote_info_for(x):
        nonlocal price_attempts
        code=x.get('code') or ''
        if not code:
            return {'pct': None, 'price': None}
        if code in quote_cache:
            return quote_cache[code]
        if price_attempts >= max_price_attempts:
            quote_cache[code]={'pct': None, 'price': None, 'market_cap': None}
            return quote_cache[code]
        price_attempts += 1
        info={'pct': None, 'price': None, 'market_cap': None}
        # Kiwoom can occasionally return an empty quote payload when many
        # symbol quotes are requested back-to-back. Retry a couple of times
        # before caching None, otherwise displayed leaders can become
        # "등락률 확인불가" even though the direct quote is available.
        for quote_try in range(3):
            try:
                result=client.post_tr('ka10001', '/api/dostk/stkinfo', {'stk_cd': quote_request_code(code)})
                data=result.data if hasattr(result, 'data') else result
                if isinstance(data, dict):
                    info['pct']=parse_pct_value(data.get('flu_rt') or data.get('change_pct') or data.get('change_rate'))
                    info['price']=parse_price_value(data.get('cur_prc') or data.get('stck_prpr') or data.get('price') or data.get('current_price') or data.get('close'))
                    info['market_cap']=parse_int_value(data.get('mac') or data.get('market_cap') or data.get('mkt_cap') or data.get('cap'))
                    if info.get('pct') is not None or info.get('price') is not None:
                        break
            except Exception:
                pass
            if quote_try < 2:
                time.sleep(0.12)
        quote_cache[code]=info
        return info

    def quote_pct_for(x):
        return quote_info_for(x).get('pct')

    def current_price_for(x):
        if quote_suffix:
            price = quote_info_for(x).get('price')
            if price is not None:
                return price
        metrics=x.get('metrics') if isinstance(x.get('metrics'), dict) else {}
        for source in (x, metrics):
            for key in ('price', 'current_price', 'cur_prc', 'stck_prpr', 'last_price', 'close', 'trade_price'):
                price=parse_price_value(source.get(key)) if isinstance(source, dict) else None
                if price is not None:
                    return price
        return quote_info_for(x).get('price')

    def market_cap_for(x):
        info = quote_info_for(x)
        cap = info.get('market_cap') if isinstance(info, dict) else None
        if cap is not None:
            return cap
        metrics=x.get('metrics') if isinstance(x.get('metrics'), dict) else {}
        for source in (x, metrics):
            for key in ('market_cap', 'mkt_cap', 'mac', 'cap'):
                value=parse_int_value(source.get(key)) if isinstance(source, dict) else None
                if value is not None:
                    return value
        return 0

    def fmt_flow_amount(qty, price):
        try:
            if qty is None or price is None:
                return ''
            amount = int(qty) * int(price)
            if amount == 0:
                return '약 0원'
            sign = '+' if amount > 0 else '-'
            abs_amount = abs(amount)
            if abs_amount >= 100_000_000:
                return f'약 {sign}{abs_amount / 100_000_000:.1f}억'
            if abs_amount >= 10_000:
                return f'약 {sign}{abs_amount / 10_000:.0f}만'
            return f'약 {sign}{abs_amount:,}원'
        except Exception:
            return ''

    def fmt_flow_bucket(label, qty, price):
        qty_text = fmt_qty(qty)
        amount_text = fmt_flow_amount(qty, price)
        if amount_text and qty_text != '확인불가':
            return f'{label} {qty_text}({amount_text})'
        return f'{label} {qty_text}'

    def flow_for(x):
        nonlocal attempts
        code=x.get('code') or ''
        if code in flow_cache:
            return flow_cache[code]
        if attempts >= max_attempts:
            flow_cache[code]={'status':'skipped'}
            return flow_cache[code]
        attempts += 1
        try:
            snap=direct_symbol_flow(client, code)
            top_flow = top_flow_map.get(code, {}) if live_data else {}
            direct_flow = {}
            if live_data:
                try:
                    direct_flow = direct_investor_flow(client, code)
                except Exception as exc:
                    if '429' in str(exc) and 'Kiwoom 429/rate-limit: 일부 개별확인 생략' not in caution:
                        caution.append('Kiwoom 429/rate-limit: 일부 개별확인 생략')
            inst = snap.get('institution_net_buy_qty')
            foreign = snap.get('foreign_net_buy_qty')
            fi_source = 'symbol_tr'
            if live_data:
                if direct_flow:
                    inst = direct_flow.get('institution')
                    foreign = direct_flow.get('foreign')
                    fi_source = 'ka10059'
                elif top_flow:
                    inst = top_flow.get('institution') if top_flow.get('institution') is not None else None
                    foreign = top_flow.get('foreign') if top_flow.get('foreign') is not None else None
                    fi_source = 'ka90009_top'
                else:
                    inst = None if inst == 0 else inst
                    foreign = None if foreign == 0 else foreign
            flow_cache[code]={
                'status':'ok',
                'institution': inst,
                'foreign': foreign,
                'program': snap.get('program_net_buy_qty'),
                'price': current_price_for(x),
                'env': snap.get('env') or data_env,
                'live_data': live_data,
                'fi_source': fi_source,
            }
        except Exception as exc:
            msg=str(exc)
            if '429' in msg and 'Kiwoom rate-limit: 일부 개별확인 생략' not in caution:
                caution.append('Kiwoom rate-limit: 일부 개별확인 생략')
            flow_cache[code]={'status':'rate_limit' if '429' in msg else 'error', 'error': type(exc).__name__, 'env': data_env, 'live_data': live_data}
        return flow_cache[code]

    def flow_text(flow):
        status=flow.get('status')
        flow_env = flow.get('env') or data_env
        if status == 'ok':
            price = flow.get('price')
            if not flow.get('live_data'):
                return '외인/기관 실시간 확인 불가(DATA {}) / {}'.format(flow_env, fmt_flow_bucket('프로그램', flow.get('program'), price))
            if (flow.get('foreign') in (None, 0)) and (flow.get('institution') in (None, 0)):
                return '외인/기관 확인 보류(TR필드 미확정) / {}'.format(fmt_flow_bucket('프로그램', flow.get('program'), price))
            return '{} / {} / {}'.format(
                fmt_flow_bucket('외인', flow.get('foreign'), price),
                fmt_flow_bucket('기관', flow.get('institution'), price),
                fmt_flow_bucket('프로그램', flow.get('program'), price),
            )
        if status == 'rate_limit':
            if not live_data:
                return '외인/기관 실시간 확인 불가(DATA {}) / 프로그램 확인 보류(rate-limit)'.format(data_env)
            return '외인/기관/프로그램 확인 보류(rate-limit)'
        if status == 'skipped':
            if not live_data:
                return '외인/기관 실시간 확인 불가(DATA {}) / 프로그램 확인 생략'.format(data_env)
            return '외인/기관/프로그램 확인 생략'
        return '외인/기관/프로그램 확인 실패({})'.format(flow.get('error','error'))

    def price_change_pct(x):
        if quote_suffix:
            pct = quote_pct_for(x)
            if pct is not None:
                return pct
        metrics=x.get('metrics') if isinstance(x.get('metrics'), dict) else {}
        raw=x.get('change_pct')
        if raw is None:
            raw=metrics.get('change_pct')
        pct=parse_pct_value(raw)
        if pct is not None:
            return pct
        return quote_pct_for(x)

    def price_mark(x):
        pct=price_change_pct(x)
        if pct is None:
            return '?'
        if pct > 0:
            return '+'
        if pct < 0:
            return '-'
        return '0'

    def price_label(x):
        price=current_price_for(x)
        pct=price_change_pct(x)
        price_text=f'{int(price):,}원' if price is not None else '가격 확인불가'
        if pct is None:
            return f'{price_text} 등락률 확인불가'
        sign='+' if pct > 0 else '-' if pct < 0 else '0'
        return f'{price_text} {sign}{abs(pct):.2f}%'

    def remember_issue_candidates(x, items):
        code=x.get('code') or ''
        name=str(x.get('name') or code).strip()
        if not code and not name:
            return
        rows=[]
        for item in list(items or [])[:8]:
            if not isinstance(item, dict):
                continue
            title=clean_issue_title(item.get('title'))
            if not title:
                continue
            rows.append({
                'title': title,
                'source': clean_issue_title(item.get('source')),
                'datetime': str(item.get('datetime') or item.get('date') or '').strip(),
                'url': str(item.get('url') or '').strip(),
            })
        issue_news_candidates[code or name]={
            'code': code,
            'name': name,
            'themes': list(x.get('themes') or [])[:4],
            'current_issue_line': issue_cache.get(code) or '',
            'candidates': rows,
        }

    def write_issue_candidates_sidecar(text):
        try:
            ISSUE_CANDIDATES.write_text(json.dumps({
                'generated_at': datetime.now().isoformat(timespec='seconds'),
                'body_hash': hashlib.sha1(text.encode('utf-8', 'replace')).hexdigest()[:12],
                'items': list(issue_news_candidates.values()),
            }, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception:
            pass

    def format_stock_list(members, limit=4):
        rows=[]
        seen=set()
        for x in members:
            code=x.get('code')
            if code and code in seen:
                continue
            if code:
                seen.add(code)
            name=str(x.get('name') or code or '').strip()
            if not name:
                continue
            rows.append(f'{name}: {price_label(x)}')
            if len(rows) >= limit:
                break
        return ', '.join(rows)

    def pick_theme_leaders(members, direction='+', limit=3):
        primary=[x for x in members if not direction or price_mark(x) == direction]
        fallback=list(members)
        pool=primary or fallback

        def cap_key(x):
            return (market_cap_for(x), int(x.get('score') or 0), abs(pct_value(x)))

        def mover_key(x):
            pct=pct_value(x)
            if direction == '+':
                move=pct
            elif direction == '-':
                move=abs(pct) if pct < 0 else -999.0
            else:
                move=abs(pct)
            return (move, int(x.get('score') or 0), market_cap_for(x))

        large_caps=sorted(pool, key=cap_key, reverse=True)
        movers=sorted(pool, key=mover_key, reverse=True)
        large_cap_slots=max(1, min(2, limit // 2 if limit > 2 else 1))
        picked=[]; seen=set()

        def add_from(rows, max_items):
            for x in rows:
                code=x.get('code')
                if code and code in seen:
                    continue
                if code:
                    seen.add(code)
                picked.append(x)
                if len(picked) >= max_items or len(picked) >= limit:
                    break

        add_from(large_caps, large_cap_slots)
        add_from(movers, limit)
        if not picked:
            add_from(sorted(fallback, key=mover_key, reverse=True), limit)
        return picked[:limit]

    def leader_stock_detail_lines(leaders, indent, label):
        rows=[f'{indent}- {label}']
        if not leaders:
            rows.append(f'{indent}  - 대표 종목 확인불가')
            return rows
        for leader in leaders:
            name=str(leader.get('name') or leader.get('code') or '').strip()
            if not name:
                continue
            flow=flow_for(leader)
            rows.extend([
                f'{indent}  - {name}: {price_label(leader)}',
                f'{indent}    - 수급: {flow_text(flow)}',
                f'{indent}    - 이슈: {issue_for(leader)}',
            ])
        return rows

    def leader_stock_summary(leaders):
        rows=[]
        seen=set()
        for leader in leaders:
            code=leader.get('code') or ''
            if code and code in seen:
                continue
            if code:
                seen.add(code)
            name=str(leader.get('name') or code or '').strip()
            if not name:
                continue
            rows.append(f'{name}: {price_label(leader)}')
        return ', '.join(rows) if rows else '대표 종목 확인불가'

    def root_theme_name(theme):
        text=str(theme or '').strip()
        return text.split('/', 1)[0] if '/' in text else text

    def sub_theme_label(theme):
        text=str(theme or '').strip()
        return text.split('/', 1)[1] if '/' in text else text

    def root_theme_lines(root, groups, direction='+'):
        label='주도주' if direction == '+' else '약세 주도'
        members=[]
        for g in groups:
            members.extend(g.get('members') or [])
        leaders=pick_theme_leaders(members, direction, 6)
        rows=[f'- {root}']
        rows.extend(leader_stock_detail_lines(leaders, '  ', label))
        rows.append('  - 세부 테마')
        for g in groups:
            theme=str(g.get('theme') or '')
            sub=sub_theme_label(theme)
            sub_members=[m for m in g.get('members', []) if m.get('name')]
            rows.append(f'    - {sub}')
            if not sub_members:
                rows.append('      - 없음')
                continue
            sub_leaders=pick_theme_leaders(sub_members, direction, 3)
            rows.append(f'      - {label}: {leader_stock_summary(sub_leaders)}')
            shown={x.get('code') for x in sub_leaders}
            peers=[]
            for m in sub_members:
                if m.get('code') in shown:
                    continue
                if price_mark(m) != direction:
                    continue
                shown.add(m.get('code'))
                peers.append(f'{m["name"]}: {price_label(m)}')
            if peers:
                rows.append('      - 동반: {}'.format(', '.join(peers)))
        return rows

    def theme_lines(g, limit, direction='+'):
        theme=g['theme']
        members=[m for m in g.get('members', []) if m.get('name')]
        rows=[f'- {theme}']
        if not members:
            rows.append('  - 없음')
            return rows
        leaders=pick_theme_leaders(members, direction, max(2, limit))
        leader_label='주도주' if direction == '+' else '약세 주도'
        rows.extend(leader_stock_detail_lines(leaders, '  ', leader_label))
        shown={x.get('code') for x in leaders}
        peers=[]
        for m in members:
            if m.get('code') in shown:
                continue
            if price_mark(m) != direction:
                continue
            shown.add(m.get('code'))
            peers.append(f'{m["name"]}: {price_label(m)}')
        if peers:
            rows.append('  - 동반: {}'.format(', '.join(peers)))
        return rows

    def issue_for(x):
        nonlocal issue_attempts
        code=x.get('code') or ''
        if code in issue_cache:
            return issue_cache[code]
        if issue_attempts >= max_issue_attempts:
            issue_cache[code]='최근 종목뉴스 확인 생략'
            return issue_cache[code]
        issue_attempts += 1
        try:
            from src.kr.news.symbol_supply_news import fetch_naver_stock_news
            items=fetch_naver_stock_news(code, limit=10)
            remember_issue_candidates(x, items)
            item=select_issue_item(x, items)
            issue_cache[code]=format_issue(item) if item else '관련 종목뉴스 확인불가'
            if code in issue_news_candidates:
                issue_news_candidates[code]['current_issue_line']=issue_cache[code]
        except Exception:
            issue_cache[code]='최근 종목뉴스 확인불가'
        return issue_cache[code]

    def leader_detail_lines(index, g):
        x=g['members'][0]
        rank_bits=' · '.join(x['bits']) if x['bits'] else '테마 내 점수 최상위'
        theme=g['theme']; name=x['name']
        flow=flow_for(x)
        peer_up=[f'{m["name"]}: {price_label(m)}' for m in g['members'][1:5] if m.get('name') and price_mark(m) == '+']
        peer_down=[f'{m["name"]}: {price_label(m)}' for m in g['members'][1:5] if m.get('name') and price_mark(m) == '-']
        peer_unknown=[f'{m["name"]}: {price_label(m)}' for m in g['members'][1:5] if m.get('name') and price_mark(m) not in ('+', '-')]
        extra_themes=[t for t in x.get('themes', []) if t != theme and t != '기타']
        if extra_themes:
            rank_bits = '{} · 겹테마 {}'.format(rank_bits, '/'.join(extra_themes[:2]))
        rows=[
            f'{index}) {theme}: {name}: {price_label(x)}',
        ]
        if peer_up:
            rows.append('  - 동반: {}'.format(', '.join(peer_up)))
        if peer_down:
            rows.append('  - 엇갈림: {}'.format(', '.join(peer_down)))
        if peer_unknown:
            rows.append('  - 확인필요: {}'.format(', '.join(peer_unknown)))
        if not (peer_up or peer_down or peer_unknown):
            rows.append('  - 동반: 테마 내 단독 선두')
        rows.extend([
            f'  - 수급: {flow_text(flow)}',
            f'  - 이슈: {issue_for(x)}',
        ])
        return rows

    def stock_sort_key(x):
        mark=price_mark(x)
        direction_score={'+':3, '0':2, '?':1, '-':0}.get(mark, 1)
        return (direction_score, int(x.get('score') or 0), len(x.get('bits') or []))

    def leader_theme_judgment_lines(limit=4):
        picked=[]; seen=set()
        for x in sorted(usable, key=stock_sort_key, reverse=True):
            if price_mark(x) != '+':
                continue
            pct=price_label(x)
            for theme in [t for t in x.get('themes', []) if t and t != '기타']:
                if theme in seen:
                    continue
                seen.add(theme)
                picked.append(f'{theme}({x["name"]} {pct})')
                break
            if len(picked) >= limit:
                break
        if picked:
            return [
                '- 확산형 강한 테마는 아직 약함',
                '- 주도 섹터: ' + ', '.join(picked),
            ]
        return [
            '- 확산형 강한 테마는 아직 약함',
            '- 개별 주도주 중심',
        ]

    def stock_leader_lines(limit=4, exclude_codes=None, only_mark='+'):
        rows=[]; picked=[]; exclude_codes=set(exclude_codes or [])
        ranked_stocks=sorted(usable, key=stock_sort_key, reverse=True)
        passes=[
            (True, only_mark),      # preferred: rising leaders outside already displayed theme members
            (True, None),           # fallback: strongest non-theme individual names
        ]
        seen_codes=set()
        for respect_exclude, mark in passes:
            if len(picked) >= limit:
                break
            for x in ranked_stocks:
                code=x.get('code') or ''
                if code and code in seen_codes:
                    continue
                if respect_exclude and code and code in exclude_codes:
                    continue
                if mark and price_mark(x) != mark:
                    continue
                picked.append(x)
                if code:
                    seen_codes.add(code)
                if len(picked) >= limit:
                    break
        for x in picked:
            flow=flow_for(x)
            themes=[t for t in x.get('themes', []) if t and t != '기타'][:3]
            rows.extend([
                f'- {x["name"]}: {price_label(x)}',
                '  - 테마: {}'.format(', '.join(themes) if themes else '기타'),
                f'  - 수급: {flow_text(flow)}',
                f'  - 이슈: {issue_for(x)}',
            ])
        return rows or ['- 주요 종목: 등락률 확인불가', '  - 테마: 기타', '  - 수급: 외인 확인불가 / 기관 확인불가 / 프로그램 확인불가', '  - 이슈: 관련 종목뉴스 확인불가']

    def mixed_reference_lines(limit=3, exclude_codes=None):
        rows=[]; exclude_codes=set(exclude_codes or [])
        def ref_key(x):
            return (abs(pct_value(x)), int(x.get('score') or 0), len(x.get('bits') or []))
        for x in sorted(usable, key=ref_key, reverse=True):
            code=x.get('code') or ''
            if code and code in exclude_codes:
                continue
            if price_mark(x) != '-':
                continue
            flow=flow_for(x)
            rows.extend([
                f'- {x["name"]}: {price_label(x)}',
                f'  - 수급: {flow_text(flow)}',
                f'  - 이슈: {issue_for(x)}',
            ])
            if sum(1 for line in rows if line.startswith('- ') and not line.startswith('- 없음')) >= limit:
                break
        return rows or ['- 없음', '  - 참고: 강한/약한 테마 외 하락 참고 종목 없음']

    # Prefetch quotes for displayed/ranked candidates before broader theme
    # breadth scans consume quote budget. Rank rows often already carry price
    # data, but some flow-ranked names (for example KOSDAQ leaders) need a
    # direct quote to avoid false "확인불가" in the final alert.
    for x in usable:
        metrics=x.get('metrics') if isinstance(x.get('metrics'), dict) else {}
        if parse_pct_value(x.get('change_pct')) is None and parse_pct_value(metrics.get('change_pct')) is None:
            quote_info_for(x)

    candidate_by_code={x.get('code'): x for x in usable if x.get('code')}
    candidate_theme_order=[]
    for g in ranked:
        theme=g.get('theme')
        if theme and theme != '기타' and theme not in candidate_theme_order:
            candidate_theme_order.append(theme)

    def member_row(theme, member):
        code=clean_code(member.get('code') if isinstance(member, dict) else '')
        name=str((member.get('name') if isinstance(member, dict) else '') or code).strip()
        base=candidate_by_code.get(code)
        if base:
            row=dict(base)
            row['themes']=list(dict.fromkeys([theme, *[t for t in row.get('themes', []) if t != theme]]))
            return row
        return {'raw':{}, 'code':code, 'name':name, 'score':0, 'metrics':{}, 'bits':[], 'themes':[theme]}

    def pct_value(x):
        pct=price_change_pct(x)
        return pct if pct is not None else 0.0

    def theme_universe_rows(theme, fallback_members):
        members=THEME_MEMBERS.get(theme) or []
        rows=[]; seen=set()
        for member in members:
            row=member_row(theme, member)
            code=row.get('code')
            if not code or code in seen:
                continue
            seen.add(code); rows.append(row)
        if rows:
            return rows
        for member in fallback_members or []:
            code=member.get('code')
            if not code or code in seen:
                continue
            seen.add(code); rows.append(member)
        return rows

    fallback_by_theme={g.get('theme'): g.get('members', []) for g in ranked}

    def breadth_group(theme):
        rows=theme_universe_rows(theme, fallback_by_theme.get(theme, []))
        if not rows:
            return None
        # Use the filtered display universe for breadth. The raw config count can include
        # ETF/ETN/leveraged/inverse rows that are intentionally skipped in alerts; using
        # the raw count makes valid strong/weak themes disappear.
        universe=len(rows)
        required=(universe // 2 + 1) if universe else 0
        up=[r for r in rows if price_mark(r) == '+']
        down=[r for r in rows if price_mark(r) == '-']
        def up_key(r):
            return (1 if r.get('code') in candidate_by_code else 0, int(r.get('score') or 0), pct_value(r))
        def down_key(r):
            return (1 if r.get('code') in candidate_by_code else 0, int(r.get('score') or 0), abs(pct_value(r)))
        up.sort(key=up_key, reverse=True)
        down.sort(key=down_key, reverse=True)
        return {
            'theme': theme,
            'universe_count': universe,
            'majority_required': required,
            'up_count': len(up),
            'down_count': len(down),
            'up_members': up,
            'down_members': down,
        }

    strong=[]; weak=[]; breadth_groups=[]
    for theme in candidate_theme_order:
        g=breadth_group(theme)
        if not g:
            continue
        breadth_groups.append(g)
        universe=int(g.get('universe_count') or 0)
        required=int(g.get('majority_required') or 0)
        if universe >= 3 and required and g['up_count'] >= required:
            gg={'theme': g['theme'], 'members': g['up_members'], 'count': g['up_count']}
            gg['_sort']=(g['up_count']/max(1, universe), g['up_count'], pct_value(g['up_members'][0]) if g['up_members'] else 0)
            strong.append(gg)
        if universe >= 3 and required and g['down_count'] >= required:
            gg={'theme': g['theme'], 'members': g['down_members'], 'count': g['down_count']}
            gg['_sort']=(g['down_count']/max(1, universe), g['down_count'], abs(pct_value(g['down_members'][0])) if g['down_members'] else 0)
            weak.append(gg)
    strong.sort(key=lambda g:g.get('_sort', (0,0,0)), reverse=True)
    weak.sort(key=lambda g:g.get('_sort', (0,0,0)), reverse=True)

    def movers_summary(members, limit=3):
        rows=[]
        for x in members[:limit]:
            name=str(x.get('name') or x.get('code') or '').strip()
            if not name:
                continue
            rows.append(f'{name}: {price_label(x)}')
        return ', '.join(rows) if rows else '대표 종목 확인불가'

    def no_theme_lines(direction, limit=2):
        if direction == '+':
            contenders=[g for g in breadth_groups if int(g.get('up_count') or 0) > 0]
            contenders.sort(key=lambda g:(int(g.get('up_count') or 0), int(g.get('universe_count') or 0), pct_value((g.get('up_members') or [{}])[0])), reverse=True)
            lines=['- 없음']
            for g in contenders[:limit]:
                lines.append('  - 참고: {theme}: 상승 {up}/{total}, 하락 {down}/{total} / 대표: {movers}'.format(
                    theme=g.get('theme') or '기타',
                    up=int(g.get('up_count') or 0),
                    down=int(g.get('down_count') or 0),
                    total=int(g.get('universe_count') or 0),
                    movers=movers_summary(g.get('up_members') or []),
                ))
            if len(lines) == 1:
                lines.append('  - 참고: 테마 단위 상승 대표 종목 없음')
            return lines
        contenders=[g for g in breadth_groups if int(g.get('down_count') or 0) > 0]
        contenders.sort(key=lambda g:(int(g.get('down_count') or 0), int(g.get('universe_count') or 0), abs(pct_value((g.get('down_members') or [{}])[0]))), reverse=True)
        lines=['- 없음']
        for g in contenders[:limit]:
            lines.append('  - 참고: {theme}: 하락 {down}/{total}, 상승 {up}/{total} / 대표: {movers}'.format(
                theme=g.get('theme') or '기타',
                down=int(g.get('down_count') or 0),
                up=int(g.get('up_count') or 0),
                total=int(g.get('universe_count') or 0),
                movers=movers_summary(g.get('down_members') or []),
            ))
        if len(lines) == 1:
            lines.append('  - 참고: 테마 단위 하락 대표 종목 없음')
        return lines

    def section_theme_lines(groups, direction='+'):
        lines=[]
        emitted_roots=set()
        root_groups={}
        for g in groups:
            root=root_theme_name(g.get('theme'))
            if root:
                root_groups.setdefault(root, []).append(g)
        for g in groups:
            root=root_theme_name(g.get('theme'))
            siblings=root_groups.get(root, [])
            if len(siblings) >= 2 and root not in emitted_roots:
                if lines:
                    lines.append('')
                lines.extend(root_theme_lines(root, siblings, direction))
                emitted_roots.add(root)
                continue
            if len(siblings) >= 2:
                continue
            if lines:
                lines.append('')
            lines.extend(theme_lines(g, 3, direction))
        return lines

    strong_display=strong[:MAX_STRONG_THEMES]
    strong_lines=section_theme_lines(strong_display, '+')
    if not strong_lines:
        strong_lines=no_theme_lines('+')

    weak_lines=[]
    strong_theme_names={g.get('theme') for g in strong_display}
    weak_display=[x for x in weak if x.get('theme') not in strong_theme_names][:MAX_WEAK_THEMES]
    weak_lines=section_theme_lines(weak_display, '-')
    if not weak_lines:
        weak_lines=no_theme_lines('-')

    theme_used_codes={m.get('code') for g in [*strong_display, *weak_display] for m in g.get('members', []) if m.get('code')}
    leader_lines=stock_leader_lines(4, exclude_codes=theme_used_codes, only_mark='+')
    text = chr(10).join([
        f'국장 {now}',
        index_line,
        '',
        '1) 강한 테마',
        *strong_lines[:STRONG_SECTION_LINE_LIMIT],
        '',
        '2) 약한 테마',
        *weak_lines[:WEAK_SECTION_LINE_LIMIT],
        '',
        '3) 개별 주도주',
        *leader_lines[:24],
        '',
    ]).strip()
    write_issue_candidates_sidecar(text)
    return text

def main() -> int:
    try:
        text = build_regular_text()
        CACHE.write_text(text, encoding="utf-8")
        print(text, flush=True)
    except Exception as exc:
        import traceback
        ERRLOG.write_text(traceback.format_exc(), encoding="utf-8")
        now = datetime.now().strftime("%H:%M")
        print(
            chr(10).join([
                f"국장 {now}",
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
