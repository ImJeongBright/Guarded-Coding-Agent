# 001-06 — Exact Operator Approval

Date: 2026-10-03. Base commit: b93ba56. Policy: 001.

## Implementation

workspace 밖 0700 state와 0600 SQLite store에 pending/grant/used/expiry를 둔다.
action, workspace identity, actor/run, policy version/digest, branch/HEAD, URL과
local remote identity를 binding한다. 재정규화 후 원자적 one-use consume을 수행한다.
운영자 CLI는 정확한 action과 context를 출력하고 TTY에서 approve를 입력받는다.
Agent MCP에는 grant endpoint와 자동 승인 옵션이 없다.

## Tests

AP-01~04, changed branch/HEAD, policy binding, same-run replay, other-run replay,
expiry, noninteractive grant 거부, 네 개 동시 소비 중 한 개만 성공을 검증했다.
최종 full suite 67 pass.

## Observed / Decisions

승인 후 bare remote를 같은 경로의 새 repo로 교체하면 기존 승인이 실행되는 실패를 재현했다.
remote st_dev/st_ino를 binding에 포함해 재사용을 차단했다.
공개 review에는 workspace/run/actor/policy도 넣어 운영자가 scope를 확인하도록 했다.

## Evidence / Limits

X는 승인 전 remote ref 없음, 정확한 승인 후 ref 생성, replay 차단을 확인했다.
X의 grant는 synthetic operator fixture다. 실제 사람의 승인 시간·피로도는 측정하지 않았다.
동일 OS 권한의 악성 운영자나 모든 외부 상태 경쟁을 해결하는 승인 시스템은 아니다.
