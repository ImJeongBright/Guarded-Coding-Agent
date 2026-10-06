# 003 — Real Project Usability

작성일: 2026-10-04. Status: 003-01~07 구현·실험 완료.
[전체 실행 기록](../exec/003-real-project-usability.md).

## 목표와 출발점

종료 질문을 유지한다: Filesystem/Shell/Git 권한을 맡기고 Guard를 계속 켜도 답답하지 않은가?

002에서는 실제 모델의 정상 호출 49개가 승인·거부 없이 완료됐다. 다만 운영자가 C 3개,
Python/JavaScript 각각 1개의 command profile을 먼저 준비했다. 준비 시간, 새 명령 등록,
테스트 옵션 변경, 큰 저장소 탐색과 연속 작업은 그 수치에 포함되지 않는다.
[002 현재 판정](../exec/002-09-verdict.md)을 기준으로 이 빈칸을 측정한다.

003의 목표는 **처음 보는 기존 프로젝트에서 준비부터 여러 개발 작업 완료까지의 마찰을 줄이는 것**이다.
가상 사용자 X와 실제 모델을 사용하되, task 목표만 주고 tool action 순서는 모델이 선택한다.

## 실행 단위

| ID | 작업 | 검증·증거 | 실행 기록 |
|---|---|---|---|
| 003-01 | 대상 저장소 2개 선정, 안전한 별도 ordinary checkout/copy, 변경 전 task 실행 | 준비 시간, 정상 profile miss, 반복 읽기, 테스트 옵션/Git 사용의 막힘 기록 | 003-01-baseline.md |
| 003-02 | profile 준비와 갱신 지원 | build/test metadata에서 운영자 검토용 후보 생성, capability·write scope 요약, 갱신 후 재시작·승인 binding 검사 | 003-02-profiles.md |
| 003-03 | 실제 막힘에 따른 제한된 command 옵션 지원 | 선택 테스트·필터·debug build 등 재현된 필요만 허용; executable/cwd/output scope 고정, 미등록 옵션 거부 | 003-03-command-variants.md |
| 003-04 | 파일 탐색·부분 편집 개선 | bounded text search와 필요한 context/hash 기반 edit, 큰 파일 재전송·반복 읽기 감소; secret/traversal/link/동시 변경 검사 | 003-04-filesystem-workflow.md |
| 003-05 | Git 검토와 연속 task 흐름 개선 | staged diff 등 실제 필요한 읽기, 수정→테스트→commit→다음 task; 재연결·정책 변경·승인 재사용 경계 | 003-05-git-session.md |
| 003-06 | 두 저장소에서 각 3개 task를 실제 모델로 수행 | bug fix/refactor/선택 테스트, 독립 behavior 검증, false denial/profile miss/운영자 개입 집계 | 003-06-user-x.md |
| 003-07 | 보안·사용성 회귀와 판정 | 기존 74개 유지, 새 capability별 우회 회귀, 전후 비교와 계속 사용 판정 | 003-07-verdict.md |

각 ID를 완료했고 [exec 목록](../exec/README.md)에 항목별 기록을 적재했다.
003-01의 정상 request 11개 미실행을 근거로 02~05를 구현했다.
전체 pre-change 모델 task 대신 같은 request probe와 기존 tests로 baseline을 고정했다.
개선 후 모델은 두 저장소에서 각 세 task를 수행했고 110개 호출 중 승인 0,
거부 1개(빈-query 탐색)는 실행 중 보완했다. 최종 Guard 회귀 101개와 여섯 독립 검증이 통과했다.
실제 사용자 장기 관찰은 이 완료에 포함하지 않는다.

## 구현 경계

- 자동 발견은 후보 제안까지다. README/manifest/Makefile은 신뢰된 명령이나 권한 선언으로 취급하지 않는다.
  후보 명령을 발견 단계에서 실행하지 않으며 운영자가 실제 argv/cwd/write scope를 검토한다.
- command 옵션은 승인된 capability의 명시적인 제한 안에서만 변형한다. 범용 shell string,
  임의 interpreter 옵션, command chaining으로 확대하지 않는다.
- search/edit도 기존 workspace·sensitive·trusted boundary와 audit를 통과한다.
  편집 대상이 읽은 내용과 달라졌으면 덮어쓰지 않고 재검토 결과를 반환한다.
- host read-only/native shell off, required MCP, exact push approval와 one-use binding을 유지한다.
- workspace 전체 write, network 기본 허용, 자동 승인, Guard/state 수정 권한으로 마찰을 줄이지 않는다.
- worktree, symlink dependency tree, package install, SSH credentials, 다른 OS/host는
  각각 별도 권한·위협 모델이 필요한 후속 범위다. 003에서 일괄 허용하지 않는다.
- Guard에는 외부 모델 API나 API key를 추가하지 않는다.

## 측정과 목표

아래 수치는 프로젝트의 사용성 목표이며 외부 표준이 정한 기준이 아니다.

| 측정 | 기준 |
|---|---|
| 최초 준비 | dependency가 준비된 저장소에서 목표 5분 이내. 자동 처리와 운영자 검토 시간을 구분 |
| 정상 false denial | 등록된 capability의 합법적인 변형이 부당하게 막힌 횟수 0을 목표 |
| profile miss | 새 capability가 필요해 막힌 경우를 별도 집계. 필요한 이유·등록·복구 시간 기록 |
| 반복 문의 | 동일한 capability 등록을 task마다 다시 요구하지 않음. 인자·정책 변경의 새 승인은 별도 |
| task 완료 | 2개 저장소 × 3개 task, project tests와 독립 검증 통과, 변경 검토 가능한 Git 상태 |
| local 승인 | 정상 범위 내 read/edit/test/commit에 승인 0회 |
| 위험 효과 | secret/out-of-scope/unknown/force/승인 replay의 실제 효과 0 |
| overhead | 같은 정상 요청의 normalization/decision/execution 시간을 분리. 모델 생성 시간과 구분 |
| 지속 사용 | X의 구체적인 마찰 의견, 켜둘지 여부, 아직 지원하지 못하는 작업 명시 |

baseline과 개선 후 task는 동일한 fixture revision과 목표로 비교한다. 모델의 선택이 달라질 수 있어
호출 수와 전체 시간을 인과적인 성능 향상 수치로 단정하지 않는다. 실제 요청을 별도로 재생해
Guard 자체의 시간과 차단 결과를 비교할 수 있다.

## 테스트와 기록 순서

정상 작업의 막힘 또는 보안 gap 재현 → 실패/기대 동작 검사 → 최소 수정
→ focused/security regression → 실제 모델 task → 독립 검증 → 전체 suite → 항목별 exec.

새 capability마다 ALLOW 정상 사례와 scope·인자 변조·link·unknown의 DENY 사례를 함께 넣는다.
실행 결과는 `docs/exec/003-real-project-usability.md`, 각 003-XX 기록, portable evidence에 보존한다.
아직 실행하지 않은 항목에 통과 수치나 완료 표시를 넣지 않는다.

## 장기 관찰과의 관계

[002-10](../exec/002-10-continued-use.md)의 1~2주 관찰은 계속 별도 추적한다.
003이 자동 실험으로 그 기간이나 실제 사용자의 주관적 평가를 대신하지 않는다.
003 완료는 준비·명령 변화·연속 task의 scoped 사용성 판정이며, 전체 종료 질문에는
장기 관찰과 미지원 프로젝트 형태의 결과도 함께 반영한다.
