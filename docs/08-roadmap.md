# Roadmap

## Stage 00 — Contract Freeze

목적:

- 프로젝트 문제와 비목표 고정
- Filesystem/Shell/Git 기본 정책 고정
- 위협 시나리오 고정

완료:

- docs 00~07
- ADR 0001~0003
- MVP plan

## Stage 01 — Deterministic Policy Core

구현:

- ToolRequest schema
- normalized action model
- Policy Engine
- ALLOW / APPROVAL / DENY
- rule id / reason
- default deny

테스트:

- pure policy unit tests
- unknown action
- precedence

완료 기준:

- OS side effect 없이 전체 기본 정책 테스트 가능

## Stage 02 — Filesystem Guard

구현:

- workspace root
- canonicalization
- traversal 차단
- symlink 처리
- sensitive path
- write/delete executor

테스트:

- FS-01~FS-06
- TOCTOU 최소 재검증

완료 기준:

- workspace 내부 정상 수정 가능
- 외부/secret/policy write 차단

## Stage 03 — Shell Guard

구현:

- structured command request
- command normalization
- project allowlist
- chaining/redirection/nested shell 처리
- fail closed

테스트:

- SH-01~SH-05
- temp workspace

완료 기준:

- build/test 같은 정상 명령 실행
- 해석할 수 없는 복합 명령 차단

## Stage 04 — Git Guard + Approval

구현:

- read/local/remote mutation 구분
- push approval
- force push deny
- Approval Manager
- action digest
- expiry/replay protection

테스트:

- GT-01~GT-05
- AP-01~AP-04
- local bare remote

완료 기준:

- 실제 push는 승인 전 실행되지 않음
- 승인 후 인자 변경 차단

## Stage 05 — Audit and Redaction

구현:

- JSONL 또는 동등한 structured audit
- rule/reason
- execution result
- secret redaction
- policy version

테스트:

- AU-01~AU-02

완료 기준:

- run 단위로 의사결정 재구성 가능
- raw secret 미기록

## Stage 06 — Coding Agent Integration

구현:

- 최소 한 종류의 coding agent 연결
- agent tool request → gateway
- deny/approval 결과를 agent workflow에 반환
- 정상 개발 task 수행

완료 기준:

- Agent가 filesystem/shell/git을 직접 우회하지 않고 gateway를 통해 작업

## Stage 07 — Dogfooding

기간:

- 최소 1~2주 권장

대상:

- 여러 실제 repository
- 실제 bug/refactor/test/config task

기록:

- false positive
- policy gap
- approval fatigue
- policy decision 변경

완료 기준:

- 실제 사용에서 나온 최소 2개의 policy refinement
- refinement마다 regression test

## Stage 08 — Optional Expansion

필요할 때만 진행한다.

후보:

- network egress
- package install
- DB mutation
- MCP tool proxy
- container isolation
- richer approval UI
- policy profiles

실사용 문제 없이 기능을 늘리지 않는다.
