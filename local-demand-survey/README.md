# THREAD AUTO 개인 강의 사전조사

운영 중인 THREAD AUTO의 개인 강의·원격지원·PDF 구성을 설계하기 위한 Next.js 16 설문 앱입니다. 응답은 구매 계약이 아니며 제출 시 결제되지 않습니다. 별도의 혜택 발급 시스템과 연결되어 있지 않으므로 무료 이용권 발급을 약속하지 않습니다.

## 저장 및 개인정보 흐름

1. 브라우저는 최초 제출 전에 응답 UUID와 32바이트 철회 증명을 생성하고, 네트워크 결과가 불명확해도 같은 값을 재사용합니다.
2. `/api/reservations`는 32KiB 제한과 전체 schema를 검증하고 이메일을 trim/lowercase로 정규화합니다. 제출 시간·수요 점수·분류는 서버에서만 계산합니다.
3. Upstash Redis REST의 Lua 트랜잭션은 응답 ID와 철회 증명 조합을 기준으로 idempotency를 보장합니다. 이메일 소유권을 확인하지 않으므로 이메일은 독점 접수 키가 아니며, 같은 이메일의 서로 다른 응답 ID도 rate limit 범위 안에서 접수됩니다. 전체 응답 TTL은 제출 시점부터 365일입니다.
4. Google Sheets는 분석용 best-effort 미러입니다. 이름·이메일·연락처·직업·수익 경험·자유서술 답변은 Sheets에 보내지 않습니다. 실패 상태와 단일 mirror claim은 Redis에 남으며 응답 ID와 철회 증명만 보낸 재시도가 Redis 정본으로 미러를 다시 시도합니다. 철회가 동기화와 겹치면 Redis가 먼저 철회 상태를 확정하고, 늦게 끝난 append는 보상 삭제합니다.
5. 완료 화면은 전체 JSON이 아닌 응답 ID만 복사합니다. 철회 버튼은 브라우저가 보관한 증명으로 Redis에 철회 tombstone을 먼저 남긴 뒤 Sheets 행과 중앙 응답을 삭제합니다.
6. 개인정보 동의 전에는 초안을 저장하지 않습니다. 동의 후 초안은 현재 탭의 `sessionStorage`에만 두고, 접수가 확인되면 즉시 지웁니다. `localStorage` 완료 확인에는 응답 ID·접수 시각·설문 버전·철회 증명·미러 상태만 최대 365일 보관하며 이름·이메일·연락처·자유서술·점수·분류는 저장하지 않습니다. 이전 버전의 전체 응답 영수증은 읽는 즉시 최소 요약으로 축소하고, 기존 영구 초안과 손상된 값은 제거합니다.

IP와 이메일은 rate-limit 저장소에 평문으로 저장하지 않고 `SURVEY_SECURITY_HMAC_SECRET`으로 분리 HMAC 처리합니다. 운영 환경에서 Redis나 HMAC 설정이 없으면 접수를 성공으로 가장하지 않고 `503`으로 닫힙니다.

## 환경변수

`.env.example`을 `.env.local`로 복사하고 실제 값을 입력합니다. `.env.local`과 토큰은 커밋하지 않습니다.

### Upstash Redis

권장 변수는 다음 공식 Upstash REST 쌍입니다.

- `UPSTASH_REDIS_REST_URL`
- `UPSTASH_REDIS_REST_TOKEN`

Vercel Marketplace의 `upstash/upstash-kv` 연동이 아래 이름을 주입하는 경우 그대로 사용할 수 있습니다.

- `KV_REST_API_URL`
- `KV_REST_API_TOKEN`

완전한 `UPSTASH_*` 쌍이 있으면 이를 우선합니다. `UPSTASH_*` 중 하나만 설정된 경우 서로 다른 credential이 섞이지 않도록 설정 오류로 처리하며 `KV_*`로 우회하지 않습니다.

`SURVEY_SECURITY_HMAC_SECRET`에는 비밀번호 생성기로 만든 32자 이상의 예측 불가능한 값을 사용합니다. 예제 파일은 안전을 위해 값을 비워 두며 `replace-with-*`, `change-me`, `example` 형태의 공개 placeholder는 운영 코드가 거부합니다. 이 값은 rate-limit용 이메일 해시와 철회 증명에 연결되므로 기존 응답의 1년 보유 기간 중 임의로 회전하지 않습니다. 회전이 필요하면 기존 키 마이그레이션 계획을 먼저 세웁니다. `SURVEY_RATE_LIMIT_IP_PER_HOUR`와 `SURVEY_RATE_LIMIT_EMAIL_PER_DAY`는 생략 시 각각 10, 3입니다.

`SURVEY_HEALTH_CHECK_SECRET`에는 HMAC secret과 다른 32자 이상의 값을 설정합니다. 두 값이 같거나 공개 placeholder이면 시작 단계에서 거부합니다. 공개 요청이 Redis와 Sheets를 호출하지 않도록 health endpoint는 이 값을 별도 헤더로 받은 경우에만 외부 상태를 점검합니다.

```powershell
curl.exe -H "x-survey-health-check-secret: $env:SURVEY_HEALTH_CHECK_SECRET" https://example.com/api/reservations
```

### Google Sheets와 Vercel OIDC

다음 값은 소스에 고정하지 않고 배포 환경마다 설정합니다.

- `GOOGLE_SHEETS_SPREADSHEET_ID`
- `GOOGLE_SHEETS_SHEET_NAME` — 기본값 `응답 원본`
- `GCP_PROJECT_NUMBER`
- `GCP_SERVICE_ACCOUNT_EMAIL`
- `GCP_WORKLOAD_IDENTITY_POOL_ID`
- `GCP_WORKLOAD_IDENTITY_POOL_PROVIDER_ID`

설정 순서:

1. Google Cloud 프로젝트에서 Google Sheets API와 IAM Credentials API를 활성화합니다.
2. Sheets 쓰기 전용 서비스 계정을 만들고 대상 스프레드시트를 해당 이메일에 편집자로 공유합니다.
3. Workload Identity Pool과 OIDC provider를 만든 뒤 Vercel 프로젝트/팀 subject 및 audience를 제한합니다.
4. provider principal에 서비스 계정의 `roles/iam.workloadIdentityUser` 권한만 부여합니다.
5. Vercel 프로젝트에서 OIDC token 발급을 활성화하고 위 환경변수를 Production/Preview별로 분리합니다.
6. 배포 후 위 전용 헤더를 포함한 `GET /api/reservations`가 `authoritative: "upstash-redis"`와 Redis `ok: true`를 반환하는지 확인합니다. 헤더가 없거나 틀리면 외부 저장소를 호출하지 않고 `404`를 반환합니다. Sheets 장애는 `mirror: "pending-or-unreachable"`로 별도 표시됩니다.

스프레드시트의 `응답 원본` 탭 첫 행은 다음 36개 열 순서로 만듭니다. 개인정보 최소화를 위해 일부 열은 의도적으로 빈 값으로 미러됩니다.

```text
responseId,createdAt,surveyVersion,fullName,email,privacyConsent,marketingConsent,interview,occupation,stage,platforms,monthlyPosts,revenueExperience,bottlenecks,manualMinutes,desiredPosts,tools,controlPreference,intent,priceReaction,comfortablePrice,paymentPreference,valuedBundle,purchaseBlockers,purchaseTiming,courseTopics,support,liveTime,desiredOutcome,buyCondition,painWords,contactMethod,contact,demandScore,segment,status
```

로컬 개발에서 OIDC header가 없으면 Google Application Default Credentials를 사용합니다. Sheets가 설정되지 않거나 일시 실패해도 Redis 접수는 완료되고 미러 상태는 `pending`으로 유지됩니다.

## 실행과 검증

Node.js 22.13 이상이 필요합니다.

```powershell
npm ci
npm run dev
```

Windows에서는 `로컬_설문_실행.bat`을 실행할 수 있습니다. 이 스크립트는 잠긴 의존성을 설치하고 실제 Next.js production build를 만든 뒤 `http://localhost:4173`을 엽니다.

전체 검증:

```powershell
npm run lint
npm run build
npm test
npm audit --omit=dev
```

테스트는 점수 계산, schema/본문 제한, 동시 idempotency·동일 이메일 비독점성, rate limit, Sheets 실패·자격 증명만 사용한 재시도, 동기화/철회 경쟁 보상, 증명 기반 철회, 보호된 health, 최소 영수증 TTL·이전 PII 제거, CSV formula neutralization, 보안 헤더 및 접근성 semantics를 검사합니다.
