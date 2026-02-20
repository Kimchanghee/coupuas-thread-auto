@echo off
setlocal

echo ====================================
echo CEO Thread Auto 실행
echo ====================================
echo.

REM Python 설치 여부 확인
python --version >nul 2>&1
if errorlevel 1 (
    echo [오류] Python이 설치되어 있지 않습니다.
    echo Python 3.9 이상을 설치해 주세요: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Python 확인 완료
echo.

REM 보안상 자동 패키지 설치 금지
pip show google-generativeai >nul 2>&1
if errorlevel 1 (
    echo [오류] 필수 패키지가 설치되어 있지 않습니다.
    echo 보안상의 이유로 run.bat에서 자동 설치를 수행하지 않습니다.
    echo 아래 명령으로 수동 설치 후 다시 실행해 주세요:
    echo     pip install -r requirements.txt
    pause
    exit /b 1
)

echo 애플리케이션을 실행합니다...
echo.
python main.py

if errorlevel 1 (
    echo.
    echo [오류] 애플리케이션 실행 중 오류가 발생했습니다.
    pause
    exit /b 1
)

pause
