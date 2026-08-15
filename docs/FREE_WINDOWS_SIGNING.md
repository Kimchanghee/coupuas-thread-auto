# 무료 Windows 공개 서명 경로

이 프로젝트는 유료 인증서 구매 없이 Microsoft Store의 MSIX 재서명을 사용한다.
Store 인증을 통과하면 Microsoft가 패키지에 공개 신뢰 서명을 적용하므로 별도의
Authenticode 인증서나 SSL.com eSigner 구독이 필요하지 않다.

## 배포 구분

- `.github/workflows/store-release.yml`: 무료 Microsoft Store 경로다. 항상 MSIX를
  빌드·검증하고, `publish` 입력이 켜진 경우에만 Partner Center로 제출한다.
- `.github/workflows/build-release.yml`: GitHub에서 EXE/설치 프로그램을 직접
  배포할 때 사용한다. 공개 신뢰 인증서를 우선 사용하며, 준비 전에는 저장소에
  고정된 동일한 자체서명 인증서만 제한적으로 허용한다. 파일 내용, 인증서 지문,
  코드 서명 용도와 공개 타임스탬프를 모두 확인한다. 일반 `master` 푸시로는 이
  워크플로가 자동 실행되지 않는다.

## 최초 1회 Partner Center 설정

Microsoft Store 자동 제출에는 다음 GitHub Actions 비밀 값이 필요하다.

- `AZURE_AD_APPLICATION_CLIENT_ID`
- `AZURE_AD_APPLICATION_SECRET`
- `AZURE_AD_TENANT_ID`
- `SELLER_ID`

그리고 저장소 변수 `MS_STORE_PRODUCT_ID`가 필요하다. 최초 앱 제출과 연령 등급
설문은 Partner Center에서 한 번 완료해야 한다. 이후에는 `Build Free Microsoft
Store Package` 워크플로의 `publish` 옵션으로 무료 자동 업데이트를 제출할 수 있다.

현재 패키지 매니페스트는 예약된 Store ID를 사용한다.

- Identity: `YMcompany.30069A065C875`
- Publisher: `CN=447AAE61-8C19-4267-91D6-45419445A405`

GitHub Releases에 직접 올리는 EXE/설치본은 Store가 재서명하지 않는다. 따라서
무료 Store 서명을 사용하려면 사용자가 Microsoft Store를 통해 설치해야 한다.
