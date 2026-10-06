# 005 — CI·마지막 실패 주입·최종 판정

2026-10-06. 브랜치 `finalize/ci-verdict`. 기능을 확장하지 않고 현재 실행 경계를 회귀로 고정했다. 기존 구현·001–004 evidence를 `523b77c`에 보존한 뒤, `0060a56`에 감사 실패 수정과 CI를 분리했다. [계획](../plans/005-finalization.md), [최종 판정](../FINAL-VERDICT.md).

## 변경

- [check.py](../../scripts/check.py)에 unit/adversarial/lifecycle/scale/full group과 source SHA-256·HEAD·환경·실패/오류/skip evidence를 추가했다. skip이 있으면 통과로 판정하지 않는다.
- [macOS workflow](../../.github/workflows/regression.yml)는 syntax/unit과 실행 경계/full을 두 job으로 나눴다. 실행 backend·CLT·Python 3.12·Node 22를 확인하며 모델 session이나 API key가 필요 없다.
- Scale fixture의 CLT 고정 Git 경로를 기존 resolver로 바꿨다. [회귀](../../tests/test_scale_git_metadata.py).
- Controller Python의 `sys.base_prefix`와 Apple toolchain의 실제 Xcode Developer 경로를 runtime 읽기 범위에 반영했다. 쓰기 권한을 추가하지 않았고 secret deny와 인접 외부 read 차단 회귀를 유지했다. [Sandbox](../../guarded_agent/sandbox.py), [회귀](../../tests/test_sandbox_edges.py).
- 결과 audit 실패를 [MCP](../../guarded_agent/mcp.py)의 오류와 [CLI](../../guarded_agent/cli.py)의 exit 1로 전달하고, [Gateway](../../guarded_agent/gateway.py)가 같은 instance의 모든 후속 요청을 AU-ERROR로 차단하도록 수정했다.

## 출발점과 실패 기록

처음 전체 baseline은 중첩 sandbox의 Seatbelt/lifecycle 제한 때문에 173개 중 failures 55 / errors 14 / skip 0이었다. 실제 host에서 동일 baseline을 다시 실행하자 173개가 모두 통과했다. 실패를 제품 회귀나 성공 결과로 섞지 않고 [최초 JSON](evidence/005/baseline.json)과 [host JSON](evidence/005/baseline-host.json)을 함께 보존했다.

기존 004-05 이후 source 변경과 현재 회귀의 source hash를 [source-binding.json](evidence/005/source-binding.json)에 기록했다. 현재 source/test/script 57개는 모든 group evidence와 일치한다. Lifecycle/scale은 HEAD `523b77c`에서 uncommitted 마감 코드를 검사한 기록이고, unit/adversarial/full은 `0060a56`에서 검사했다. 당시 HEAD 차이는 그대로 남기며 실제 검사한 소스는 hash로 결합한다.

## 마지막 두 실패 주입

### 결과 audit 저장 실패

실제 FS executor가 `effect.txt`를 쓴 직후 audit pathname을 directory로 바꿔 result 저장을 실패시켰다. Decision은 이미 내구 기록됐고 파일에는 `applied fixture`가 남았다.

수정 전에는 `audit_error`가 있어도 MCP `isError:false`, CLI exit 0이었다. 감사 저장소를 복구한 뒤 같은 Gateway의 후속 write도 실행됐다. [red 회귀](evidence/005/focused-red.log), [초기 주입](evidence/005/injection-initial.json).

수정 후에는 execution 자체의 `succeeded`·`applied`를 유지하면서 audit_error를 전달한다. MCP는 오류, CLI는 exit 1이고 후속 요청은 AU-ERROR/미실행이다. 저장소를 복구하고 운영자가 실제 파일을 확인한 뒤 새 Gateway에서 읽을 수 있다. 자동 rollback이나 프로세스 간 영구 recovery lock을 구현한 것은 아니다. [green 회귀](evidence/005/focused-green.log), [최종 주입](evidence/005/injection-final.json), [tests](../../tests/test_final_failures.py).

### 활성 command 중 controller SIGKILL

자식의 ready marker를 확인한 뒤 controller를 SIGKILL했다. 종료 전후 contained process가 각각 1개였고, 자식은 허용된 `output`에 late marker를 썼다. 외부 marker write는 거부됐지만 controller 결과는 0 bytes, audit는 decision만 남고 자동 scope 기록은 없었다.

Trusted fixture가 controller가 살아 있을 때 캡처한 scope identity로 잔여 프로세스 1개를 종료하고 scope가 비었음을 확인했다. 이것은 operator cleanup이다. 제품의 controller 손실 자동 탐지·복구는 검증하거나 구현하지 않았다. [주입 결과](evidence/005/injection-final.json), [재현 코드](../../scripts/final_failure_probe.py).

## 회귀와 CLI smoke

macOS 15.7.8 arm64, Python 3.12.1, 실행 코드 `0060a56`. 모든 성공 group은 failures/errors/skipped 0이다.

| 명령 | tests | 결과 | elapsed (s) |
|---|---:|---|---:|
| `python3 scripts/check.py --group unit` | 18 | 통과 | 1.081 |
| `python3 scripts/check.py --group adversarial` | 106 | 통과 | 26.049 |
| `python3 scripts/check.py --group lifecycle` | 40 | 통과 | 31.580 |
| `python3 scripts/check.py --group scale` | 13 | 통과 | 20.433 |
| `python3 scripts/check.py --group full` | 177 | 통과 | 74.578 |

각 명령에는 `--evidence <새 JSON 경로>`를 붙였다. [JSON/log 목록](evidence/005/README.md). 추가 runtime 집중 회귀는 10개 통과, 1.749초다. `python3 -m compileall -q guarded_agent scripts tests examples`와 문서 재현 script syntax, diff whitespace 검사도 통과했다.

세션이 끊긴 뒤 남은 full/source hash와 M1/M2 결과를 확인해 완료된 검증을 복구했다. `/tmp` CLI helper의 최초 import 실패는 저장소 root import 설정으로 정리했고, 다시 실패한 build는 Seatbelt `Operation not permitted`로 실행 전 SH-SANDBOX이었다. [보존한 중첩 sandbox 결과](evidence/005/cli-smoke-nested.json).

현재 [재현 script](evidence/005/repro/cli_smoke.py)를 실제 host에서 실행해 basic init → discover → reviewed profile-apply → host config 생성·TOML parse → c-build/c-tests → host preflight를 확인했다. 모두 통과했고 preflight는 `codex-cli 0.160.0`이다. 모델 session은 실행하지 않았다. [host 결과](evidence/005/cli-smoke-host.json), [audit](evidence/005/cli-audit/host.jsonl).

## 보존 M1/M2 재측정

기존 `.guard-runs/scale-probe-03/live-M1|M2/workspace`와 각각의 기존 policy를 사용했다. 새로운 state/audit는 별도 `/tmp` 디렉터리에 기록하고 과거 session/verification/audit는 덮어쓰지 않았다. Guard status 각 세 번 뒤 build/tests를 실행했다. [재현 script](evidence/005/repro/scale_recheck.py).

| 항목 | M1 | M2 |
|---|---:|---:|
| tracked files | 3,000 | 10,000 |
| ignored files (생성된 binary 포함) | 10,001 | 25,001 |
| Git status median total | 960.448ms | 1,748.278ms |
| build | exit 0 | exit 0 |
| project tests | 22 통과 | 33 통과 |
| 실행 전후 HEAD / ending status | 같음 / clean | 같음 / clean |

다른 회귀와 겹친 첫 측정은 M1 1,003.104ms / M2 1,730.045ms였다. 전체 회귀가 끝난 뒤 단독 측정한 위 결과를 현재 수치로 사용하고, [겹친 측정](evidence/005/scale-recheck-overlapping.json)도 보존한다. [단독 결과](evidence/005/scale-recheck-serial.json), [M1 audit](evidence/005/scale-audit/M1.jsonl), [M2 audit](evidence/005/scale-audit/M2.jsonl).

004-05의 최적화 후 여섯 번 status median 626.48ms / 1,113.897ms보다 이번 수치가 높다. 서로 다른 시점·sample 수의 replay이며 특정 코드 변경의 성능 회귀 원인은 확인하지 않았다. 현재 build/test와 정상 경계 통과를 확인한 합성 scale 재실행으로 해석하고 새 live 모델 결과나 추가 속도 개선으로 주장하지 않는다.

## CI

로컬에서 CI와 같은 group 명령이 모두 통과했다. 복구 환경에서는 GitHub 주소 전용 `gh auth git-credential` 설정이 시스템 `osxkeychain`과 사용자 `store` helper를 덮고 있었고, CLI에 저장된 GitHub token은 유효하지 않았다. 전역 설정은 건드리지 않고 이번 명령의 helper 우선순위만 `osxkeychain`→`store`로 바꿔 push했다. GitHub 사용자 세션 인증은 다시 설정하지 않았다.

PR [#1](https://github.com/ImJeongBright/Guarded-Coding-Agent/pull/1)은 `8b432ef`에서 열었고, workflow run [37445603891](https://github.com/ImJeongBright/Guarded-Coding-Agent/actions/runs/37445603891)의 Syntax and policy contracts와 Execution boundaries and full regression이 모두 성공했다. Workflow는 `pull_request`, main push, 수동 실행을 trigger로 사용하므로 feature branch push만으로는 CI를 실행하지 않는다. 이 설명을 기록하는 후속 문서 commit은 PR의 새 head이므로 해당 head의 CI도 다시 확인한다.

## 자체 검토와 마감

- 결과 audit 실패의 applied 효과·MCP 오류·CLI exit·Gateway 후속 차단이 서로 일치하는지 확인했다.
- Controller SIGKILL 결과를 정상/timeout cleanup 통과와 구분하고 operator fixture cleanup을 자동 복구로 표기하지 않았다.
- 과거 173개, 현재 177개, 실제 모델 session과 현재 replay를 구분했다. 소스 hash·evidence 숫자·문서 링크를 교차검증했다.
- 기존 001–004 portable evidence는 수정하지 않고 005 증거를 추가했다. Export에는 검증에 필요한 JSON/JSONL/log만 포함하고 사용자 인증 저장소나 approvals DB를 포함하지 않았다.

README의 Portfolio Highlights와 [최종 열 가지 판정](../FINAL-VERDICT.md)을 작성했다. 한 PR에 기존 구현 snapshot, 마감 수정/CI, 문서·현재 evidence를 별도 commit으로 제공한다. 핵심 개발은 검증한 범위에서 마감하고 실제 사용의 새 문제를 재개 조건으로 삼는다. 장기 사용자 관찰은 미완료로 남긴다.
