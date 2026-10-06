# Tool Contracts

## 구현된 계약 — 003

아래 설계의 후보 목록과 현재 capability를 구분한다. 실제 요청은 domain.SCHEMA와 MCP
oneOf schema를 따르는 flat object다. workspace/run/actor/policy는 trusted host가 주입한다.

| Tool | 구현된 operation/추가 field |
|---|---|
| filesystem | list/read/write/delete/search/edit. read: start_line/end_line, search: query/glob/optional exact exclude_dirs, edit: old_text/new_text/expected_sha256 |
| shell | exec: exact argv/cwd/stdin. run: profile/optional mode/filter/stdin |
| git | status/diff/log/add/commit/branch/push. diff: optional paths/staged |

create/update는 write로 처리한다. show/restore, 임의 npm/pytest/Gradle 명령은 후보일 뿐
일괄 허용하지 않는다. [실행·한계](10-local-usage.md)와 [003 기록](exec/003-real-project-usability.md)이
구현 상태를 설명한다. edit는 전체 file hash를 확인하는 unique substitution이고 search는
bounded literal search 또는 빈 query의 file-path listing이다.
search의 `exclude_dirs`는 search path 기준 최대 32개의 literal 하위 디렉터리이며,
`.gitignore`의 pattern/negation semantics를 적용하지 않는다. 제외한 subtree는 순회하지 않고
응답에 적용된 경로를 반환한다.

결과는 decision/matched_rule/reason/executed/exit_code/stdout/stderr/audit_event_id와
timings_ms, execution_status/effect_status를 포함한다. read/edit는 sha256,
search는 matches/incomplete/truncation_reasons/excluded_dirs, list는 returned_entries와 생략 metadata를 추가한다.
일반 출력 redaction과 audit의 내용 생략은 서로 다르며 full-file hash는 원본 bytes 기준이다.

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

현재 search는 entry 5,000개, 읽기 8MB, match 200개, match 출력 64KB로 제한한다.
entry 열거가 끝나도 이미 모은 파일은 나머지 byte/match/output 한도 안에서 검색한다.
직접 지정한 대형 파일의 내용 검색은 `FS-SIZE`로 거부하며, 재귀 검색에서 생략한 대형 파일은
`skipped_oversized_files`에 센다. list는 최대 5,000개 entry를 열거하고 이름 2,000개와
UTF-8 출력 64KB까지 반환한다. 두 연산 모두 제한으로 생략하면 `incomplete`와 `truncated`를
true로 두고 `truncation_reasons`에 entry/byte/match/result/output/file-size 제한 사유를 기록한다.
보호 경로 및 binary/non-UTF-8 내용은 원래 검색 대상에서 제외하며, 빈 query는 파일명만 탐색한다.

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

현재 backend는 macOS Seatbelt와 Darwin 프로세스 검사·signal 기능을 요구한다.
작업 시작 전에 process scope 판별·열거·signal을 자체 검사하고, 최초 검사에서는 적용한
sandbox identity를 다시 설정할 수 없는지도 확인한다. fork/exec 및 `setsid`로 분리된 자식은
상속한 Seatbelt scope로 식별한다. 정상 종료와 timeout 모두 scope에 남은 프로세스의 종료를
확인한 뒤 반환한다. 확인 실패는 `SH-LIFECYCLE` 실행 오류로 남기고 현재 Gateway의 후속 요청을
거부한다. 이는 검증한 macOS backend의 실행 lifecycle 계약이며 전체 CPU/memory 격리는 아니다.

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

현재 add/diff의 `paths`는 literal 파일 경로다. wildcard와 Git pathspec magic으로 확장하지
않으며 실제 특수문자 파일명은 그대로 취급한다. 디렉터리와 `.`는 `GT-PATHS`로 거부한다.
삭제된 tracked 파일은 명시할 수 있다. diff는 `--no-renames`로 렌더링하며 staged 삭제·이름 변경의
이전 경로까지 본문 반환 전에 검사한다. 민감 경로가 있는 변경 집합은 일반 파일만 필터해도 거부한다.
전체 tracked/change 경로 metadata 검사는 최대 8 MiB·250,000 paths까지 완전히 읽고 검사하며,
그 이상이나 malformed/truncated state는 `GT-STATE`로 executor 전에 거부한다.
일반 Git diff/log와 Shell 결과의 사용자 출력은 계속 64,000 bytes다. Metadata 한도는 사용자 출력에
노출되는 값이 아니며, 둘 중 더 작은 한도로 Git 경로를 잘라 위험 상태를 숨기지 않는다.

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
execution_status
effect_status
execution_stage
execution_error_rule
exit_code
stdout_summary
stderr_summary
changed_targets
approval_id
audit_event_id
~~~

Agent에게 raw secret이 노출되지 않도록 결과도 redaction한다.

`decision`은 정책 결정이다. 실행이 시작된 뒤 실패하거나 exit code가 0이 아니어도 원래
ALLOW/REQUIRE_APPROVAL을 유지하고 `execution_status:failed`로 실패를 표시한다.
실행 전 검증 거부는 `DENY / executed:false / execution_status:not_started`다.
`executed:true`는 성공을 뜻하지 않으며 실제 파일 변경·부분 생성 이후 실패도 포함한다.
`effect_status`는 none(관측된 변경 없음), partial(불완전한 변경), applied(변경 적용),
possible(프로세스의 영향 가능성) 중 하나다. applied도 fsync 내구성까지 보장하지 않는다.
typed 실행 오류는 `execution_stage`, `execution_error_rule`, `execution_error`를 응답과 audit에
남긴다. MCP의 `isError`는 DENY, nonzero exit 또는 execution_status failed일 때 true다.

## 7. Adapter 구현 규칙

- Policy Gateway를 우회하는 direct executor API를 외부에 노출하지 않는다.
- 실제 실행 함수는 trusted package 내부에 둔다.
- adapter 테스트에서는 fake executor를 주입할 수 있어야 한다.
- 정책 판정 unit test는 OS side effect 없이 수행 가능해야 한다.
