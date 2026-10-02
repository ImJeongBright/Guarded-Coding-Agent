# ADR 0001 — Deterministic Policy at the Execution Boundary

- Status: Accepted

## Context

코딩 에이전트에게 "이 작업은 하지 마라"라고 instruction을 줄 수 있다. 그러나 중요한 side effect의 실행 여부를 모델의 지시 준수에만 의존하면 모델이 잘못 판단하거나 prompt injection의 영향을 받을 때 실제 변경이 발생할 수 있다.

## Decision

중요한 권한 판단은 tool execution 직전의 deterministic Policy Engine이 수행한다.

LLM은 다음을 할 수 있다.

- 작업 의도 해석
- 필요한 action 제안
- 실패 이유를 읽고 대안 제시

LLM은 다음을 최종 결정하지 않는다.

- workspace 밖 write 허용
- secret 접근 허용
- remote push 승인
- force push 허용
- policy 우회 허용

## Consequences

장점:

- 모델이 잘못 판단해도 선언된 경계를 강제할 수 있다.
- 정책을 단위 테스트할 수 있다.
- 동일 입력의 정책 결과가 재현 가능하다.

비용:

- 정책 엔진이 잘못 구현되면 새로운 단일 실패 지점이 된다.
- 일부 복잡한 action은 deterministic하게 분류하기 어렵다.
- 너무 엄격하면 Agent 사용성이 낮아진다.

## Rule

> LLM interprets intent; the program enforces authority.
