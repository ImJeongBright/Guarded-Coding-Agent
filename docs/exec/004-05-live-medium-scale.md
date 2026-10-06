# 004-05 — M1/M2 실제 개발과 X의 사용 판정

2026-10-05. Codex CLI 0.160.0으로 분리된 M1/M2 C DBMS 복사본에서 계획된 다섯 feature task를 수행했다. M2 Git 흐름에서 반복되는 약 4초 정규화 비용을 찾아 안전 검사를 유지한 최적화를 추가했고, 최적화 뒤 짧은 Codex task를 하나 더 실행해 결과를 확인했다.

## 결과

| 세션 | 규모 | 변경 | Guard 호출 | full tests | 독립 확인 |
|---|---:|---|---:|---:|---|
| [M1 task 1](004-05-01-m1-delete.md) | 3,000 tracked / 10,000 ignored | `delete` | 28 ALLOW | 15 | 통과 |
| [M1 task 2](004-05-02-m1-find.md) | 같음 | 읽기 전용 `find` | 24 ALLOW | 19 | 통과 |
| [M1 task 3](004-05-03-m1-rename.md) | 같음 | `rename` | 27 ALLOW | 22 | 통과 |
| [M2 task 4](004-05-04-m2-clear.md) | 10,000 tracked / 25,000 ignored | `clear` | 24 ALLOW, 없는 `AGENTS.md` 읽기 1 DENY | 26 | 통과 |
| [M2 task 5](004-05-05-m2-stats.md) | 같음 | 읽기 전용 `stats` | 29 ALLOW | 32 | 통과 |
| [최적화 후 확인](004-05-06-post-optimization.md) | 같음 | `.help` 회귀 테스트 | 20 ALLOW | 33 | 통과 |

계획된 다섯 task는 모두 각자의 clean commit을 만들었고, 각 session audit와 독립 동작 검증이 통과했다. 최적화 확인 task까지 합치면 실제 Codex 호출 153회 중 ALLOW 152, DENY 1, APPROVAL 0이며, incomplete 검색은 최적화 후 확인 task의 한 번이다. 여섯 세션의 끝 tree는 모두 clean했다. 테스트 호출은 각각 전부 exit 0이다.

## 성능 문제와 수정

M2 task 4·5의 Guard Git `status`, `diff`, `add`, `commit`은 평균적으로 3.8–4.0초가 걸렸다. phase timing상 Shell 실행보다 Git normalization이 느렸고, `cProfile`에서는 tracked path 10,000개 각각에 대해 `Filesystem.relative()`가 `Path.resolve/stat`을 하면서 4.26초를 썼다. 전체 workspace integrity scan은 별도 0.40초였다.

[git.py](../../guarded_agent/git.py)에서 Git의 NUL 경로 metadata를 `PurePosixPath`로 엄격히 검사하도록 바꿨다. 절대경로, traversal, 비정규 경로, replacement 문자, 4 KiB 초과, sensitive/protected path 검사는 그대로 적용한다. 이 metadata는 앞뒤의 전체 symlink/hardlink 검사로 둘러싸여 있으며, Git executor 직전 마지막 검사도 유지했다. [회귀](../../tests/test_scale_git_metadata.py)는 whitespace/Unicode, malformed path, sensitive/protected path와 metadata 조회 중 추가된 symlink가 실행 전에 차단되는지 확인한다.

최적화 뒤 Guard `git status`를 같은 M1/M2 복사본에서 각각 6회 실행했다. M1 median은 1.47초에서 0.63초, M2는 3.90초에서 1.11초로 줄었다. 이후 실제 M2 Codex 확인 task에서도 `status` 1.10초, `diff` median 1.23초, `add` 1.03초, `commit` 1.10초였다. 최적화 뒤 Git latency는 이번에 실제 모델 session으로도 확인했다.

## 처음 실패한 관찰

M2 baseline 최초 build 요청은 executor 시작 전 `FS-LINK`로 DENY됐다. 바로 실행한 35,048개 항목 link scan은 통과했고, 같은 workspace에서 build와 tests를 다시 Guard로 실행하자 둘 다 통과했다. 첫 오류 원인은 기록에서 더 구체적으로 드러나지 않아 transient라고 단정하지 않는다. 이후 여섯 live Codex task에서 같은 integrity DENY는 재현되지 않았다.

M2 task 4는 존재하지 않는 `AGENTS.md`를 읽으려 해 `EXEC-ERROR` DENY를 한 번 받았다. 모델은 재시도하지 않고 알려진 C 경로에서 계속 진행했다. 최적화 후 확인 task에서는 guidance를 찾는 root search가 5,000-entry 한도에 도달해 `incomplete: true, entry_limit`을 반환했다. 모델은 결과를 완전한 검색으로 취급하지 않고 경로를 좁혔고 후속 탐색은 완료됐다. 범용 root search는 M2에서 여전히 끝까지 보장되지 않으며, 경로·exclude를 선택해야 한다.

독립 확인 스크립트를 첫 실행할 때 macOS Seatbelt 권한 없이 실행해 lifecycle self-test가 `Operation not permitted`로 끝났다. 이는 task의 Guard call이 아니었고, 승인된 sandbox 실행으로 다시 수행해 통과했다. 기록은 첫 실패와 재실행을 함께 보존한다.

## 최종 판정 — 모의 사용자 X

수정 전 M2 Git 작업은 매번 4초가량 기다려야 해 눈에 띄게 답답했다. 최적화 뒤 같은 scale의 실제 Guard Git 동작은 대략 1.0–1.3초였고, edit/read는 대체로 몇 ms였다. 정상 변경·build·전체 tests·명시적 diff/stage/commit이 거부되거나 재시도 없이 이어졌으며, 최적화 후 Codex task에서도 같은 흐름을 확인했다.

**X 판정: 이 macOS profile과 10,000/25,000 M2 fixture 범위에서는 Guard를 켜고 계속 개발할 수 있다.** 넓은 저장소 검색은 의도대로 incomplete를 드러내므로 작업 경로를 좁히는 습관이 필요하다. 이 판정은 약 2분 내외의 여섯 세션을 합친 결과이며, 실제 사람의 1–2주 연속 사용·주관적 만족도는 측정하지 않았다.

## 검증과 증거

- 집중 Git metadata 회귀: 5 tests, 모두 통과, 10.353초.
- 전체 회귀: 173 tests, 실패/error/skip 0, 50.549초.
- 계획된 live task 다섯 개와 최적화 후 여섯 번째 task: build/full tests, 독립 동작 검사, session audit 귀속, 새 local commit 모두 통과.
- [portable evidence](evidence/004/004-05/README.md): path-scrubbed session/event/audit, 각 commit patch, M1/M2 latency, post-optimization measurement, source manifest와 delta.
- 원본 live workspace와 audit는 `.guard-runs/scale-probe-03/` 아래에 남겼다. 별도 Guard 프로젝트 원본은 변경하지 않았다.

다음에는 M1/M2의 안전성 및 기능 회귀가 새 metadata 경로 최적화와 함께 CI에서 항상 실행되는지 확인하고, 장기 사용 평가는 실제 사용자 관찰로 분리한다.
