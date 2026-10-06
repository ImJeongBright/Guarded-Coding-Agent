# 004-02 — workspace integrity scan 비용과 안전성

2026-10-05. Git/Shell 요청 전후에 반복되던 workspace 전체 순회를 재검토했다. 목적은 검사 횟수를 줄이되 link/hardlink와 Git attributes 차단, 실행 직전 재검사를 유지하는 것이다.

## 변경

- `Filesystem.check_workspace_links()`가 한 번의 tree traversal에서 symlink, 일반 파일 hardlink, 선택적인 `.gitattributes`를 확인한다. 파일별 metadata는 `lstat()` 한 번으로 읽으며 link 검사에 실패하거나 트리가 사라지는 경우 fail closed 한다.
- Gateway의 Shell 검사는 link/hardlink를 확인하고, Git 검사는 같은 traversal에서 `.gitattributes`도 거부한다. attributes를 위해 별도로 실행하던 `Path.rglob()`은 제거했다.
- Git adapter는 config parsing 뒤 `sandbox.run()` 직전에 combined scan을 다시 한다. 따라서 정상 mediated Git action은 두 번의 Gateway 검사와 마지막 실행 직전 검사, 총 3회 순회한다. Shell은 Gateway의 normalize와 pre-execution normalize에서 2회 순회한다.
- 신규 [workspace scan tests](../../tests/test_workspace_scan.py)는 nested `.gitattributes`, 실행 직전 새 attributes/hardlink 삽입, 검사 중 사라진 entry의 fail-closed 동작을 확인한다. `.gitattributes`가 있어도 정책에 등록된 정확한 Shell argv는 계속 실행된다.

## 검사 결과

- 집중 회귀: 새 workspace scan 4개, 기존 Git fix 12개, Shell/Git 통합 21개 모두 통과.
- 전체 `scripts/check.py`: 166 tests, failure/error/skip 0, 57.885초. 테스트 JSON은 `passed: true`다. 실행 후 결과를 출력하는 zsh wrapper가 예약된 read-only 변수 `status`에 값을 넣으려 해 바깥 명령은 1을 반환했다. 테스트 프로세스와 결과 JSON은 성공을 기록하며, 이건 suite 실패가 아닌 wrapper 오류다.
- `python3 -m compileall -q guarded_agent tests` 및 `git diff --check` 통과.
- 구 방식은 2회 link scan + 3회 `.gitattributes` 탐색, 새 방식은 3회 combined scan이다. 같은 M1/M2 저장소에서 각 3회 재생한 scan-only 비교의 median은 M1 480.610 → 398.802 ms(-17.02%), M2 945.081 → 831.444 ms(-12.02%)였다.

## M1/M2 요청 latency

기존 `.guard-runs/scale-probe-02` 합성 fixture를 그대로 사용했다. 아래는 별도 Gateway state로 요청별 3회 실행한 median / max이며, 각 결정은 모두 `ALLOW`다.

| Profile | Git status | 단일 파일 diff | Shell no-op | 순회 횟수 |
|---|---:|---:|---:|---|
| M1: tracked 3,000 / ignored 10,000 | 1,705 / 2,318 ms | 1,799 / 2,529 ms | 403 / 404 ms | Git 3, Shell 2 |
| M2: tracked 10,000 / ignored 25,000 | 5,091 / 5,230 ms | 4,582 / 4,605 ms | 696 / 704 ms | Git 3, Shell 2 |

Scan-only 비교는 순회 비용 감소를 확인했지만, 전체 Git 요청은 metadata query와 Git 실행도 포함한다. 이전 004-01은 operation당 한 번 측정했고 이번은 세 번이므로 전체 latency가 개선됐다고 단정하지 않는다. 특히 M2 status/diff는 여전히 약 4.6~5.1초라 연속 개발에서 빠르다고 판정할 수준이 아니다.

## 실패·경계와 판단

- 신규 테스트에서 `.gitattributes`가 있는 경우 Git은 `GT-CONFIG / executed:false`, Shell exact profile은 exit 0이었다.
- Git config 검사 뒤 `.gitattributes` 또는 outside file hardlink를 삽입하는 adversarial fixture는 최종 scan에서 각각 `GT-CONFIG`, `FS-LINK`로 차단했고 Git executor는 호출하지 않았다.
- scan 도중 entry `lstat()`이 실패하는 fixture는 `FS-LINK`로 fail closed 했다. 검사 이후 다른 host process가 동시 변경하는 경우를 원자적으로 잠그는 설계는 아니다. 이번 변경은 mediated action 사이의 생성/교체를 다음 검사에서 잡으며, 동시 host writer까지 차단한다고 주장하지 않는다.
- 10,000/25,000개의 synthetic fixture다. 실제 중규모 C 애플리케이션 task, 사용자 체감, 장시간 사용을 검증하지 않았다. root search는 이전 측정에서 `entry_limit / incomplete:true`였고 이 단계에서 개선하지 않았다.

## 완료 판정

004-02의 안전 조건에서 반복된 전체 탐색을 5회에서 3회로 줄였고, combined scan의 M1/M2 비용, 실행 직전 재검사 및 late mutation fail-closed를 확인했다. 이 단계는 완료한다. M2 Git latency는 여전히 높고 검색·빌드 scope는 남아 있어 004 전체 종료 조건은 미충족이다.

## 증거

- [portable evidence](evidence/004/004-02/README.md): scan-only 비교, M1/M2 반복 결과, regression log/JSON, source manifest와 test source.
- 원본 실행·측정 파일: `.guard-runs/scale-probe-03/`; 이전 생성 repository: `.guard-runs/scale-probe-02/`.
- 전체 회귀의 최초 wrapper 출력 오류는 위에 기록했다. JSON이 166개 test 성공과 0 failure/error/skip을 증명한다.
