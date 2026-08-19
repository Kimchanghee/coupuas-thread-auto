# CEO Thread Auto

쓰레드(Threads) 플랫폼에 글을 자동으로 업로드하는 Windows용 Python 애플리케이션입니다.

**현재 버전: v3.0.78** · [Windows 설치 파일 다운로드](https://github.com/Kimchanghee/coupuas-thread-auto/releases/latest/download/CoupangThreadAutoSetup.exe)

## 이용권

- **무료**: 매월 5회 작업, 첫 작업 1회 쇼핑 프로 링크 체험
- **7일 쿠팡 기본**: 19,000원 · Threads 발행 계정 1개
- **7일 쇼핑 프로**: 29,000원 · Threads 발행 계정 3개
- **월간 쿠팡 기본**: 49,000원/30일 정기결제 · Threads 발행 계정 최대 10개
- **월간 쇼핑 프로**: 69,000원/30일 정기결제 · Threads 발행 계정 최대 10개

이용권별 계정 수와 작업량은 앱의 결제 화면에 표시되는 최신 정책을 따릅니다. 결제 또는 이용 문의는 [GitHub Issues](https://github.com/Kimchanghee/coupuas-thread-auto/issues)에서 남길 수 있습니다.

## 주요 기능

- **멀티 쇼핑몰 상품 분석**: 국내 7개 제휴 프로그램의 발급 링크와 AliExpress 호환 링크를 API 연동 없이 공개 상품 페이지에서 분석
- **AI 기반 문구 생성**: 쇼핑몰별 광고·제휴 고지를 포함한 Threads용 짧은 홍보 문구를 생성
- **상품 이미지 검색**: 1688 이미지 검색 결과를 캐시에 저장해 첫 번째 게시글에 첨부
- **브라우저 세션 기반 업로드**: Playwright로 Threads 웹을 제어하고 로그인 세션을 암호화 저장
- **Supabase 기반 회원 DB**: 회원가입, 로그인, 작업량과 결제 상태는 운영 인증 API를 통해 Supabase PostgreSQL에서 관리
- **업로드 이력 관리**: 업로드한 링크를 기록해 중복 업로드를 방지
- **간편한 AI 사용**: 별도 AI API 키 없이 로그인과 이용권만으로 Grok 4.3 문안 생성
- **설정 관리**: Threads 계정, 업로드 간격, 계정별 대기열 등을 앱에서 설정

## 지원 제휴 프로그램

Thread Auto는 아래 프로그램에서 사용자가 **이미 발급받은 제휴 링크**를 입력받습니다. 앱이 가입, 제휴 승인, 링크 발급 또는 일반 상품 URL의 제휴 링크 전환을 대신하지 않습니다.

| 프로그램 | 이용권 | 대표 입력 URL |
| --- | --- | --- |
| 쿠팡 파트너스 | 쿠팡 기본·쇼핑 프로 | `link.coupang.com`, `coupang.com` |
| 네이버 쇼핑 커넥트 | 쇼핑 프로 | `naver.me`, `shopping.naver.com`, `smartstore.naver.com` 등 |
| 토스 쇼핑 쉐어링크 | 쇼핑 프로 | `toss.im/_m/`, `toss.shopping`, `shopping.toss.im` 등 |
| 오늘의집 큐레이터 | 쇼핑 프로 | `ozip.me`, `link.ohou.se`, `ohou.se`, `store.ohou.se` |
| 무신사 큐레이터 | 쇼핑 프로 | `musinsa.com`, `musinsa.onelink.me` |
| 컬리 큐레이터 | 쇼핑 프로 | `lounge.kurly.com`, `kurly.com` |
| 올리브영 쇼핑 큐레이터 | 쇼핑 프로 | `oy.run`, `oliveyoung.co.kr` |
| AliExpress | 쇼핑 프로 · 호환 지원 | `aliexpress.com` |

입력한 원본 제휴 URL은 수수료 귀속 정보를 보호하기 위해 Threads 게시물에 그대로 사용합니다. 상품명·특징 수집은 로그인 없이 볼 수 있는 공개 메타데이터와 허용된 리다이렉트 경로에 한정됩니다. 앱 전용·로그인 전용 페이지, 차단된 요청, 새로운 단축 도메인 또는 허용 범위 밖으로 이동하는 리다이렉트에서는 상품 정보가 일부 누락되거나 분석이 실패할 수 있습니다. 자세한 내용은 [제휴 링크 지원 안내](docs/AFFILIATE_MARKETPLACES.md)를 참고하세요.

## 시스템 요구사항

- Windows 10 이상
- Python 3.9 이상

## 설치 방법

### 방법 1: 설치형 (권장) ✨

1. [최신 설치 파일](https://github.com/Kimchanghee/coupuas-thread-auto/releases/latest/download/CoupangThreadAutoSetup.exe)을 다운로드
2. `CoupangThreadAutoSetup.exe` 실행
3. 설치 마법사의 안내대로 설치

**자동 업데이트**: 프로그램 실행 시 자동으로 새 버전을 확인하고 업데이트할 수 있습니다! 🔄

### 방법 2: 소스코드 실행

#### 1. Python 설치
[Python 공식 웹사이트](https://www.python.org/downloads/)에서 Python 3.9 이상을 다운로드하여 설치합니다.

#### 2. 프로젝트 클론
```bash
git clone https://github.com/Kimchanghee/coupuas-thread-auto.git
cd coupuas-thread-auto
```

#### 3. 필요한 패키지 설치
```bash
pip install -r requirements.txt
```

## 사용 방법

### 1. 초기 설정 (최초 1회만)

**Threads 로그인 세션 저장**:

```bash
# Windows
setup_login.bat

# 또는
python setup_login.py
```

실행 후:
1. 브라우저가 자동으로 열립니다
2. Instagram 계정으로 로그인하세요
3. 피드가 보이면 터미널에서 Enter를 누르세요
4. 세션이 사용자 홈의 `.shorts_thread_maker/sessions` 아래에 암호화 저장됩니다

**이후 실행 시 자동으로 로그인 상태가 유지됩니다!** ✅

### 2. 애플리케이션 실행
```bash
python login_main.py
```

### 3. AI 이용 준비
1. 애플리케이션에서 회원가입 후 로그인합니다.
2. 무료 사용량 또는 구매한 이용권이 있으면 AI 문안 생성이 바로 활성화됩니다.
3. 별도의 xAI·Google API 키 발급이나 입력은 필요하지 않습니다.

### 4. Threads 로그인 준비

설정 화면에서 **Threads 로그인** 버튼을 눌러 브라우저를 열고 로그인하세요.
로그인 후 브라우저를 닫으면 세션이 저장되어 다음 실행부터 재사용됩니다.

### 5. 업로드 간격 설정
1. **업로드 설정** 화면에서 시간/분/초를 입력합니다.
2. 최소 간격은 30초입니다.
3. **저장** 버튼을 눌러 설정을 반영합니다.

### 6. 링크 입력 및 업로드
1. **링크 입력** 화면에 지원 제휴 프로그램에서 이미 발급받은 상품 URL을 붙여넣습니다. 한 줄에 하나씩 입력하며, 쿠팡 파트너스 외 프로그램은 쇼핑 프로가 필요합니다.
2. **자동화 시작** 버튼을 누릅니다.
3. 앱이 링크 분석, 이미지 검색, 문구 생성, Threads 업로드를 순서대로 진행합니다.
4. 게시물에는 입력한 원본 제휴 URL이 유지되며, 이미 업로드된 링크는 이력 기준으로 자동 스킵됩니다.

## 프로젝트 구조

```
coupuas-thread-auto/
├── src/
│   ├── __init__.py
│   ├── config.py                      # 설정 관리
│   ├── auth_client.py                 # 인증/작업량 API 클라이언트
│   ├── coupang_uploader.py            # 쇼핑 상품 처리 및 업로드 파이프라인
│   ├── computer_use_agent.py          # 브라우저 세션/Computer Use 에이전트
│   ├── threads_playwright_helper.py   # Playwright 직접 제어 헬퍼
│   ├── threads_navigation.py          # Threads 접속 도메인 폴백
│   ├── main_window.py                 # 메인 GUI
│   └── services/
│       ├── coupang_parser.py          # 지원 쇼핑몰 링크 분석
│       ├── marketplaces.py            # 쇼핑몰 판별·URL·광고 고지 정책
│       ├── image_search.py            # 1688 이미지 검색/캐시
│       ├── aggro_generator.py         # Threads 문구 생성
│       └── link_history.py            # 업로드 이력 관리
├── images/                            # 앱 아이콘 등 정적 이미지
├── main.py                            # 개발자 자동 진입 실행 파일 (로그인 우회)
├── login_main.py                      # 실제 로그인 시작 실행 파일
├── setup_login.py                     # 초기 로그인 설정 스크립트
├── requirements.txt                   # 필요한 패키지
└── README.md                          # 사용 설명서
```

## 주의사항

- Threads 계정과 로그인 세션 정보를 안전하게 보관하세요
- 검색된 상품 이미지는 사용자 홈의 `.shorts_thread_maker/media_cache`에 저장됩니다
- 설정은 사용자 홈 디렉토리의 `.shorts_thread_maker/config.json`에 저장됩니다
- **세션 파일**은 사용자 홈의 `.shorts_thread_maker/sessions`에 암호화되어 저장되며 공유하지 마세요

### Computer Use 사용 시 주의사항
- **초기 로그인 필수**: `setup_login.py`를 먼저 실행하세요
- **세션 유효기간**: 일반적으로 수개월 유지되지만, 만료 시 재로그인 필요
- **Chromium 브라우저**: Playwright가 자동으로 설치 및 관리
- **Instagram OAuth**: Threads는 Instagram 계정으로 로그인합니다
- **이용량 제한**: 무료·7일·월 정기권에 설정된 작업 횟수 안에서 사용할 수 있습니다
- **중지 처리**: 작업 중 중지를 누르면 현재 네트워크/API 단계가 끝나는 대로 안전하게 중단됩니다

## AI 비용과 API 키

운영 서버가 Vercel AI Gateway를 통해 `xai/grok-4.3`을 호출합니다. 사용자는 AI 제공자 계정을 만들거나 API 키를 직접 관리하지 않습니다.

## 라이선스

이 프로젝트는 개인 용도로 제작되었습니다.

## 문제 해결

### 애플리케이션이 실행되지 않는 경우
- Python이 올바르게 설치되었는지 확인
- 필요한 패키지가 모두 설치되었는지 확인: `pip install -r requirements.txt`

### AI 오류가 발생하는 경우
- 로그인 상태와 남은 무료·유료 작업 횟수를 확인
- 인터넷 연결 상태 확인
- 잠시 후 다시 시도하고 계속 실패하면 운영자에게 문의

### 이미지가 검색되지 않는 경우
- 1688 검색 결과가 없거나 이미지 다운로드가 차단되면 이미지 없이 진행될 수 있습니다

### Computer Use가 작동하지 않는 경우

**세션 관련:**
```bash
# 세션이 만료되었으면 재생성
python setup_login.py
```

**API 오버로드:**
- "API 오버로드" 메시지가 나오면: 5-10분 대기 후 재시도
- 이용량 소진 메시지가 나오면 다음 무료 갱신을 기다리거나 이용권을 구매

**일반적인 문제:**
- Playwright 설치 확인: `playwright install chromium`
- 방화벽이나 보안 소프트웨어 확인

## 최근 업데이트

### 2026-08-05 쇼핑 프로
- 쿠팡 파트너스·네이버 쇼핑 커넥트·토스 쇼핑 쉐어링크·오늘의집 큐레이터·무신사 큐레이터·컬리 큐레이터·올리브영 쇼핑 큐레이터 링크를 한 입력창에서 처리합니다.
- AliExpress 링크는 기존 사용자를 위한 호환 대상으로 계속 지원합니다.
- 쇼핑 프로 7일권·월간권과 Threads 다계정 한도를 결제 서버 권한에 연결했습니다.
- 기존 유료 고객에게 한시적 무료 확장과 전환 혜택을 서버에서 판정합니다.

### 2026-05-27 버그 수정
- 중복 업로드 방지: 메인 업로드 화면에서도 업로드 이력을 확인해 이미 처리한 쿠팡 링크를 건너뜁니다.
- 중지 반응 개선: 쿠팡 분석, Gemini 재시도 대기, 1688 이미지 검색 중에도 중지 요청을 더 빠르게 반영합니다.
- 링크 분석 안정화: 일부 쿠팡 단축 링크가 상품 페이지까지 풀리지 않던 리다이렉트 케이스를 보완했습니다.
- 작업량 동기화 개선: 서버 응답 형식 차이로 성공 업로드가 실패 처리될 수 있는 부분을 수정했습니다.
- 실행 배치 파일 수정: Windows `run.bat`이 실제 로그인 진입점으로 앱을 실행합니다.

### v3.0
- [x] 로그인/작업량 서버 연동
- [x] 암호화된 Threads 세션 저장
- [x] 쿠팡 링크 분석 및 1688 이미지 검색
- [x] 업로드 이력 기반 중복 방지

### v1.0
- [x] 기본 브라우저 자동화 업로드 ✅
- [x] Gemini 3 기반 글 변환 ✅
- [x] 이미지 미리보기 ✅

## 자동 업데이트 기능 🔄

### 특징
- ✅ **자동 확인**: 프로그램 시작 시 자동으로 새 버전 확인
- ✅ **원클릭 업데이트**: 버튼 클릭만으로 다운로드 및 설치
- ✅ **안전한 설치**: 기존 파일을 백업하고 문제 발생 시 자동 복구
- ✅ **GitHub Releases 연동**: 공식 릴리즈만 자동으로 설치

### 사용 방법
1. 프로그램 실행 시 새 버전이 있으면 자동으로 알림
2. 또는 상단의 **"업데이트"** 버튼 클릭
3. 다이얼로그에서 변경사항 확인
4. **"다운로드 및 설치"** 버튼 클릭
5. 자동으로 업데이트 설치 후 프로그램 재시작

## 개발자 가이드

### 빌드 방법

```bash
# 의존성 설치
pip install -r requirements.txt

# Playwright 브라우저 설치
playwright install chromium

# EXE 빌드
python build_exe.py

# 설치 파일 빌드 (Windows + Inno Setup 필요)
python build_installer.py
```

빌드된 파일은 `dist/CoupangThreadAuto.exe`, 설치 파일은 `dist/CoupangThreadAutoSetup.exe`에 생성됩니다.

### 릴리즈 배포

1. **변경사항 커밋**
   ```bash
   git add .
   git commit -m "Update app"
   git push origin master
   ```

2. **자동 버전/릴리즈**
   - `master`에 프로그램 변경사항이 푸시되면 GitHub Actions가 최신 태그 기준으로 다음 패치 버전을 계산합니다.
   - 수동 실행 시 `version`을 비워두면 자동 패치 버전, `bump`으로 minor/major를 선택할 수 있습니다.
   - 릴리즈에는 설치형 `CoupangThreadAutoSetup.exe`, 단독 실행형 `CoupangThreadAuto.exe`, SHA-256 체크섬, `latest.json`이 업로드됩니다.
   - 웹사이트 다운로드 버튼은 `releases/latest/download/CoupangThreadAutoSetup.exe`를 사용하므로 최신 릴리즈로 자동 연결됩니다.

### GitHub Actions 워크플로우

- `.github/workflows/build-release.yml`: master 푸시, 태그 푸시, 수동 실행 시 자동 버전 산출/빌드/릴리즈
- Windows 환경에서 PyInstaller EXE와 Inno Setup 설치 파일 빌드
- Authenticode 서명, SHA-256 체크섬 생성 후 GitHub Releases에 업로드

## 향후 계획

- [x] 자동 업데이트 기능 ✅
- [x] GitHub Releases 통합 ✅
- [ ] 실제 이미지 생성 API 통합 (DALL-E, Stable Diffusion 등)
- [ ] 예약 업로드 기능
- [x] 업로드 기록 저장 및 관리
- [ ] 다크 모드 지원
- [x] 여러 Threads 계정 관리
- [ ] Headless 모드 옵션 (브라우저 숨김)

## 추가 문서

- [docs/AFFILIATE_MARKETPLACES.md](docs/AFFILIATE_MARKETPLACES.md) - 제휴 프로그램, 링크 보존, 분석 범위 안내
- [TESTING.md](TESTING.md) - 테스트/배포 검증 체크리스트
- [AUTO_UPDATE_SETUP.md](AUTO_UPDATE_SETUP.md) - 자동 업데이트 설정
- [IMPLEMENTATION_NOTES.md](IMPLEMENTATION_NOTES.md) - 구현 메모
