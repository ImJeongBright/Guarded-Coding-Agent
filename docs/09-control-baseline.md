# Control Baseline

확인일: 2026-10-03. 공개 지침을 로컬 실행 모델로 구체화한 매핑이며 인증 선언이 아니다.

## 원문 기준

[OWASP LLM06:2025](https://genai.owasp.org/llmrisk/llm062025-excessive-agency/)는
불필요한 기능·권한·자율성을 줄이고, 중요한 동작에 사람 검토를 두며,
downstream 요청마다 정책을 검사하도록 권고한다.

[Microsoft Agent Safety](https://learn.microsoft.com/en-us/agent-framework/concepts/agents/safety)는
side effects, data sensitivity, reversibility, scope of impact를 승인 판단 요소로 제시한다.
파일 경로는 절대경로로 해결해 허용 디렉터리 안인지 확인하도록 한다.

[OpenAI Guardrails and human review](https://developers.openai.com/api/docs/guides/agents/guardrails-approvals)는
side effect를 만드는 도구 곁에 검증을 두고 민감한 실행을 검토하도록 한다.
사이버 작업 예시의 target/action/arguments/identity/window 검사와 fail closed를
workspace·run·정확한 argv·승인 만료 검사로 적용한다.

[Microsoft Least Privilege](https://learn.microsoft.com/en-us/security/zero-trust/catalog-ai-defense-capabilities/identity-access-least-privilege)는
주체와 task에 권한을 결합하고 범위와 기간을 제한하며 영향이 큰 행동에 새 승인을 요구한다.

## 정책 매핑

| Control | Rule | PRD | Scenario / regression |
|---|---|---|---|
| 최소 capability | CORE-UNKNOWN / CORE-SCHEMA | FR-08 | unknown/malformed |
| 경로·범위 | FS-SCOPE / FS-LINK | FR-01 | FS-03/04, non-existent ancestor, hardlink |
| 민감 데이터 | FS-SENSITIVE / SH-SANDBOX | FR-02 | FS-05, shell secret-read |
| 신뢰 저장소 | FS-TRUSTED | FR-07 | FS-06, shell state-write |
| complete mediation | Gateway.submit + MCP tools/call | FR-03/04 | executed action audit, endpoint |
| 제한된 Shell | SH-PROFILE / SH-SYNTAX | FR-03 | SH-01~05, shadow/argv/cwd, command write scope |
| 사람 검토 | GT-PUSH | FR-04 | GT-04, grant 전 push 미실행 |
| 파괴적 행동 | GT-DESTRUCTIVE / FS-DELETE | FR-02/04 | GT-05, recursive delete |
| 정확한 승인 | AP-BINDING / AP-INVALID | FR-05 | AP-01~04, HEAD/remote/policy, one-use |
| 감사 | decision/result phases / AU-ERROR | FR-06 | AU-01/02, audit unavailable |
| fail closed | CORE-SCHEMA / SH-SANDBOX / AU-ERROR | FR-08 | parsing/isolator/audit failure |
| host 최소 권한 | native shell off / host read-only | FR-03/04 | 002-02/03, hook 오류 대조군과 보강 |
| 실행 scope 유지 | 고정 write path / SH-SANDBOX | FR-01/03 | 검사 후 symlink 교체, 외부 파일 생성 차단 |
| 과거 Git content source 검사 | FS-SENSITIVE / GT-STATE | FR-02/04 | R001, staged 삭제·rename·불완전 metadata |
| 검증 범위와 실행 범위 일치 | GT-PATHS / literal pathspecs | FR-04 | R004, wildcard·magic 파일명·directory 거부 |
| 실행 수명과 정확한 결과 기록 | SH-LIFECYCLE / execution status | FR-03/06 | R002/003, applied 실패·분리 자식·exec 경쟁 |

위 추가 행은 [001~003 수정](exec/fix-001-003.md)의 내부 control 매핑이다.
R005의 세션 증거와 R006/007의 불완전 탐색 표시는 완료 판정·사용성 회귀로 별도 검증한다.

## 프로젝트 해석

workspace 내부의 제한된 복구 가능한 편집과 local commit ALLOW는 승인 피로를 줄이려는
프로젝트 결정이다. Microsoft가 모든 local 편집 자동 허용을 규정한 것은 아니다.
외부 push는 REQUIRE_APPROVAL, secret/out-of-scope/force/unknown은 DENY한다.
단일 파일 delete만 제공하고 recursive delete는 capability에서 제외한다.

Level 0 unrestricted, Level 1 prompt, Level 2 runtime policy, Level 3 usable guard로
구분한다. [002의 Level 3 판정](exec/002-09-verdict.md)은 검증한 host와 세 task에 한정하며
장기·범용 프로젝트의 미확인 범위를 함께 기록한다.
