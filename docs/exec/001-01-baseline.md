# 001-01 — Requirements and Control Baseline

Date: 2026-10-03. Base commit: b93ba56. Policy: 001. 변경은 아직 commit하지 않았다.

## Scope / Implementation

기존 PRD와 설계 00~08을 확인했다. PDR은 개발 결정 기록으로 별도 작성하고,
001을 10개 항목으로 나눴다. `09-control-baseline.md`에서 OWASP/Microsoft/OpenAI 원문을
프로젝트 rule, FR, 기존 FS/SH/GT/AP/AU test ID와 연결했다.

## Verification

공식 페이지를 search 후 실제 open해 확인했다. 기준 원문과 프로젝트의 local write/commit
자동 허용 결정을 구분했다. 외부 API나 키 없이 로컬 구현하는 범위를 고정했다.

## Observed / Decisions

초기 저장소에는 설계 문서만 있었으며 실행 코드·PDR·exec 결과가 없었다.
PRD를 다시 만들지 않고 PDR을 추가했다. 공개 지침을 인증 또는 특정 승인율의 근거로 주장하지 않는다.

## Evidence / Limitations

[PDR](../PDR.md), [plan](../plans/001-mvp.md), [baseline](../09-control-baseline.md).
외부 문서는 구현 검증을 대체하지 않는다. 후속 항목에서 실제 차단·실행과 X 사용성을 확인한다.
