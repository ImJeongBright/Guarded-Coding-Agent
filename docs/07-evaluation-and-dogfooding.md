# Evaluation and Dogfooding

## 1. 평가 목적

이 프로젝트는 특정 숫자를 만들기 위한 벤치마크가 아니다.

가장 중요한 질문은 다음이다.

> 실제 개발에서 Agent에게 더 많은 작업을 맡기면서도, 사람이 계속 tool call을 감시하지 않아도 될 만큼 경계가 명확한가?

## 2. 두 종류의 검증을 구분한다

### 기능 검증

설계한 정책이 정확히 동작하는가.

필수:

- 위험 행동 차단
- 승인 대기
- 승인 binding
- audit
- 정상 행동 허용

이 영역은 정량적 생산성 지표가 없어도 된다.

### 비교 주장 검증

다음과 같은 표현을 하고 싶다면 측정해야 한다.

- 생산성이 향상됐다
- 사람 개입이 줄었다
- 더 안전하다
- token을 줄였다
- 작업 시간이 줄었다

측정하지 않았다면 이런 비교형 표현을 사용하지 않는다.

## 3. Dogfooding 방식

최소 1~2주의 실제 개발에서 사용한다.

작업 예:

- 작은 bug fix
- 테스트 추가
- refactor
- config 수정
- dependency update
- 문서/코드 동시 변경

특정 포트폴리오 repository 하나만을 위해 정책을 맞추지 말고 여러 저장소에서 사용한다.

## 4. 실제 사용 로그

각 run에 다음을 기록한다.

~~~text
task
repository
policy_version

allowed actions
approval actions
denied actions

false positive
false negative / policy gap
manual override

final outcome
notes
~~~

개인 정보나 secret은 기록하지 않는다.

## 5. 관찰할 핵심 현상

### A. Approval Fatigue

승인이 너무 많아서 Agent 사용성이 떨어지는가?

예:

- 모든 write approval은 과도한가?
- commit approval은 필요한가?
- push approval은 계속 유지할 가치가 있는가?

### B. Over-permission

편의를 위해 ALLOW한 규칙이 실제로 예상보다 넓은가?

### C. Policy Gap

Agent가 새로운 방식으로 같은 위험 행동을 제안해 기존 rule을 우회하는가?

### D. Explainability

사용자가 DENY/APPROVAL 이유를 즉시 이해할 수 있는가?

### E. Recovery

DENY된 뒤 Agent가 정상적인 대안으로 작업을 계속할 수 있는가?

## 6. 정책 변경 기록

Dogfooding 중 policy를 바꿀 때 다음 형식을 권장한다.

~~~text
Observed:
모든 source write approval이 지나치게 자주 발생했다.

Decision:
workspace 내부 일반 source write는 ALLOW.

Boundary:
workspace 밖 write, secret, policy files는 계속 DENY.

Evidence:
실제 run N건에서 반복 승인 발생.

Regression:
inside-write allowed / outside-write denied scenario 추가.
~~~

이 기록이 프로젝트의 핵심 엔지니어링 서사가 된다.

## 7. 선택적 지표

필수 성과 지표는 아니지만 실제로 측정 가능하면 다음을 기록한다.

- tool call count
- allow/approval/deny count
- approval rate
- false-positive policy count
- policy-induced failed task count
- task completion
- elapsed time

"안전성 X% 개선"처럼 정의가 모호한 단일 점수는 만들지 않는다.

## 8. Portfolio Evidence

최종적으로 보여줄 evidence는 다음 정도면 충분하다.

1. 정책 아키텍처
2. 실제 ALLOW / APPROVAL / DENY 예시
3. adversarial scenario test
4. Dogfooding 중 정책을 변경한 2~3개 의사결정
5. 한계와 우회 가능성
6. 실제 개발에 사용한 기록

핵심 메시지:

> AI에게 더 많은 일을 위임하기 위해 모델의 지시 준수와 실제 실행 권한을 분리하고, reversible한 작업은 자동화하면서 위험 side effect는 승인·차단하는 경계를 설계했다.
