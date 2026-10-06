# 003 — Real Project Usability 실행 결과

2026-10-04. 003-01~07 완료. 가상 X가 기존 C DBMS와 MoneyPilot 독립 도메인 복사본에서
각 세 개발 task를 실제 Codex로 수행했다. 원본 소스는 수정하지 않았다.

| 결과 | 측정 |
|---|---|
| 정상 요청 baseline | 11개 DENY → 같은 요청 11개 ALLOW |
| 실제 모델 작업 | 2 저장소 × 3 task, 각각 독립 검증·clean local commit |
| live 호출 | 110개: ALLOW 109 / DENY 1 / 승인 0 |
| 실제 사용 중 마찰 | Git 경고, 빈-query 파일 탐색 거부를 보완; 이후 73개 호출 DENY 0 |
| profile | 두 저장소 한 번씩 등록; task 사이 재등록 0 |
| 최종 project tests | C 16, domain 40; domain property test 23,040조합 |
| Guard 회귀 | 기존 74 + 추가 27 = 101 통과, 실패/error/skip 0 |
| 원본 source | 11개 file hash 모두 유지 |

추가한 기능은 운영자 검토용 command discovery/apply, fixed mode/literal test filter,
bounded text/file-path search, 부분 읽기·hash edit, staged diff, 실제 phase timing이다.
workspace 전체 write, 기본 network, Agent profile 수정/승인 권한은 추가하지 않았다.

X의 현재 판정은 **이번 범위에서는 Guard를 계속 켜둘 수 있다**다. C 초기 두 작업에서
약한 마찰이 있었고 이를 보완했다. 이후 네 작업은 승인·재시도 없이 마쳤다.
실제 사용자 인터뷰, 1~2주 장기 사용, dependency 설치와 큰/worktree 저장소는 아직 미측정이다.

항목별 기록:

- [003-01 baseline](003-01-baseline.md)
- [003-02 profile 준비](003-02-profiles.md)
- [003-03 command 변형](003-03-command-variants.md)
- [003-04 filesystem 흐름](003-04-filesystem-workflow.md)
- [003-05 Git/세션](003-05-git-session.md)
- [003-06 실제 X task](003-06-user-x.md)
- [003-07 회귀/판정](003-07-verdict.md)

증거:

- [machine-readable summary](evidence/003/summary.json)
- [최종 회귀](evidence/003/regression-final-101.json)
- [마찰과 보안 보완](evidence/003/workflow-refinements.json)
- [실행 source manifest](evidence/003/source-manifest.json)

`evidence/003`은 검토한 92개 파일 약 1.21MB다. trace/audit/preflight/prompt/patch,
baseline/final source, golden comparison, 초기 실패와 legacy 합성 X를 포함한다.
계정 auth·host log/database는 내보내지 않았다. 경로는 $RUN/$REPO/$HOME으로 바꿨다.
실제 content/stdin/edit text는 JSON trace에서 생략하고 source/patch를 별도로 제공한다.
익명화된 digest/context는 과거 증거용이며 현재 workspace의 승인이나 profile을 재사용하는 입력이 아니다.

재현은 `scripts/prepare_003.py`, `setup_003.py --phase discover`의 후보 검토,
`--phase apply`, `prompt_003.py`, 여섯 `run_guarded_codex.py` 호출과 각 `verify_003.py`로 진행한다.
원본 domain golden은 모델 task 전에 `verify_003.py --golden`으로 캡처한다.
baseline은 전체 pre-change 모델 세션이 아니라 동일 요청 probe+기존 suite다.
현재 source manifest는 최종 구현을 가리킨다. live 초기 세션의 경고/거부와 실행 중 수정을
같은 final revision의 결과라고 덮어쓰지 않고 개별 기록으로 구분했다.
