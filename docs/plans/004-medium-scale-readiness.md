# 004 — 중규모 저장소 지속 사용 계획

## 목적

003과 fix-001~003은 두 작은 저장소와 작은 C DBMS 개발 task에서 사용성을 확인했다.
뒤이어 생성한 저장소 네 개에서 파일 수와 ignored 산출물을 키워 보니,
tracked source 3,000개에서 `git status`와 파일 하나 diff가 `GT-STATE`로 거부됐다.
tracked source 1,000개에서는 Git 두 동작의 median이 0.55초/0.70초였고,
ignored 산출물 10,000개를 추가하면 0.82초/0.97초로 증가했다.
이 계획은 소규모 성공 판정이 중규모까지 검증된 것으로 확대되는 것을 막고,
측정한 한계부터 단계적으로 수정한다.

초기 용량 측정은 81줄 fixture를 담은 **합성 Git 저장소**였다. M1/M2 live 검증에서는 기능이 있는
multi-module C DBMS 실험 프로젝트와, 별도로 harmless source/build volume fixture를 사용했다.
외부 production 저장소와 실제 사람의 장기 연속 사용은 아직 검증하지 않았다. 기준 장비와 초기 호출별
상세 결과는 [scale 관찰 Exec](../exec/scale-observation.md)에서 확인한다.

## PDR

### 사용자 문제

Agent에게 Filesystem/Shell/Git 권한을 주고 Guard를 계속 켜면, 프로젝트가 커져도 정상적인
탐색·검사·빌드·Git 작업이 반복적으로 거부되거나 기다리게 되지 않는가?

### 종료 조건

- 아래 정의한 보통 규모 workspace에서 정상 read/search/build/test/status/single-file diff/stage/commit이 완료된다.
- 위험·미해결 상태는 계속 fail closed이고, 민감 Git 내용 노출·workspace 밖 쓰기·승인 우회는 허용하지 않는다.
- 제한 때문에 search/list 결과가 incomplete이면 이유와 재시작 범위를 알 수 있다.
- 신규 regression, 이전 누락 경로 regression, 실제 모델 세션과 독립 동작 검증이 모두 통과한다.
- 정상 action의 ALLOW/APPROVAL/DENY와 시간, operator 개입 및 retry 횟수를 기록해 사용성 판정을 낸다.

### 측정 workspace

“중규모”를 업계 공통 단위라고 주장하지 않는다. 이 계획의 재현 기준은 아래 용량이다.

| Profile | Tracked 파일 | Ignored/build 파일 | 목적 |
|---|---:|---:|---|
| M1 | 3,000 | 10,000 | 직전 관찰에서 발생한 Git 거부·탐색 비용을 수정 뒤 재검사 |
| M2 | 10,000 | 25,000 | 여유 용량·성장 한도 관찰 |

생성 fixture의 파일 수 부하 결과와 functional C DBMS feature/build/test 결과를 별도로 표기한다.
multi-module C DBMS 실험 workspace에서 모델이 여러 수정·전체 test·선택 test·commit을 수행하게 한다.
실제 프로젝트가 symlink-heavy, linked worktree 또는 외부 credentials에 의존하면 현재 미지원 조건을
먼저 기록하고, 해당 프로젝트를 지원한다고 가장하지 않는다.

### 비목표

- 이 계획에서 Linux/Windows 지원, unrestricted shell, 일반 package install, credential을 동반한 push를 열지 않는다.
- 단순히 metadata·출력·timeout 한도를 크게 올려 문제를 숨기지 않는다.
- 검색에서 `.gitignore`를 정규식처럼 대충 적용해 경계 검사나 incomplete 상태를 생략하지 않는다.
- 벤치마크 성공만으로 실제 중규모 Agent task가 편했다고 판정하지 않는다.

## 실행 계획

| Exec | 우선순위 | 할 일 | 완료 기준 | 상태 |
|---|---|---|---|
| [004-01 Git metadata](#004-01--git-metadata) | P0 | 전체 NUL 경로 확인과 64KB 사용자 출력 제한 분리 | M1/M2의 status와 한 파일 diff가 정상 완료, oversized/malformed metadata는 명시적으로 fail closed | 완료: [004-01 Exec](../exec/004-01-git-metadata.md) |
| [004-02 workspace 검사](#004-02--workspace-검사) | P1 | Shell/Git의 반복 link scan과 `.gitattributes` discovery 비용 측정·안전한 감소 설계 | 같은 안전 조건에서 scan 비용이 기록되고, 실행 직전 late link/hardlink 삽입 fail-closed 확인 | 완료: [004-02 Exec](../exec/004-02-workspace-scan.md) |
| [004-03 탐색](#004-03--탐색) | P1 | 대규모·generated tree에서 explicit directory exclusion과 경로 좁히기 | generated tree를 제외한 M1 검색 완료, M2 module 검색 완료, exclude 우회·불완전 표식 regression 통과 | 완료: [004-03 Exec](../exec/004-03-search-exclusions.md) |
| [004-04 빌드 scope](#004-04--빌드-scope) | P2 | build time/file-size 제한과 큰 산출물 영향 측정 | timeout·32MiB·output bound의 실제 trigger 확인, bounded profile 설계와 oversize 실패 명시 | 완료: [004-04 Exec](../exec/004-04-build-limits.md) |
| [004-05 실제 개발](#004-05--실제-개발) | P0 통합 | M1·M2 scaled C DBMS 복사본에서 live agent 개발·독립 검증, Git 비용 후속 최적화 | clean 시작/종료, 세션 audit attribution, task tests·새 commit·성능/마찰 기록 통과 | 완료: 다섯 계획 task + 최적화 후 task 통과. 실제 사용자 장기 평가는 보류 |

### 004-01 — Git metadata

현재 Git은 전체 `ls-files -z` 결과와 changed-path metadata를 64,000-byte output bound로 실행한다.
이는 MCP/파일 내용 표시에는 적절하지만, 숨은 내부 경로 검증용 한도로 사용하면 M1도 실패한다.

구현 전 NUL 경계, whitespace/Unicode, malformed/truncated result, staged sensitive deletion/rename,
literal pathspec과 parser가 사용하는 전체 source list를 정리한다. 내부 metadata 조회에는 사용자 결과와
분리된 크기 상한을 적용한다. 우선 8 MiB bound로 M1/M2 및 oversize 대조군을 측정한다.
3,000개 실험의 132 KB를 수용하면서 초과에서 fail closed하는 크기인지 검증한다.
Metadata 전용 경로는 내용을 Agent에게 반환하지 않고 내부에서 complete하게 검사한다. 경로 수에 최종 상한을 두며,
상한을 넘거나 output truncation·NUL 누락이 있으면 executor를 시작하지 않는다.
일반 Git diff/log 응답은 현재 사용자 출력 한도를 유지한다.

확인 요청: `status`, `diff` 전체와 explicit 단일 파일의 staged/unstaged diff, `add`, `commit`.
M1과 M2 모두에서 status·단일 파일 diff를 검증하고, 민감 파일 staged 삭제·rename과 잘린 metadata는 거부한다.

### 004-02 — workspace 검사

현재 Shell/Git은 normalization과 execution 재검사에서 workspace 전체를 걷고,
Git config 검사도 `.gitattributes`를 찾기 위해 다시 전체를 걷는다. `.gitignore`는 이 검사에서 제외하지 않는다.
산출물 10,000개 실험에서는 Shell normalization median 27.732 → 260.131 ms였다.

먼저 생성·수정/삭제 분포와 link validation 소요시간을 별도로 기록한다.
이후 가능한 변경은 validation proof의 수명·workspace identity·동시 mutation 사이 조건을 설계 리뷰한다.
파일 전체 검사를 단순 생략하거나 오래된 cache만 신뢰하지 않는다.
위험한 race를 완전히 차단할 안전한 감소안이 없으면 scan을 유지하고 실제 결과로 사용성 판정한다.

### 004-03 — 탐색

현재 entry 5,000개·읽기 8MB·match 200개의 경계 때문에 build/generated output이 root 탐색에서
먼저 budget을 소진하는 상황을 다룬다. `exclude_dirs`는 search path 기준 literal directory 목록으로
제한하며, 최대 32개까지 명시한 하위 폴더를 subtree 단위로 건너뛴다. glob은 파일 선택에만 쓴다.
`.gitignore`의 nesting/negation/escaping을 흉내 내지 않으며 Agent가 확인한 디렉터리를 정확히 넘긴다.
M1 root search는 `build`를 명시 제외해 완료하고, M2는 제외 뒤에도 5,000-entry 한계가 남는 경우
target module로 좁혀 완료하는지 확인한다. entry/byte/match/output 제한이면 `incomplete`와 이유를
유지한다. pagination cursor는 workspace mutation 뒤 안전하게 재사용할 binding 설계가 없어서 이번에
추가하지 않는다. 대신 path/glob/exclude로 범위를 줄일 수 있는지 측정한다.

### 004-04 — 빌드 scope

현재 Shell profile 기본 timeout 20초/최대 120초, child file 생성 32MiB, stdout/stderr 64KB 제한을
small project의 당연한 기본값으로 취급하지 않는다. 실제 `cc` C DBMS build/run과 timeout·33 MiB
write·100 KB output 대조군을 돌린다. 이 fixture에서 일반 build가 기존 제한 안에서 끝나면 공통값은
그대로 둔다. 이후 더 큰 task에 timeout 증가가 필요하면 operator가 고정 argv/profile에 최대 120초,
좁은 `write_paths`를 지정한다. 32 MiB는 단일 파일 한도이며 aggregate workspace storage 보장은 아니다.

### 004-05 — 실제 개발과 판정

M1/M2 fixture를 위해 workspace 밖 trusted setup에서 정해진 수의 파일과 ordinary Git baseline을 만든다.
각 action은 이미 허용된 Guard MCP를 통해 실행하고, session baseline/completion과 per-call audit를 기록한다.
기존 source hash를 보존하고, 계획된 다섯 task는 적어도 세 개의 관련 source/test 수정, targeted test,
full test, diff review, explicit staging과 새 commit을 포함한다.
독립 검증기가 새 behavior를 확인하고 ending tree가 clean인지 확인한다.

다섯 task 모두 M1/M2 functional multi-module C DBMS 사본에서 끝났다. M2에서 Git call당 약 3.8–4.0초
정규화 지연을 확인해 `Git._state_paths`의 경로별 `Path.resolve/stat`을 엄격한 lexical metadata parser로
바꿨다. symlink/hardlink의 전체 workspace 검사와 executor 직전 recheck는 그대로 유지한다.
수정 후 M1/M2 각 6회 read-only status 측정과 여섯 번째 실제 Codex regression-only task를 수행했다.
M2 status median은 3.90초에서 1.11초로 줄었다. malformed/traversal/sensitive/protected metadata와
조회 중 삽입된 symlink를 대상으로 한 회귀 및 173개 전체 회귀가 모두 통과했다.

실행 기록은 [통합 결과](../exec/004-05-live-medium-scale.md)와 [task별 Exec](../exec/README.md#004-m1m2-live-task-records)에 있다.
M2 최초 baseline에서 `FS-LINK` setup DENY 1회가 있었으나 같은 35,048-entry scan·build·tests 재시도는 통과했다.
Task 4에는 존재하지 않는 `AGENTS.md` read DENY 1회가 있었다. 최적화 후 task에는 5,000-entry 한도에
따른 명시적 incomplete root search 1회가 있었고 경로 축소 후 탐색은 완료됐다.

기술적인 M1/M2 실행 기준은 완료했다. simulated X는 수정 뒤 이 profile에서 계속 사용할 수 있다고 판단했지만,
사람이 1–2주 실제 작업에서 느끼는 불편은 측정하지 않았으므로 PDR의 장기 만족 판정은 열어 둔다.

각 profile에서 read/search/status/diff/build/test/stage/commit latency와 median/max,
결정 분포, DENY 원인, incomplete result, 사용자가 수동으로 좁힌 경로, 재시도를 기록한다.
M1/M2에 걸친 다섯 live task에서 정상 요청에 대한 불필요한 거부가 없고 setup/retry가
task마다 반복되지 않아야 한다.
작업이 완수돼도 1~2주 연속 사용 또는 사람의 답답함을 직접 관찰하기 전에는 장기 만족을 통과로 쓰지 않는다.

## 공통 기록 형식

각 `docs/exec/004-NN-*.md`에 변경 범위, 명령, source/policy hash, case별 결과,
처음 실패한 내용, 회귀 결과, latency와 다음 제한을 쓴다. `docs/exec/evidence/004/`에는
portable JSON/manifest/patch를 남기고 원본 session은 `.guard-runs/`에 유지한다.
로컬 경로 변환본은 재검증 가능한 원본 session인 것처럼 표기하지 않는다.

004-01~04와 004-05의 planned M1/M2 workload를 완료했다. 여섯 번째 후속 Codex task에서 metadata 최적화 뒤 Git edit/build/test/stage/commit 흐름도 확인했다. 현재 전체 회귀는 173 tests다. `docs/exec/004-05-live-medium-scale.md`는 실제 호출·거부·incomplete search와 성능 근거, 장기 사용 한계를 기록한다.
