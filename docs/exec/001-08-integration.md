# 001-08 — Local MCP and Coding-agent Configuration

Date: 2026-10-03. Base commit: b93ba56. Policy: 001.
Status: local adapter 완료, live host enforcement 미검증.

## Implementation

CLI init/exec/serve/inspect/approve, absolute launcher, local newline JSON-RPC MCP를 만들었다.
initialize/notification, ping, tools/list/call, frame/schema validation과 error recovery를 지원한다.
미지원 modern discovery probe는 method-not-found로 응답해 legacy handshake 전환을 돕는다.
등록 argv/cwd/write scope는 Shell tool description에 공개해 Agent가 policy file을 읽지 않고도
정확한 명령을 선택한다. approval 발급 도구는 노출하지 않는다.

Codex용 별도 TOML 생성기와 PreToolUse 보조 gate를 추가했다. 이 gate는 Guard MCP 세 도구와
update_plan만 허용하고 native shell/edit/unknown을 거부한다. 사용자 global 설정은 바꾸지 않았다.

## Tests

`test_mcp.py`의 실제 stdio child round-trip 1 pass.
`test_host_hook.py`의 native/unknown 거부, exact tools 허용, malformed deny 3 pass.
설치된 codex-cli 0.160.0에 command-line overlay로 `mcp get guard --json` 실행: exit 0,
세 도구·launcher·args를 정상 인식. 모델 API는 호출하지 않았다.

## Observed / Limits

MCP 모듈 부재와 hook script 부재의 red test를 먼저 확인한 뒤 구현했다.
현재 세션의 native tool routing은 새 코드로 변경하지 못했다. hook의 local JSON 계약과
Codex 설정 인식은 live tool interception 증거가 아니다. 공식 hook trust review와 coverage를
확인해야 한다. [사용 가이드](../10-local-usage.md)에 activation과 경계를 명시했다.
