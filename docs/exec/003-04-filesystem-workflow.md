# 003-04 — 검색, 부분 읽기와 편집

2026-10-04. 구현·live 후속 관찰 완료.

read는 optional start_line/end_line(최대 500줄)과 전체 파일의 SHA-256/줄 수를 반환한다.
파일 최대 1MB는 유지한다. edit는 expected_sha256이 일치하고 old_text가 정확히 한 번
나타날 때만 new_text로 치환한다. 편집 결과의 hash를 다음 편집에 사용할 수 있다.

edit는 UTF-8 파일을 descriptor로 읽고, 같은 parent의 exclusive temp에 완성한 뒤 fsync와
원본 inode/content 재검증 후 replace한다. ordinary mode를 유지하며 temp를 정리한다.
변경된 파일은 FS-STALE로 멈춘다. 외부 writer에 대한 OS-level compare-and-swap은 아니며,
마지막 검사와 rename 사이의 비협조적 동일 UID writer까지 해결한다고 주장하지 않는다.
파일 소유권·xattr·ACL 보존을 목적으로 만든 일반 편집기 기능도 아니다.

search는 literal UTF-8 검색이다. 최대 entry 5,000개, 읽기 8MB, match 200개/64KB,
파일당 1MB, excerpt 300문자로 제한한다. secret/trusted path, symlink/hardlink, binary는
검색 결과에 넣지 않는다. 경로 resolve와 descriptor traversal은 기존 FS 경계를 재사용한다.
old_text/new_text와 search match 내용은 audit에 보존하지 않는다.

실제 C task 2에서 `query:"", glob:"AGENTS.md"`가 DENY되어 한 번 retry가 발생했다.
이 정상 파일 탐색의 마찰을 재현한 뒤 빈 query를 content 미열람 file-path listing으로 보완했다.
entry/result/output 제한과 숨겨진 경로 제외는 그대로다. 최초 DENY와 수정 후 결과를 보존한다.

회귀는 range/schema bounds, unique/stale edit, source 변경·link swap, original 보존,
audit 내용 누락, secret/link search 제외와 result 상한을 검사한다.

최종 검토에서 exclusive temp 생성 실패 때 cleanup이 기존 파일까지 지울 수 있는 예외 경로를
발견했다. UUID를 고정해 충돌을 강제로 만들자 별도의 ordinary 파일이 삭제되는 red test가
실패했다. 생성에 성공한 temp만 cleanup 대상으로 설정하도록 수정하고 원본·충돌 파일
둘 다 보존하는 green regression을 추가했다. 실제 모델 작업에서 충돌이 발생한 사례는 아니다.
