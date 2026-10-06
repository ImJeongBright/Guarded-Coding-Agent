# 002-03 — Hook과 MCP 장애

실제 CLI에서 각각 별도 workspace를 만들어 실패를 주입했다.

| 시험 | Native marker | Guard marker | 판정 |
|---|---|---|---|
| hook executable 누락 | 미생성 | 생성 | read-only host가 native patch 거부 |
| hook exit 1 | 미생성 | 생성 | read-only host가 native patch 거부 |
| hook timeout | 미생성 | 생성 | read-only host가 native patch 거부 |
| required MCP 시작 실패 | 미생성 | 미생성 | 세션 시작 실패, CLI exit 1 |
| handshake 후 MCP 첫 호출에서 종료 | 미생성 | 미생성 | Transport closed, fallback 효과 없음 |
| 고장난 hook + workspace-write 대조군 | **생성** | 생성 | **hook 단독 방어 실패** |

대조군은 `native-marker.txt`라는 가짜 파일만 대상으로 했다. 제품 launcher에는
이 구성을 제공하지 않는다. 직접 쓰기 권한이 남은 host에서 hook만 보호 수단으로 삼으면 안 된다는
실제 재현이며, read-only host를 실행 구성에 고정한 이유다.

실행 도중 종료 fixture는 handshake를 완료한 뒤 첫 tools/call에서 exit 86을 반환했다.
모델의 write/read 두 호출은 Transport closed였고 파일은 생성되지 않았다.
CLI 자체는 final 보고 후 exit 0으로 끝나므로 **CLI exit 0만으로 task 성공을 판정하지 않는다.**
원본: `.guard-runs/probe-{missing,crash,timeout,mcp-down,mcp-dies,unsafe-control}-01`.
재현 도구: `scripts/live_probe.py`의 각 variant.

[portable probe summary](evidence/002/summary.json),
[mid-call trace](evidence/002/probes/mcp-dies-01/events.jsonl).

[공식 Hooks 문서](https://learn.chatgpt.com/docs/hooks)의 실패 동작 설명과 관찰 결과가 일치했다.
hook이 오류를 냈다는 사실과 실제 도구 효과가 차단됐다는 사실을 구분한다.
