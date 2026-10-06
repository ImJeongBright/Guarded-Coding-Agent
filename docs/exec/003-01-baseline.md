# 003-01 — 대상과 변경 전 기준

2026-10-04. 완료.

C DBMS의 기존 5개 파일과 MoneyPilot_Backend/packages/domain의 기존 6개 파일을
별도 ordinary workspace에 복사했다. 원본 Git metadata, node_modules, credentials,
프로젝트 설정은 복사하지 않았다. 두 복사본에 평가용 Git 이력만 새로 만들었다.
MoneyPilot의 독립 도메인은 기존 TypeScript 521줄과 테스트 236줄이며 외부 의존성 없이 Node로 실행된다.

변경 전 C 11개, domain 32개 테스트가 통과했다. 실제 개발에 필요한 선택 테스트,
debug compile, search, read range, hash edit, staged diff를 probe했다.
C 6개와 domain 5개 요청이 모두 미실행 DENY였다. Shell 3개는 미등록 capability,
나머지 8개는 아직 없는 operation/field였다. 위험 요청을 false denial로 세지 않았다.

baseline은 전체 모델 task의 실행 시간이 아니라 같은 정상 요청과 기존 테스트를 측정했다.
이후 같은 request 11개 재생은 모두 ALLOW/exit 0이었다. 모델의 작업 순서는 별도 live 실험이다.
복사·Git 초기화·기존 profile 설정·probe·기존 테스트의 자동 시간은 C 1.335초,
domain 0.317초였다. 운영자의 탐색·선정·검토 시간은 이 수치에 포함하지 않는다.

새 profile discovery/apply의 자동 시간은 C 약 0.033초, domain 약 0.007초였다.
후보 표시부터 등록까지 agent 운영자의 검토 경과는 각각 21.224초와 22.387초로,
5분 목표 안에 들어왔다. 실제 사람의 시간, 저장소 선정 시간, dependency 설치 시간은 아니다.

재현: `scripts/prepare_003.py --output <새 경로>`. 현재 source allowlist와 domain 위치는
이 저장소 환경의 평가용이며 범용 repository importer가 아니다.
원본 hash, requests/results, task 목표는 portable `evidence/003`에 보존한다.
