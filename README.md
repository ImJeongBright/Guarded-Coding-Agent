# Guarded Coding Agent

코딩 에이전트의 Filesystem / Shell / Git 요청을 실행 전에 검사하는 로컬 도구다. 모델은 작업을 제안하고, 프로그램은 실제 실행 권한을 결정한다.

> LLM interprets intent; the program enforces authority.

정상적인 source 수정·build·test·local commit은 등록한 범위에서 실행한다. Push는 정확한 행동에 결합한 운영자 승인을 요구하고, workspace escape·secret 접근·force push는 차단한다. [최종 판정](docs/FINAL-VERDICT.md)에 검증한 범위와 남은 한계를 정리했다.

## 실행

Python 3.11+ 표준 라이브러리만 사용한다. Shell/Git 실행에는 macOS, Command Line Tools, 사용 가능한 `sandbox-exec`가 필요하다. Guard 자체에는 API key나 모델 서비스가 필요 없다. 실제 Codex 개발 실험은 기존 Codex 로그인과 모델 서비스를 사용했다.

```sh
python3 -m compileall -q guarded_agent scripts tests examples
python3 scripts/check.py --group full --evidence /tmp/guard-regression.json
python3 scripts/dogfood.py --output /tmp/guard-user-x-new-run
```

Dogfood 출력은 새 경로를 지정한다. 중첩 sandbox가 Seatbelt 적용을 금지하면 실행 전에 실패하므로 Guard의 자체 sandbox를 적용할 수 있는 macOS host에서 실행한다.

Workspace 준비, 프로필 발견·검토·등록, stdio MCP 연결과 승인은 [Local Usage](docs/10-local-usage.md)를 따른다. 전용 host profile은 Codex CLI **0.160.0**에서 검증했으며, 직접 실행 경로 차단과 host read-only 설정을 함께 요구한다.

## 검증 결과

- 현재 실행 코드 `0060a56`: **전체 회귀 177개 통과**, 실패·오류·skip 0. [JSON](docs/exec/evidence/005/regression-full.json), [소스 해시 결합](docs/exec/evidence/005/source-binding.json).
- CI: macOS 한 환경에서 syntax/unit과 adversarial/approval/audit/lifecycle/scale/full을 두 job으로 실행한다. [Workflow](.github/workflows/regression.yml), [CI 상태 기록](docs/exec/005-final-failure-injection.md#ci).
- 004 실제 Codex 개발: M1/M2 C DBMS의 다섯 feature task와 최적화 후 확인 task, Guard 호출 153회 중 ALLOW 152 / DENY 1 / 승인 0. 독립 검증과 clean local commit을 완료했다. [004 실행 기록](docs/exec/004-05-live-medium-scale.md).
- 005 재측정: 보존된 M1/M2에서 Guard Git status 중앙값 **960ms / 1,748ms**, build 및 프로젝트 테스트 **22개 / 33개 통과**. 새 모델 session 없이 재실행한 결과이며 004의 성능 수치와 구분한다. [재측정 증거](docs/exec/evidence/005/scale-recheck-serial.json).
- 마지막 실패 주입: 결과 audit 저장 실패 뒤 MCP/CLI가 성공으로 판정하던 결함을 수정했다. Controller SIGKILL 뒤 자식이 남는 한계는 재현해 기록했다. [005 실행 기록](docs/exec/005-final-failure-injection.md).

## Portfolio Highlights

- **권한과 판단 분리:** 구조화된 요청, deterministic policy, 실행 직전 재검증과 OS sandbox를 연결했다. [Gateway](guarded_agent/gateway.py), [Sandbox](guarded_agent/sandbox.py).
- **정확한 승인:** workspace/run/actor/policy/remote/branch/HEAD/expiry에 결합한 일회용 grant와 replay·동시 consume 회귀를 구현했다. [Approval](guarded_agent/approval.py), [회귀](tests/test_hardening.py).
- **실패 실험으로 경계 보강:** hook 단독 fail-open, 쓰기 scope 경쟁, 감사 기록 손실을 재현하고 red→green 회귀를 남겼다. [002](docs/exec/002-live-dogfooding.md), [001–003 수정](docs/exec/fix-001-003.md), [005](docs/exec/005-final-failure-injection.md).
- **성능과 안전성 함께 검증:** 10,000 tracked / 25,000 ignored fixture의 Git metadata 병목을 줄이면서 link·secret·불완전 state 차단을 유지했다. [구현과 측정](docs/exec/004-05-live-medium-scale.md), [회귀](tests/test_scale_git_metadata.py).

## 현재 한계

모의 X는 검증한 macOS/C DBMS 흐름에서 계속 사용할 수 있다고 판정했다. 실제 사람의 1–2주 연속 사용, 임의의 대규모 저장소, linked worktree, symlink dependency tree, package 설치와 다른 OS/host는 평가하지 않았다.

정상 반환·timeout의 자식 cleanup을 검증했지만, controller를 SIGKILL하면 자식이 허용 scope 안에서 계속 실행할 수 있다. 자동 supervisor·복구는 구현하지 않았다. 결과 audit 실패도 이미 생긴 변경을 되돌리지 않으며 운영자의 확인·복구가 필요하다. [실패 주입 증거](docs/exec/evidence/005/injection-final.json).

핵심 개발은 이번 범위에서 마감한다. 재개는 실제 사용에서 새 결함이나 지원할 workload가 확인됐을 때 결정한다. 설계·계획·001–005 실행 기록은 [문서 지도](docs/README.md)에서 찾을 수 있다.
