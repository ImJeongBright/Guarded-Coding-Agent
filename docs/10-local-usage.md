# Local Usage

Python 3.11+ 표준 라이브러리만 사용한다. API key, SaaS, HTTP 서버는 필요 없다.
Shell/Git 실제 실행은 macOS + Command Line Tools + 사용 가능한 sandbox-exec를 요구한다.
Linux/Windows 및 중첩 sandbox가 금지된 환경에서는 실행을 우회하지 않고 실패한다.

## 한 번에 재현

저장소 루트에서 새 출력 경로를 지정한다. 기존 경로는 덮어쓰지 않는다.

```sh
python3 scripts/dogfood.py --output /tmp/guard-user-x-demo-001
python3 scripts/check.py --evidence /tmp/guard-regression.json
```

dogfood는 trusted setup에서 임시 Git repo와 bare remote를 생성한다. 이후 개발 작업은
별도 stdio MCP 프로세스의 Guard 도구로 진행한다. 승인은 가상 사용자 X의 operator
fixture이며 실제 사람의 승인 인터뷰를 측정한 것이 아니다. trace/summary/audit와
완성한 C 프로젝트는 출력 디렉터리에 남는다. .git metadata는 Agent FS 도구로 수정할 수 없다.

## 개발 workspace 준비

```sh
guard_demo_root="$(mktemp -d /tmp/guard-demo.XXXXXX)"
cp -R examples/c-dbms "$guard_demo_root/workspace"
mkdir -p "$guard_demo_root/workspace/build"
python3 -m guarded_agent init --workspace "$guard_demo_root/workspace" --state "$guard_demo_root/state" --c-dbms
python3 scripts/make_host_config.py --workspace "$guard_demo_root/workspace" --state "$guard_demo_root/state" --output "$guard_demo_root/state/codex.example.toml"
```

`init --c-dbms`는 컴파일러·SDK의 실제 경로, 생성될 binary, DB 테스트 runner의 정확한
argv를 등록한다. 기본 `init`은 Shell 명령을 하나도 허용하지 않는다. `policy.json`의
commands, cwd, timeout, git_remotes를 운영자가 좁게 설정한다. Agent는 이 파일을 수정하지 못한다.
프로필의 `write_paths`는 workspace 상대 경로이며 생략하면 command가 workspace에 쓸 수 없다.
C compiler는 `build`, tests는 `build/test-data`, DBMS는 두 data 파일만 쓴다.
전체 workspace `.`를 쓰기 범위로 지정할 수 없다. 허용 argv/cwd/write scope는 MCP tool 설명에 나타난다.
프로필을 바꾸면 기존 MCP 세션을 재시작하며 기존 승인을 재사용하지 않는다.
Agent는 shell tool description의 `Profiles` 목록을 읽는다. `profiles`라는 Shell operation은 없으며
등록된 `run` 또는 `exec`를 사용한다.
현재 프로필은 임의의 Node/npm/JVM 프로젝트를 자동으로 설정하지 않는다.
002의 Python/Node fixture에는 각각 정확한 test argv 1개를 등록했다.

003에서는 운영자용 후보 발견과 명시 등록을 추가했다.

```sh
python3 -m guarded_agent discover --workspace "$guard_demo_root/workspace" --state "$guard_demo_root/state"
python3 -m guarded_agent profile-apply --workspace "$guard_demo_root/workspace" --state "$guard_demo_root/state" --reviewed-digest REVIEWED_DIGEST --ids c-build c-tests c-db
```

첫 명령의 후보 argv/cwd/write_paths와 source/workspace/policy binding을 검토한 뒤 표시된 digest를
두 번째 명령에 넣는다. Agent에게 이 CLI를 맡기지 않는다. C DBMS layout과 제한된 Node builtin
test script만 제안하며 Makefile/npm script 실행이나 package 설치는 하지 않는다.
갱신 후 MCP를 재시작한다. 실제 후보 JSON은 state/profile-candidates.json에만 둔다.

## CLI 요청

```sh
python3 -m guarded_agent exec --workspace "$guard_demo_root/workspace" --state "$guard_demo_root/state" --run-id x-session <<'JSON'
{"tool":"filesystem","operation":"read","path":"src/db.c"}
JSON
```

등록된 command 배열을 `shell/exec`의 argv로 보낸다. 문자열 shell, chaining, nested shell은
지원하지 않는다. `shell/run`의 profile ID, 등록된 mode와 literal filter도 사용할 수 있다.
예: `{"tool":"shell","operation":"run","profile":"c-tests","filter":"test_find"}`,
`{"tool":"shell","operation":"run","profile":"c-build","mode":"debug"}`.
필터는 regex가 아니며 실행한 선택 테스트 수를 확인하고 전체 suite도 돌린다.
데이터 입력은 `stdin`으로 전달할 수 있다. workspace list/read/write/search/edit,
단일 파일 delete와 git status/diff/log/add/commit/branch/push를 제공한다. 디렉터리 삭제,
`git add .`, restore/reset/clean, force/protected-branch push는 capability에 포함하지 않는다.

read의 start_line/end_line은 최대 500줄이다. 응답 sha256은 부분 출력과 관계없이 전체 파일을
대상으로 한다. edit는 path/old_text/new_text/expected_sha256을 받아 정확히 한 번 치환하며,
바뀐 파일은 FS-STALE로 멈춘다. 성공 응답의 새 sha256을 이어지는 edit에 사용할 수 있다.
search는 path/query와 optional glob, `exclude_dirs`를 받고 literal match를 반환한다. 빈 query는
파일명 탐색이다. `exclude_dirs`는 search path 기준으로 정확히 지정하는 최대 32개 하위 디렉터리다.
예를 들어 root 검색에서 생성물만 건너뛰려면
`guard_filesystem({operation:"search",path:".",query:"TODO",glob:"*.c",exclude_dirs:["build","generated"]})`를
호출한다. `.gitignore` 패턴 문법은 적용하지 않으므로 제외할 폴더를 먼저 확인해 이름을 넘긴다.
search는 entry 5,000개/읽기 8MB/match 200개/64KB로 제한한다. truncated가 true이면 경로나
glob/query를 좁힌다. entry 한도에 도달해도 이미 모은 파일은 나머지 한도 안에서 처리한다.
직접 지정한 1MB 초과 파일의 내용 검색은 FS-SIZE로 거부한다. 재귀 검색에서 큰 파일을
건너뛰면 incomplete/truncated와 file_size_limit 사유, skipped_oversized_files를 반환한다.
list는 entry 5,000개/이름 2,000개/UTF-8 출력 64KB까지 반환하며 returned_entries와
incomplete/truncated/truncation_reasons를 제공한다. incomplete 또는 truncated가 true인 결과를
전체 목록으로 판단하지 않는다. `guard_git({operation:"diff",staged:true})`로 commit할 index를 검토한다.
Git paths는 literal 파일명이며 `*.txt`나 pathspec magic으로 여러 파일을 확장하지 않는다.
디렉터리는 거부하고, diff는 rename을 끈 상태로 staged 삭제·이름 변경의 이전 경로까지 검사한다.
전체 Git 경로 metadata는 최대 8 MiB/250,000 paths까지 검사하며 이 한도를 넘거나 상태가 잘리면
실행 전 GT-STATE로 거부한다. 이 내부 metadata 상한은 diff/stdout 64,000-byte 표시 한도와 따로다.

정책 허용과 실행 성공은 별개다. 실행 후 실패는 ALLOW/REQUIRE_APPROVAL을 유지한 채
executed:true와 execution_status:failed를 반환한다. effect_status는 none/partial/applied/possible이며,
execution_stage와 execution_error_rule로 실패 위치를 확인한다. 예를 들어 edit replace 뒤 directory
fsync가 실패하면 파일은 바뀌었으므로 applied다. 재시도 전에 파일과 부분 생성된 경로를 확인한다.
실행 전 거부는 DENY/미실행이고, MCP isError는 정책 거부뿐 아니라 실행 실패·nonzero exit에도 true다.
응답과 result audit에 같은 실행 상태를 기록하며 applied가 내구성 보장을 의미하지는 않는다.

실행 후 result audit 저장이 실패하면 `audit_error`가 추가된다. 실제 execution/effect 상태는
그대로 남고 MCP는 오류, CLI는 exit 1을 반환한다. 같은 Gateway의 후속 요청은 AU-ERROR로
차단한다. 운영자가 실제 효과와 감사 저장소를 확인·복구한 뒤 새 Gateway를 시작해야 한다.
이 차단은 instance 상태이며 프로세스 간 영구 recovery lock은 아니다. [005 실패 주입](exec/005-final-failure-injection.md).

## 승인

push는 operator profile의 remote, 현재 feature branch, HEAD, canonical URL과 local
remote identity에 결합한다. `REQUIRE_APPROVAL` 응답의 approval_id를 별도 운영자 터미널에서 검토한다.

```sh
python3 -m guarded_agent inspect --state "$guard_demo_root/state" PENDING_ID
python3 -m guarded_agent approve --state "$guard_demo_root/state" PENDING_ID
```

표시된 workspace/run/actor/policy/URL/branch/HEAD/expiry를 보고 `approve`를 입력한다.
Agent용 MCP에는 approve가 없다. noninteractive 자동 승인 flag도 없다.
동일 요청·동일 run으로 `approval_id`를 전달하면 1회 실행한다. CLI resume에서는
`{"request": {...}, "approval_id": "..."}` envelope와 처음의 `--run-id`를 사용한다.
실제 인증이 필요한 SSH·credential-bearing URL은 이 release에서 지원하지 않는다.
credential-free HTTPS의 실제 서비스 push는 테스트하지 않았으며 테스트는 local bare remote만 사용했다.

## Coding-agent 연결

[Codex 공식 MCP 가이드](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)의 stdio 구성으로
생성된 `codex.example.toml`을 검토해 전용 세션의 설정에 적용한다. 생성기는 사용자 global
config를 변경하지 않는다. 서버 key는 `guard`다. [공식 설정](https://learn.chatgpt.com/docs/config-file/config-reference)
의 shell/unified exec 및 불필요한 도구를 비활성화하고 host read-only/approval never를 사용한다.
Guard MCP의 추가 host 승인은 `approve`로 설정해 반복 prompt를 줄인다.
고위험 push의 운영자 승인은 Guard 내부에서 계속 요구한다.

보조 `PreToolUse` hook은 정확한 Guard 도구 3개와 `update_plan`만 통과시키며 native
Bash/apply_patch 및 다른 local 도구 경로를 거부한다. [공식 Hooks 문서](https://learn.chatgpt.com/docs/hooks)에 따라
non-managed hook은 `/hooks`에서 정의를 검토하고 신뢰하기 전에는 실행되지 않는다.
특수 도구가 hook 경로를 우회할 수 있으므로 hook만으로 complete mediation을 주장하지 않는다.
새 세션에서 직접 shell/edit가 사라지거나 거부되는지, 지원 도구 목록과 실패 동작을 확인해야 한다.
002에서는 **Codex CLI 0.160.0**의 직접 patch/shell 거부와 hook/MCP 장애를 실제로 검증했다.
hook이 실패하면 쓰기 가능한 host의 native patch가 통과하는 실패도 재현했다.
read-only host는 이 실패를 막는 필수 조건이다. 외부의 현재 세션 tool routing을 이 코드가
소급해 변경하지는 않으며, 검증한 전용 세션 구성에만 결과를 적용한다.

## 실제 모델 개발 실험 재현

설치된 Codex의 기존 로그인과 모델 서비스를 사용한다. Guard는 모델 API를 호출하지 않는다.
launcher는 검증한 CLI 버전 외에는 활성화를 거부하며, 추가 project `.codex/config.toml`도 별도 검토를 요구한다.
기본 code-mode dispatcher는 Guard의 중첩 호출에 필요하므로 유지한다.

```sh
python3 scripts/prepare_live_workload.py --kind c --output /tmp/guard-live-c-new
python3 scripts/run_guarded_codex.py --workspace /tmp/guard-live-c-new/workspace --state /tmp/guard-live-c-new/state --prompt-file /tmp/guard-live-c-new/prompt.txt --output /tmp/guard-live-c-new/session --reviewed-hook
python3 scripts/verify_live_workload.py /tmp/guard-live-c-new
```

`--reviewed-hook`은 운영자가 `scripts/codex_pre_tool.py`를 검토한 자동화용이다.
launcher는 hook의 정규 파일 여부, ALLOW/DENY 자체 검사와 hash를 기록한 후 그 invocation의
hook trust 확인만 생략한다. sandbox/approval 전체 우회는 하지 않는다. 일반 host activation에서는
`/hooks`의 trust 절차를 사용할 수 있다.

`--kind python` 또는 `--kind javascript`로 별도 task를 준비할 수 있다. JavaScript에는 Node가 필요하다.
현재 launcher의 실험 기록기는 기존 HEAD가 있는 clean checkout에서 시작해야 한다.
`session-baseline.json`과 `session-completion.json`으로 시작/종료 revision, policy/workspace,
audit window와 events/exit를 결합한다. 검증기는 해당 세션의 실제 Guard 변경·성공 검사·staging·새 commit과
독립 계약 검사를 모두 요구한다. 이 조건은 개발 workload 평가용이며 일반 Gateway에 clean 조건을 추가하지 않는다.
baseline 없는 기존 로그는 역사적 결과로 보존하고 새 규칙으로 소급 합격시키지 않는다.
준비는 trusted operator 단계이며 모델은 이후 개발 순서를 스스로 정한다. 현재 C fixture에는
002에서 검증한 count 기능이 반영되어, 재실행 task는 zero-id 회귀와 count 유지 검증도 수행한다.
당시 원본 baseline/결과는 portable evidence의 patch와 `.guard-runs/live-c-01` Git 이력으로 구분한다.

`scripts/live_probe.py`는 `native-hook`, `missing`, `crash`, `timeout`, `mcp-down`, `mcp-dies` 시험을 제공한다.
`unsafe-control`은 hook 단독 방어 실패를 재현하는 임시 marker 대조군이며 제품 실행 구성이 아니다.
각 실행의 stdout JSONL/stderr, prompt/invocation/preflight와 verification이 workspace 밖에 남는다.
전체 결과는 [002 Exec](exec/002-live-dogfooding.md), 사용성 조건은 [현재 판정](exec/002-09-verdict.md)에 있다.

MCP는 newline JSON-RPC stdio, protocol 2025-11-25 계열이다.
[transport](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports),
[tools](https://modelcontextprotocol.io/specification/2025-11-25/server/tools),
[lifecycle](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle)를 기준으로 한다.
노출 도구는 `guard_filesystem`, `guard_shell`, `guard_git`이다. arguments에는 `operation`과
해당 field를 보낸다. 예: `guard_filesystem({operation:"read",path:"src/db.c"})`.
승인 후 `guard_git`에 원래 push 인자와 approval_id를 같이 보낸다.

## 구현 경계

- FS는 ordinary 파일만 접근한다. symlink/hardlink workspace는 Shell/Git에서도 거부한다.
- 시스템 실행 파일·라이브러리·SDK는 읽을 수 있다. command의 지정된 write scope와 temp 이외 write와
  비승인 network는 OS sandbox에서 거부한다. Git은 .git만 쓰고 승인된 local remote는 push 동안만 추가한다.
- loader를 위해 root directory와 지정된 ancestor metadata를 읽는다. 모든 OS 파일 읽기를 차단하는 모델은 아니다.
- child output은 각 stream 64 KB까지 반환하고, 파일 크기는 child당 32 MiB 상한,
  명령 시간은 profile 20초 기본/120초 최대다. 큰 build는 profile/backend 설계가 추가로 필요하다.
- macOS 프로세스 scope 검사·열거·signal을 작업 시작 전에 확인하고, 최초 검사에서 sandbox
  identity 재설정 거부도 확인한다. 정상 반환과 timeout 모두 상속한 Seatbelt scope로 분리된 자식까지
  종료를 확인한다. 이 native 기능이 없거나 사전 검사가 실패하면 작업을 시작하지 않는다.
  종료 확인 실패는 SH-LIFECYCLE/실행 실패/possible로 기록하고 현재 Gateway 세션의 모든 후속
  요청을 차단한다. 남긴 lifecycle marker로 운영자가 잔여 프로세스를 확인·복구한 뒤 재시작한다.
- controller SIGKILL에서는 정상 cleanup과 marker 저장이 실행되지 않을 수 있다. 자식은
  기존 Seatbelt 안에서 허용 scope에 계속 쓸 수 있다. 자동 supervisor/recovery는 구현하지 않았고,
  운영자의 잔여 프로세스 확인·정리가 필요하다. [실측 결과](exec/evidence/005/injection-final.json).
- action/decision/rule/result metadata를 내구 audit로 저장한다. 파일 내용·stdin·stdout/stderr는
  audit에 저장하지 않는다. edit의 old/new text와 search match 내용도 생략한다.
  결과 token redaction은 알려진 형태를 대상으로 하며 모든 secret 탐지기는 아니다.
- edit는 optimistic hash 검사와 atomic replacement다. 최종 검사/rename 사이의 비협조적인
  외부 writer까지 막는 OS compare-and-swap은 아니며 xattr/ACL 보존을 지원하지 않는다.
- 결과 timings_ms는 두 차례 normalization/decision, audit, 실제 execution, total/other를
  perf_counter로 나눈다. Git normalization의 실제 state 조회 subprocess도 포함한다.
  MCP round trip이나 모델 생성 시간은 이 값에 포함하지 않는다.
- 악성 동일 UID 운영자·kernel exploit·daemon의 완전한 resource isolation은 범위 밖이다.
- Guard 구현 package, launcher scripts, pyproject와 state/policy는 Agent의 FS/Shell에서 보호한다.
- command write scope는 경로 교체 시 외부 target으로 확대하지 않으며 한글·공백 경로도 검증했다.
- linked Git worktree, symlink dependency tree, package 설치와 큰 프로젝트 command discovery는 추가 설계가 필요하다.

003의 기존 프로젝트 연속 task 재현은 `prepare_003.py`, `setup_003.py`의 discover/apply,
`prompt_003.py`, `run_guarded_codex.py`, `verify_003.py` 순서로 진행한다.
대상은 현재 환경의 C sample과 MoneyPilot의 dependency-free domain 복사본이다.
원본 프로젝트는 수정하지 않는다. 세부 조건과 실패를 [003 Exec](exec/003-real-project-usability.md)에 기록한다.
