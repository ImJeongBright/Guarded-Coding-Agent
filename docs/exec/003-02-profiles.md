# 003-02 — 운영자 profile 발견과 갱신

2026-10-04. 완료.

`discover`는 operator state에 command 후보, 고정 executable/argv/cwd/write scope,
metadata SHA-256, workspace inode와 policy digest를 기록한다. 프로젝트 명령은 실행하지 않는다.
알려진 C DBMS layout은 고정 compiler/SDK/test 명령을 제안하며 Makefile recipe를 해석하지 않는다.
Node는 manifest의 제한된 builtin test 형태만 인식한다. npm/install/require/복합 script는 자동 등록하지 않는다.

`profile-apply --reviewed-digest ... --ids ...`는 운영자가 검토한 후보 중 명시한 ID만 등록한다.
후보 변조, 다른 workspace/policy, 바뀐 metadata, 중복·없는 ID를 거부한다.
완성 policy를 검증한 뒤 workspace 밖 파일을 원자적으로 교체한다.
Agent MCP에는 discover/apply/approve가 없고 state 접근도 허용되지 않는다.

C는 c-build/c-tests/c-db 3개, domain은 node-tests 1개를 한 번 등록했다.
각 저장소의 세 task에서 같은 profile을 재사용한다. 갱신은 기존 세션에서 AP-BINDING으로
막히며 새 세션이 필요하다. policy digest가 바뀌면 같은 run/HEAD에도 이전 push 승인을 쓸 수 없다.

후보 생성 시 수행 가능한 host metadata 조회는 검토된 `/usr/bin/xcrun --find git/cc`,
SDK 조회뿐이다. Git launcher 경고 개선 뒤 subprocess 전부를 금지하던 테스트가 실패해,
고정 metadata 조회만 허용하고 프로젝트 실행은 계속 실패하도록 검사 범위를 바로잡았다.
이것은 자동 발견이 build/test를 실행해도 된다는 변경이 아니다.

운영자 검토는 이번 가상 X 실험의 agent가 수행했다. 실제 사람의 검토 시간·적정성은 측정하지 않았다.
완전히 새로운 build ecosystem의 자동 설정은 지원 범위 밖이다.
