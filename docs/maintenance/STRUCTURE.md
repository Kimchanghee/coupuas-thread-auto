# 폴더/파일 구조 가이드

요청이 섞여서 다른 기능까지 깨지는 문제를 막기 위한 기준 문서입니다.

## 1) UI 계층
- `src/main_window.py`
  - 메인 화면 UI/UX, 설정 페이지, 상태바, 버튼 동작
- `src/login_window.py`
  - 로그인/회원가입 화면
- `src/tutorial.py`
  - 튜토리얼 오버레이/가이드
- `src/theme.py`
  - 공통 스타일/색상/컴포넌트 테마
- `src/ui_messages.py`
  - 메시지 박스/알림 UI 래퍼

## 2) 인증/과금 계층
- `src/auth_client.py`
  - 로그인 토큰, 사용자 상태, 결제 API 요청
- `src/config.py`
  - 로컬 설정/비밀값 저장

## 3) Threads 자동화 계층
- `src/threads_navigation.py`
  - Threads 접속/네비게이션 처리
- `src/threads_playwright_helper.py`
  - 로그인 상태/사용자 식별 헬퍼
- `src/computer_use_agent.py`
  - 브라우저 에이전트 실행

## 4) 업로드 파이프라인 계층
- `src/coupang_uploader.py`
  - 링크 처리, 생성, 업로드 메인 로직

## 5) 운영 점검 도구
- `tools/sanity_check.py`
  - 핵심 파일 컴파일/마커 점검
- `docs/maintenance/REQUEST_FILE_MAP.md`
  - 요청 유형별 수정 허용 파일
- `docs/maintenance/CHANGE_CHECKLIST.md`
  - 수정 전/후 필수 검증 절차

## 작업 원칙
- UI 요청과 결제 요청은 같은 턴에 섞지 않기
- 한 요청에서 바꿀 파일 범위를 먼저 고정하고 시작
- 완료 전 `py_compile`, `sanity_check`, `git diff --stat` 반드시 확인
