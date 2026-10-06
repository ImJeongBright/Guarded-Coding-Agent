# PDR — Product Development Record

Date: 2026-10-03. 기존 요구사항은 [PRD](01-product-requirements.md)를 유지한다.
요청의 `pdr`은 개발 결정 기록으로 해석해 별도 작성한다.

## 종료 질문

> 실제 개발에서 Agent에게 Filesystem/Shell/Git 권한을 주고 Guard를 계속 켜도 답답하지 않은가?

가상의 개발자 X로 C언어 DBMS 엔진 실험을 수행한다. 파일 탐색·작성, 컴파일,
실패 수정, 회귀 테스트, Git diff/add/commit, 승인된 테스트용 push를 Gateway로 실행한다.
모델 추론은 기존 코딩 에이전트가 맡으며 Guard는 외부 API·키·서비스를 요구하지 않는다.

## 구현 결정

- Python 3.11+ 표준 라이브러리, 구조화된 요청, 범용 shell string 거부.
- Shell은 신뢰된 프로필의 정확한 argv/cwd와 OS 격리를 함께 요구한다.
- 첫 backend는 macOS sandbox-exec. 가용성 실패는 실행 실패이며 우회하지 않는다.
- 승인·정책·감사 상태는 workspace 밖 사용자 전용 디렉터리에 둔다.
- Agent에 승인 발급 도구를 제공하지 않는다. 운영자 CLI가 pending action을 확인한다.
- MCP 사용 시 호스트의 직접 filesystem/shell/git 도구를 꺼야 complete mediation이 성립한다.
- C DBMS는 평가 workload이며 DB Guard 확장이 아니다.

## 이번 실행의 합격 기준

1. 기존 22개 matrix와 추가 우회·승인·격리 테스트 통과.
2. X가 create → build → 실패 → fix → test → refactor → commit 완료.
3. 정상 local 개발 단계 승인 0회, 위험 probe 실제 side effect 0건.
4. push 1건당 정확한 action 승인 1회, 변경/만료/재사용 차단.
5. 단계별 audit와 exec 기록으로 재현 가능.
6. 차단 후 정상 대안으로 복구, 두 정책 개선을 회귀 테스트로 고정.

이 수치는 workload의 사전 기준이며 공개 표준이 정한 수치가 아니다.
한 번의 합성 실험을 1~2주 실사용이나 모든 저장소의 사용성으로 일반화하지 않는다.
호스트 직접 도구를 끌 수 없으면 세션 전체가 Guard로 보호됐다고 주장하지 않는다.

[001 계획](plans/001-mvp.md), [외부 기준](09-control-baseline.md),
[실행 목록](exec/README.md)을 함께 갱신한다.

## 002 후속 결정 — 2026-10-04

hook 오류 때 native tool이 계속될 수 있는 실제 실패를 재현했다. 전용 Codex launcher는
native shell을 끄고 host read-only/approval never를 고정한다. Guard MCP에서만 제한된
Filesystem/Shell/Git 효과를 수행하며, known hook을 사전 검사하고 required MCP를 요구한다.
검증한 CLI 버전과 project config가 달라지면 별도 검토 전 활성화를 거부한다.

command write scope는 실행 시 symlink로 바뀌어도 외부 target을 권한으로 확대하지 않는다.
경쟁 조건 red regression과 한글 경로 정상 실행 회귀를 함께 유지한다.

[002 결과](exec/002-live-dogfooding.md): 실제 모델 개발 49개 정상 호출 승인/거부 0,
세 task 독립 검증 통과, 최종 회귀 74개. 가상 X의 scoped 계속 사용 판정은 통과다.
범용 개발과 장기 사용자 평가를 포함한 전체 종료 질문은 계속 관찰한다.

## 003 후속 결정 — 2026-10-04

준비한 profile 밖의 정상 변형과 탐색 마찰을 11개 probe로 고정했다. 운영자-only 후보
발견/명시 등록, fixed mode와 literal test filter, bounded search/read range/hash edit,
staged diff를 추가했다. 정책 변경은 재시작과 기존 승인 무효화를 요구한다.

두 기존 ordinary/dependency-free 저장소의 여섯 실제 모델 task는 110개 호출,
local 승인 0, 정상 탐색 DENY 1개였고 그 마찰을 보완했다. Git 경고를 제거하고,
불완전 Git state query와 edit temp 충돌 cleanup의 red→green 보안 회귀도 추가했다.
최종 Guard 회귀 101개와 각 task의 독립 검증·clean commit이 통과했다.

같은 저장소/프로필을 새 ephemeral 세션에서 이어 사용하는 범위에서는 계속 켜둘 수 있다.
원본 MoneyPilot/C 소스는 변경하지 않았다. 실제 사람의 준비 시간·만족도, 1~2주 관찰과
미지원 프로젝트 형태는 [003 판정](exec/003-07-verdict.md)과 함께 계속 남겨 둔다.

## 004 후속 결정 — 2026-10-05

중규모 storage 부담은 M1(3,000 tracked / 10,000 ignored)과 M2(10,000 / 25,000)로 분리 측정했다.
다섯 계획 task에서 실제 Codex가 C DBMS를 수정·빌드·전체 테스트·diff/stage/commit했고,
독립 검증 모두 통과했다. 최적화 뒤 확인 task까지 합쳐 live Guard 호출 153회 중 152 ALLOW,
DENY 1(없는 `AGENTS.md` read), APPROVAL 0이다. 검색 incomplete 1회는 5,000-entry 한도를
명시했고 agent가 범위를 좁혀 복구했다.

M2 Git 정규화 3.8–4.0초 중 대부분이 10,000 tracked path마다 반복된 `Path.resolve/stat`이었다.
NUL metadata의 strict lexical validation으로 바꾸고 workspace symlink/hardlink 전체 검사와
executor 직전 검사까지 유지했다. M2 `git status` median은 반복 Guard 측정에서 3.90초→1.11초로
줄었고, 최적화 후 실제 Codex session에서도 status/diff/add/commit은 약 1.0–1.3초였다.
집중 위험 경계 회귀와 전체 173개 테스트가 통과했다.

모의 X는 이 검증한 macOS/C DBMS 개발 흐름에서 Guard를 계속 켜고 쓸 수 있다고 판정한다.
실제 사람의 1–2주 연속 사용은 관찰하지 않았으므로 전체 종료 질문의 장기 사용성 부분은 미완료로 남긴다.
[004 계획](plans/004-medium-scale-readiness.md), [실행 결과](exec/004-05-live-medium-scale.md),
[portable evidence](exec/evidence/004/004-05/README.md)를 참고한다.
