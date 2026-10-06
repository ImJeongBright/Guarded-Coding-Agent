# 002 Live Host and Dogfooding Execution

실행: 2026-10-03~04. Base commit b93ba56, policy 001, working tree 구현.
Codex CLI 0.160.0 / macOS 15.7.8 arm64 / Python 3.12.1.

실제 모델이 Guard MCP로 C·Python·JavaScript task를 완료했다. 정상 호출 49개는 모두
ALLOW, 승인/거부 0. Project tests 11/9/8개와 별도 behavior 검사를 통과했고
각 fixture에 local commit을 만들었다. 원본 저장소는 commit/push하지 않았다.

native patch/shell의 명시적 hook 거부, hook 누락/실패/timeout, MCP startup/mid-call 종료를
실제로 시험했다. 고장난 hook과 workspace-write 대조군에서는 직접 쓰기가 통과했다.
제품 구성은 native shell을 제거하고 read-only host와 approval never를 고정했다.

쓰기 scope symlink 경쟁 조건과 한글 경로 오탐을 red 검사로 재현해 수정했다.
최종 Guard 회귀 **74개 통과**. 최종 합성 X 재실험은 정상 25개 action 승인/거부 0,
위험 7개 미실행, synthetic exact grant 1회 후 bare push 1회, DBMS 11개 테스트 통과.

**X의 현재 판정: 준비한 세 task에는 계속 켜두겠다.** 범용 저장소와 1~2주 사용은
아직 관찰하지 않았다. Level 3 판정의 조건과 범위는 09 기록에 명시했다.

## 항목별 실행

[01 실제 host](002-01-host.md), [02 native 도구](002-02-native-tools.md),
[03 장애](002-03-failures.md), [04 runtime](002-04-runtime.md),
[05 C DBMS](002-05-c-dbms.md), [06 Python](002-06-python.md),
[07 JavaScript](002-07-javascript.md), [08 수정/회귀](002-08-refinements.md),
[09 현재 판정](002-09-verdict.md), [10 지속 사용](002-10-continued-use.md).

## 증거와 재현

[측정 summary](evidence/002/summary.json), [최종 회귀](evidence/regression-002-final.json),
[source SHA256](evidence/002/source-manifest.json), [재현 가이드](../10-local-usage.md).
portable evidence는 경로를 `$RUN`/`$REPO`/`$HOME`으로 바꿨으며 auth 파일과 host DB는 포함하지 않았다.
원본 trace/audit와 fixture 저장소는 `.guard-runs/`에 보존한다.

Guard는 API client/key/SaaS 없이 local stdio로 동작한다. live 모델 통신은 기존 Codex가 맡았다.
독립 JS 검증 한 번은 자동 승인 검토의 사용량 한도로 실행되지 못했고 다음 날 같은 절차로 통과했다.
