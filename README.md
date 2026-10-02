# Guarded Coding Agent

코딩 에이전트에게 실제 개발 작업과 도구 사용을 위임하되, 모델의 판단과 실제 실행 권한을 분리하는 로컬 개발 도구입니다.

핵심 아이디어:

> LLM interprets intent; the program enforces authority.

에이전트는 필요한 행동을 제안할 수 있지만, Filesystem / Shell / Git의 실제 side effect는 deterministic policy를 통과해야 합니다.

## MVP

- Filesystem / Shell / Git tool gateway
- ALLOW / REQUIRE_APPROVAL / DENY
- workspace boundary와 secret 보호
- git push approval / force push deny
- approval binding 및 replay 방지
- structured audit log
- adversarial regression tests
- 실제 개발 dogfooding

## Documents

설계와 구현 기준은 [docs/README.md](docs/README.md)에서 시작합니다.

주요 문서:

- [Project Charter](docs/00-project-charter.md)
- [Product Requirements](docs/01-product-requirements.md)
- [Architecture](docs/02-architecture.md)
- [Policy Model](docs/03-policy-model.md)
- [Threat Model](docs/05-threat-model.md)
- [Testing Strategy](docs/06-testing-strategy.md)
- [Roadmap](docs/08-roadmap.md)
- [001 MVP Plan](docs/plans/001-mvp.md)

현재 단계는 설계 기준 고정이며, 구현 이후 발견되는 우회·오탐은 회귀 테스트로 누적합니다.
