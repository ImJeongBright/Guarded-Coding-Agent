# Execution Records

이 디렉터리는 구현·실험 결과를 기록한다.

## 005 최종 마감

- [005 CI·마지막 실패 주입](005-final-failure-injection.md): 결과 audit 오류 전달·세션 차단 수정, controller SIGKILL 한계, 177개 full 회귀와 보존 M1/M2 재측정.
- [최종 판정](../FINAL-VERDICT.md): 열 가지 판정과 scoped 핵심 개발 마감. 장기 실제 사용자 관찰은 미측정이다.
- [005 evidence](evidence/005/README.md): 최초 실패, red→green, 소스 해시, CLI smoke와 scale replay.

## 001~003 후속 검토

- [재검토와 수정 우선순위](review-001-003.md): 수정 전 High 1 / Mid 4 / Low 2 재현 기록.
- [수정과 재검증](fix-001-003.md): 7개 모두 수정, 기존 101개와 신규 58개를 합친 159개 회귀 통과.
- [수정 계획](../plans/fix-001-003.md): 항목별 작업과 완료 기준.
- 새 실제 Codex C 작업·독립 검사 통과. 합성 X 정상 25개 action의 승인·거부는 0회다.
- 수정 전 증거는 `evidence/review-001-003/`, 수정 후 증거는 `evidence/fix-001-003/`에 보존했다.
- 계속 사용 판정은 검증한 macOS·host·소규모 C 흐름에 한정한다. 장기 실제 사용자 관찰은 미측정이다.
- [중규모 용량 관찰](scale-observation.md): 1,000개에서 Git 약 0.5~1초, 3,000개에서 metadata 한도로 정상 Git 거부. 확장 보완 필요.
- [004 중규모 지속 사용 계획](../plans/004-medium-scale-readiness.md): 다섯 계획 task와 최적화 후 live 확인을 완료. 실제 사용자 장기 평가는 미측정.
- [004-01 Git metadata](004-01-git-metadata.md): 64KB user output과 8MiB/250K hidden metadata 검사 분리. 162 regression 통과.
- [004-02 workspace scan](004-02-workspace-scan.md): 중복 전체 순회를 5회에서 3회로 줄이고 실행 직전 integrity scan을 유지. 새 regression 포함 166개 전체 통과.
- [004-03 search exclusions](004-03-search-exclusions.md): 생성물 subtree의 explicit exclusion을 추가하고 incomplete budget을 유지. M1 root/M2 module search와 170개 전체 회귀 통과.
- [004-04 build limits](004-04-build-limits.md): 실제 C build와 timeout/output/32 MiB limit을 자극하고 공통 한도 유지. 171개 전체 회귀 통과.
- [004-05 M1/M2 통합 판정](004-05-live-medium-scale.md): 다섯 계획 task와 post-optimization follow-up, Git metadata 속도 수정 및 X 판정.

<a id="004-m1m2-live-task-records"></a>
### 004 M1/M2 live task 기록

- [M1 task 1 — delete](004-05-01-m1-delete.md)
- [M1 task 2 — find](004-05-02-m1-find.md)
- [M1 task 3 — rename](004-05-03-m1-rename.md)
- [M2 task 4 — clear](004-05-04-m2-clear.md)
- [M2 task 5 — stats](004-05-05-m2-stats.md)
- [최적화 후 확인 — help regression](004-05-06-post-optimization.md)

Portable sessions, audit, patches와 latency evidence는 [004-05 evidence](evidence/004/004-05/README.md)에 있다.

## 001 실행 목록

- [전체 결과](001-mvp.md)
- [01 기준/PDR](001-01-baseline.md)
- [02 코어/정책](001-02-core.md)
- [03 Filesystem](001-03-filesystem.md)
- [04 Shell/격리](001-04-shell.md)
- [05 Git](001-05-git.md)
- [06 승인](001-06-approval.md)
- [07 Audit](001-07-audit.md)
- [08 MCP/host 연결](001-08-integration.md)
- [09 사용자 X](001-09-user-x.md)
- [10 판정](001-10-verdict.md)

`evidence/`에는 regression JSON, X summary/trace/audit의 path 익명화 사본이 있다.
원본 실행 디렉터리는 `.guard-runs/`에 보존하고 Git에 포함하지 않는다.

## 002 실행 목록

- [전체 결과](002-live-dogfooding.md)
- [01 실제 host 연결](002-01-host.md)
- [02 직접 도구 차단](002-02-native-tools.md)
- [03 hook/MCP 장애](002-03-failures.md)
- [04 OS 실행 경계](002-04-runtime.md)
- [05 C DBMS](002-05-c-dbms.md)
- [06 Python](002-06-python.md)
- [07 JavaScript](002-07-javascript.md)
- [08 수정과 전체 회귀](002-08-refinements.md)
- [09 현재 사용 판정](002-09-verdict.md)
- [10 지속 사용 관찰](002-10-continued-use.md)

`evidence/002/`에 portable live trace/audit, 초기 실패, 최종 patch/verification,
실패 주입 대조군과 source manifest를 보존했다. 002-01~09는 완료했고
002-10의 1~2주 사용과 실제 사용자 평가는 미측정이다.

## 003 실행 목록

- [전체 결과](003-real-project-usability.md)
- [01 기존 프로젝트 baseline](003-01-baseline.md)
- [02 profile 발견·검토·갱신](003-02-profiles.md)
- [03 command mode·선택 테스트](003-03-command-variants.md)
- [04 검색·부분 읽기·hash edit](003-04-filesystem-workflow.md)
- [05 staged diff·연속 세션](003-05-git-session.md)
- [06 사용자 X의 여섯 live task](003-06-user-x.md)
- [07 회귀·현재 판정](003-07-verdict.md)

003-01~07 완료. `evidence/003`에 baseline/final source, 여섯 session/commit,
독립 검증, 초기 실패와 refinement, 원본 source hash, phase timing과 최종 101개 회귀를 보존했다.
실제 사람의 setup 시간·1~2주 만족도는 계속 미측정이다.

Plan 문서는 실행 전에 목표와 완료 기준을 고정한다. Exec 문서는 실제로 무엇을 구현했고 어떤 테스트가 통과하거나 실패했는지 기록한다.

## 파일 이름

~~~text
001-mvp.md
002-...
~~~

## Exec 문서 템플릿

~~~text
# NNN <title>

## Scope

이번 실행에서 실제로 변경한 범위.

## Implementation

구현한 내용.

## Tests

실행한 명령과 결과.

- focused:
- integration:
- adversarial:
- full regression:

## Observed Failures

처음 실패한 테스트나 구현 중 발견한 문제.

## Decisions

실제 구현 과정에서 변경한 설계와 이유.

## Evidence

commit
policy version
test counts
relevant artifacts

## Limitations

이번 실행으로 보장하지 않는 것.

## Next

다음 작업.
~~~

## 기록 원칙

- 통과한 테스트만 기록하지 않는다.
- 실패 후 수정했다면 최초 실패 원인도 남긴다.
- 실제 측정하지 않은 수치를 만들지 않는다.
- "안전함"처럼 범위가 불명확한 표현을 피한다.
- 어떤 위험을 차단했고 어떤 위험이 여전히 남는지 구분한다.
- 테스트가 fixture인지 실제 dogfooding인지 구분한다.
