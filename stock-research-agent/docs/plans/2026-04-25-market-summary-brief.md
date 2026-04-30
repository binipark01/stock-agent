# Market Summary Brief Implementation Plan

> For Hermes: follow TDD. Write the failing test first, verify failure, then implement the smallest code that passes.

Goal: brief 모드와 DB 기반 브리핑 상단에 Perplexity-style 한줄 Market Summary를 추가한다.

Architecture:
- 기존 Toss/SaveTicker 저장 데이터를 재조합해 상단용 summary line을 만든다.
- 새 외부 API는 붙이지 않고 현재 DB evidence만 사용한다.
- summary line은 tone + 핵심 지수/헤드라인 + source_count를 포함한다.

Tech Stack: Python, sqlite repository helpers, unittest

Assumptions:
- "Perplexity+Toss 혼합형"은 Perplexity 답변 스타일의 상단 요약 포맷을 뜻하고, 실제 데이터는 현재 저장된 Toss/SaveTicker evidence를 활용한다.
- source_count는 Market Summary를 만들 때 실제 사용한 evidence row 개수다.

Tasks:
1. tests/test_main.py에 brief focus 첫 줄이 Market Summary인지 검증하는 failing test 추가
2. tests/test_main.py에 build_brief_from_db 텍스트에 [Market Summary] 섹션과 source_count가 포함되는 failing test 추가
3. src/main.py에 build_market_summary helper 추가
4. brief mode에서 focus 맨 앞에 Market Summary line prepend
5. build_brief_from_db에서 [Market Summary] 섹션을 상단에 삽입
6. targeted tests -> full suite 검증

Expected output shape:
- build_response(... mode=brief)["focus"][0]
  Market Summary: risk_off | 나스닥 -0.88%, S&P 500 -0.41% | 핵심뉴스: ... | source_count=4
- build_brief_from_db(...)
  [시장 브리핑]
  [Market Summary]
  - risk_off | ... | source_count=4

Verification commands:
- python3 -m unittest tests.test_main.StockResearchAgentTest.test_brief_mode_prepends_market_summary_with_source_count
- python3 -m unittest tests.test_main.StockResearchAgentTest.test_build_brief_from_db_uses_stored_data
- python3 -m unittest discover -s tests -p 'test_*.py'
