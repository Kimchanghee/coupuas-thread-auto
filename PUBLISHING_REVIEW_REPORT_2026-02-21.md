# 퍼블리싱 준비 상태 종합 검토 보고서

- 프로젝트: 쿠팡 파트너스 스레드 자동화 (v2.3.1)
- 검토일: 2026-02-21

## 종합 판정

퍼블리싱 전 핵심 수정 사항(CRITICAL/HIGH)은 반영 완료했습니다.  
현재 빌드/테스트 기준 퍼블리싱 가능 상태입니다.

## 수정 반영 요약

### 1) 회원관리/등록
- `LoginWorker` / `RegisterWorker` 예외 발생 시에도 `finished_signal` emit 처리
- 로그인 체크박스 문구를 실제 동작과 일치하도록 `아이디 저장`으로 수정
- 로그인/회원가입 UI에 비밀번호 8자 이상 사전 검증 추가
- 사용자명 중복확인 워커에 토큰 기반 stale 결과 무시 로직 추가
- `paintEvent` 내 프레임 단위 import 제거(버전 값 캐시)

### 2) 결제/구독/작업량
- 과금 동기화 실패 시 중단 로직은 유지(안전 정책)
- 세션 만료 상태를 하트비트에서 UI 경고(1회)로 안내

### 3) 보안
- `_auth_state` 접근에 락 적용(멀티스레드 동기화)
- 임시 파일 저장 시 권한 강화 타이밍 보강
- 프로덕션(frozen)에서 외부 `.env` 로딩 차단
- TLS 인증서 핀 검증(옵션/고정핀 지원) 추가
- DPAPI 엔트로피를 사용자 기반 동적 값으로 변경 + 레거시 복호화 호환
- `bare except`를 `except Exception`으로 정리

### 4) 인코딩/문자 깨짐
- 요청 목록 14개 파일에 UTF-8 헤더 추가
- 한국어 문자열 정상 확인

### 5) 버그/단기·장기 안정성
- `_cancel_flag`를 `threading.Event` 기반으로 전환
- 워커 스레드에서 UI 직접 업데이트하던 큐 라벨 갱신을 시그널 방식으로 변경
- 워커 내부 step reset도 시그널 방식으로 전환
- 로그인 대기 실패 시 브라우저 누수 없도록 워커 종료 정리 보장
- 실행 중 설정 저장 시 파이프라인 재생성으로 인한 stale 참조 위험 완화
- 종료(`closeEvent`) 시 `_closed` 플래그 설정 순서 보정
- 워커에 설정 스냅샷 전달(실행 중 config 경쟁 최소화)
- `verify_post_success`에서 실제 실패(False) 경로 추가
- `src/services/coupang_parser.py`의 `bare except` 2건을 `except Exception`으로 정리

## 검증 결과

- `pytest -q`: **14 passed**
- `python -m compileall -q src main.py setup_login.py`: **성공**
- `python -m pip_audit -r requirements.lock --disable-pip`: **No known vulnerabilities found**

## 비고

- 비밀번호의 서버 전송 포맷(SHA-256)은 서버 API 계약에 의존하므로, 완전한 bcrypt/argon2 전환은 서버/클라이언트 동시 변경이 필요합니다.
- 클라이언트는 현재 계약 하에서 가능한 범위의 보안 강화(동기화/핀검증/비밀저장/권한강화)를 반영했습니다.
