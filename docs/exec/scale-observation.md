# 중규모 확장 전 용량 관찰

2026-10-04 KST. 질문은 소규모 C 실험에서 확인한 사용성이 중규모에서도 유지되는가다.
현재 판정은 **그대로 확대할 수 없다**다. 생성한 저장소의 실제 Guard 호출에서 지연과 정상 Git 거부를 확인했다.
제품 구현은 변경하지 않았고, 외부 원본 프로젝트를 접근하거나 수정하지 않았다.
이 측정은 004-01 metadata 상한 분리 전 baseline이며, 이후의 code state는
[004-01 Exec](004-01-git-metadata.md)에서 다시 잰다.

## 실험 범위

macOS 15.7.8 arm64 / Python 3.12.1. 네 개의 독립 ordinary Git 저장소를 생성했다.
각 source 파일은 81줄의 용량 fixture이며 마지막 파일에 변경과 고유 검색어를 넣었다.
실제 중규모 애플리케이션의 설계·빌드·기능 개발을 완료한 실험은 아니다.
모델 세션 없이 Guard.submit을 실제로 호출해 경로 검증·OS backend·audit를 측정했다.

- source 파일 100 / 1,000 / 3,000개: 같은 깊이의 경로, 등록된 Python no-op command.
- source 1,000개 + ignored build output 10,000개: 같은 Git index에 비추적 산출물만 추가.
- read, shell no-op, status, 파일 하나 diff는 각각 3회; root/module search는 각각 1회.
- 총 56회 호출. 숫자는 total wall time의 중앙값이며 모델·MCP transport 시간은 포함하지 않는다.
- 빈 이력에서 baseline commit 하나만 만들었다. 깊은 이력·많은 Git objects·동시 변경·dependency tree는 측정하지 않았다.

## 측정 결과

| source / ignored 파일 수 | 단일 파일 read | Shell no-op | Git status | 파일 하나 diff |
|---|---:|---:|---:|---:|
| 100 / 0 | 0.959 ms | 71.587 ms | 177.572 ms | 271.165 ms |
| 1,000 / 0 | 1.005 ms | 94.296 ms | 547.717 ms | 700.451 ms |
| 3,000 / 0 | 1.836 ms | 145.719 ms | **DENY / GT-STATE** | **DENY / GT-STATE** |
| 1,000 / 10,000 | 0.948 ms | 327.224 ms | 819.997 ms | 965.871 ms |

3,000개 case의 빠른 DENY를 빠른 Git 실행으로 해석하면 안 된다. executor는 실행하지 않았다.
각 repeated operation의 표본은 3개뿐이며 p95나 일반적인 성능 비율을 주장하지 않는다.

## 정상 Git 차단의 임계

[git.py](../../guarded_agent/git.py)의 모든 normalize는 `ls-files -z`로 전체 index 경로를 읽는다.
이는 status, log와 한 파일의 add/diff에도 적용된다. metadata query에 사용자 출력용
`MAX_OUTPUT = 64,000 bytes`를 함께 적용해서 전체 경로가 잘리면 `GT-STATE`로 닫는다.

| source 파일 수 | 실제 전체 tracked 경로 byte 수 | 결과 |
|---|---:|---|
| 100 | 4,411 | 정상 |
| 1,000 | 44,011 | 정상 |
| 3,000 | 132,011 | Git 거부 |

임계는 파일 수 자체가 아니라 UTF-8 경로와 NUL 구분자의 byte 합이다.
따라서 이 실험의 1,000/3,000 결과를 모든 프로젝트의 동일한 한계로 적용하면 안 된다.
긴 경로와 한글 파일명에서는 더 적은 파일에서도 도달할 수 있다.
거부는 불완전한 검사를 실행에 사용하지 않는 올바른 fail-closed 동작이지만,
중규모 정상 개발을 계속할 수 있다는 사용성 조건은 충족하지 못한다.

## 산출물과 탐색

[gateway.py](../../guarded_agent/gateway.py)는 Shell/Git 정규화마다 workspace 전체를 순회해 링크를 확인한다.
허용 요청은 실행 전 재정규화에서도 순회한다. `.git`, build output과 ignored 파일도 포함한다.
Git config 검사의 `.gitattributes` 검색도 전체 순회이므로 .gitignore에 넣는 것만으로 비용을 줄이지 못한다.
산출물 10,000개를 추가한 case의 Shell normalization 중앙값은 27.732 → 260.131 ms였다.

ignored case의 root search는 entry 5,000개를 먼저 소진해 `matches:[] / incomplete:true / entry_limit`이었다.
같은 검색을 target module로 좁히면 101 entries, 266,526 bytes, 1 match, **20.662 ms**로 완료했다.
현재 search의 glob은 파일 match를 제한하며 traversal에서 .gitignore나 디렉터리 제외를 적용하지 않는다.
따라서 반환된 incomplete 상태를 확인하고 `path`를 좁히는 작업이 필요하다.

## 코드에서 확인한 추가 제약

아래는 이번 timing 실험에서 직접 부하 재현한 결과와 구분되는 현재 코드의 제한이다.

- dependency의 symlink/hardlink가 workspace에 있으면 Shell/Git을 거부한다. ignored 경로도 동일하다.
- linked worktree, `.gitattributes`, allowlist 밖 Git config는 지원하지 않는다.
- build timeout은 기본 20초/최대 120초이고, child가 쓰는 파일은 각각 32 MiB 상한이다.
- search는 entry 5,000개/총 읽기 8 MB/200 matches로 제한하며, 직접 파일 read/edit는 1 MB까지다.
- package install·dependency cache·credentials·user config가 필요한 일반 build는 별도 reviewed capability가 필요하다.

## 다음 수정 우선순위

1. **Git metadata와 사용자 출력 분리:** 전체 경로를 streaming 등으로 끝까지 검증하면서 tool 출력 상한을 유지한다.
   malformed·중간 실패·민감 경로·staged 삭제/rename 회귀를 함께 유지한다.
2. **반복 전체 순회 비용:** 변경과 링크 교체를 놓치지 않는 방식으로 중복 검사를 줄인다.
   단순 cache나 ignored directory의 무조건 검사 생략으로 권한 경계를 바꾸지 않는다.
3. **탐색 범위:** 제외 규칙·페이지 또는 명시적 module 탐색을 제공하고, incomplete 상태를 계속 알린다.
4. **실제 중규모 C 개발:** 여러 모듈·선택/전체 test·연속 commit을 실제 모델로 수행하고,
   resource/caching capability와 정상 거부·운영자 개입·시간을 다시 관찰한다.

지금 단계에서 중규모까지 '계속 켜도 답답하지 않다'고 판정하지 않는다.
1,000개 ordinary fixture에서는 동작했지만 Git마다 약 0.5~1초가 들었고, 3,000개 fixture에서는 정상 Git이 막혔다.
소규모에서의 [159개 회귀와 실제 C 결과](fix-001-003.md)는 유지하며, 이 용량 측정은 그 판정의 적용 범위를 좁힌다.

## 증거

[요약 JSON](evidence/scale-observation/summary.json), case별 results/audit와
[재현 코드](evidence/scale-observation/probe.py)를 보존했다.
원본은 `.guard-runs/scale-probe-01/`이며 portable 사본에는 `$RUN/$REPO/$HOME` 경로 치환이 적용됐다.
제품 source manifest는 이전 수정 결과와 동일함을 확인한다.
