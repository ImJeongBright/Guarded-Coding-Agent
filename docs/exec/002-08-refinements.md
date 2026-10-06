# 002-08 — 발견한 문제 수정과 최종 회귀

실행일: 2026-10-03~04. Policy 001, source는 원본 저장소 working tree에 있다.

| 문제 | 실패 증거 | 수정 | 최종 결과 |
|---|---|---|---|
| 문서/CLI 설정 차이 | strict-config가 tools.view_image 거부 | 설치 binary의 feature 사용 | 실제 연결 통과 |
| dispatcher 제거 | code-mode host disabled, Guard 호출 불가 | 필요한 dispatcher 유지 | 실제 MCP 호출 통과 |
| hook 단독 fail-open | workspace-write 대조군 native marker 생성 | native shell 제거 + read-only host + approval never | hook 누락/오류/timeout 때 직접 쓰기 차단 |
| 쓰기 scope 경로 교체 | 검사 후 build symlink 교체로 외부 fixture 파일 생성 | 실행 직전 symlink 확인, 고정 경로 regex 권한 | DENY, 실행/외부 파일 생성 없음 |
| 한글 write scope 오탐 | 한글·공백 산출물에 PermissionError | Seatbelt 경로를 UTF-8 문자열로 작성 | 정상 생성 통과 |

경쟁 조건 검사는 `_execute` 직전에 경로를 교체해 검사와 실행 사이의 틈을 재현했다.
runtime permission을 `realpath`로 외부 경로까지 확대하던 실패는 실제 보안 gap이었다.
고정 경로 regex를 사용해 새 symlink target이 permission이 되지 않도록 했다.
단순히 재검사만 추가한 것으로 전체 경쟁 조건 문제가 해결됐다고 주장하지 않는다.

예방적으로 `/System` 읽기 root도 `/System/Library`로 좁혔다.
system-volume alias 검사는 기존 구현에서도 차단됐으며 성공한 exploit으로 집계하지 않는다.

최종 명령:

```sh
python3 scripts/check.py --evidence docs/exec/evidence/regression-002-final.json
python3 scripts/dogfood.py --output .guard-runs/user-x-09
```

회귀 **74개 통과, failure/error/skip 0**. X 최종 재실험은 정상 local action 25개
승인/거부 0, 위험 proposal 7개 미실행, 정확한 synthetic grant 1회 후 bare remote push 1회,
DBMS 11개 테스트 통과. 승인 요청/재개 응답 2개는 grant 2회라는 뜻이 아니다.

[최종 회귀](evidence/regression-002-final.json), [X summary](evidence/002/scripted-x/summary.json),
[초기 red 결과](evidence/002/refinements.json). 최초 72개 회귀 기록도 별도로 보존했다.
