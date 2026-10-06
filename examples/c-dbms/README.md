# C언어 DBMS 엔진 간단 실험

C11로 구현한 작은 영속 row store. `insert <uint32 id> <name>`, `select`, `count`, `.exit`, `.help`를 지원한다.
100개 row, 고유 id(0부터 4294967295까지), 이름 최대 31바이트.
`count`는 현재 row 수를 `Count: N` 한 줄로 출력한다. 재시작 후에도 저장된 row 수를 표시하며,
중복 id로 거절된 insert는 row 수를 바꾸지 않는다. `data.db`는 GDB1 magic/count와 little-endian id,
32바이트 name으로 저장한다. 임시 파일을 flush/fsync하고 rename해 매 insert를 저장한다.
트랜잭션, SQL 전체 문법, 동시 쓰기, index, directory fsync를 포함한 crash durability는 실험 범위 밖이다.

Guard 설정과 재현은 [사용 가이드](../../docs/10-local-usage.md)를 참고한다.
컴파일 후 `tests/test_db.py`에 있는 11개의 실제 프로세스·파일 영속성 테스트를 실행한다.
