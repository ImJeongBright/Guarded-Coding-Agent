# Policy Model

## 1. 결정 값

### ALLOW

정책상 자동 실행 가능한 행동.

예:

- workspace 내부 source read
- 명시된 build/test 명령
- git status
- git diff
- workspace 내부 일반 source 수정

### REQUIRE_APPROVAL

정상적인 작업일 수 있지만 side effect의 범위가 크거나 외부 상태를 변경하는 행동.

예:

- git push
- 대량 파일 삭제
- 명시적으로 허용되지 않은 package install
- 정책에 따라 특정 생성/삭제 작업

### DENY

현재 신뢰 경계에서 실행해서는 안 되는 행동.

예:

- workspace 밖 write
- secret/credential 접근
- force push
- policy 파일 변경
- 승인 우회 시도
- 파싱 불가능한 복합 shell command

## 2. 정책 우선순위

가장 제한적인 규칙이 우선한다.

~~~text
explicit DENY
    >
REQUIRE_APPROVAL
    >
explicit ALLOW
    >
default DENY
~~~

ALLOW rule 하나가 존재한다고 더 구체적인 DENY를 덮어쓰면 안 된다.

## 3. 정책 입력

정책 엔진은 자연어 문자열이 아니라 정규화된 구조를 받는다.

예:

~~~json
{
  "actor": "coding-agent",
  "tool": "git",
  "operation": "push",
  "workspace": "/repo",
  "repository": "/repo",
  "branch": "feature/x",
  "remote": "origin",
  "force": false
}
~~~

Filesystem 예:

~~~json
{
  "tool": "filesystem",
  "operation": "write",
  "requested_path": "./src/A.java",
  "resolved_path": "/repo/src/A.java",
  "workspace": "/repo",
  "sensitive": false
}
~~~

## 4. 정책 범주

### Filesystem

판정 요소:

- read/write/delete
- workspace 내부/외부
- canonical path
- symlink target
- sensitive path
- file count / recursive action

### Shell

판정 요소:

- executable
- argv
- working directory
- redirection
- shell chaining
- subshell
- network side effect
- destructive flag

### Git

판정 요소:

- local/remote operation
- branch
- force
- remote
- history rewrite 여부
- protected branch 여부

## 5. 기본 정책 예시

| 행동 | 기본 결정 | 이유 |
|---|---|---|
| workspace source read | ALLOW | read-only |
| workspace source write | ALLOW | local, bounded |
| workspace 외부 write | DENY | boundary escape |
| secret read | DENY | credential exposure |
| build/test | ALLOW | expected dev action |
| arbitrary unknown shell | DENY | unknown side effect |
| git status/diff/log | ALLOW | read-only |
| git add/commit | ALLOW | local and reversible |
| git push | REQUIRE_APPROVAL | remote side effect |
| git push --force | DENY | destructive remote rewrite |
| policy config write | DENY | trust-boundary violation |

## 6. 승인 정책

사용자에게는 다음을 표시한다.

- 무엇을 실행하는지
- 대상
- 위험 이유
- 되돌릴 수 있는지
- 적용된 rule
- 승인 유효 범위

"이 작업을 허용하시겠습니까?"처럼 추상적인 승인만 받지 않는다.

## 7. 승인 Artifact

승인은 최소한 다음 필드를 가진다.

~~~text
approval_id
run_id
tool
normalized_action_digest
workspace_id
policy_version
issued_at
expires_at
optional_state_digest
~~~

실행 직전에 재검증한다.

## 8. 정책 버전

모든 run은 사용한 policy version을 기록한다.

정책이 바뀐 뒤 이전 승인 token을 재사용하지 않는다.

## 9. 정책 변경

정책 완화는 code review 대상이다.

새로운 ALLOW 규칙을 추가할 때는 최소한:

- 필요 이유
- 영향 범위
- 테스트
- 되돌림 방법

을 남긴다.
