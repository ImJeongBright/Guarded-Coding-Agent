# Guarded Coding Agent 문서

Guarded Coding Agent는 코딩 에이전트에게 실제 개발 작업과 도구 사용을 위임하되, 모델의 판단과 실제 실행 권한을 분리하는 로컬 개발 도구를 목표로 한다.

핵심 질문은 단순하다.

> 에이전트가 더 많은 일을 자율적으로 수행하게 하면서도, 잘못된 판단이 실제 피해로 이어지는 범위를 프로그램이 제한할 수 있는가?

## 문서 지도

- [00-project-charter.md](00-project-charter.md): 프로젝트 정체성, 문제, 비목표
- [01-product-requirements.md](01-product-requirements.md): MVP 요구사항과 완료 조건
- [02-architecture.md](02-architecture.md): 구성요소와 실행 흐름
- [03-policy-model.md](03-policy-model.md): ALLOW / REQUIRE_APPROVAL / DENY 정책 의미와 우선순위
- [04-tool-contracts.md](04-tool-contracts.md): Filesystem / Shell / Git 도구 계약
- [05-threat-model.md](05-threat-model.md): 오용·우회·실패 시나리오
- [06-testing-strategy.md](06-testing-strategy.md): 단위·통합·회귀·적대적 테스트
- [07-evaluation-and-dogfooding.md](07-evaluation-and-dogfooding.md): 실제 사용 검증과 평가 기록
- [08-roadmap.md](08-roadmap.md): 단계별 구현 순서
- [plans/001-mvp.md](plans/001-mvp.md): 첫 구현 계획
- [exec/README.md](exec/README.md): 구현·실험 실행 기록 규칙
- [adr/0001-deterministic-policy-boundary.md](adr/0001-deterministic-policy-boundary.md): 정책 결정 경계
- [adr/0002-three-way-decision.md](adr/0002-three-way-decision.md): 3단계 정책 결정
- [adr/0003-least-privilege-by-default.md](adr/0003-least-privilege-by-default.md): 최소 권한 기본값

## 핵심 설계 원칙

1. 모델은 의미를 해석할 수 있지만 최종 권한을 결정하지 않는다.
2. 실제 side effect 직전의 정책 엔진이 최종 결정을 내린다.
3. 허용되지 않은 행동은 기본적으로 실행되지 않는다.
4. 승인은 추상적인 의도가 아니라 정규화된 실제 행동에 결합한다.
5. 모든 정책 결정은 재현 가능한 감사 기록으로 남긴다.
6. 정책은 에이전트가 임의로 수정할 수 없는 신뢰 경계 밖에 둔다.
7. 정상 개발 흐름을 지나치게 방해하는 정책은 실제 사용을 통해 완화하되, 위험 경계는 유지한다.

## 현재 범위

MVP는 로컬 개발 환경의 세 가지 표면만 다룬다.

- Filesystem
- Shell
- Git

DB, 클라우드, 배포, 이메일, 외부 SaaS 작업은 이후 범위다.
