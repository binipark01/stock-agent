# Threads View Miner MVP — @bullish_bee / 양봉업자

목표: @bullish_bee를 첫 번째 스레더 관점 학습 타깃으로 삼아, 단순 언급 수가 아니라 “이 사람이 어떤 논리로 종목을 보는지”를 누적 프로파일링한다.

## 대상

- handle: `bullish_bee`
- display_name: `양봉업자`
- profile: `https://www.threads.com/@bullish_bee`
- seed status: `config/threads_seed_accounts.json`에 이미 포함
- classified status: `trader / high`
- view target config: `config/threads_view_targets.json`

공개 프로필에서 확인된 초기 메타:
- bio: `양봉업자 투자일기 📈 차트 좋아합니다 🍯 양봉 좋아합니다`
- tags: `Investing`, `Content Creators`
- observed followers: `58.1K`
- pinned post 요지: 기술적 분석을 좋아하지만 본인 관점은 참고용이며 맹목 추종은 위험하다고 명시

## 핵심 설계

이 계정은 “뉴스 소스”가 아니라 `persona/view source`로 다룬다.

각 글에서 추출할 항목:

```json
{
  "author_handle": "bullish_bee",
  "symbols": ["IREN"],
  "themes": ["AI infra", "crypto beta"],
  "direction": "bullish | bearish | neutral",
  "horizon": "intraday | swing | medium | long",
  "method": "chart | catalyst | macro | filing | options | narrative | rumor",
  "claim": "핵심 주장 1문장",
  "risk": "무효화/손절/주의 조건",
  "confidence": 0.0,
  "post_url": "...",
  "published_at": "..."
}
```

## 프로필 카드 필드

`author_view_profiles`에 누적할 항목:

- style: 차트/기술적 분석 중심인지, 재료/뉴스 중심인지
- favorite_symbols: 반복 언급 종목
- favorite_themes: 반복 언급 테마
- horizon: 당일/스윙/중기/장기 비중
- setup_patterns: 돌파, 눌림, 지지선, 저항 돌파, 거래량 등
- risk_language: 손절, 무효화, 비중, 추격금지 등 사용 빈도
- bias_tags: momentum_chaser, chart_only, rumor_sensitive 등
- recent_view_summary: 최근 14~30일 관점 요약
- track_record_score: 향후 1D/5D/20D 사후검증으로 계산

## 출력 모드

1. `threads_profile bullish_bee`
   - 양봉업자 스타일/선호 테마/리스크 언어/최근 관점 요약

2. `symbol_social_views IREN`
   - IREN에 대한 양봉업자 포함 seed 계정들의 관점 비교

3. `view_change bullish_bee`
   - 최근 관점 변화: 강세→중립, 추격→눌림, 특정 테마 언급 급증 등

4. `who_to_follow_for 우주`
   - 우주/코인/반도체 등 테마별 유효 계정 랭킹

## MVP 구현 순서

1. `config/threads_view_targets.json`를 읽는 loader 추가
2. Jina/public profile fetch로 target account 최신 글 일부 저장
3. raw post와 해석 분리:
   - `raw_threads_posts`
   - `thread_claims`
   - `author_view_profiles`
   - `author_symbol_stances`
4. claim extraction은 먼저 rule/LLM prompt 혼합으로 시작
5. 결과를 `brief`에 바로 섞지 말고 별도 `Threads View` 섹션으로 표시
6. 가격 사후검증은 나중에 1D/5D/20D로 붙인다

## 해석 원칙

- 스레더 관점은 매수/매도 신호가 아니라 시장 참여자 관점 데이터다.
- 사실/차트/의견/루머를 반드시 분리한다.
- 계정 한 명의 글만으로 alert를 만들지 않는다.
- 종목별 결론은 가격, 뉴스, SEC/공시, 옵션, 섹터 강약과 교차검증한다.
