# Execution Records

이 디렉터리는 구현·실험 결과를 기록한다.

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
