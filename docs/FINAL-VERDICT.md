# 최종 판정

2026-10-06. **검증한 macOS 전용 host와 ordinary C/Python/JavaScript 개발 흐름에서 로컬 Guard의 핵심 개발을 마감한다.** 모델에 정상 개발을 맡기면서 Filesystem/Shell/Git 실행 권한을 별도 프로그램으로 제한한다는 목표는 충족했다. 범용 코딩 에이전트의 모든 도구와 장기 사용성까지 검증한 판정은 아니다.

현재 실행 코드 `0060a5626eabe7b1045478fa3ec46d6267e1fb0b`에서 전체 회귀 177개가 통과했고 실패·오류·skip은 없다. 실제 모델 결과는 002–004 당시 기록이다. 005는 현재 코드의 회귀·실패 주입·보존 workspace 재실행이며 새 모델 개발 session을 포함하지 않는다. [005 Exec](exec/005-final-failure-injection.md), [회귀 JSON](exec/evidence/005/regression-full.json), [소스 해시](exec/evidence/005/source-binding.json).

## 열 가지 판정

| 항목 | 판정 | 근거와 적용 범위 |
|---|---|---|
| 1. 모델 판단과 실행 권한 분리 | 충족 | Schema → 정규화 → 정책 → durable decision audit → 재검증 → adapter 실행. 알 수 없는 요청은 DENY다. [Gateway](../guarded_agent/gateway.py), [정책](../guarded_agent/policy.py), [core 회귀](../tests/test_core.py). |
| 2. Filesystem 경계와 secret 보호 | 충족 | Ordinary 파일만 접근하고 traversal/link/secret/보호된 state를 차단한다. hash edit는 stale 변경을 거부한다. [Filesystem](../guarded_agent/filesystem.py), [적대적 회귀](../tests/test_review_filesystem_fixes.py), [write scope 회귀](../tests/test_write_scope.py). |
| 3. Shell의 실제 효과 제한 | 충족 | Exact argv/cwd/write scope, clean env, Seatbelt와 시간·출력·파일 크기 한도를 적용한다. CI의 선택된 Python runtime은 읽기만 열며 secret·인접 외부 경계는 유지한다. [Sandbox](../guarded_agent/sandbox.py), [runtime 회귀](../tests/test_sandbox_edges.py), [focused 결과](exec/evidence/005/runtime-focused.log). |
| 4. Git 위험 동작과 정확한 승인 | 충족 | Local 작업은 허용하고 push는 remote/branch/HEAD 등 실제 행동에 결합한 일회용 승인을 요구한다. force/protected push·stale/replay/concurrent consume를 차단한다. [Git](../guarded_agent/git.py), [Approval](../guarded_agent/approval.py), [회귀](../tests/test_hardening.py). Push 실행 검증은 local bare remote다. |
| 5. 감사 실패와 실제 변경의 전달 | 수정 후 충족 | 결과 audit 손실을 MCP `isError:true`와 CLI exit 1로 전달하고 같은 Gateway의 후속 요청을 AU-ERROR로 차단한다. 이미 적용된 파일 변경은 applied로 남긴다. [실패 주입](exec/evidence/005/injection-final.json), [회귀](../tests/test_final_failures.py). |
| 6. 프로세스 lifecycle | 조건부 | 정상 반환·timeout의 detached/reparent 자식 종료와 cleanup 실패 차단을 검증했다. Controller SIGKILL에서는 자식이 남아 허용 경로에 쓸 수 있고 result audit도 없다. 운영자 정리가 필요하다. [lifecycle 회귀](../tests/test_review_lifecycle_fixes.py), [SIGKILL 증거](exec/evidence/005/injection-final.json). |
| 7. 실제 coding-agent host 연결 | 검증한 profile에서 충족 | Codex CLI 0.160.0의 직접 도구·hook/MCP 장애를 실험했다. hook 단독 fail-open 때문에 native 도구 차단과 host read-only가 필수다. 현재 세션이나 다른 host의 routing을 소급 보호하지 않는다. [002](exec/002-live-dogfooding.md), [host 구현](../guarded_agent/host.py), [사용 안내](10-local-usage.md). |
| 8. 정상 개발의 승인·차단 마찰 | scoped 통과 | 002 세 언어 task는 49개 호출에 승인·거부 0. 003 두 기존 프로젝트의 여섯 task는 110개 호출에 승인 0, 탐색 거부 1을 보완했다. 004 여섯 session은 153개 호출에 승인 0, 없는 파일 read 거부 1이다. [002](exec/002-live-dogfooding.md), [003](exec/003-real-project-usability.md), [004](exec/004-05-live-medium-scale.md). |
| 9. M1/M2 규모와 Git 비용 | fixture 범위에서 통과 | 004의 M2 metadata 병목 수정 뒤 실제 모델 Git 호출은 약 1.0–1.3초였다. 005 단독 replay의 status 중앙값은 M1 960ms / M2 1,748ms, build와 22/33개 프로젝트 테스트가 통과했다. [004 측정](exec/004-05-live-medium-scale.md), [005 replay](exec/evidence/005/scale-recheck-serial.json). |
| 10. 회귀 고정·증거·마감 | 로컬·원격 CI 검증 완료 | macOS 두 job workflow를 추가하고 177개 full suite, red→green, CLI smoke, 소스 해시와 portable evidence를 보존했다. 2026-10-07 확인 시 최종 PR head `2b70c35`와 main merge `c64912a`의 두 job CI가 모두 성공했다. [Workflow](../.github/workflows/regression.yml), [005 및 CI 상태](exec/005-final-failure-injection.md#ci), [증거 목록](exec/evidence/005/README.md). |

## 실패 실험에서 남은 결론

결과 audit 저장은 실행 이후에 실패할 수 있다. 이번 주입에서는 파일 write가 실제 적용됐지만 result audit가 남지 않았다. 수정 전 MCP/CLI는 이를 성공으로 취급했고, 저장소를 복구한 뒤 같은 Gateway의 추가 write도 통과했다. 수정 후에는 오류를 전달하고 세션을 차단한다. 운영자는 실제 효과와 감사 저장소를 확인·복구한 뒤 새 Gateway를 시작해야 한다. 차단 flag는 해당 Gateway instance에 있으며 프로세스 간 영구 recovery lock이 아니다. [초기 결과](exec/evidence/005/injection-initial.json), [수정 후 결과](exec/evidence/005/injection-final.json).

Controller SIGKILL은 `finally`를 실행하지 않는다. Ready handshake 뒤 kill했을 때 contained child 1개가 남았고, controller 종료 뒤 허용 scope의 marker를 썼다. 외부 write는 Seatbelt가 계속 거부했지만 controller 응답·result audit·자동 scope 기록은 없었다. Trusted fixture가 미리 확보한 scope identity로 자식을 정리한 결과를 제품의 자동 복구로 해석하지 않는다. [재현 코드](../scripts/final_failure_probe.py), [실측 결과](exec/evidence/005/injection-final.json).

## 사용성·성능 해석

모의 사용자 X의 판정은 **검증한 profile에서 계속 켜고 개발할 수 있다**다. 정상 source edit/build/test/local commit의 반복 승인은 없었고, 실제 모델이 실패와 incomplete 검색 뒤 작업을 이어 clean commit까지 완료했다. 사람이 직접 느끼는 준비 부담·만족도·1–2주 지속 사용은 측정하지 않았다.

005 status 측정은 각 세 번의 Guard `timings_ms.total` 중앙값이다. 004의 여섯 번 측정보다 높으므로 추가 성능 개선이나 정확한 회귀 원인을 주장하지 않는다. 모델 생성·MCP round trip 시간도 포함하지 않는다. 보존 workspace에는 합성 ignored fixture 외에 build binary 한 개가 있어 실제 ignored count는 M1 10,001 / M2 25,001이었다. 재실행 전후 HEAD가 같고 Git status는 clean했다. [단독 replay](exec/evidence/005/scale-recheck-serial.json).

## 마감과 재개 조건

이번 마감에서 Linux/Windows, browser/DB/cloud, 범용 package manager, linked worktree, symlink dependency tree, 자동 supervisor, 범용 정책 DSL은 추가하지 않는다. 동일 UID의 악성 운영자·kernel exploit·모든 resource isolation도 보장 범위 밖이다. 넓은 검색의 5,000-entry 한도와 실제 인증을 쓰는 원격 push 미검증은 [사용 안내](10-local-usage.md)에 남겼다.

검증한 workload를 반복하기 위해 핵심 기능을 더 늘릴 필요는 없다. 실제 사용에서 새로운 경계 결함·지속적인 정상 작업 차단·지원할 프로젝트 형태가 확인되면 해당 재현과 회귀를 기준으로 재개한다. Stage 07의 장기 사용자 관찰은 미완료 상태로 남긴다. [Roadmap](08-roadmap.md), [005 계획](plans/005-finalization.md).
