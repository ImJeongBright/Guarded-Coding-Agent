# 004-03 — 생성물 폴더를 명시적으로 제외하는 검색

2026-10-05. M1/M2 generated tree에서 root search가 source에 도달하기 전에 5,000-entry 한도를 쓰는 문제를 다뤘다. 목적은 전체 tree scan budget을 유지하면서 Agent가 확인한 생성물 디렉터리를 안전하게 제외하고 결과의 불완전 여부를 분명히 하는 것이다.

## 변경

- `filesystem.search`가 optional `exclude_dirs`를 받는다. search `path` 기준 literal 하위 디렉터리 최대 32개를 지정한다. symlink, workspace 밖, 검색 루트 자신, 일반 파일, 32개 초과는 거부한다. 아직 생성되지 않은 디렉터리는 재사용 가능한 요청을 위해 허용한다.
- 지정된 디렉터리는 하위 순회를 시작하기 전에 건너뛰고, canonical 제외 목록을 결과 `excluded_dirs`에 돌려준다. 기존 entry 5,000·읽기 8MB·match 200·output 64KB 제한과 `incomplete`/이유 표식은 유지한다.
- glob은 파일을 고르는 데만 쓴다. `.gitignore` pattern/negation semantics를 모사하지 않는다. Agent가 실제 디렉터리를 확인해 literal 제외값으로 보내도록 MCP 설명과 local usage 문서를 갱신했다.
- pagination cursor는 workspace 변경 후 안전한 재사용 binding을 제공할 설계가 없어 추가하지 않았다. 불완전하면 경로/glob/exclusion으로 범위를 좁힌다.

## 검증

- 새 scale search 4개, 기존 search 및 MCP descriptor regression 6개 통과.
- 전체 회귀: 170 tests, 실패/error/skip 0, 52.601초. JSON 결과는 `passed: true`.
- `python3 -m compileall -q guarded_agent tests`와 `git diff --check` 통과.
- 5,005개 ignored generated file 뒤의 C source를 둔 재현에서 exclude 전 root search는 `entry_limit`로 incomplete, exclude 후는 1 match로 complete했다.
- absolute/path traversal/self/file/symlink/oversized exclude 요청이 DENY됐다. 제외된 subtree의 hardlink target 내용은 결과와 audit에 나타나지 않았다.

## M1/M2 synthetic 결과

각 operation을 3회 실행한 median이다. `root_without_exclusion`과 `root_excluding_build`는 root search이며, module search는 해당 target module을 path로 지정했다.

| Profile | Root, exclude 없음 | Root, `build` 제외 | Target module |
|---|---|---|---|
| M1: 3,000 tracked / 10,000 ignored | 848 ms, incomplete `entry_limit`, match 0 | 579 ms, complete, match 1 | 19.6 ms, complete, match 1 |
| M2: 10,000 tracked / 25,000 ignored | 845 ms, incomplete `entry_limit`, match 0 | 978 ms, incomplete `entry_limit`, match 0 | 20.0 ms, complete, match 1 |

M2에서는 generated `build` subtree를 건너뛰어도 tracked source만으로 5,000-entry 한도를 넘는다. 정상 사용 경로는 incomplete marker를 보고 target module로 좁히는 것이다. 수치는 합성 파일 fixture 한 번의 세 번 반복이며 실제 C application 작업 latency가 아니다.

## 완료 판정과 남은 제한

004-03은 M1 generated-tree root search 완료, M2 module search 완료, 제외 경로 경계 및 기존 budgets regression 통과로 완료한다. 사용자가 명시한 directory 제외는 동작하지만 자동 `.gitignore` 해석과 paging은 제공하지 않는다. match/output/byte limit 도달도 이전처럼 incomplete와 이유를 반환한다. 004 종료 조건의 실제 중규모 개발 task와 빌드 검증은 남아 있다.

## 증거

- [portable evidence](evidence/004/004-03/README.md): 반복 M1/M2 결과, policy/audit, regression log/JSON, source delta.
- 원본: `.guard-runs/scale-probe-03/search-measurement.json`, `regression-004-03.*`, `M1-3000-10000-search-state/`, `M2-10000-25000-search-state/`.
