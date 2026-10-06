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
- [002 Live Plan](docs/plans/002-live-dogfooding.md)
- [003 Real Project Plan](docs/plans/003-real-project-usability.md)
- [004 Medium Scale Plan](docs/plans/004-medium-scale-readiness.md)

현재 로컬 MVP, 실제 Codex 연결, 세 언어 task와 두 기존 프로젝트의 연속 개발 실험을 구현했습니다. Guard 자체에는 외부 API,
API key 또는 HTTP 서버가 필요 없습니다. Python 3.11+ 표준 라이브러리만 사용하며,
Shell/Git 격리 backend는 macOS sandbox-exec입니다.

## 실행

```sh
python3 scripts/check.py --evidence /tmp/guard-regression.json
python3 scripts/dogfood.py --output /tmp/guard-user-x-new-run
```

출력 디렉터리는 새 경로여야 합니다. 설치 없이 저장소에서 실행할 수 있습니다.
실제 coding-agent 연결과 프로필·승인은 [Local Usage](docs/10-local-usage.md)를 참고합니다.

## 검증 결과

- 수정 후 001–003 회귀 159개 통과. 최신 Guard 전체 회귀는 173개이며 C DBMS profile도 계속 통과.
- 002: 실제 Codex의 C·Python·JavaScript 호출 49개, 승인·정책 차단 0회.
- 003: 두 기존 프로젝트 × 세 task, 110개 호출 ALLOW 109/DENY 1/승인 0, 모두 독립 검증·clean local commit 완료.
- 003의 Git 경고와 빈-query 탐색 거부를 보완했고 이후 73개 live 호출은 거부 없이 완료했습니다.
- 최종 합성 X의 정상 개발 25개 action 승인·차단 0회, 위험 7개 미실행, bare push에는 exact grant 1회.
- 004: M1/M2 실제 Codex task 5개와 Git 성능 수정 후 후속 task 1개, 153 Guard 호출 ALLOW 152/DENY 1/승인 0. 전체 173개 회귀와 task별 독립 검증 통과.
- hook 단독 fail-open과 쓰기 scope 경쟁 조건을 재현해 수정했습니다.
- 항목별 결과와 증거는 [001 Exec](docs/exec/001-mvp.md), [002 Exec](docs/exec/002-live-dogfooding.md), [003 Exec](docs/exec/003-real-project-usability.md)에 있습니다.

후속 [001~003 리뷰](docs/exec/review-001-003.md)의 High 1 / Mid 4 / Low 2를 모두 수정했습니다.
[수정 문서와 재검증](docs/exec/fix-001-003.md)에 항목별 변경·실패 실험·증거를 기록했습니다.
새 실제 Codex C 작업은 호출 17회, 승인 0회로 새 커밋과 독립 검증을 완료했습니다.
거부 1회는 실험 프롬프트가 지원하지 않는 동작을 지시한 오류였으며 자동으로 복구했습니다.
소규모 C 흐름과 이번 10,000 tracked / 25,000 ignored M2 fixture에서는 Git metadata 최적화 뒤 계속 사용할 수 있다는 모의 X 판정입니다. 실제 사용자 1–2주 연속 사용은 아직 측정하지 않았습니다.
이전 [중규모 용량 관찰](docs/exec/scale-observation.md)의 Git metadata 한도는 보완했고, 현재 root search는 M2에서 5,000-entry 뒤 incomplete를 알리므로 경로를 좁혀야 합니다. [004-05 실행 기록](docs/exec/004-05-live-medium-scale.md)에 수치와 한계를 남겼습니다.
검증 범위는 macOS와 전용 Codex CLI 0.160.0 profile입니다. 큰 저장소·worktree·dependency 설치·
다른 host·1~2주 실제 사용자 평가는 [현재 판정과 한계](docs/exec/003-07-verdict.md)에 구분했습니다.
