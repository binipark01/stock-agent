# US multi-agent prompts

미장 에이전트별 LLM 프롬프트를 관리한다.

구조:

```text
prompts/us_agents/<agent_name>/system.md
prompts/us_agents/<agent_name>/user.md
```

원칙:
- `system.md`: 해당 에이전트의 고정 역할, 금지사항, 출력 계약.
- `user.md`: 실행 시점 데이터와 함께 들어가는 일반 프롬프트 템플릿.
- 템플릿 변수는 `{{NAME}}` 형식으로 둔다.

현재 변수:
- `{{MIN_LEADERS}}`
- `{{MAX_LEADERS}}`
- `{{REQUEST_PAYLOAD_JSON}}`

현재 에이전트:
- `theme_leader_reranker`: 미장 테마별 대장주 후보를 LLM으로 3~5개 재선정한다.
