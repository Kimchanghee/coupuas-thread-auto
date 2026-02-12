# 자동 업데이트 설정 가이드

이 프로젝트는 GitHub Releases를 통한 자동 업데이트 기능을 지원합니다.

## 초기 설정 (필수)

### 1. GitHub 저장소 정보 설정

`src/auto_updater.py` 파일을 열고 다음 부분을 수정하세요:

```python
# GitHub 저장소 정보 (실제 저장소로 변경 필요)
GITHUB_OWNER = "yourusername"  # ← 여기를 GitHub 사용자명으로 변경
GITHUB_REPO = "coupuas-thread-auto"  # ← 여기를 저장소명으로 변경
```

**예시:**
```python
GITHUB_OWNER = "mycompany"
GITHUB_REPO = "coupang-partners-auto"
```

### 2. README.md의 릴리즈 링크 수정

`README.md` 파일에서 다음 부분을 찾아 수정하세요:

```markdown
1. [최신 릴리즈 페이지](https://github.com/yourusername/coupuas-thread-auto/releases/latest)
```

실제 저장소 경로로 변경:
```markdown
1. [최신 릴리즈 페이지](https://github.com/mycompany/coupang-partners-auto/releases/latest)
```

## 릴리즈 프로세스

### 1. 버전 번호 결정

[시맨틱 버저닝](https://semver.org/lang/ko/) 규칙을 따릅니다:
- **메이저 (v2.0.0 → v3.0.0)**: 하위 호환성이 깨지는 변경
- **마이너 (v2.1.0 → v2.2.0)**: 하위 호환성을 유지하는 새 기능
- **패치 (v2.1.1 → v2.1.2)**: 버그 수정

### 2. 버전 업데이트

`main.py` 파일을 열고 VERSION 상수를 수정:

```python
VERSION = "v2.3.0"  # ← 새 버전으로 변경
```

### 3. 변경사항 커밋

```bash
git add .
git commit -m "Release v2.3.0: 새로운 기능 및 버그 수정"
```

### 4. 태그 생성 및 푸시

```bash
# 로컬 태그 생성
git tag v2.3.0

# 태그를 원격 저장소에 푸시
git push origin v2.3.0
```

**중요**: 태그는 `v`로 시작해야 합니다 (예: `v2.3.0`)

### 5. 자동 빌드 확인

1. GitHub 저장소의 **Actions** 탭으로 이동
2. "Build and Release" 워크플로우가 실행되는지 확인
3. 빌드가 완료되면 **Releases** 탭에서 확인

### 6. 릴리즈 노트 작성

릴리즈가 생성되면:

1. GitHub 저장소의 **Releases** 탭으로 이동
2. 새로 생성된 릴리즈를 클릭
3. **Edit release** 버튼 클릭
4. 변경사항 섹션에 실제 내용 작성:

```markdown
### 새로운 기능
- ✨ 기능 1 추가
- ✨ 기능 2 추가

### 버그 수정
- 🐛 버그 1 수정
- 🐛 버그 2 수정

### 개선사항
- 🚀 성능 개선
- 🎨 UI 개선
```

5. **Update release** 버튼 클릭

## 자동 업데이트 테스트

### 로컬 테스트

1. **이전 버전 빌드**
   ```bash
   # main.py에서 VERSION = "v2.2.0"으로 설정
   python build_exe.py
   ```

2. **새 버전으로 릴리즈**
   ```bash
   # main.py에서 VERSION = "v2.3.0"으로 변경
   git tag v2.3.0
   git push origin v2.3.0
   ```

3. **이전 버전 실행**
   - `dist/CoupangThreadAuto.exe` 실행
   - 업데이트 알림이 나타나는지 확인
   - 업데이트 다운로드 및 설치 테스트

### 수동 업데이트 체크 테스트

1. 프로그램 실행
2. 상단의 **"업데이트"** 버튼 클릭
3. 업데이트 다이얼로그 확인

## 문제 해결

### 업데이트 확인 실패

**원인**: GitHub API 접근 실패 또는 잘못된 저장소 정보

**해결**:
1. `src/auto_updater.py`의 `GITHUB_OWNER`와 `GITHUB_REPO` 확인
2. 인터넷 연결 확인
3. GitHub 저장소가 public인지 확인

### 빌드 실패

**원인**: GitHub Actions 환경 문제

**해결**:
1. GitHub Actions 로그 확인
2. `requirements.txt`의 의존성 버전 확인
3. PyInstaller 버전 확인

### 설치 실패

**원인**: 권한 문제 또는 백업 파일 충돌

**해결**:
1. 관리자 권한으로 실행
2. `.backup` 파일 수동 삭제
3. 프로그램을 완전히 종료한 후 재시도

## 고급 설정

### Private 저장소 사용

private 저장소를 사용하는 경우:

1. GitHub Personal Access Token (PAT) 생성
2. `src/auto_updater.py`의 `__init__` 메서드 수정:

```python
def __init__(self, current_version: str):
    self.current_version = current_version.lstrip('v')
    self.session = requests.Session()
    self.session.headers.update({
        'User-Agent': f'CoupangThreadAuto/{self.current_version}',
        'Accept': 'application/vnd.github.v3+json',
        'Authorization': f'token YOUR_GITHUB_TOKEN'  # ← 토큰 추가
    })
```

**주의**: 토큰을 코드에 직접 넣지 말고 환경 변수를 사용하세요!

### 업데이트 알림 비활성화

자동 업데이트 알림을 비활성화하려면:

`src/main_window.py`에서 다음 줄을 주석 처리:

```python
# 자동 업데이트 체크 (시작 후 3초 뒤)
# QTimer.singleShot(3000, self._check_for_updates_silent)
```

## 체크리스트

릴리즈 전 확인사항:

- [ ] `src/auto_updater.py`에서 GitHub 저장소 정보 수정
- [ ] `README.md`에서 릴리즈 링크 수정
- [ ] `main.py`에서 VERSION 업데이트
- [ ] 변경사항 커밋
- [ ] 태그 생성 및 푸시
- [ ] GitHub Actions 빌드 성공 확인
- [ ] 릴리즈 노트 작성
- [ ] 로컬 테스트 완료

---

**문의**: 문제가 발생하면 GitHub Issues에 등록해주세요.
