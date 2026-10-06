# 005 — 최종 마감 계획

2026-10-06. 브랜치: `finalize/ci-verdict`. 기능 확장이 아니라 현재 실행 경계의 회귀 고정과 증거 정리가 목적이다.

## 확인한 출발점

- 시작 HEAD `b93ba56`은 설계 문서만 포함한다. 구현·테스트·001~004 portable evidence와 일부 문서 변경은 이미 작업 트리에 있었으며 삭제하거나 과거 기록을 고치지 않는다. 한 PR 안에서 기존 구현 snapshot과 마감 변경을 별도 commit으로 구분한다.
- Python 3.11+ 표준 라이브러리, unittest, macOS Seatbelt/Darwin lifecycle backend다. 현재 CI는 없다. 로컬 장비는 macOS 15.7.8 arm64/Python 3.12.1이다.
- 제품 모듈·scripts·18개 test 파일·설계/계획/Exec를 검토했고, portable JSON/JSONL 257개를 파싱했다. 시작 코드와 004-05 source manifest의 일치 여부를 별도 기록한다.
- 이전 173개 회귀 수치는 재사용하지 않는다. 중첩 sandbox 최초 실행은 55 failures/14 errors이며 실제 host 재실행을 별도 보존한다.
- 기존 failure coverage: decision audit 실패, 승인 binding/replay/동시 consume, policy 변경, profile 후보 변조, detached/reparent child, backend/cleanup 실패, hook/MCP 시작 및 첫 호출 실패. 마지막 두 실험은 기존 검증이 비운 실행 이후 경계를 대상으로 한다.

## 필요한 변경과 완료 기준

| 순서 | 작업 | 완료 기준 |
|---|---|---|
| 1 | 기존 구현 snapshot 보존, baseline 재실행 | 과거 evidence 불변; 현재 실행 hash/환경/실패·성공 구분 |
| 2 | CI group 명령과 macOS workflow | syntax, unit/policy, FS/Shell/Git adversarial, approval/audit/lifecycle, scale, full; API/model 필요 없음 |
| 3 | CI fixture 이식성 | scale test의 CLT 고정 Git 경로를 기존 resolver로 변경; Python/Node runner runtime이 sandbox에서 실제 실행됨 |
| 4 | 결과 audit 저장 실패 주입 | 실제 FS 효과와 미저장 결과를 정직하게 전달; MCP/CLI 성공 판정 및 후속 요청 경계를 검사; 결함이면 최소 수정·red→green 회귀 |
| 5 | 활성 명령 중 controller SIGKILL | 준비 완료 handshake 뒤 kill; 남은 child/허용 scope·차단 scope·audit gap 관찰; trusted fixture가 identity 기반으로 정리; 자동 복구와 혼동하지 않음 |
| 6 | focused와 full, CLI 안내 smoke, M1/M2 재측정 | CI와 동일 명령 통과; skip 없이 실행; 재측정은 현재 synthetic 결과로 별도 기록 |
| 7 | FINAL-VERDICT와 README | 요청한 10개 판정 항목, 사용 명령·portfolio·한계; 모든 핵심 주장에 code/test/evidence 링크 |
| 8 | 문서/숫자 교차검증·self-review·PR | historical/current 및 synthetic/live 구분; 한 PR, remote CI 실행 상태 정직하게 표시 |

## 판단 경계

Audit 장애가 실행 후 발생하면 이미 생긴 효과를 rollback된 것으로 표시하지 않는다. Controller SIGKILL은 Python finally와 정상 cleanup을 실행할 수 없으므로 살아남은 프로세스가 관찰되어도 supervisor를 새로 만들지 않는다. operator recovery 필요라는 제한을 최종 판정에 반영한다.

macOS runner 한 환경과 빠른/실행 회귀 두 job만 사용한다. matrix/cache/artifact pipeline, Linux/Windows, multi-agent, browser/DB/cloud/network capability, 범용 package manager나 policy DSL은 추가하지 않는다. 실제 모델 session은 기존 증거를 검토하되 CI 필수 조건으로 두지 않는다.

README 자체에 Portfolio Highlights를 짧게 두고, 같은 내용을 반복하는 PORTFOLIO 문서는 만들지 않는다. 핵심 개발은 검증한 workload와 자동 회귀 조건에서 종료하고, 실제 사용에서 새 문제가 확인될 때 재개한다.

결과: [005 Exec](../exec/005-final-failure-injection.md), [최종 판정](../FINAL-VERDICT.md).

## 실행 상태 — 2026-10-06

1–7 완료. 현재 코드 full 177개와 모든 group이 실패·오류·skip 없이 통과했고,
CLI host smoke 및 보존 M1/M2 build/tests가 통과했다. 결과 audit 손실은 최소 수정과
red→green으로 고정했으며 controller SIGKILL의 잔여 자식은 자동 복구 한계로 명시했다.
8의 문서·소스/evidence 교차검증을 완료했다. PR #1에서 `8b432ef`와 최종 문서 commit
`2b70c35` 기준 원격 두 job CI가 모두 통과했다. 2026-10-07 확인 시 PR #1은 `main`에
`c64912a`로 병합됐고 main push CI도 통과했다. 1–8을 완료했으며, 실행 링크는
[005 CI 기록](../exec/005-final-failure-injection.md#ci)에 보존했다.
