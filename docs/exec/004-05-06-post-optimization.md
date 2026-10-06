# 004-05-06 — 최적화 후 M2 live 확인

2026-10-05. M2 Git metadata 정규화의 성능 개선 뒤 실제 Codex를 같은 10,000/25,000 workspace에서 다시 실행했다.

`.help` exact-output, repeated-call, 빈 workspace에서 파일을 생성하지 않는 동작, populated DB bytes 불변을 확인하는 process test를 추가하고 README에 `.help`를 command list의 기준으로 적었다. Command behavior는 변경하지 않았다.

- Guard 호출 20회, 모두 ALLOW. denial과 failed action retry 없음.
- root-level `AGENTS.md` guidance search는 `build`만 제외한 채 5,000-entry 한도에서 `incomplete: true, entry_limit`을 반환했다. 모델은 이를 완전 결과로 사용하지 않고 검색 범위를 좁혔고, 후속 탐색은 완료됐다.
- 변경 파일은 `tests/test_db.py`, `README.md` 두 개.
- build와 전체 tests 33개 통과. 독립 verifier에서 정확한 help output과 빈/기존 DB 보존을 다시 확인했다.
- 세션 76.9초, clean tree, commit `0e920239e420e10caf5e925de409917216b2019c`.
- Git status 1.1–1.2초, diff 1.17–1.30초, add 1.03초, commit 1.10초.

M2 root search 한도는 여전히 유효하며, 이번 결과는 incomplete 상태와 이유가 노출되고 범위를 좁혀 복구 가능함을 보여준다. [독립 검증](evidence/004/004-05/sessions/M2-task-6/independent-verification.json), [patch](evidence/004/004-05/patches/M2-task-6.patch).
