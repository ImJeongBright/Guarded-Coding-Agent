# Architecture

## 1. 상위 구조

~~~text
┌─────────────┐
│    User     │
└──────┬──────┘
       │ task / approval
       ▼
┌─────────────┐
│ Coding Agent│
└──────┬──────┘
       │ proposed tool call
       ▼
┌────────────────────────────┐
│        Tool Gateway        │
│ normalize → classify       │
└────────────┬───────────────┘
             ▼
┌────────────────────────────┐
│       Policy Engine        │
│ ALLOW / APPROVAL / DENY    │
└───────┬─────────┬──────────┘
        │         │
     allow     approval
        │         ▼
        │   ┌─────────────┐
        │   │ Approval UI │
        │   └──────┬──────┘
        │          │ approved action digest
        └──────┬───┘
               ▼
┌────────────────────────────┐
│        Tool Executor       │
│ FS / Shell / Git adapters  │
└────────────┬───────────────┘
             ▼
┌────────────────────────────┐
│ Validation + Audit         │
└────────────────────────────┘
~~~

## 2. 신뢰 경계

### Untrusted

- 자연어 사용자 입력
- LLM output
- Agent가 만든 tool arguments
- repository 내부의 일반 콘텐츠
- repository 문서에 포함된 prompt-like instruction

### Trusted

- Policy Engine 코드
- policy configuration
- approval verification logic
- workspace identity
- audit redaction rules
- executor boundary

Agent가 trusted 영역을 수정할 수 있어서는 안 된다.

## 3. 주요 구성요소

### Agent Adapter

특정 coding agent와 통합한다. Agent 종류에 종속적인 메시지 형식을 내부 ToolRequest로 변환한다.

MVP에서 한 종류만 지원해도 된다. 핵심은 agent framework 다양성이 아니라 실행 경계다.

### Tool Gateway

책임:

- 입력 schema validation
- path/command/git argument normalization
- tool classification
- policy input 생성

Gateway는 "안전한 것 같다" 같은 의미 판단을 하지 않는다.

### Policy Engine

입력:

- actor
- tool
- normalized action
- workspace
- repository state
- policy version

출력:

- decision
- rule id
- reason
- approval requirement

### Approval Manager

REQUIRE_APPROVAL action을 사용자에게 표시하고 승인 artifact를 발급한다.

승인은 action digest에 묶여야 하며 다른 action으로 재사용할 수 없다.

### Tool Executor

승인된 정확한 action만 실행한다.

정책 판정 전 실행하거나, 판정된 입력과 다른 입력을 실행하면 안 된다.

### Audit Recorder

정책 결정과 실행 결과를 구조화 기록한다.

secret/token 원문은 redaction한다.

## 4. 실행 순서

~~~text
ToolRequest
  ↓
Schema validation
  ↓
Normalization
  ↓
Policy evaluation
  ↓
DENY ───────────→ return denial
  │
  ├─ ALLOW ─────→ pre-execution recheck
  │
  └─ APPROVAL ──→ user approval
                    ↓
                digest/state recheck
                    ↓
                execute
                    ↓
                record result
~~~

## 5. 중요한 불변조건

### INV-01

Policy decision 이전에는 side effect가 발생하지 않는다.

### INV-02

승인받은 action과 실행 action의 digest가 다르면 실행하지 않는다.

### INV-03

모든 write target은 실행 직전에 다시 workspace boundary를 검증한다.

### INV-04

정책 파일은 Agent의 일반 workspace write 권한 범위 밖에 둔다.

### INV-05

알 수 없는 tool/action은 DENY다.

### INV-06

Audit log에는 raw secret을 남기지 않는다.

## 6. TOCTOU 고려

승인 이후 repository 또는 filesystem 상태가 바뀔 수 있다.

MVP에서 최소한 다음은 재검증한다.

- normalized path
- symlink resolution
- current Git branch
- remote target이 승인 당시와 동일한지
- command/action digest

상태가 달라졌다면 재승인을 요구한다.
