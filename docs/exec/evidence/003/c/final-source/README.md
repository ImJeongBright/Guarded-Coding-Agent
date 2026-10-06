# C언어 DBMS 엔진 간단 실험

C11로 구현한 작은 영속 row store. `insert <uint32 id> <name>`, `select`, `count`, `find <uint32 id>`, `.exit`, `.help`를 지원한다.
100개 row, 고유 id(0부터 4294967295까지), 이름 최대 31바이트.
`count`는 현재 row 수를 `Count: N` 한 줄로 출력한다. 재시작 후에도 저장된 row 수를 표시하며,
중복 id로 거절된 insert는 row 수를 바꾸지 않는다. `data.db`는 GDB1 magic/count와 little-endian id,
32바이트 name으로 저장한다. 임시 파일을 flush/fsync하고 rename해 매 insert를 저장한다.
`find <uint32 id>`는 해당 row가 있으면 `(id, name)` 한 줄만, 없으면 `Not found.`를 출력한다.
음수, 범위 초과, 잘못된 id, 누락되거나 추가된 인자는 거절하며 데이터를 변경하지 않는다.
예: `find 0`, `find 4294967295`. 조회는 재시작 후에도 동작하며 GDB1 파일을 변경하지 않는다.
트랜잭션, SQL 전체 문법, 동시 쓰기, index, directory fsync를 포함한 crash durability는 실험 범위 밖이다.

Guard 설정과 재현은 [사용 가이드](../../docs/10-local-usage.md)를 참고한다.
컴파일 후 `tests/test_db.py`에 있는 16개의 실제 프로세스·파일 영속성 테스트를 실행한다.
`find` 회귀 테스트는 빈 DB(파일 없음/저장된 빈 파일), 경계 id, 중복 insert 후 원래 row,
재시작, 없는 id, 잘못된 문법을 확인한다. 조회 전후 파일 내용·inode·크기·수정 시각·
변경 시각·권한과 디렉터리 항목을 비교해 DB 재작성이나 임시 파일 생성을 감지한다.
파일 읽기에 따른 접근 시각 변경은 비교에서 제외한다.
