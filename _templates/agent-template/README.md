# agent-template

새 에이전트 시작용 기본 템플릿.

## 시작 방법
1. 이 폴더를 새 에이전트 이름으로 복사
2. `AGENT.md`, `README.md`, `config/default.yaml` 수정
3. 필요한 언어에 맞게 `requirements.txt` 또는 `package.json` 추가
4. `.env.example` 채우기

## 포함 구조
- `AGENT.md` : 에이전트 역할/제약/행동 규칙
- `prompts/` : system/developer/task 프롬프트
- `src/` : 실행 코드
- `config/` : 설정
- `tests/` : 테스트
- `scripts/` : 실행/세팅 스크립트
- `data/` : input/output/cache
- `logs/` : 런타임 로그
