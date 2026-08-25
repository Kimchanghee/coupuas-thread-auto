@echo off
chcp 65001 >nul
cd /d "%~dp0"

where node >nul 2>nul
if errorlevel 1 (
  echo Node.js 22.13 이상을 먼저 설치해주세요.
  pause
  exit /b 1
)

if not exist "node_modules\.bin\next.cmd" (
  echo 잠긴 버전의 의존성을 설치하고 있습니다...
  call npm ci --no-audit --no-fund
  if errorlevel 1 (
    echo 설치에 실패했습니다. 인터넷 연결과 Node.js 버전을 확인해주세요.
    pause
    exit /b 1
  )
)

echo Next.js 운영 빌드를 만들고 있습니다...
call npm run build
if errorlevel 1 (
  echo 설문 화면 생성에 실패했습니다.
  pause
  exit /b 1
)

if not exist ".next\BUILD_ID" (
  echo Next.js 빌드 결과를 찾지 못했습니다.
  pause
  exit /b 1
)

start "THREAD AUTO 설문 서버" /min cmd /c "npm run start"
timeout /t 3 /nobreak >nul
start "" "http://localhost:4173"
echo 설문 웹을 열었습니다. 서버를 멈추려면 작업 관리자에서 Node.js 프로세스를 종료해주세요.
timeout /t 2 /nobreak >nul
