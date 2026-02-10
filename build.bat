@echo off
chcp 65001 >nul
echo ===================================================
echo CEO Thread Auto - 빌드 스크립트
echo ===================================================
echo.

:: 가상환경 확인
if not exist ".venv\Scripts\python.exe" (
    echo [오류] 가상환경이 없습니다. 먼저 가상환경을 생성하세요.
    echo python -m venv .venv
    pause
    exit /b 1
)

:: 가상환경의 Python 사용
set PYTHON=.venv\Scripts\python.exe

:: 1. 의존성 설치
echo [1/4] 의존성 설치 중...
%PYTHON% -m pip install --upgrade pip
%PYTHON% -m pip install -r requirements.txt
if errorlevel 1 (
    echo [오류] 의존성 설치 실패
    pause
    exit /b 1
)
echo [완료] 의존성 설치 완료
echo.

:: 2. Playwright 브라우저 설치 (필요한 경우)
echo [2/4] Playwright 브라우저 확인 중...
%PYTHON% -m playwright install chromium
echo [완료] Playwright 브라우저 준비 완료
echo.

:: 3. 이전 빌드 정리
echo [3/4] 이전 빌드 정리 중...
if exist "build" rmdir /s /q build
if exist "dist" rmdir /s /q dist
echo [완료] 정리 완료
echo.

:: 4. PyInstaller로 빌드
echo [4/4] PyInstaller 빌드 시작...
%PYTHON% -m PyInstaller ceo_thread_auto.spec --clean
if errorlevel 1 (
    echo [오류] 빌드 실패
    pause
    exit /b 1
)
echo.

echo ===================================================
echo 빌드 완료!
echo 실행 파일: dist\CEO_Thread_Auto.exe
echo ===================================================
echo.

:: dist 폴더 열기
if exist "dist\CEO_Thread_Auto.exe" (
    echo dist 폴더를 엽니다...
    explorer dist
)

pause
