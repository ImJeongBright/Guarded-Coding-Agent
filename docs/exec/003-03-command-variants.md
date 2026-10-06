# 003-03 — 고정 모드와 선택 테스트

2026-10-04. 완료.

`shell/run`에 profile ID와 optional mode/filter를 추가했다. C debug는 고정 argv의
`-O0 -g` 모드이고 release는 기존 `-O2`다. 필터는 Python unittest `-k`와 Node builtin
test-name-pattern의 literal test name에 한정한다. Node에는 escaped literal을 전달한다.
exe/cwd/output scope/timeout은 profile에서 가져오고 Agent가 바꾸지 못한다.

기존 exec도 등록된 fixed variant 또는 같은 제한된 filter 형태만 정규화한다.
unknown profile/mode, 새 arbitrary flag, composition, regex/wildcard filter,
path-like filter, newline, option-like filter는 실행하지 않는다.

필터는 실행할 테스트를 좁히는 기능이다. matching test 0개인 exit 0을 task 검증 성공으로
단정하지 않는다. live task에는 실제로 선택된 테스트 수와 전체 suite를 함께 확인한다.

초기 red regression은 새 run operation을 사용할 수 없었다. 구현 뒤 실제 Node profile의
selected/full 테스트와 C release/debug가 동작했다. 초기 baseline의 필터·debug 요청 3개도
같은 argv 그대로 ALLOW가 됐다. workspace 전체 쓰기나 network 허용은 추가하지 않았다.
