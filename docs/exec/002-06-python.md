# 002-06 — Python 저장소 개발

실제 Codex가 별도 ledger 저장소에서 debit 버그를 수정하고 Decimal 이체 기능을 구현했다.
Guard 명령 profile은 `python -B -m unittest discover -v` 하나이며 workspace write scope는 없다.
수정은 Filesystem 도구로 수행하고 테스트 프로세스가 source를 바꿀 권한은 갖지 않는다.

baseline은 4개 테스트 중 debit 테스트가 실패했다. `abs()` 때문에 6.90이어야 할 잔액이
13.10이 되는 실제 실패를 Guard로 확인한 뒤 모델에게 작업을 맡겼다.

결과: Guard 호출 16개 모두 ALLOW, 승인/거부 0. 모델 테스트 9개 통과,
fixture commit `37eb29a`, working tree clean. 별도 검사에서도 Decimal 정확도,
원본 dict 불변, 잘못된 금액·계정·비유한 잔액 거부를 확인했다.

모델은 이 task에서 마찰이 없었다고 보고했다. dependency 설치, virtualenv, 대규모
Python 서비스 작업을 측정한 것은 아니다.

증거: [portable verification](evidence/002/python/verification.json),
[초기 실패](evidence/002/python/baseline.json), [live trace](evidence/002/python/events.jsonl),
[변경 결과](evidence/002/python/result.patch). 원본은 `.guard-runs/live-python-01`.
