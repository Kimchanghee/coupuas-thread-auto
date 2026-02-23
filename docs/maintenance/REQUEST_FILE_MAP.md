# 요청별 수정 파일 맵

앞으로 수정 요청이 들어오면 아래 매핑대로 파일 범위를 먼저 고정하고 작업합니다.

## A. 설정 페이지 UI/UX
- 파일:
  - `src/main_window.py`
- 주 수정 메서드:
  - `_build_page2_settings`
  - `_relayout_settings_sections`
  - `_load_settings`
  - `_save_settings`
- 금지:
  - 결제/인증 파일 동시 수정 금지

## B. Gemini API 키(키 추가/저장/자동 전환)
- 파일:
  - `src/gemini_keys.py`
  - `src/config.py`
  - `src/main_window.py` (설정 연동)
- 확인 포인트:
  - 설정 저장 후 재실행 시 키 개수 유지
  - 업로드 시작 시 첫 유효 키 선택

## C. Threads 로그인/세션
- 파일:
  - `src/main_window.py`
  - `src/threads_playwright_helper.py`
  - `src/threads_navigation.py`
- 확인 포인트:
  - "로그인 후 창 닫기" 흐름
  - 닫은 뒤 자동 저장, 수동 상태 확인 버튼 동작

## D. 결제/구독
- 파일:
  - `src/auth_client.py`
  - `src/main_window.py`
- 확인 포인트:
  - 버튼 클릭 즉시 `create_payapp_checkout()` 호출
  - 응답 URL(`payurl`/`payapp_url`) 브라우저 오픈

## E. 작업량/무료횟수 표시
- 파일:
  - `src/auth_client.py`
  - `src/main_window.py`
- 확인 포인트:
  - FREE 계정에서 `0/0` 표시 방지
  - 기본 무료 횟수 fallback 표시

## F. 업로드 엔진
- 파일:
  - `src/coupang_uploader.py`
- 확인 포인트:
  - 설정에서 제거된 기능(예: fallback)과 실행 경로 일치

## 빠른 확인 명령
```powershell
python -m py_compile src/main_window.py src/auth_client.py src/coupang_uploader.py src/settings_dialog.py
python tools/sanity_check.py
git diff --stat
```
