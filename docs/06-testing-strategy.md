# Testing Strategy

## 1. 목적

이 프로젝트에서 테스트는 부가 기능이 아니라 핵심 산출물이다.

정책 엔진이 "안전해 보인다"는 설명보다, 특정 행동이 실제로 허용·승인·차단되는지를 반복 검증할 수 있어야 한다.

## 2. 테스트 계층

### L1. Pure Policy Unit Tests

OS side effect 없이 normalized action → decision을 검증한다.

예:

- workspace read → ALLOW
- external write → DENY
- git push → REQUIRE_APPROVAL
- force push → DENY
- unknown action → DENY

각 rule은 최소 하나의 positive/negative test를 가진다.

### L2. Normalization Tests

정책보다 먼저 깨질 수 있는 입력 정규화를 검증한다.

필수:

- relative path
- ..
- absolute path
- unicode/space path
- non-existent target
- symlink
- nested symlink
- cwd change
- Git remote/branch normalization

### L3. Adapter Integration Tests

temp directory와 temp Git repository에서 실제 adapter를 실행한다.

검증:

- ALLOW는 실제 실행됨
- DENY는 side effect가 없음
- APPROVAL 전에는 실행되지 않음
- 승인 후 정확한 action만 실행됨
- audit event 생성

### L4. Adversarial Scenario Tests

docs/05-threat-model.md의 T01~T15를 executable test case로 유지한다.

새로운 우회가 발견되면:

1. 실패하는 regression test 추가
2. 수정
3. 전체 scenario suite 재실행

순서를 지킨다.

### L5. Dogfooding Regression

실제 repository에서 사용하다가 정책 문제를 발견하면 익명화/축소된 fixture로 회귀 테스트를 만든다.

## 3. MVP Scenario Matrix

최소 다음 시나리오를 자동화한다.

| ID | Surface | Scenario | Expected |
|---|---|---|---|
| FS-01 | FS | workspace read | ALLOW |
| FS-02 | FS | workspace write | ALLOW |
| FS-03 | FS | ../ outside write | DENY |
| FS-04 | FS | symlink → outside | DENY |
| FS-05 | FS | .env read | DENY |
| FS-06 | FS | policy file write | DENY |
| SH-01 | Shell | approved test command | ALLOW |
| SH-02 | Shell | unknown command | DENY |
| SH-03 | Shell | command chaining | DENY |
| SH-04 | Shell | nested shell | DENY |
| SH-05 | Shell | redirection outside | DENY |
| GT-01 | Git | status | ALLOW |
| GT-02 | Git | diff | ALLOW |
| GT-03 | Git | commit | ALLOW or configured |
| GT-04 | Git | push | REQUIRE_APPROVAL |
| GT-05 | Git | force push | DENY |
| AP-01 | Approval | exact approved action | EXECUTE |
| AP-02 | Approval | changed args | DENY |
| AP-03 | Approval | expired approval | DENY |
| AP-04 | Approval | replay other run | DENY |
| AU-01 | Audit | normal event | RECORDED |
| AU-02 | Audit | secret-like value | REDACTED |

## 4. 안전한 테스트 원칙

- destructive test는 temp directory/temp repository에서만 수행한다.
- 실제 remote push는 테스트용 bare local remote를 사용한다.
- 실제 home directory의 .ssh/.env를 읽지 않는다.
- secret fixture는 가짜 token을 사용한다.
- rm -rf 같은 시나리오는 policy decision을 검증하되 실제 사용자 경로에서 실행하지 않는다.

## 5. 회귀 정책

모든 변경은 최소 다음을 통과해야 한다.

~~~text
unit
→ normalization
→ integration
→ adversarial scenario
~~~

정책 완화 PR은 해당 ALLOW를 정당화하는 신규 테스트를 반드시 포함한다.

## 6. 테스트 결과 기록

docs/exec에 실행별로 다음을 남긴다.

~~~text
date
commit
policy_version
test counts
pass/fail
new regression scenarios
known failures
environment
~~~

## 7. 테스트를 계속 돌리는 방식

초기에는 기능별로 짧은 suite를 자주 실행한다.

- parser/normalizer 변경 → normalization + policy
- policy 변경 → full policy + adversarial
- executor 변경 → integration + adversarial
- approval 변경 → approval + integration
- release candidate → full suite

CI가 생기면 main 기준 full suite를 자동 실행한다.
