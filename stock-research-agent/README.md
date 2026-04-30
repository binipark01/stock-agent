# stock-research-agent

해외주식, 특히 미국주식을 메인으로 두고 주식/시장/포트폴리오 관련 요청을 투자 판단 보조용으로 구조화하는 로컬 에이전트.

## 현재 되는 것
- 미국주식 메인 워치리스트 기준으로 요청 해석
- 미국장 브리핑, 리스크 체크, 소셜/뉴스 감시 포인트 제안
- 강세/약세/촉매/리스크 4축 요약
- Yahoo Finance 기반 가격 저장 + seed 뉴스 저장
- yfinance가 설치되어 있으면 가격/히스토리 fallback으로 자동 사용
- yfinance optional pack: quote/options/fundamentals/news/calendar/holders/actions/recommendations 요약
- SEC/EDGAR 최근 공시 요약: 8-K/10-Q/10-K/S-3 등 form 분류와 SEC filing URL 제공
- Fincept식 DataHub-lite topic hub: quote/news/filing/options/social/earnings topic list + 캐시 peek
- Yahoo quote page 기반 실제 미국 실적일 파싱 + fallback seed 일정 저장
- 토스증권 공개 미국지수/미국뉴스 보조지표 저장
- SaveTicker 속보 수집 및 티커/루머 분류
- Earnings Preview Pack 생성
- 실행 가능한 다음 액션 제안

## 기본 메인 워치리스트
기본값은 `config/watchlist.json` 에서 읽습니다.

현재 기본값:
- NVDA
- MSFT
- AMZN
- META
- GOOGL
- TSLA

## 실행
```bash
cd /mnt/d/Agents/stock-research-agent
python3 -m pip install --user --break-system-packages -r requirements.txt  # WSL user-site 설치
python3 src/main.py "NVDA랑 TSLA 오늘 체크포인트 정리해줘"
python3 src/main.py --mode brief "오늘 뭐 봐야 해?"   # watchlist.json 기준
python3 src/main.py --mode saveticker_sync "SaveTicker 미국주 속보 수집"
python3 src/main.py --mode toss_sync "토스 미국지수 뉴스 수집"
python3 src/main.py --mode ingest "NVDA MSFT AMZN 데이터 수집"
python3 src/main.py --mode brief "NVDA MSFT 장전 브리핑 만들어줘"
python3 src/main.py --mode earnings "MSFT AMZN 이번 실적 일정 보여줘"
python3 src/main.py --mode earnings_preview "NVDA MSFT 실적 프리뷰 만들어줘"
python3 src/main.py --mode yfinance_pack "NVDA yfinance 싹 가져와"
python3 src/main.py --mode sec_filings "NVDA 최근 8-K 10-Q 공시 요약"
python3 src/main.py --mode topic_hub "NVDA topic hub 보여줘"
python3 src/main.py --mode brief "NVDA 브리핑 yfinance 옵션도"
python3 src/main.py --json '{"mode":"brief","symbols":["NVDA","MSFT","AMZN"],"portfolio":["NVDA"],"request":"미국장 브리핑 만들어줘"}'
```

## 참고 repo 적용 메모
- 상세 메모: `docs/REFERENCE_REPOS.md`
- 현재 반영 완료: SEC/EDGAR mode, DataHub-lite topic hub mode
- 다음 후보: TradingAgents식 분석위원회, PyPortfolioOpt/Riskfolio식 포트폴리오 리스크, alert backtest
- 라이선스 주의: FinceptTerminal/OpenBB는 AGPL 계열이라 코드 복붙 금지, UX/아키텍처만 참고

## 다음 확장 후보
1. TradingView webhook → 텔레그램 자동 전송
2. 실제 뉴스 API 연결
3. Threads/소셜 시그널 고도화
4. 포트폴리오 thesis guard 연결
5. 토스증권 커뮤니티/스크리너까지 확장
6. NASDAQ/NDX/US100 같은 지수 알림 전용 처리 — 보류
7. FinceptTerminal은 통합 대상이 아니라 기능 참고용: AGPL-3.0/상용 라이선스라 코드 복붙 금지, equity research/portfolio/news UX만 참고
