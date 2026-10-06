# Product Requirements Document

## 1. 제품 요약

Guarded Coding Agent는 코딩 에이전트의 Filesystem, Shell, Git tool call을 실행 전에 검사하고 정책에 따라 ALLOW / REQUIRE_APPROVAL / DENY로 결정하는 로컬 실행 계층이다.

## 2. MVP 사용자 흐름

1. 사용자가 workspace와 작업을 지정한다.
2. Agent가 필요한 도구 호출을 제안한다.
3. Gateway가 입력을 정규화한다.
4. Policy Engine이 정책을 평가한다.
5. ALLOW면 즉시 실행한다.
6. REQUIRE_APPROVAL이면 실제 실행될 정규화된 행동을 사용자에게 표시한다.
7. 사용자가 승인하면 같은 행동인지 재검증한 뒤 실행한다.
8. DENY면 실행하지 않고 이유를 Agent에 반환한다.
9. 모든 결정과 실행 결과를 audit log에 기록한다.

## 3. MVP 기능 요구사항

### FR-01 Workspace Boundary

- 실행 시작 시 workspace root를 고정한다.
- 상대 경로, .., symbolic link 등을 정규화한 실제 대상 경로를 검사한다.
- workspace 밖 write는 기본 DENY다.
- workspace 밖 read는 기본 DENY이며 명시적 정책으로만 완화한다.

### FR-02 Filesystem Policy

최소 지원:

- read
- create
- update
- delete

기본 정책:

- workspace 내부 일반 source/config read: ALLOW
- workspace 내부 일반 source write: ALLOW
- 정책 파일 수정: DENY
- .env, credential, SSH key 등 민감 파일: DENY
- workspace 외부 write: DENY
- 대량 삭제: REQUIRE_APPROVAL 또는 DENY

### FR-03 Shell Policy

- 실제 실행 argv 또는 파싱된 command representation을 정책 입력으로 사용한다.
- build/test/lint 등 명시된 개발 명령은 ALLOW 가능하다.
- destructive command는 DENY 또는 REQUIRE_APPROVAL이다.
- shell chaining, redirection, subshell 등 정책 우회 요소를 식별하지 못하면 fail closed 한다.
- 단순 문자열 contains 검사만으로 안전을 판정하지 않는다.

### FR-04 Git Policy

최소 지원:

- status
- diff
- log
- add
- commit
- push

기본 예시:

- status/diff/log: ALLOW
- add/commit: ALLOW
- push: REQUIRE_APPROVAL
- force push: DENY
- protected branch에 직접 destructive rewrite: DENY

### FR-05 Approval Binding

승인은 최소한 다음과 결합한다.

- tool
- normalized arguments
- workspace identity
- policy version
- 필요 시 repository/branch state
- expiry

승인 후 인자가 변경되면 기존 승인을 재사용하지 않는다.

### FR-06 Audit

각 정책 결정에 다음을 기록한다.

- timestamp
- run id
- tool
- normalized action
- decision
- matched rule
- approval id
- execution result

민감 값은 원문 그대로 기록하지 않는다.

### FR-07 Policy Immutability

실행 중 Agent가 policy config, approval store, audit integrity 설정을 임의로 변경할 수 없어야 한다.

### FR-08 Fail Closed

파싱 실패, 알 수 없는 action, 정책 평가 오류에서는 기본 DENY한다.

## 4. 비기능 요구사항

### NFR-01 Determinism

같은 정규화 입력과 같은 policy version은 같은 결정을 내린다.

### NFR-02 Explainability

모든 결정은 사람이 이해할 수 있는 rule id와 reason을 가진다.

### NFR-03 Testability

정책 엔진은 실제 shell/git 실행 없이도 pure decision test가 가능해야 한다.

### NFR-04 Low Friction

정상적인 read/build/test/source edit는 반복 승인을 최소화한다.

### NFR-05 Local First

MVP는 로컬에서 동작하며 외부 서버를 필수로 요구하지 않는다.

## 5. MVP 완료 기준

- Filesystem/Shell/Git adapter가 모두 policy gateway를 통과한다.
- ALLOW / REQUIRE_APPROVAL / DENY가 실제로 동작한다.
- 승인 replay 또는 argument substitution이 차단된다.
- workspace escape, symlink escape, secret access, force push가 테스트된다.
- 정상적인 작은 코딩 작업을 실제 repository에서 수행한다.
- audit log가 생성된다.
- 전체 테스트가 반복 실행 가능하다.

## 2026-10-03 구현 Profile

Guard 자체는 외부 API/key/SaaS를 사용하지 않는다. 모델 통신은 기존 coding agent의 역할이다.
FR-03은 exact argv/cwd, command별 write_paths, clean env, macOS sandbox-exec를 함께 적용한다.
write_paths 기본은 비어 있으며 workspace 전체 쓰기는 등록할 수 없다. FR-07의 runtime/launcher/state
보호는 FS와 child sandbox에 적용한다. CLI/stdio MCP는 구현됐고 live host와 장기 사용 판정은 미검증이다.
