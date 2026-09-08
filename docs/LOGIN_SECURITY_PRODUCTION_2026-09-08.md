# 로그인 보안 운영 적용 기록 — 2026-09-08

## 적용된 변경

- 클라이언트/사이트 PR #3을 master에 병합: 8fceab61cf228312cb9a4bddaf6fa8955bcc302e.
- 실제 인증 서버 PR #7을 main에 병합: 7b0d08e1aadcd27f10b7f6846a9a09984cf0e2b0.
- 운영 복구 검증에서 PostgreSQL INSERT rowcount=-1로 새 큐 요청이 중복으로 오인되어 메일이 누락되는 문제를 발견했다. PostgreSQL CI에서 실패를 재현한 뒤 RETURNING으로 수정하고 PR #8을 병합: 73419d98dc522aa52f489b07b535d3754cc2732c.
- Resend 요청 식별 헤더 누락으로 API 진입 전 거부되는 문제를 추가 수정했다. 실제 앱 이름인 User-Agent를 사용하며, 인증된 auth.universelink.online 도메인을 복구 발신 주소에 적용했다. PR #9를 main에 병합했다: 6dc4c4998d68ba11c137360a15837fa567df52a8. 단, 마지막 변경의 운영 배포는 아래 한도로 대기 중이다.
- Cloudflare 계정이나 Turnstile 키는 필요하지 않다. Vercel Functions와 기존 공유 제한 저장소를 사용한다.

## 확인된 운영 상태

사이트 운영 URL: https://coupuas-thread-auto-ten.vercel.app
인증 서버 운영 URL: https://newshopping-shorts-auth.vercel.app

사이트 배포 dpl_ArdMHdGmgR5rDrWWQn8g3Rws7LiX와 서버 복구 수정 배포 dpl_D73HVjWjQVkLAaMz1qPQfFXkfhGt가 READY이고 실제 운영 도메인에 연결됨을 확인했다.

전용 계정 codex_security_f48df25347로 실제 가입, 로그인, MFA 등록, remember 발급·회전, 회전 전 세션 거부를 확인했다. 비밀번호·MFA 비밀키·복구 코드는 테스트 프로세스 메모리에서만 관리한다. 기존 고객 계정은 사용하지 않았다.

실제 복구 메일 수신과 이후 검증은 미완료다. 마지막 메일 헤더 수정 PR #9의 CI 34231419725 및 인증 서버 미리보기 dpl_EDK5CZrQWRVZYGX9bjeW93bZFsQ1은 통과했다. 그러나 main 자동 배포와 공식 `vercel promote` 모두 Vercel Hobby의 100회/일 배포 한도에 거부됐다(HTTP 402, api-deployments-free-per-day, try again in 24 hours). 운영 인증 서버에는 PR #8까지 적용돼 있고, 발신 주소 변경도 다음 배포 때 적용된다. 관리자 대시보드 배포도 동일 한도에 걸렸다.

테스트 계정의 로그아웃 및 remember 세션 해제를 실행했다. 테스트 계정 레코드는 남아 있으며 임의 비밀번호·MFA 키는 저장하지 않았다. 여기서 cleanup 완료는 복구 검증 완료를 의미하지 않는다.

### 한도 해제 후 남은 절차

1. NewshoppingShorts의 최신 main과 후속 변경을 확인하고 인증 서버를 production 환경으로 재배포한다. PR #9의 User-Agent 수정과 production 발신 주소가 포함되어야 한다. 미리보기에 운영 도메인만 강제로 연결하지 않는다.
2. 배포 READY, 운영 도메인 연결, 민감 환경변수의 기존 값 유지 여부를 확인한다. MFA 암호화 키는 회전하지 않는다.
3. 새 전용 계정으로 가입·MFA 등록·remember 회전 후 복구 메일을 한 번 요청한다. 운영 발송 성공과 실제 수신함 도착을 모두 확인한다.
4. 메일 토큰으로 재설정 성공, 같은 토큰 재사용 거부, 기존 access/remember 거부, 재설정 후 MFA 필수 유지, 새 비밀번호와 복구 코드 로그인, 이전 비밀번호 거부, 복구 코드 재사용 거부를 검증한다.
5. 테스트 세션을 정리하고 이 기록에 실제 결과를 추가한다. 데스크톱 소스 검증을 설치 패키지 배포 완료로 표현하지 않는다.

## 검증 근거

- 사이트 Node 테스트 74개, Python 전체 465개, 설문 테스트 32개와 lint/build/audit 검증.
- 사이트 master CI와 CodeQL 통과. 기본 브랜치 Dependabot qs 경고는 fixed 상태.
- 서버 PostgreSQL/MySQL CI 34230584948: 601 passed, 1 skipped. 제외 항목은 MySQL의 PostgreSQL 전용 권한 검사다.
- 수정 전 PostgreSQL 복구 발송 실패 재현: CI 34230261156.
- Resend 식별 헤더 회귀 검증을 포함한 로컬 복구 테스트 28개 통과. 후속 전체 DB CI 34231419725도 통과했다.

## 보호 범위

12개 공격 항목별 대응은 LOGIN_SECURITY_FIXES_2026-09-08.md에 기록했다. MFA는 등록된 계정에 강제되며 전체 기존 계정 강제 등록 정책은 아니다. CAPTCHA 없는 요청 제한은 자동화의 양을 제한하며 사람 여부를 판별하지 않는다. Vercel의 추가 WAF 관측 규칙은 draft/log-only이며 실제 차단으로 계산하지 않는다.

참고: https://resend.com/docs/knowledge-base/403-error-1010

배포 한도 공식 문서: https://vercel.com/docs/limits
