# 001-03 — Filesystem Boundary

Date: 2026-10-03. Base commit: b93ba56. Policy: 001.

## Implementation

list/read/write/delete를 구현했다. lexical·resolved path와 원래 path component를 검사한다.
디렉터리 descriptor를 따라 이동하며 O_NOFOLLOW로 열고 열린 file의 type/link count를
검사한 뒤 truncate한다. symlink/hardlink, sensitive path, .git/.guard/.agents/.codex와
실행 package/launcher/state/policy는 보호한다. 삭제는 ordinary 파일 하나만 허용한다.

## Tests

`test_gateway.py`: 18 pass. FS-01~06, non-existent path, Unicode/space,
link escape, hardlink, FIFO, 실행 직전 link 교체, list filtering과 single delete 포함.
`test_hardening.py::test_protected_path_case_variants`도 최종 전체 회귀에서 pass.

## Observed / Decisions

대소문자가 다른 `.GIT/config` write가 ALLOW되는 실패를 먼저 재현했다.
보호 component 및 trusted path 비교를 casefold로 수정했다.
첫 X run은 Guard checkout 전체를 trusted로 잡아 sibling workspace도 거부했다.
신뢰 영역을 executing package·scripts·pyproject·state로 좁히고 위험 경계를 유지했다.

## Limitations

내부 symlink도 거부한다. Shell/Git은 workspace 전체의 link 여부를 검사한다.
동일 UID 악성 운영자가 directory descriptor의 위치를 외부에서 재배치하는 공격은 범위 밖이다.
원본 home secret은 읽지 않았으며 모든 위험 fixture는 임시 디렉터리에 만들었다.
