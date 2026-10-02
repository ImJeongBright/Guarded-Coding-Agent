# ADR 0002 — ALLOW / REQUIRE_APPROVAL / DENY

- Status: Accepted

## Context

정책 결과를 단순 allow/deny로 만들면 두 문제가 생긴다.

1. 위험한 작업을 전부 deny하면 Agent가 실제 개발에 쓸 수 없다.
2. 편의를 위해 allow 범위를 넓히면 외부 side effect까지 자동 실행될 수 있다.

## Decision

정책 결과를 세 단계로 둔다.

### ALLOW

낮은 위험이며 자동 실행 가능한 action.

### REQUIRE_APPROVAL

사용자 의도에 따라 필요한 작업일 수 있지만 외부 영향이 크거나 범위가 넓은 action.

### DENY

현재 시스템에서 실행을 허용하지 않는 action.

## Examples

- read source: ALLOW
- write source inside workspace: ALLOW
- git push: REQUIRE_APPROVAL
- large delete: REQUIRE_APPROVAL 또는 DENY
- force push: DENY
- secret read: DENY
- policy file mutation: DENY

## Consequences

- 정상 작업의 자동화와 위험 통제를 동시에 표현할 수 있다.
- approval fatigue를 실제 사용에서 관찰해야 한다.
- approval 자체도 replay/substitution 공격에 대비해야 한다.
