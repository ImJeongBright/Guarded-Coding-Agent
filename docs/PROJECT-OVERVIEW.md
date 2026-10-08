# 프로젝트 개요 및 포트폴리오 요약

## 한 문장

Guarded Coding Agent는 코딩 에이전트가 파일·명령·Git을 사용할 때 요청을 실행 전에 검사하는 로컬 policy gateway다. 모델은 작업을 제안하고, 코드로 구현한 정책이 실행 허용·운영자 승인·차단을 결정한다.

## 실제로 해주는 일

| 영역 | 에이전트가 할 수 있는 일 | 적용하는 경계 |
|---|---|---|
| Filesystem | 저장소 파일 나열·읽기·검색·쓰기·수정·단일 파일 삭제 | workspace 밖 경로, secret, symlink escape를 차단한다. edit는 파일 hash가 바뀌었으면 중단한다. |
| Shell | 운영자가 등록한 build/test 등의 명령 실행 | 기본은 명령 미허용이다. exact argv, 작업 디렉터리, 쓰기 경로를 검토해 등록하고 macOS Seatbelt sandbox 안에서 실행한다. |
| Git | status/diff/log, 명시적 파일 stage, local commit, branch 및 push 작업 | `git add .`, 강제 push, 보호 대상 branch의 위험한 변경을 막는다. 원격 push는 remote·branch·HEAD 등 실제 상태에 결합한 1회 승인이 필요하다. |
| 정책·감사 | 각 요청의 결정과 실제 실행 결과 확인 | `ALLOW`, `REQUIRE_APPROVAL`, `DENY`를 반환하고, 결정·결과를 감사 로그에 남긴다. 실행 후 실패와 이미 생긴 효과도 구분해 기록한다. |

stdio MCP server는 `guard_filesystem`, `guard_shell`, `guard_git` 도구를 coding agent에 제공한다. CLI로도 같은 Gateway를 호출할 수 있다. Guard는 coding agent나 모델을 포함하지 않으며 자체 동작에 API key나 모델 서비스가 필요하지 않다.

## 사용 흐름

```text
에이전트가 도구 요청 → schema 검사와 정규화 → 정책 판정 → 필요한 경우 운영자 승인
                   → 실행 직전 재검증 → 제한된 실행 → 결과와 감사 기록
```

일반적인 용도는 저장소 안의 코드를 읽고 수정한 다음, 등록된 build/test 명령을 실행하고, diff를 검토해 local commit을 만드는 것이다. 저장소마다 workspace와 상태 디렉터리를 지정하고, 필요한 명령 권한을 운영자가 좁게 검토해 등록한다. 설치 예시와 MCP/host 설정은 [Local Usage](10-local-usage.md)에 있다.

## 무엇이 검증됐나

- 현재 코드의 전체 회귀 **177개 통과**. CI는 syntax/policy와 execution boundary/full regression 두 macOS job으로 나뉘며, 현재 GitHub `main` branch protection은 두 job 모두를 required status check로 지정한다. [workflow](../.github/workflows/regression.yml), [최종 판정](FINAL-VERDICT.md)
- Codex CLI 0.160.0에 Guard를 연결해 C, Python, JavaScript 작업과 두 기존 저장소의 task를 수행했다. 중규모 C 저장소 여섯 session에서는 153회 tool call 중 152회 ALLOW, 1회 DENY, 승인 0회였고 독립 검증과 local commit까지 완료했다. [004 실행 기록](exec/004-05-live-medium-scale.md)
- 보존한 합성 규모 fixture에서 Guard Git status 중앙값은 M1 **960 ms**, M2 **1,748 ms**였다. 이는 Guard 내부 timing이며 모델 생성 및 MCP 왕복 시간을 포함하지 않는다. [005 재측정](exec/evidence/005/scale-recheck-serial.json)

이 수치는 검증한 host와 workload의 결과다. 임의의 저장소·coding agent·장기 사용에 대한 일반 성능이나 호환성 보장은 아니다.

## 적용 범위와 한계

- Shell/Git 격리는 macOS, Command Line Tools, `sandbox-exec`가 있는 환경을 요구한다. 다른 OS와 중첩 sandbox에서는 우회하지 않고 실패한다.
- 프로젝트별 Shell capability는 자동 허용되지 않는다. 운영자가 argv/cwd/write scope를 등록해야 하며, 검증한 coding-agent host 설정은 Codex CLI 0.160.0이다.
- Controller가 강제 종료되면 sandbox 안의 자식 프로세스가 남아 허용된 경로에 계속 쓸 수 있다. 자동 supervisor나 복구 기능은 없으며 운영자 확인이 필요하다.
- linked worktree, symlink dependency tree, package 설치, 실제 credential을 쓰는 원격 push와 1–2주 지속 사용은 평가하지 않았다.

GitHub `main`의 required checks는 이 프로젝트 저장소의 변경을 검사하는 CI 설정이다. 실행 중인 에이전트의 filesystem/shell/git 권한을 대신 통제하는 기능은 Guard의 로컬 Gateway다.

## 포트폴리오 소개 문안

**한국어**

> 코딩 에이전트의 도구 실행을 프로그램 정책으로 통제하는 macOS 로컬 gateway를 구현했습니다. Filesystem·Shell·Git 요청을 정규화해 실행 전에 판단하고, 저장소 경계와 명령별 쓰기 범위를 제한하며, 원격 push는 실제 branch와 HEAD에 결합된 일회성 승인으로 보호합니다. Codex CLI를 이용한 C/Python/JavaScript 및 중규모 C 저장소 개발 실험, 실패 주입, 177개 회귀 테스트로 동작 경계를 검증했습니다. 강제 종료 시 자식 프로세스가 남을 수 있는 조건 등 미해결 한계도 재현하고 문서화했습니다.

**English**

> Built a local macOS policy gateway for coding-agent tool calls. It validates normalized filesystem, shell, and Git requests before execution, applies repository and command-specific write boundaries, and binds remote-push approval to the exact repository state. I evaluated it with Codex CLI across C, Python, JavaScript, and medium-scale C repository tasks, and used failure injection plus 177 regression tests to verify the boundaries. I also reproduced and documented unresolved cases, including child processes that may outlive a force-killed controller.

## 포트폴리오·이력서용 bullet

- **실행 권한 분리:** 코딩 에이전트의 파일·명령·Git 요청을 실행 전에 검사하는 macOS 정책 gateway 설계·구현. 기본 차단 정책, 실행 직전 재검증, 명령별 쓰기 범위와 OS sandbox를 연결해 모델이 제안한 작업의 실행 범위를 제한. [Gateway](../guarded_agent/gateway.py), [Sandbox](../guarded_agent/sandbox.py)
- **정확한 승인:** 원격 push 승인을 대상 저장소와 원격 목적지, branch·HEAD 등 실제 상태에 결합한 일회용 권한으로 구현. 만료·상태 변경·승인 재사용을 거부하고, 동시 요청에서도 한 번만 소비되는 동작을 회귀로 검증. [Approval](../guarded_agent/approval.py), [회귀](../tests/test_hardening.py)
- **성능 개선:** Git 추적 파일 1만 개·ignored 파일 2만 5천 개의 합성 저장소에서 반복적인 경로 해석·파일 정보 조회가 병목임을 프로파일링으로 확인. 링크·민감 경로 검사를 유지하면서 004 전후 측정의 Guard `git status` 중앙값을 **3.90초에서 1.11초로 약 71.4% 단축**. [측정과 수정](exec/004-05-live-medium-scale.md#성능-문제와-수정), [회귀](../tests/test_scale_git_metadata.py)
- **실패 대응:** 실제 파일 변경 뒤 감사 로그 저장이 실패해도 성공으로 반환되던 결함을 실패 주입으로 재현·수정. MCP 오류 응답, CLI 실패 코드, 동일 gateway의 후속 요청 차단을 적용하고 이미 발생한 변경과 기록 실패를 구분해 전달하도록 회귀로 고정. [실패 주입](exec/005-final-failure-injection.md#결과-audit-저장-실패), [회귀](../tests/test_final_failures.py)
- **개발 흐름 검증:** Codex CLI를 연결한 중규모 C 개발 여섯 세션에서 도구 호출 **153회(허용 152·차단 1·승인 0)**를 기록하고 독립 동작 검증과 local commit까지 완료. 최종 코드의 **177개 회귀 테스트 통과** 결과를 소스 해시와 함께 보존하고 macOS CI에 연결. [개발 실험](exec/004-05-live-medium-scale.md), [최종 회귀와 CI](exec/005-final-failure-injection.md)

성능 개선 수치는 004의 같은 M2 합성 fixture에서 최적화 전 실제 개발 호출 5회와 최적화 후 status 호출 6회의 중앙값을 비교한 결과다. 약 71.4%는 원본 중앙값 **3,897.409ms → 1,113.897ms**로 계산했다. Guard 내부 timing이며 모델 생성·MCP 왕복 시간은 포함하지 않는다. 별도 시점에 각 3회 실행한 005 재측정의 M2 중앙값은 **1.748초**로, 위 개선 수치와 구분한다. [004 원본 측정](exec/evidence/004/004-05/latency-M2.json), [최적화 후 측정](exec/evidence/004/004-05/post-optimization-benchmark.json), [005 재측정](exec/evidence/005/scale-recheck-serial.json)

## 자소서 사례 초안

### 성능 병목 해결

Guarded Coding Agent를 실제 개발 흐름에 연결해 검증하던 중, Git 추적 파일 1만 개를 가진 합성 저장소에서 Git 요청마다 약 4초가 걸리는 문제를 발견했습니다. 명령 실행과 실행 전 검사에 걸리는 시간을 나누어 측정하고 프로파일링한 결과, 파일마다 경로를 반복해서 해석하고 파일 정보를 조회하는 과정이 병목이었습니다.

Git metadata의 경로 형식을 엄격히 검사하도록 처리 방식을 바꾸고, 저장소의 링크 검사와 민감 경로 차단, 실행 직전 재검증은 유지했습니다. 같은 fixture에서 Guard `git status` 중앙값이 3.90초에서 1.11초로 약 71.4% 줄었고, 후속 Codex 개발 세션에서도 Git 요청이 약 1.0–1.3초에 완료되는 것을 확인했습니다. 잘못된 경로와 민감 파일, 검사 중 추가된 링크를 차단하는 회귀도 통과했습니다. 병목을 측정해 수정 범위를 정하고, 속도와 기존 차단 조건을 함께 검증했습니다.

근거: [성능 분석과 수정 기록](exec/004-05-live-medium-scale.md#성능-문제와-수정), [최적화 후 실제 개발](exec/004-05-06-post-optimization.md), [안전성 회귀](../tests/test_scale_git_metadata.py)

### 감사 기록 실패 대응

Guarded Coding Agent의 파일 쓰기를 검증하면서 실행 결과를 감사 로그에 기록하는 단계에 실패를 주입했습니다. 파일은 이미 변경됐는데 감사 로그 저장이 실패해도 MCP와 CLI가 성공을 반환하는 결함을 재현했습니다. 감사 저장소를 복구한 뒤에는 같은 gateway가 다음 쓰기까지 허용했습니다.

실제 파일 변경과 감사 기록의 저장 결과를 구분하고, 기록 실패를 MCP 오류 응답과 CLI 실패 코드로 전달하도록 수정했습니다. 같은 gateway의 후속 요청도 차단해 운영자가 실제 변경 내용과 기록 상태를 확인한 뒤 새 gateway를 시작하도록 했습니다. 이미 발생한 변경은 결과에 남겨 복구 판단에 필요한 정보를 보존했습니다. 수정 전 실패하던 회귀가 수정 후 통과했고, 최종 전체 회귀 177개도 통과했습니다. 파일 변경, 오류 응답, 후속 실행 여부를 함께 확인해 실패가 다음 작업에 미치는 영향까지 검증했습니다.

근거: [실패 주입과 수정 기록](exec/005-final-failure-injection.md#결과-audit-저장-실패), [수정 전 실패](exec/evidence/005/focused-red.log), [수정 후 통과](exec/evidence/005/focused-green.log), [최종 회귀](exec/evidence/005/regression-full.json)

## 더 읽을 자료

- [README](../README.md): 빠른 시작과 portfolio highlights
- [FINAL-VERDICT](FINAL-VERDICT.md): 판정별 검증 결과와 남은 위험
- [Local Usage](10-local-usage.md): 다른 저장소에서 Guard를 준비하고 연결하는 절차
- [실험·증거 지도](README.md): 설계, 실행 기록, 재현 가능한 evidence
