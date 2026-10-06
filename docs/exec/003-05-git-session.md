# 003-05 — staged 검토와 이어지는 작업

2026-10-04. 구현·live 연속 task 검증 완료.

`git/diff`에 boolean staged를 추가해 `--cached --no-ext-diff --no-textconv -- <paths>`로
정규화한다. add는 여전히 명시한 파일만 받는다. stage 후 원본을 다시 바꿔도 staged diff는
index만 표시하는 회귀를 추가했다. push/force/protected branch 기준은 그대로다.

첫 C task에서 모든 호출이 성공했지만 Apple `/usr/bin/git` launcher의 xcrun cache 실패와
system attributes 경고가 반복됐다. X는 이 출력을 불편하다고 보고했다.
trusted host에서 선택된 개발자 Git의 실제 절대경로를 한 번 resolve하고,
clean child environment에 GIT_ATTR_NOSYSTEM=1을 지정했다. 다른 경고를 숨기지 않는다.
다음 C task의 Git status/add/diff/commit/status stderr는 모두 빈 문자열이었다.
경고 제거와 기존 sandbox/approval 동작을 함께 회귀로 확인했다.

세 task는 같은 ordinary workspace, Git 이력, operator profile을 사용하는 별도 ephemeral
Codex 세션으로 실행한다. 재연결 후 변경·commit이 유지되는지 검증한다.
이것은 Codex persistent conversation resume 기능을 검증한 결과가 아니다.
policy 변경 시 재시작 필요와 기존 approval 재사용 거부는 별도 회귀로 유지한다.

보안 검토 중 Git state query의 64KB 출력 절단을 확인하지 않는 gap도 발견했다.
잘린 ls-files 목록에서 뒤쪽 tracked sensitive path를 확인할 수 없으므로 state를 완전하다고
가정하면 안 된다. truncated query fixture가 executor까지 도달하는 red test를 만든 뒤
GT-STATE로 실행 전에 멈추도록 수정했다. 실제 큰 저장소에서 secret 유출을 재현한 결과는
아니며, 명시적으로 알려진 불완전 조회를 fail closed하지 않던 코드 경로의 회귀다.
