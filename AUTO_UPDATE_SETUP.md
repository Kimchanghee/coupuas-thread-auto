# 자동 업데이트 및 GitHub Release 운영

앱은 `Kimchanghee/coupuas-thread-auto`의 최신 GitHub Release에서 설치 파일과
SHA-256 체크섬을 확인합니다. 저장소 주소와 asset 이름은 이미
`src/auto_updater.py`에 설정되어 있으므로 사용자명이나 저장소명을 수동으로
바꾸지 않습니다.

## 버전의 단일 기준

현재 버전은 `src/version.py`의 `VERSION` 한 곳에서만 저장합니다.

```powershell
python .github/scripts/set_version.py vX.Y.Z
git add src/version.py
git commit -m "chore(release): prepare vX.Y.Z"
git tag vX.Y.Z
git push origin master vX.Y.Z
```

태그 및 수동 workflow 입력은 이 값과 정확히 같아야 합니다. README, 엔트리포인트,
Python 패키지와 Store 패키지는 이 값을 가져다 쓰며 독립적인 버전 문자열을
관리하지 않습니다.

## 공개 릴리스 보안 경로

`build-release.yml`은 다음 단계를 모두 통과해야 Release를 만듭니다.

1. 잠긴 Python/Node 의존성 설치와 전체 자동 테스트
2. 업데이트 검증 코드에 현재 서명 인증서 지문 주입 후 unsigned EXE 빌드
3. 보호된 `production-code-signing` 환경에서 GitHub OIDC로 Azure Artifact Signing
4. 서명된 EXE를 포함하는 Inno Setup 설치 파일 빌드
5. 두 번째 격리 job에서 설치 파일 서명
6. 인증서 공개 체인·폐기 상태·정확한 지문·RFC 3161 타임스탬프·SHA-256 검증
7. 실제 설치, 설치본 첫 실행, 제거 smoke
8. 검증 완료 artifact만 GitHub Release로 승격

PFX, 인증서 Base64, 인증서 비밀번호 또는 장기 Azure client secret은 사용하지
않습니다. 관리형 서명 설정이 하나라도 없으면 workflow는 실패하도록 닫혀 있습니다.
필수 외부 설정은 `docs/FREE_WINDOWS_SIGNING.md`를 따릅니다.

## 인증서 지문 회전

업데이터는 정확한 인증서 지문만 신뢰합니다. 인증서가 바뀌기 전에 다음 bridge
릴리스를 먼저 배포해야 합니다.

1. `AZURE_ARTIFACT_SIGNING_CERT_THUMBPRINTS`를 `현재지문,다음지문`으로 설정합니다.
2. 아직 현재 인증서로 서명되는 bridge 릴리스를 배포합니다.
3. bridge 릴리스가 충분히 설치된 뒤 Artifact Signing 프로필의 활성 인증서를
   다음 인증서로 전환합니다.
4. 새 인증서로 릴리스를 배포합니다.
5. 이전 버전 지원 기간이 지난 뒤 변수에서 이전 지문을 제거합니다.

세 지문 이상, 잘못된 지문, pin 없이 만든 공개 빌드는 허용하지 않습니다.

## 검증 체크리스트

- [ ] `src/version.py`와 태그가 일치한다.
- [ ] `production-code-signing` 환경 승인자가 릴리스를 승인했다.
- [ ] `src/version.py`와 일치하는 `v*.*.*` tag가 ruleset으로 보호되어 있다.
- [ ] `signing-manifest.json`의 commit과 workflow run이 릴리스와 일치한다.
- [ ] EXE와 설치 파일의 `.sha256` asset이 함께 공개됐다.
- [ ] 이전 공개 버전에서 업데이트 알림, 다운로드, 설치가 정상 동작한다.
- [ ] Microsoft Store 버전의 첫 세 숫자가 앱 버전과 일치한다.

운영 토큰이나 PAT를 애플리케이션 코드에 넣지 마십시오. 이 저장소는 공개 GitHub
Release만 읽으므로 업데이트 확인에 PAT가 필요하지 않습니다.
