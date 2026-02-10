@echo off
echo ====================================
echo CEO Thread Auto 실행
echo ====================================
echo.

REM Python이 설치되어 있는지 확인
python --version >nul 2>&1
if errorlevel 1 (
    echo [오류] Python이 설치되어 있지 않습니다.
    echo Python 3.8 이상을 설치해주세요: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Python이 확인되었습니다.
echo.

REM 필요한 패키지가 설치되어 있는지 확인
echo 필요한 패키지 확인 중...
pip show google-generativeai >nul 2>&1
if errorlevel 1 (
    echo.
    echo [알림] 필요한 패키지를 설치합니다...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [오류] 패키지 설치에 실패했습니다.
        pause
        exit /b 1
    )
)

echo.
echo 애플리케이션을 실행합니다...
echo.

REM 애플리케이션 실행
python main.py

if errorlevel 1 (
    echo.
    echo [오류] 애플리케이션 실행 중 오류가 발생했습니다.
    pause
    exit /b 1
)

pause
