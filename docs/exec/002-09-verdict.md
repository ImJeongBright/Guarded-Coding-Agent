# 002-09 — 현재 사용 판정

질문: 실제 개발에서 Filesystem/Shell/Git 권한을 맡기고 Guard를 켜도 답답하지 않은가?

**가상 사용자 X라면, 이번 세 소규모 저장소에서는 Guard를 계속 켜두겠다.**
파일 읽기·수정·테스트·Git commit을 실제 모델이 스스로 수행했고 49개 정상 호출에서
불필요 승인·정책 차단·정책 추가 요청이 없었다. 각 task의 테스트와 별도 behavior 검사가
통과했고 working tree도 깨끗했다. 세 모델 응답은 모두 이 task에서 마찰이 없었다고 보고했다.

| Task | Guard 호출 | 승인 / 거부 | Project test | 독립 검사 | Local commit |
|---|---:|---:|---:|---|---|
| C DBMS | 20 | 0 / 0 | 11 pass | pass | de37b9a |
| Python ledger | 16 | 0 / 0 | 9 pass | pass | 37eb29a |
| JavaScript CSV | 13 | 0 / 0 | 8 pass | pass | 695f73d |

audit decision→result 간격 중앙값은 C 0.941 ms, Python 1.252 ms, JS 1.823 ms였다.
이 값은 normalization·모델 생성·host 시작 시간을 제외하며 순수 Guard overhead 측정치도 아니다.
느린 build/test를 포함하는 이 구간의 최대값은 각각 512.732/115.002/141.593 ms였다.
사용성을 latency만으로 판정하지 않는다.

## 현재 조건

운영자가 좁은 compiler/test profile을 미리 준비했다. C 3개, Python/JS 각각 1개다.
Guard tool 설명에 argv가 제공되어 모델이 명령을 추측할 필요가 없었다. 이 준비 비용과
새로운 command가 필요할 때의 운영자 등록 과정은 49개 호출의 마찰 수치에 포함되지 않는다.

host는 검증한 Codex CLI 0.160.0와 macOS에 한정한다. shell을 범용 권한으로 열지 않고
등록된 capability와 command별 write scope로 실행한다. 위험한 push는 여전히 사람 승인이 필요하다.
hook 단독 방어의 실제 실패를 확인했으므로 read-only host가 이 사용 판정의 필수 조건이다.

## 전체 실개발에 대한 판정

임의의 기존 프로젝트에도 답답하지 않다고 확정할 증거는 아직 부족하다. worktree,
symlink dependency tree, package install, SSH 인증, 수시로 달라지는 command, 대규모 파일 탐색은
현재 capability에서 막히거나 추가 설계가 필요하다. 1~2주 사용과 실제 사용자의 피로도는 측정하지 않았다.

따라서 **현재 profile에서 Level 3 실험은 통과**, 범용 개발과 장기 사용까지 포함한 최종 종료 조건은
열어둔다. 이 미확인 항목을 테스트가 통과한 것처럼 처리하지 않는다.

[측정 summary](evidence/002/summary.json), [후속 관찰](002-10-continued-use.md).
