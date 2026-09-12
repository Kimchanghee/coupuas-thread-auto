# Windows 관리형 서명 설정

Microsoft Store 패키지는 Partner Center가 심사 후 다시 서명합니다. GitHub
Release에서 직접 제공하는 EXE와 Inno Setup 설치 파일은 Azure Artifact Signing을
사용합니다. 두 배포 경로는 서로 독립적입니다.

## Azure 최초 설정

1. Azure Artifact Signing 계정과 공개 신뢰 certificate profile을 만듭니다.
2. Microsoft Entra 애플리케이션을 만들고 해당 profile 범위에
   `Artifact Signing Certificate Profile Signer` 역할을 부여합니다.
3. Entra 애플리케이션에 GitHub Actions federated credential을 추가합니다.
   subject는 다음 보호 환경으로 제한합니다.

   ```text
   repo:Kimchanghee/coupuas-thread-auto:environment:production-code-signing
   ```

4. GitHub에 `production-code-signing` Environment를 만들고 required reviewers 및
   허용된 release tag 배포 규칙을 설정합니다.
5. `v*.*.*` release tag ruleset을 만들고 tag 생성·수정을 제한합니다. 릴리스 workflow는
   `src/version.py`와 일치하는 보호된 tag ref에서만 진행됩니다. 수동 실행도 branch가
   아니라 해당 보호 tag를 ref로 선택해야 합니다.

## GitHub Actions 변수

보호 환경에서 사용하는 값:

- `AZURE_ARTIFACT_SIGNING_ENDPOINT`
- `AZURE_ARTIFACT_SIGNING_ACCOUNT_NAME`
- `AZURE_ARTIFACT_SIGNING_CERTIFICATE_PROFILE_NAME`
- `AZURE_ARTIFACT_SIGNING_CLIENT_ID`
- `AZURE_ARTIFACT_SIGNING_TENANT_ID`
- `AZURE_ARTIFACT_SIGNING_SUBSCRIPTION_ID`

빌드와 검증에도 필요한 공개 repository variable:

- `AZURE_ARTIFACT_SIGNING_CERT_THUMBPRINTS`: 현재 SHA-1 지문 하나, 또는 인증서
  회전 중 `현재지문,다음지문`

PFX, `WINDOWS_CODE_SIGN_CERT_BASE64`, 인증서 비밀번호, exportable private key 또는
Azure client secret은 만들거나 GitHub에 저장하지 않습니다. workflow의 두 서명
job은 source checkout을 하지 않으며, 앞 단계가 만든 binary artifact만 받습니다.
필수 값이 비어 있거나 endpoint·지문 형식이 잘못되면 서명 전에 실패합니다.

## 인증서 회전 순서

정확한 지문 pin 때문에 전환 순서가 중요합니다.

1. repository variable에 현재 지문과 다음 지문을 함께 넣습니다.
2. 현재 인증서로 bridge 릴리스를 서명합니다. 이 릴리스는 두 지문을 모두
   업데이터에 포함합니다.
3. bridge 배포 후 Azure profile의 활성 인증서를 다음 인증서로 전환합니다.
4. 새 인증서 릴리스를 배포합니다.
5. 구버전 지원 기간이 끝난 뒤 이전 지문을 제거합니다.

bridge 릴리스 없이 서명 인증서를 먼저 바꾸면 기존 설치본이 새 업데이트를 거부할
수 있습니다.

## Microsoft Store 자동 제출

`store-release.yml`의 `publish=true`는 별도의 Partner Center 자격 증명을 사용합니다.

GitHub에 `production-store-publishing` Environment를 먼저 만들고 required reviewers와
허용된 보호 branch/tag 배포 규칙을 설정합니다. workflow는 repository code를 실행하는
빌드 job과 이 보호 환경에서 자격 증명을 받는 clean 게시 job을 분리합니다. 게시 job은
source checkout을 하지 않고 같은 workflow run의 MSIX를 다시 내려받아 해시, package
identity, publisher, version을 재검증한 뒤에만 Partner Center 자격 증명을 사용합니다.

- GitHub secrets: `AZURE_AD_APPLICATION_CLIENT_ID`,
  `AZURE_AD_APPLICATION_SECRET`, `AZURE_AD_TENANT_ID`, `SELLER_ID`
- GitHub variable: `MS_STORE_PRODUCT_ID`

Store workflow가 만드는 MSIX의 `major.minor.patch`는 반드시 `src/version.py`와
같아야 하며, 네 번째 Store revision만 선택적으로 변경할 수 있습니다.
