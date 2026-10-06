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

## 더 읽을 자료

- [README](../README.md): 빠른 시작과 portfolio highlights
- [FINAL-VERDICT](FINAL-VERDICT.md): 판정별 검증 결과와 남은 위험
- [Local Usage](10-local-usage.md): 다른 저장소에서 Guard를 준비하고 연결하는 절차
- [실험·증거 지도](README.md): 설계, 실행 기록, 재현 가능한 evidence
