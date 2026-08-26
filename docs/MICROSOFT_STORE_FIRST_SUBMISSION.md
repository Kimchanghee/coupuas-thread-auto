# Microsoft Store first submission

This document contains the ready-to-paste Korean listing and certification
details for product `9PFB17P6MRMV`. The Store download is free. Some service
features require an account, an entitlement, or an AI provider selected by the
user.

## Product setup

- Product type: MSIX app
- Product ID: `9PFB17P6MRMV`
- Category: Productivity
- Pricing: Free
- Markets: All markets where the service and Microsoft Store are available
- Primary language: Korean (Korea), `ko-KR`
- Privacy policy: `https://coupuas-thread-auto-ten.vercel.app/privacy`
- Website: `https://coupuas-thread-auto-ten.vercel.app/`
- Support: `https://coupuas-thread-auto-ten.vercel.app/support`
- Support email: `support@fitshot.ai`

## Store listing (ko-KR)

### Product name

Thread Auto

### Short description

쇼핑 제휴 링크를 분석해 채널별 콘텐츠를 만들고 여러 Threads 계정의 게시 흐름을 한곳에서 관리하는 Windows 데스크톱 앱입니다.

### Description

Thread Auto는 쇼핑 제휴 콘텐츠 운영자가 상품 링크 확인부터 문안 생성, Threads 게시 준비까지 반복되는 작업을 한곳에서 관리하도록 돕는 Windows 앱입니다.

쿠팡뿐 아니라 네이버 쇼핑커넥트, AliExpress, Temu, 오늘의집, 무신사, 컬리 등 지원 채널의 링크를 분류하고 상품 정보를 확인합니다. 사용자가 선택한 AI 방식으로 여러 문안 후보를 만들고, 계정별 대기열과 작업 기록을 통해 게시 흐름을 정리할 수 있습니다.

브라우저 로그인 세션과 앱 설정은 사용자 PC를 중심으로 저장합니다. 서버 요청은 로그인 토큰으로 인증하며 작업량은 예약, 확정, 해제 흐름으로 안전하게 처리합니다.

앱 다운로드와 월 기본 사용량은 무료입니다. 일부 고급 기능은 별도 이용권이 필요할 수 있으며, 사용자가 직접 제공하는 AI API 키 또는 지원되는 무료 AI 로그인 방식을 선택할 수 있습니다. Threads 게시 기능을 사용하려면 사용자가 자신의 Threads 계정으로 로그인해야 합니다.

### Product features

Enter each line as a separate feature. Partner Center adds bullets automatically.

1. 7개 쇼핑 제휴 채널 링크 자동 분류
2. 상품 정보 확인과 AI 문안 후보 생성
3. 여러 Threads 계정과 계정별 게시 대기열 관리
4. 예약·확정·해제 방식의 안전한 작업량 처리
5. 작업 기록, 실패 복구, 이어서 실행
6. 로그인 세션과 주요 설정의 PC 중심 저장
7. Microsoft Store를 통한 안전한 설치와 자동 업데이트

### Search terms

Threads 자동화, 쇼핑 제휴, 제휴 마케팅, 상품 링크, SNS 콘텐츠, 게시 대기열, AI 문안

### What's new

Leave this field empty for the first submission.

### Screenshot captions

1. 여러 쇼핑 채널 링크를 한 번에 분류하고 게시 작업을 시작합니다.
2. 채널과 계정에 맞는 문안 생성 방식을 세밀하게 설정합니다.
3. 여러 Threads 계정과 계정별 게시 간격을 관리합니다.
4. 사용할 AI 제공 방식과 앱 동작을 한곳에서 설정합니다.

## Properties and disclosures

- Recommended category: Productivity
- Intended audience: General audience; the service is not directed to children under 14
- Internet access: Required for authentication, product-page analysis, optional AI generation, and Threads publishing
- Account required: Yes; a new account can be created in the app
- Free access: New accounts receive the currently advertised free monthly work allowance
- User-generated content/social interaction: The app prepares and publishes content through the user's own Threads account
- Purchases: The Store download is free; optional service entitlements may be sold outside Microsoft Store and are explained before purchase
- Hardware capabilities: Standard desktop internet access only; no camera, microphone, location, or background device capability is required

Answer the IARC questionnaire from the actual app behavior above. Do not mark
social interaction or optional purchases as absent merely to obtain a lower
rating.

## Certification notes (ko-KR)

앱 실행 후 회원가입 화면에서 새 계정을 만들 수 있습니다. 무료 계정에는 기본 작업량이 제공되므로 결제 없이 링크 분류와 문안 생성 흐름을 확인할 수 있습니다. 실제 Threads 게시는 심사자가 소유한 Threads 계정 로그인이 필요합니다. 외부 계정 로그인을 원하지 않는 경우 링크 입력, 채널 분류, 설정, 대기열 구성까지 검증할 수 있습니다.

패키지는 Microsoft Store 배포 모드에서 자체 EXE 업데이트를 사용하지 않으며 Store 업데이트를 따릅니다. 브라우저 세션과 앱 설정은 사용자 PC에 저장됩니다. 개인정보처리방침과 고객지원 페이지는 위 URL에서 로그인 없이 확인할 수 있습니다.

## Submission order

1. Pricing and availability
2. Properties and IARC questionnaire
3. Upload `ThreadShoppingAutomation_3.2.2.0_x64.msix`
4. Add the Korean listing above
5. Upload the four desktop screenshots produced by
   `tools/build_store_submission_pack.ps1`
6. Add the certification notes
7. Submit for certification

After the first version becomes live, configure the four Partner Center secrets
documented in `docs/FREE_WINDOWS_SIGNING.md` and run `store-release.yml` with
`publish=true` for subsequent updates.
