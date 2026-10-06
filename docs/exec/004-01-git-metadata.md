# 004-01 — Git metadata 한도 분리

2026-10-05. 사용자 결과의 64,000-byte 한도가 숨은 전체 Git 경로 검사까지 자르던 문제를 다룬다.
목표는 전체 NUL path state를 bounded 범위에서 검증하면서, diff/stdout 사용자 결과와 민감 경로 fail-closed를 유지하는 것이다.

## 변경

- [domain.py](../../guarded_agent/domain.py)에 내부 Git metadata 8 MiB 및 path count 250,000 상한을 추가했다.
- [sandbox.py](../../guarded_agent/sandbox.py)는 일반 Shell/Git 출력 64,000-byte 기본값을 유지하고, trusted adapter가 지정한 내부 capture limit만 제한된 metadata 범위에서 받는다.
- [git.py](../../guarded_agent/git.py)의 `ls-files -z` 및 changed-path 조회가 내부 metadata cap을 사용한다. NUL 종료·경로 검증·완전성 검사 후에도 기존 literal path와 sensitive source 정책을 적용한다.
- capture/path 수 상한 초과, malformed 또는 truncated metadata는 `GT-STATE`로 executor 전에 닫힌다.
- 새 [scale 회귀](../../tests/test_scale_git_metadata.py)는 2,000개 tracked C 경로(사용자 출력보다 큰 metadata), status·단일 diff·stage·commit, staged sensitive 삭제, metadata truncation 및 path count overflow를 확인한다.

8 MiB와 250,000은 무제한 metadata를 허용하는 값이 아니다. M1/M2를 수용하고 bound 초과에서 실행하지 않는 후보 상한이며,
큰 파일명 저장소·over-bound 대조군의 결과를 보고 조정 여부를 기록한다.

## 실행 결과

- 신규 focused suite: 3 tests, 통과, 12.136초.
- 2,000개 tracked path integration: status·단일 diff·stage·commit·clean status ALLOW. 전체 path metadata는 64KB보다 크고 일반 diff 응답은 계속 64KB 이하.
- fake `.env` staged deletion은 `FS-SENSITIVE / executed:false`. audit/MCP 결과에도 dummy content 없음.
- truncated metadata와 patch한 250,000 path 초과는 `GT-STATE`로 executor 전에 거부.
- M1/M2: metadata path bytes 99,011 / 330,011; 두 규모 모두 status와 단일 파일 diff ALLOW.
- M1: status 1.686초, diff 2.004초; Shell no-op 0.586초.
- M2: status 4.465초, diff 4.552초; Shell no-op 0.954초.
- M1/M2 root search는 `entry_limit / incomplete:true`; module 경로로 좁힌 search는 1 match로 각각 19.389 / 26.591ms 완료.
- 전체 회귀 162 tests, 실패/error/skip 0, macOS 15.7.8 arm64/Python 3.12.1, 51.475초.
- 사용자 출력 cap을 지키는 기존 100,000-byte Shell 출력 회귀와 staged deletion/rename·literal path·truncated metadata를 재통과했다.

M1/M2 각 operation은 한 번씩 실행한 smoke timing이라 median/p95로 해석하지 않는다.
이 테스트는 생성 C 경로의 크기·파일 수를 대상으로 하며, 실제 중규모 C 앱을 컴파일한 실험은 아니다.

## 첫 실패와 판단

초기 통합 fixture에서 `.env`를 baseline에 커밋하자 `git status`가 `FS-SENSITIVE`로 닫혔다.
전체 tracked list에 민감 경로가 있으면 status까지 거부하는 현 기존 정책이 정상 작동한 것이다.
따라서 일반 large-repository flow는 민감 파일이 없는 fixture에서 끝까지 확인하고,
별도 대조 단계에 fake `.env`를 넣어 staged 삭제 diff가 secret을 노출하지 않는지 검사했다.
실패를 통과 처리하거나 정책 우선순위를 바꾸지 않았다.

## 완료 판정

004-01 완료: M1/M2의 status/single-file diff, 2,000-file stage/commit flow, 민감 삭제 차단,
truncated/path-count overflow fail-closed와 전체 기존+신규 회귀가 통과했다.
M2(10,000 / 25,000)는 status/diff/Shell/search smoke로 확인했다.
M2 Git latency와 root search incomplete는 다음 workspace scan/search phase의 입력이다.

## 증거

원본 smoke 결과는 `.guard-runs/scale-probe-02/`에 보존한다.
[portable evidence](evidence/004/004-01/README.md)에 case 결과, policy/audit, source manifest와 회귀 기록을 뒀다.
portable path 대체본은 동일한 capture-time session으로 재인증할 수 있는 원본이 아니다.
