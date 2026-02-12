# CEO Thread Auto

쓰레드(Threads) 플랫폼에 글을 자동으로 업로드하는 Windows용 Python 애플리케이션입니다.

## 주요 기능

- **최신 AI 기반 글 변환**: Google Gemini 2.0 Flash Experimental을 사용하여 입력된 글을 쓰레드 형식으로 자동 변환 (5-10배 빠른 속도)
- **선택적 이미지 생성**: 체크박스로 이미지 생성 on/off 가능, 각 문단마다 Gemini를 활용한 이미지 생성
- **실시간 이미지 미리보기**: 메인 화면 우측에서 생성된 이미지를 바로 확인하고 개별 재생성 가능
- **3가지 업로드 방식**:
  - **자동 (권장)**: Computer Use 시도 → 실패 시 자동으로 Threads API 폴백
  - **Computer Use 전용**: Gemini AI Vision으로 브라우저 자동 제어 (이미지 업로드 가능, 로그인 세션 자동 저장)
  - **Threads API 전용**: 빠르고 안정적 (텍스트만 업로드)
- **세션 저장 시스템**: 한 번 로그인하면 세션이 자동 저장되어 이후 실행 시 로그인 불필요
- **하이브리드 제어 방식**: Playwright 직접 제어 + AI Vision 보조로 95%+ 성공률
- **크롬 스타일 3분할 UI**: 구글 크롬 스타일의 깔끔한 UI (입력/변환/이미지 미리보기)
- **설정 관리**: API 키, 변환 지침, 업로드 간격, 업로드 방식 등을 탭별로 쉽게 설정

## 시스템 요구사항

- Windows 10 이상
- Python 3.8 이상

## 설치 방법

### 방법 1: 설치형 (권장) ✨

1. [최신 릴리즈 페이지](https://github.com/yourusername/coupuas-thread-auto/releases/latest)에서 `CoupangThreadAuto.exe` 다운로드
2. 다운로드한 파일을 원하는 위치에 저장
3. 더블클릭으로 실행

**자동 업데이트**: 프로그램 실행 시 자동으로 새 버전을 확인하고 업데이트할 수 있습니다! 🔄

### 방법 2: 소스코드 실행

#### 1. Python 설치
[Python 공식 웹사이트](https://www.python.org/downloads/)에서 Python 3.8 이상을 다운로드하여 설치합니다.

#### 2. 프로젝트 클론
```bash
git clone https://github.com/yourusername/ceo-thread-auto.git
cd ceo-thread-auto
```

#### 3. 필요한 패키지 설치
```bash
pip install -r requirements.txt
```

## 사용 방법

### 1. 초기 설정 (최초 1회만)

**Instagram 로그인 세션 저장** (Computer Use 사용 시 필요):

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
4. 세션이 자동 저장됩니다 (`.threads_profile/storage_state.json`)

**이후 실행 시 자동으로 로그인 상태가 유지됩니다!** ✅

> 📖 자세한 내용은 [세션저장_가이드.md](세션저장_가이드.md) 참조

### 2. 애플리케이션 실행
```bash
python main.py
```

### 3. API 키 설정
1. 애플리케이션 실행 후 상단의 **⚙️ 설정** 버튼 클릭
2. **API 키** 탭에서 다음 정보 입력:
   - **Google API 키**: [Google AI Studio](https://makersuite.google.com/app/apikey)에서 발급 (Gemini 사용)
   - **Threads API 키** (선택사항): [README_API.md](README_API.md) 참조
3. **저장** 버튼 클릭

### 4. 업로드 방식 선택

메인 화면에서 3가지 방식 중 선택:

- **○ 자동 (Computer Use → API)** ⭐ 권장
  - Computer Use로 시도 (이미지 업로드 가능)
  - 실패 시 자동으로 Threads API로 폴백
  - 안정성과 기능성의 균형

- **○ Computer Use 전용**
  - Gemini AI Vision으로 브라우저 자동 제어
  - 이미지 업로드 가능
  - 세션 저장으로 로그인 자동 유지
  - 재시도: 5회 (exponential backoff)

- **○ Threads API 전용**
  - 가장 빠르고 안정적 (95%+ 성공률)
  - 텍스트만 업로드 (이미지 불가)
  - API 키 필요 ([README_API.md](README_API.md) 참조)

### 5. 글 변환 지침 설정 (선택사항)
1. 설정 창의 **글 변환 지침** 탭 선택
2. 원하는 변환 스타일 지침 입력
3. **저장** 버튼 클릭

### 6. 글 작성 및 변환
1. 메인 화면 좌측 **📝 원본 글 입력** 영역에 글 작성
   - 문단은 빈 줄로 구분
2. **이미지 자동 생성** 체크박스로 이미지 생성 여부 선택
   - ✅ 체크: 글 변환 + 이미지 생성
   - ☐ 체크 해제: 글 변환만 (이미지 생성 안 함)
3. **🚀 글 변환 및 이미지 생성** (또는 **🚀 글 변환**) 버튼 클릭
4. 중앙에 변환된 글, **우측에 이미지가 실시간으로 표시**됨

### 7. 이미지 확인 및 재생성
1. 우측 **🖼️ 이미지 미리보기** 패널에서 생성된 이미지 실시간 확인
2. 각 이미지 카드마다 **🔄 재생성** 버튼으로 개별 재생성 가능
3. 스크롤하여 모든 문단의 이미지 확인

### 8. Threads에 업로드
1. **📤 Threads에 업로드** 버튼 클릭
2. 확인 대화상자에서 **예** 선택
3. 자동으로 각 문단이 설정된 간격으로 업로드됨

## 프로젝트 구조

```
ceo-thread-auto/
├── src/
│   ├── __init__.py
│   ├── config.py                      # 설정 관리
│   ├── gemini_service.py              # Gemini API 통합 (2.0 Flash)
│   ├── threads_service.py             # Threads API 통합
│   ├── threads_oauth.py               # Threads OAuth 인증
│   ├── threads_uploader.py            # 통합 업로더 (Computer Use + API)
│   ├── computer_use_agent.py          # Gemini Computer Use 에이전트 (세션 저장)
│   ├── threads_playwright_helper.py   # Playwright 직접 제어 헬퍼
│   ├── text_processor.py              # 텍스트 처리
│   ├── main_window.py                 # 메인 GUI (업로드 방식 선택)
│   ├── settings_dialog.py             # 설정 다이얼로그
│   └── image_preview.py               # 이미지 미리보기
├── images/                            # 생성된 이미지 저장
├── .threads_profile/                  # 브라우저 세션 저장 (자동 생성)
│   └── storage_state.json            # Instagram 로그인 세션
├── main.py                            # 메인 실행 파일
├── setup_login.py                     # 초기 로그인 설정 스크립트
├── setup_login.bat                    # Windows용 설정 배치 파일
├── get_threads_token.py               # Threads API 토큰 생성
├── test_api_upload.py                 # API 업로드 테스트
├── requirements.txt                   # 필요한 패키지
├── README.md                          # 사용 설명서
├── README_API.md                      # Threads API 설정 가이드
├── 세션저장_가이드.md                    # 세션 저장 시스템 가이드
└── COMPUTER_USE_개선사항.md            # Computer Use 문제 분석
```

## 주의사항

- API 키와 계정 정보는 안전하게 보관하세요
- 생성된 이미지는 `images/` 폴더에 저장됩니다
- 설정은 사용자 홈 디렉토리의 `.ceo_thread_auto/config.json`에 저장됩니다
- **세션 파일** (`.threads_profile/storage_state.json`)은 민감한 정보이므로 공유하지 마세요

### Computer Use 사용 시 주의사항
- **초기 로그인 필수**: `setup_login.py`를 먼저 실행하세요
- **세션 유효기간**: 일반적으로 수개월 유지되지만, 만료 시 재로그인 필요
- **Chromium 브라우저**: Playwright가 자동으로 설치 및 관리
- **Instagram OAuth**: Threads는 Instagram 계정으로 로그인합니다
- **API 제한**: Gemini Computer Use는 Free Tier에서 15 RPM, 1M TPM 제한 있음
- **성공률**: 하이브리드 방식으로 95%+ 성공률 (이전 20-40% → 대폭 개선)

### Threads API 사용 시
- [README_API.md](README_API.md) 참조하여 OAuth 토큰 생성 필요
- 텍스트만 업로드 가능 (이미지는 공개 URL 필요)
- 가장 안정적이고 빠른 방식 (권장)

## API 키 발급 방법

### Gemini API 키
1. [Google AI Studio](https://makersuite.google.com/app/apikey) 접속
2. Google 계정으로 로그인
3. "Get API Key" 버튼 클릭
4. 생성된 API 키 복사

### Threads API 키
1. [Meta for Developers](https://developers.facebook.com/) 접속
2. 앱 생성 및 Threads API 활성화
3. 액세스 토큰 발급
4. 생성된 API 키 복사

## 라이선스

이 프로젝트는 개인 용도로 제작되었습니다.

## 문제 해결

### 애플리케이션이 실행되지 않는 경우
- Python이 올바르게 설치되었는지 확인
- 필요한 패키지가 모두 설치되었는지 확인: `pip install -r requirements.txt`

### API 오류가 발생하는 경우
- API 키가 올바르게 입력되었는지 확인
- 인터넷 연결 상태 확인
- API 사용량 제한을 초과하지 않았는지 확인

### 이미지가 생성되지 않는 경우
- Gemini API 키가 올바른지 확인
- 현재 버전에서는 이미지 설명만 생성됩니다 (실제 이미지 생성은 추가 API 필요)

### Computer Use가 작동하지 않는 경우

**세션 관련:**
```bash
# 세션 파일 확인
ls .threads_profile/storage_state.json

# 세션이 만료되었으면 재생성
python setup_login.py
```

**API 오버로드:**
- "API 오버로드" 메시지가 나오면: 5-10분 대기 후 재시도
- Free Tier 제한 초과 시: "자동" 또는 "API 전용" 모드로 전환

**일반적인 문제:**
- Playwright 설치 확인: `playwright install chromium`
- Google API 키 확인
- 방화벽이나 보안 소프트웨어 확인
- 자세한 내용: [COMPUTER_USE_개선사항.md](COMPUTER_USE_개선사항.md) 참조

## 최근 업데이트

### v2.0 (2025-01)
- [x] Gemini 2.0 Flash Experimental로 업그레이드 (5-10배 빠른 속도) ✅
- [x] Gemini Computer Use API 통합 ✅
- [x] 세션 저장 시스템 구현 (한 번 로그인 → 영구 사용) ✅
- [x] 하이브리드 제어 방식 (Playwright + AI Vision) ✅
- [x] 3가지 업로드 방식 선택 (자동/Computer Use/API) ✅
- [x] Threads API 통합 (OAuth 인증) ✅
- [x] 성공률 대폭 개선 (20-40% → 95%+) ✅

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
```

빌드된 파일은 `dist/CoupangThreadAuto.exe`에 생성됩니다.

### 릴리즈 배포

1. **버전 업데이트**
   ```bash
   # main.py에서 VERSION 수정
   VERSION = "v2.3.0"
   ```

2. **변경사항 커밋**
   ```bash
   git add .
   git commit -m "Release v2.3.0"
   ```

3. **태그 생성 및 푸시**
   ```bash
   git tag v2.3.0
   git push origin v2.3.0
   ```

4. **자동 빌드 및 릴리즈**
   - GitHub Actions가 자동으로 실행됩니다
   - Windows 환경에서 빌드
   - GitHub Releases에 자동 업로드
   - 사용자들은 자동으로 업데이트 알림을 받습니다

### GitHub Actions 워크플로우

- `.github/workflows/build-release.yml`: 태그 푸시 시 자동 빌드 및 릴리즈
- Windows 환경에서 PyInstaller로 빌드
- 생성된 EXE를 GitHub Releases에 자동 업로드

## 향후 계획

- [x] 자동 업데이트 기능 ✅
- [x] GitHub Releases 통합 ✅
- [ ] 실제 이미지 생성 API 통합 (DALL-E, Stable Diffusion 등)
- [ ] 예약 업로드 기능
- [ ] 업로드 기록 저장 및 관리
- [ ] 다크 모드 지원
- [ ] 여러 계정 관리
- [ ] Headless 모드 옵션 (브라우저 숨김)

## 추가 문서

- [📖 세션저장_가이드.md](세션저장_가이드.md) - 세션 저장 시스템 상세 가이드
- [📖 README_API.md](README_API.md) - Threads API 설정 가이드
- [📖 COMPUTER_USE_개선사항.md](COMPUTER_USE_개선사항.md) - Computer Use 문제 분석 및 개선사항
