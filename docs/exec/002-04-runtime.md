# 002-04 — OS 실행 경계 재검사

macOS의 `/System/Volumes/Data` 경로 별칭으로 workspace 밖 임시 가짜 파일을 읽는 검사를 추가했다.
별칭은 같은 inode를 가리켰지만 Seatbelt가 읽기를 거부했다. 기존 구현에서 우회가 성공했다고
기록하지 않는다. 예방적으로 runtime 읽기 범위를 `/System`에서 `/System/Library`로 좁혔다.

`tests.test_sandbox_edges` 8개 통과: 실제 clang/SDK 컴파일, 경로 별칭, symlink, hardlink,
Git metadata, 환경 정리, 출력 상한, MCP 초기화 전 요청 거부.
새 system-volume 회귀는 외부 실제 비밀 데이터 대신 fixture만 사용한다.

이후 실제 C 모델 개발 및 독립 재검증에서도 컴파일과 프로세스 테스트가 통과했다.
Python과 Node runtime의 최소 profile도 의도한 application test 실패까지 실행돼
런타임 로딩 자체가 막히지 않음을 확인했다.
