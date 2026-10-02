# Tool Contracts

## 1. 목적

Tool adapter는 Agent의 자유형 출력을 실제 시스템 호출로 직접 연결하지 않는다. 모든 요청을 명확한 schema로 변환한 뒤 Policy Gateway를 통과시킨다.

각 tool은 다음 계약을 가진다.

~~~text
Agent Request
→ Schema Validation
→ Normalization
→ Policy Decision
→ Optional Approval
→ Execution
→ Result + Audit
~~~

## 2. 공통 ToolRequest

권장 공통 필드:

~~~json
{
  "run_id": "run-...",
  "tool": "filesystem|shell|git",
  "operation": "...",
  "workspace": "/canonical/workspace",
  "arguments": {},
  "requested_by": "coding-agent"
}
~~~

Agent가 결정 필드나 trusted metadata를 임의로 제공하지 못하도록 구분한다.

예:

- policy_version: 시스템이 주입
- workspace_id: 시스템이 주입
- approval_id: Approval Manager가 발급
- current_branch: executor가 직접 조회

## 3. Filesystem Contract

### 지원 연산

- read
- list
- create
- update
- delete

### 입력 정규화

반드시 다음을 수행한다.

1. workspace root canonicalize
2. requested path를 workspace 기준으로 resolve
3. .. 제거 후 canonical path 계산
4. symlink가 있으면 최종 target 확인
5. 대상이 존재하지 않는 create의 경우 가장 가까운 존재 ancestor부터 boundary 확인
6. sensitive path classification

### 실행 전 재검증

판정과 실행 사이에 symlink가 바뀔 수 있으므로 write/delete 직전에 target을 다시 확인한다.

### 금지 예시

- ../../outside
- workspace 내부 symlink → ~/.ssh
- .env
- credential 파일
- policy storage
- approval store

## 4. Shell Contract

Shell은 가장 넓은 권한을 가질 수 있으므로 MVP에서 보수적으로 처리한다.

### 권장 입력

가능하면 raw shell string보다:

~~~json
{
  "executable": "pytest",
  "argv": ["-q"],
  "cwd": "/workspace"
}
~~~

처럼 구조화한다.

### 주의 대상

- ;
- &&
- ||
- |
- >
- >>
- $()
- backtick substitution
- eval
- sh -c
- bash -c
- env 변경을 통한 실행 우회
- absolute executable path
- PATH shadowing

MVP parser가 의미를 안전하게 보존할 수 없는 경우 DENY한다.

### 초기 allow 후보

프로젝트별 allowlist로 관리한다.

예:

- pytest
- npm test
- npm run lint
- gradle test
- mvn test
- git이 아닌 별도 build command

명령 이름만 보고 허용하지 말고 cwd와 argv도 함께 판정한다.

## 5. Git Contract

Git은 local state와 remote side effect를 구분한다.

### Read-only

- status
- diff
- log
- show
- branch 조회

기본 ALLOW 후보.

### Local mutation

- add
- commit
- restore 일부
- branch 생성

MVP에서는 허용 범위를 좁게 시작한다.

### Remote mutation

- push
- tag push
- delete remote branch

기본 REQUIRE_APPROVAL.

### Explicit DENY 후보

- push --force
- push --force-with-lease to protected branch
- reset --hard가 승인되지 않은 작업을 삭제하는 경우
- clean -fdx
- 정책상 protected branch history rewrite

## 6. Result Contract

도구 결과는 다음을 분리한다.

~~~text
decision
matched_rule
executed
exit_code
stdout_summary
stderr_summary
changed_targets
approval_id
audit_event_id
~~~

Agent에게 raw secret이 노출되지 않도록 결과도 redaction한다.

## 7. Adapter 구현 규칙

- Policy Gateway를 우회하는 direct executor API를 외부에 노출하지 않는다.
- 실제 실행 함수는 trusted package 내부에 둔다.
- adapter 테스트에서는 fake executor를 주입할 수 있어야 한다.
- 정책 판정 unit test는 OS side effect 없이 수행 가능해야 한다.
