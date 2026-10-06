# 003-07 — 보안·사용성 회귀와 판정

후속 [001~003 재검토](review-001-003.md)의 High 1 / Mid 4 / Low 2는 모두 수정했다.
수정 후 159개 회귀와 새 실제 C 세션의 독립 검증이 통과했다.
아래는 003 당시의 실험 결과이며, 현재 판정과 성능은 [수정 문서](fix-001-003.md)를 따른다.
시작 baseline이 없던 기존 여섯 세션은 보존된 역사적 실험이며, 강화한 검증기로 소급 인증하지 않는다.

2026-10-04. 003 완료. 판정은 **이번 두 ordinary, dependency-free 저장소에서는 계속 켜둘 수 있다**다.
프로필 준비 뒤 local 개발에 승인 문의가 없었고, 정상 흐름에서 발견한 경고와 파일 탐색의
마찰을 수정했다. 임의의 모든 개발 환경이나 실제 사용자의 장기 만족까지 통과했다는 뜻은 아니다.

기존 74개와 003의 27개를 합친 Guard 회귀 101개가 통과했다. 실패/error/skip 0,
2026-10-04T10:49:02Z, 8.341초, macOS 15.7.8 arm64/Python 3.12.1이다.
[최종 JSON](evidence/003/regression-final-101.json)은 기본 policy version 001을 표기하는
기존 check runner의 envelope다. 실제 테스트들은 여러 fixture version을 사용하며 live
003 profile version/digest는 각 policy/preflight에 따로 보존했다.

추가 회귀는 trusted candidate 변조/stale metadata, unknown mode/filter/flag, 정책 갱신,
부분 읽기·편집의 stale/link/크기/cleanup, search secret/link/상한, staged diff,
이전 push 승인 재사용과 불완전 Git state를 검사한다. danger probe의 밖 write/secret/force/replay
등 기대한 경계는 모두 유지됐다. profile 적용 권한이나 자동 승인은 Agent에게 주지 않았다.

legacy 합성 MCP X도 다시 실행했다. 정상 25 action 승인/거부 0, 위험 7개 미실행,
operator fixture grant 1개로 local bare push 1회, approval replay 거부, C tests 11개 통과다.
이 push는 실사용 사람의 승인을 대신한 것이 아니라 승인 구현의 회귀다.

처음 실패한 결과도 남겼다: 미구현 workflow의 red test, MCP 설명 문구 호환 실패,
Git metadata 조회를 전부 막던 discovery mock 실패, 빈 query 거부, 잘린 Git state가 executor로
가던 경로와 temp collision cleanup 삭제. 뒤의 두 보안 경로에는 red→green 회귀를 추가했다.
기본 tool sandbox 안에서 실행한 focused suite에는 nested Seatbelt 거부가 3개 있었고,
실제 실행 검증은 허용된 host에서 fail-closed 경계를 유지한 채 수행했다.

반환된 perf_counter 시간을 phase별로 나눴다. ALLOW 호출의 `total - execution`은
두 normalization/decision, durable audit와 schema/hash/redaction 등의 시간을 포함한다.

| Tool | samples | boundary median/p95 (ms) | execution median (ms) |
|---|---:|---:|---:|
| Filesystem | 59 | 1.265 / 2.605 | 0.355 |
| Shell | 19 | 5.159 / 8.786 | 190.315 |
| Git | 31 | 61.165 / 82.797 | 27.651 |

Git normalization에는 실제 state query subprocess가 두 번 포함돼 상대적으로 비용이 크다.
이 수치는 pure policy CPU benchmark나 MCP round trip/모델 생성 시간이 아니다.
같은 요청 11개의 DENY→ALLOW 비교는 capability 마찰을 보여주며 전체 개발 시간의 인과적 개선 수치가 아니다.

003의 scoped 목표는 충족했다: 여섯 task/독립 검증/clean commit, 반복 profile 등록 0,
local 승인 0, 관찰한 정상 거부 보완, 위험 경계 유지와 문서·portable evidence 보존.
다만 worktree, symlink dependency tree, package install, SSH auth, 큰 저장소 탐색/상태 조회와
다른 host/OS는 남아 있다. 마지막 검사/rename 사이의 비협조적 외부 writer에 대한 edit CAS도 아니다.
[002-10](002-10-continued-use.md)의 1~2주 실제 사용자 관찰은 계속 미측정이다.
