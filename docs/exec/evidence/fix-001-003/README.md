# 001~003 수정 증거

2026-10-04 macOS 15.7.8 arm64 / Python 3.12.1 / Codex CLI 0.160.0.

- regression-final: 159개 통과, 실패/error/skip 0.
- regression-first-156-failed: 최초 전체 실행의 실패를 보존했다.
- user-x: 합성 역할극의 실제 도구 실행, 승인 fixture 포함.
- live-c: 실제 모델 세션, 새 commit, 별도 독립 계약 검사 및 source/patch.
- audit-signal/marker/lifecycle-probe: 제한된 native backend 실험. 일부 실패 실험도 포함한다.

`$RUN`, `$REPO`, `$HOME`은 원본 경로의 대체 표기다. 이 사본은 결과를 검토하기 위한
변환본이며, 실제 verifier는 `.guard-runs/fix-001-003`의 캡처 당시 원본으로 통과했다.
원본 workspace identity, audit byte cursor와 event hash는 기계와 원본 byte sequence에 묶여 있다.
따라서 이 사본을 `validate_session`에 넣어 재인증할 수 있다고 주장하지 않는다.
`export-manifest.json`은 원본/변환본 hash와 변환 여부를 함께 기록한다.
`source-manifest.json`은 수정 후 구현·테스트·샘플의 hash다. 이전 review 증거는 수정하지 않았다.

repro 디렉터리 파일도 경로 변환본이다. 재현하려면 새 임시 경로를 선택하고 `$REPO/$RUN`
및 해당 OS 실행 경로를 맞춰야 한다. prepare-live의 원본 프롬프트는 지원하지 않는
`guard_shell profiles`를 지시한 실험 오류를 그대로 보존한다. 새 실행에서는 shell tool
description의 Profiles 목록을 읽고 등록된 `run`/`exec`만 사용한다.
host 로그·SQLite·인증 파일·실제 승인 DB는 export하지 않았다.
