# Agents

이 저장소는 D:\Agents 아래에서 관리하는 개인 에이전트 작업공간이다.

## 목적
- 여러 에이전트 프로젝트를 한 곳에서 관리
- 공용 템플릿과 공유 자산 재사용
- 다른 컴퓨터로 Git clone 후 빠르게 복구 가능하게 유지

## 구조
- `_templates/` : 새 에이전트 시작 템플릿
- `_shared/` : 공용 프롬프트, 스크립트, 유틸
- `_archive/` : 중단/보관 프로젝트
- `_lab/` : 빠른 실험/프로토타입
- `<agent-name>/` : 실제 에이전트 프로젝트

## 규칙
- 에이전트 이름은 `kebab-case` 사용
- 비밀값은 `.env`에 두고 `.env.example`만 커밋
- 캐시/로그/산출물은 Git에 넣지 않기
- 가능하면 절대경로 대신 상대경로 사용

## 새 에이전트 만드는 순서
1. `_templates/agent-template`를 복사해서 새 폴더 생성
2. 프로젝트 이름에 맞게 `README.md`, `AGENT.md`, `config/default.yaml` 수정
3. 의존성 파일(`requirements.txt` 또는 `package.json`) 추가
4. `.env.example` 정리
5. 필요하면 개별 repo 분리, 아니면 monorepo 안에서 계속 관리

예시:
- `research-agent`
- `coding-agent`
- `personal-ops-agent`
- `market-watcher`
