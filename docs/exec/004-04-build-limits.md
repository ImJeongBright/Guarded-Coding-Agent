# 004-04 — 실제 C build와 실행 한도

2026-10-05. Shell sandbox가 실제 C compiler를 사용할 때의 기본 build·timeout·output·file limit을 작은 isolated C DBMS fixture로 확인했다. 이 단계에서 limit을 키울 근거가 있는지 판정한다.

## 실행 프로필과 동작

- trusted host가 선택한 Apple `cc`와 SDK 경로를 고정 argv에 넣고, `src/main.c`를 `build/minidb`로 빌드했다. write scope는 `build`뿐이다.
- 빌드된 프로그램은 `build/result.db`에 9-byte fixture record를 생성했다.
- 별도 고정 profile은 33 MiB 단일 파일 쓰기, 100,000-byte stdout, 250 ms timeout을 재현했다.

## 결과

| 작업 | 결과 |
|---|---|
| 실제 `cc` build | ALLOW/exit 0, 436 ms, binary 33,544 bytes |
| 빌드 산출물 실행 | ALLOW/exit 0, 417 ms, 9-byte DB 파일 |
| 100,000-byte stdout | 실행 성공, 반환 64,000 bytes, `output_truncated: true` |
| 33 MiB 파일 쓰기 | child 실패, stderr `File too large`, 부분 파일 33,554,432 bytes에서 정지 |
| 2초 명령, profile timeout 250 ms | exit 124, `timed_out: true`, process lifecycle `terminated` |

33 MiB 대조군은 단일 파일 제한만 검증한다. 현재 OS limit은 명령별 aggregate disk 사용량이나 CPU/memory 전체를 제한하지 않는다.

## 정책 판단

이 C fixture는 기존 20초 기본 profile timeout과 `build` 전용 write scope 안에서 완료됐다. 따라서 이 단계에서는 공통 32 MiB/64 KB limit을 올리거나 모든 Shell 작업의 timeout을 늘리지 않는다. 필요가 확인된 더 큰 실제 project build는 승인된 profile에 한정해 최대 120초까지 timeout을 설정하고, writable directory를 좁게 지정한다. 여러 output file 또는 더 큰 단일 file이 필요한 프로젝트는 실제 workload 결과와 aggregate storage 위험을 확인한 뒤 별도 설계한다.

## 테스트와 최초 실패

- 실제 compiler probe, compiled program 실행, stdout/timeout trigger가 모두 Guard를 통과했다.
- 새 `test_child_file_size_limit_stops_at_32_mib`는 33 MiB 쓰기가 정확히 32 MiB에서 중단되는지 regression으로 고정했다.
- 집중 32 MiB regression 1개 통과. 전체 회귀 171 tests, 실패/error/skip 0, 61.949초.
- 최초 compiler probe는 SDK flag 없이 exit 1이었고 당시 child output을 보존하지 않아 정확한 원인을 단정하지 않는다. 기존 compiler integration regression과 동일하게 명시적 `-isysroot`를 넣어 재실행하자 build/실행은 성공했다.

## 한계와 다음

이것은 한 source file의 실제 C compile/run과 synthetic 한도 대조군이지 중규모 애플리케이션의 clean full build는 아니다. 004-05에서 M1/M2 및 여러 모듈 C DBMS task를 통해 실제 build/test, explicit stage/commit, independent verification과 사용 마찰을 이어서 측정한다.

## 증거

- 원본 measurement: `.guard-runs/scale-probe-03/build-scope/build-limits.json`.
- Regression: `.guard-runs/scale-probe-03/regression-004-04.json` 및 인접 log.
- [portable evidence](evidence/004/004-04/README.md): measurement, 최종 policy/audit, regression과 source delta.
- profile은 `scale-build-004-04`; source hash와 선택한 `cc`/SDK가 원본 measurement에 기록되어 있다.
