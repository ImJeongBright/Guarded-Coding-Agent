# 001-10 — Regression and Usability Verdict

Date: 2026-10-03. Base commit: b93ba56. Policy: 001. Working tree changes, no new commit.

후속: 2026-10-04 [002의 현재 판정](002-09-verdict.md)에서 실제 Codex와 세 언어 task를 검증했다.
아래의 미검증 설명은 001 실행 시점이다. 장기 사용은 후속에서도 아직 미측정이다.

## Verification

`python3 scripts/check.py --evidence docs/exec/evidence/regression.json`:
67 tests, failures/errors/skips 0. 실제 macOS sandbox 사용이 필요한 검사는
중첩 sandbox 밖의 승인된 테스트 프로세스에서 실행했다. 파괴적 fixture는 임시 경로만 사용했다.

`python3 scripts/dogfood.py --output .guard-runs/user-x-08`:
35 proposals, 정상 25개 approval/denial 0, DB 8 tests pass, approved bare remote push 1회,
denied proposal의 실제 실행 0. 보안 변경 이후 정상 개발 흐름을 다시 확인했다.

## Policy Refinements

1. registered exact argv의 문장부호는 데이터로 허용, 미등록 composition은 거부.
2. macOS path alias를 canonicalize, 원래 remote URL은 approval에 유지.
3. runtime package/launcher만 보호해 sibling workspace의 개발을 허용.
4. clang/SDK 고정과 최소 loader metadata로 build 오탐 해결.
5. protected path casefold, remote identity approval로 두 재현된 보안 gap 차단.
6. command별 write_paths로 source overwrite/delete gap 차단.
7. tool description에 허용 capability를 공개해 exact argv 추측·반복 문의를 줄임.
각 보안 경계 및 허용의 regression을 최종 suite/X에 포함했다.

## 종료 질문에 대한 판정

**이 C 개발 workload에서는 계속 켜고 사용할 수 있는 결과다.** 정상 local 개발을
승인 없이 완료했고 위험 제안은 차단하며 publish에만 한 번 승인했다.

**전체 실제 coding-agent 사용의 종료 조건은 아직 확정하지 않는다.** 현재 Codex의 native
도구 interception, hook activation/host failure behavior, 다른 언어·저장소,
1~2주 승인 피로도를 검증하지 못했다. Level 2와 한정된 Level 3 실험은 완료했다.
장기·live host 증거가 필요한 일은 [002 plan](../plans/002-live-dogfooding.md)에 분리했다.
API key나 외부 서비스는 Guard에 추가하지 않았다.
