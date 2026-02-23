# 변경 체크리스트 (작업 전/후)

## 작업 전
- 요청을 1개 기능으로 분류한다.
- `docs/maintenance/REQUEST_FILE_MAP.md`에서 대상 파일만 고정한다.
- 고정된 파일 외 수정은 금지한다.

## 작업 중
- 큰 파일(`src/main_window.py`)은 메서드 단위로만 수정한다.
- "정리"가 필요해도 전체 파일 덮어쓰기 방식은 사용하지 않는다.
- UI 수정 시 레이아웃 메서드(`_relayout_settings_sections`)까지 같이 점검한다.

## 작업 후
- 필수 컴파일 점검:
```powershell
python -m py_compile src/main_window.py src/auth_client.py src/coupang_uploader.py src/settings_dialog.py
```
- 무결성 점검:
```powershell
python tools/sanity_check.py
```
- 변경 범위 확인:
```powershell
git diff --stat
```
- 요청 범위 외 파일이 섞이면 작업을 되돌리고 다시 분리한다.

## 회귀 방지 핵심
- 설정 화면 수정 후 필수 확인:
  - 키 추가 버튼 동작
  - 저장 후 재실행 시 키 개수 유지
  - 결제 섹션/문의 섹션 존재
- Threads 수정 후 필수 확인:
  - 로그인 버튼 -> 브라우저 -> 닫기 -> 세션 저장 메시지
- 결제 수정 후 필수 확인:
  - 결제 버튼 클릭 시 PayApp URL 열림
