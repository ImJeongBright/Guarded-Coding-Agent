# ADR 0003 — Least Privilege and Default Deny

- Status: Accepted

## Context

코딩 에이전트는 편의를 위해 넓은 Filesystem/Shell/Git 권한을 받기 쉽다. 그러나 Agent가 사용하지 않는 capability까지 제공하면 잘못된 tool 선택이나 prompt injection의 영향 범위가 커진다.

## Decision

기본 정책은 최소 권한과 default deny를 따른다.

원칙:

- 필요한 tool만 노출
- 필요한 operation만 허용
- workspace 범위 제한
- secret/policy storage 제외
- unknown tool/action deny
- remote side effect approval
- destructive action deny 우선

## Policy Expansion

권한 완화는 실제 사용상의 필요가 확인된 후 수행한다.

새 ALLOW rule에는 다음이 필요하다.

- 실제로 막힌 정상 task
- 영향 범위 설명
- positive test
- boundary negative test
- 필요 시 rollback plan

## Consequences

초기에는 false positive와 approval friction이 발생할 가능성이 높다.

이는 의도된 출발점이다. Dogfooding으로 과도한 제한을 점진적으로 줄이되, 제한 완화마다 regression test를 남긴다.
