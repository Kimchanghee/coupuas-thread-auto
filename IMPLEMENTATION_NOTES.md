# 자동 업데이트 시스템 구현 노트

## 구현 개요

쿠팡 파트너스 스레드 자동화 프로그램에 GitHub Releases 기반 자동 업데이트 시스템을 구현했습니다.

## 핵심 구성 요소

### 1. 자동 업데이트 모듈 (`src/auto_updater.py`)

**기능**:
- GitHub Releases API를 통한 최신 버전 확인
- 시맨틱 버저닝 기반 버전 비교
- HTTP 스트리밍을 통한 파일 다운로드
- 진행률 콜백 지원
- 안전한 설치 메커니즘 (백업 및 복구)

**주요 메서드**:
- `check_for_updates()`: 새 버전 확인
- `download_update()`: 업데이트 파일 다운로드
- `install_update()`: 배치 스크립트를 통한 설치

**설치 메커니즘**:
```
1. 현재 실행 파일 백업 (.backup 확장자)
2. 배치 스크립트 생성
3. 배치 스크립트 실행 (프로그램 종료 대기)
4. 기존 파일 삭제 시도 (최대 10회 재시도)
5. 새 파일 복사
6. 실패 시 백업에서 복구
7. 프로그램 재시작
8. 배치 스크립트 자체 삭제
```

### 2. 업데이트 다이얼로그 (`src/update_dialog.py`)

**기능**:
- Stitch Blue 테마 적용
- 백그라운드 업데이트 체크 (QThread)
- 백그라운드 다운로드 (QThread)
- 진행률 표시
- 변경사항 미리보기

**UI 컴포넌트**:
- 현재/최신 버전 표시
- 변경사항 텍스트 영역
- 진행률 바
- 다운로드 및 설치 버튼

### 3. 메인 윈도우 통합 (`src/main_window.py`)

**추가 사항**:
- 헤더에 "업데이트" 버튼 추가
- 시작 시 자동 업데이트 체크 (3초 후)
- 수동 업데이트 체크 메서드
- 자동 업데이트 알림 (선택적)

### 4. GitHub Actions 워크플로우 (`.github/workflows/build-release.yml`)

**트리거**:
- 태그 푸시 (`v*.*.*` 패턴)
- 수동 실행 (workflow_dispatch)

**단계**:
1. Python 3.11 환경 설정
2. 의존성 설치
3. Playwright 브라우저 설치
4. 버전 정보 추출
5. `main.py`의 VERSION 자동 업데이트
6. PyInstaller로 빌드
7. 빌드 검증
8. GitHub Release 자동 생성
9. EXE 파일 업로드
10. Artifacts 보관 (30일)

### 5. 빌드 스크립트 개선 (`build_exe.py`)

**추가 내용**:
- 자동 업데이트 관련 모듈 포함
- `packaging` 라이브러리 포함
- 버전 정보 출력
- 릴리즈 가이드 표시

## 기술적 결정 사항

### 1. 배치 스크립트 사용 이유

**문제**: Python 프로세스가 실행 중인 EXE 파일을 직접 교체할 수 없음

**해결**: 배치 스크립트를 생성하여 다음 작업 수행:
- 프로그램 종료 대기
- 파일 교체
- 프로그램 재시작
- 자체 삭제

**장점**:
- Windows 네이티브 방식
- 추가 의존성 불필요
- 안정적인 파일 교체

### 2. QThread 사용

**이유**: PyQt6에서 네트워크 작업이나 긴 작업을 메인 스레드에서 실행하면 UI가 멈춤

**구현**:
- `UpdateCheckThread`: 백그라운드 업데이트 확인
- `UpdateDownloadThread`: 백그라운드 다운로드

**신호**:
- `update_found`: 업데이트 정보 전달
- `no_update`: 최신 버전 사용 중
- `error`: 에러 발생
- `progress`: 다운로드 진행률
- `finished`: 다운로드 완료

### 3. 시맨틱 버저닝 (Semantic Versioning)

**형식**: `vMAJOR.MINOR.PATCH` (예: v2.3.0)

**비교 로직**: `packaging.version.parse()` 사용
- `v2.2.0` < `v2.3.0`
- `v2.3.0` < `v3.0.0`

### 4. 안전한 설치

**백업 메커니즘**:
1. 기존 파일을 `.backup` 확장자로 복사
2. 새 파일 설치 시도
3. 실패 시 백업에서 자동 복구

**재시도 로직**:
- 파일 삭제 최대 10회 재시도 (1초 간격)
- 다른 프로세스가 파일을 사용 중일 수 있음

## 보안 고려사항

### 1. HTTPS 전용

- GitHub API는 HTTPS 강제
- 다운로드 URL도 HTTPS
- 중간자 공격(MITM) 방지

### 2. GitHub 인증

현재: 공개 저장소, 인증 불필요

Private 저장소 사용 시:
```python
self.session.headers.update({
    'Authorization': f'token {GITHUB_TOKEN}'
})
```

**중요**: 토큰을 하드코딩하지 말고 환경 변수 사용!

### 3. 파일 검증

**현재 미구현, 향후 추가 권장**:
- SHA256 체크섬 검증
- GPG 서명 검증

```python
# 예시 코드
import hashlib

def verify_checksum(file_path, expected_hash):
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest() == expected_hash
```

## 성능 최적화

### 1. 스트리밍 다운로드

```python
for chunk in response.iter_content(chunk_size=8192):
    if chunk:
        f.write(chunk)
```

**장점**:
- 메모리 사용량 최소화
- 대용량 파일도 안정적으로 다운로드
- 실시간 진행률 업데이트

### 2. 비동기 체크

- 시작 후 3초 뒤 자동 체크 (UI 블로킹 방지)
- QThread 사용으로 UI 응답성 유지

## 제한사항 및 향후 개선

### 현재 제한사항

1. **Windows 전용**
   - 배치 스크립트는 Windows 전용
   - macOS/Linux 지원 필요 시 쉘 스크립트 추가 필요

2. **단일 플랫폼**
   - 현재 EXE 파일만 지원
   - 크로스 플랫폼 빌드 미지원

3. **델타 업데이트 미지원**
   - 전체 파일 다운로드
   - 50MB+ 파일의 경우 시간 소요

4. **롤백 기능 제한**
   - 이전 버전으로 되돌리기 어려움
   - 백업은 1개만 유지

### 향후 개선 사항

1. **델타 업데이트**
   ```python
   # bsdiff 라이브러리 사용
   import bsdiff4
   patch = bsdiff4.diff(old_file, new_file)
   ```

2. **파일 검증**
   - SHA256 체크섬
   - GPG 서명 검증

3. **롤백 기능**
   - 여러 버전 백업 유지
   - 버전 히스토리 관리

4. **통계 및 분석**
   - 업데이트 성공률 추적
   - 에러 리포팅

5. **크로스 플랫폼 지원**
   - macOS: DMG 파일
   - Linux: AppImage 또는 DEB/RPM

## 디버깅 팁

### 로그 추가

```python
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('updater.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('auto_updater')
logger.debug('Checking for updates...')
```

### 개발 모드 테스트

```python
# 개발 모드에서도 설치 가능하도록 (테스트용)
if not getattr(sys, 'frozen', False):
    print("개발 모드: 업데이트 시뮬레이션")
    # 테스트 로직
```

### GitHub API 디버깅

```python
response = self.session.get(self.RELEASES_URL)
print(f"Status: {response.status_code}")
print(f"Rate Limit: {response.headers.get('X-RateLimit-Remaining')}")
print(f"Response: {response.text[:500]}")
```

## 의존성

### 런타임 의존성
- `requests`: HTTP 클라이언트
- `packaging`: 버전 비교
- `PyQt6`: GUI 프레임워크

### 빌드 의존성
- `pyinstaller`: EXE 빌드
- `playwright`: 브라우저 자동화

### GitHub Actions 의존성
- `actions/checkout@v4`
- `actions/setup-python@v5`
- `softprops/action-gh-release@v1`

## 라이선스 고려사항

사용된 오픈소스 라이브러리:
- PyQt6: GPL v3 (주의!)
- requests: Apache 2.0
- packaging: Apache 2.0 / BSD

**주의**: PyQt6는 GPL 라이선스이므로 상업용 사용 시 별도 라이선스 구매 필요

## 참고 자료

- [GitHub Releases API](https://docs.github.com/en/rest/releases/releases)
- [PyInstaller Documentation](https://pyinstaller.org/)
- [Semantic Versioning](https://semver.org/)
- [PyQt6 Documentation](https://www.riverbankcomputing.com/static/Docs/PyQt6/)

## 기여자 가이드

업데이트 시스템 개선 시:

1. 테스트 작성 (TESTING.md 참조)
2. 보안 검토
3. 크로스 플랫폼 호환성 확인
4. 문서 업데이트
5. 릴리즈 노트 작성

---

**버전**: 1.0.0
**최종 수정**: 2026-02-12
**작성자**: Claude (Sonnet 4.5)
