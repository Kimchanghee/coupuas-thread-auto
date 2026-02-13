"""
쿠팡 파트너스 스레드 자동화 - 자동 업데이트 모듈
GitHub Releases를 사용한 자동 업데이트 기능
"""
import os
import sys
import requests
import tempfile
import subprocess
from typing import Optional, Dict
from packaging import version
import shutil


class AutoUpdater:
    """GitHub Releases를 사용한 자동 업데이트 관리자"""

    # GitHub 저장소 정보
    GITHUB_OWNER = "Kimchanghee"
    GITHUB_REPO = "coupuas-thread-auto"  # 저장소명으로 변경

    # API 엔드포인트
    API_BASE = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}"
    RELEASES_URL = f"{API_BASE}/releases/latest"

    def __init__(self, current_version: str):
        """
        Args:
            current_version: 현재 애플리케이션 버전 (예: "v2.2.0")
        """
        self.current_version = current_version.lstrip('v')  # v 접두사 제거
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': f'CoupangThreadAuto/{self.current_version}',
            'Accept': 'application/vnd.github.v3+json'
        })

    def check_for_updates(self) -> Optional[Dict]:
        """
        새 버전이 있는지 확인

        Returns:
            새 버전 정보 딕셔너리 또는 None (업데이트 없음)
            {
                'version': '2.3.0',
                'download_url': 'https://...',
                'changelog': '변경사항...',
                'published_at': '2025-02-12T...',
                'size_mb': 50.5
            }
        """
        try:
            response = self.session.get(self.RELEASES_URL, timeout=10)
            response.raise_for_status()

            release_data = response.json()

            # 최신 버전 정보
            latest_version = release_data.get('tag_name', '').lstrip('v')

            # 버전 비교
            if version.parse(latest_version) > version.parse(self.current_version):
                # Windows용 .exe 파일 찾기
                assets = release_data.get('assets', [])
                exe_asset = None

                for asset in assets:
                    if asset['name'].endswith('.exe'):
                        exe_asset = asset
                        break

                if not exe_asset:
                    return None

                return {
                    'version': latest_version,
                    'download_url': exe_asset['browser_download_url'],
                    'changelog': release_data.get('body', ''),
                    'published_at': release_data.get('published_at', ''),
                    'size_mb': exe_asset['size'] / (1024 * 1024),
                    'asset_name': exe_asset['name']
                }

            return None

        except Exception as e:
            print(f"업데이트 확인 중 오류: {e}")
            return None

    def download_update(self, update_info: Dict, progress_callback=None) -> Optional[str]:
        """
        업데이트 파일 다운로드

        Args:
            update_info: check_for_updates()에서 반환된 정보
            progress_callback: 진행률 콜백 함수 (percent: float)

        Returns:
            다운로드된 파일 경로 또는 None (실패)
        """
        try:
            download_url = update_info['download_url']

            # 임시 디렉토리에 다운로드
            temp_dir = tempfile.gettempdir()
            temp_file = os.path.join(temp_dir, update_info['asset_name'])

            # 기존 파일 삭제
            if os.path.exists(temp_file):
                os.remove(temp_file)

            # 다운로드
            response = self.session.get(download_url, stream=True, timeout=60)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0

            with open(temp_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

                        if progress_callback and total_size > 0:
                            percent = (downloaded / total_size) * 100
                            progress_callback(percent)

            return temp_file

        except Exception as e:
            print(f"다운로드 중 오류: {e}")
            return None

    def install_update(self, update_file: str) -> bool:
        """
        업데이트 설치 (현재 실행 파일을 새 버전으로 교체)

        Args:
            update_file: 다운로드된 업데이트 파일 경로

        Returns:
            성공 여부
        """
        try:
            current_exe = sys.executable

            # .exe로 실행 중인지 확인 (PyInstaller로 빌드된 경우)
            if not getattr(sys, 'frozen', False):
                print("개발 모드에서는 자동 업데이트를 지원하지 않습니다.")
                return False

            # 백업 파일 경로
            backup_exe = current_exe + '.backup'

            # 기존 백업 삭제
            if os.path.exists(backup_exe):
                try:
                    os.remove(backup_exe)
                except:
                    pass

            # 현재 실행 파일을 백업
            shutil.copy2(current_exe, backup_exe)

            # 업데이트 스크립트 생성 (배치 파일)
            update_script = self._create_update_script(
                current_exe,
                update_file,
                backup_exe
            )

            # 업데이트 스크립트 실행 후 현재 프로세스 종료
            subprocess.Popen([update_script], shell=True)

            # 성공 (스크립트가 실행되면 애플리케이션 종료)
            return True

        except Exception as e:
            print(f"업데이트 설치 중 오류: {e}")
            return False

    def _create_update_script(self, current_exe: str, update_file: str, backup_exe: str) -> str:
        """
        업데이트를 수행할 배치 스크립트 생성

        Returns:
            생성된 스크립트 파일 경로
        """
        script_path = os.path.join(tempfile.gettempdir(), 'update_coupang_thread.bat')

        script_content = f'''@echo off
echo 쿠팡 파트너스 스레드 자동화 - 업데이트 설치 중...
echo.

REM 프로세스 종료 대기 (5초)
timeout /t 5 /nobreak >nul

REM 현재 실행 파일 삭제 시도 (최대 10회)
set retry=0
:delete_loop
del /f "{current_exe}" 2>nul
if exist "{current_exe}" (
    set /a retry+=1
    if %retry% lss 10 (
        timeout /t 1 /nobreak >nul
        goto delete_loop
    ) else (
        echo 기존 파일 삭제 실패. 백업에서 복원합니다.
        copy /y "{backup_exe}" "{current_exe}"
        goto cleanup
    )
)

REM 새 버전 복사
copy /y "{update_file}" "{current_exe}"
if errorlevel 1 (
    echo 업데이트 실패. 백업에서 복원합니다.
    copy /y "{backup_exe}" "{current_exe}"
    goto cleanup
)

echo 업데이트가 완료되었습니다!
echo 프로그램을 다시 시작합니다...

REM 백업 파일 삭제
del /f "{backup_exe}" 2>nul

REM 다운로드 파일 삭제
del /f "{update_file}" 2>nul

REM 프로그램 재시작
start "" "{current_exe}"
goto end

:cleanup
REM 임시 파일 정리
del /f "{update_file}" 2>nul
echo.
echo 업데이트에 실패했습니다. 이전 버전으로 복구되었습니다.
pause

:end
REM 스크립트 자체 삭제
del /f "%~f0"
'''

        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(script_content)

        return script_path

    @staticmethod
    def get_changelog_summary(changelog: str, max_lines: int = 10) -> str:
        """
        변경사항 요약 (처음 N줄만)

        Args:
            changelog: 전체 변경사항
            max_lines: 최대 라인 수

        Returns:
            요약된 변경사항
        """
        lines = changelog.split('\n')
        if len(lines) <= max_lines:
            return changelog

        summary_lines = lines[:max_lines]
        summary_lines.append(f"\n... (나머지 {len(lines) - max_lines}줄 생략)")
        return '\n'.join(summary_lines)


# 사용 예제
if __name__ == "__main__":
    # 테스트용 코드
    from main import VERSION

    updater = AutoUpdater(VERSION)

    print(f"현재 버전: {VERSION}")
    print("업데이트 확인 중...")

    update_info = updater.check_for_updates()

    if update_info:
        print(f"\n새 버전 발견: v{update_info['version']}")
        print(f"크기: {update_info['size_mb']:.1f} MB")
        print(f"\n변경사항:")
        print(AutoUpdater.get_changelog_summary(update_info['changelog']))

        response = input("\n다운로드하시겠습니까? (y/n): ")

        if response.lower() == 'y':
            print("\n다운로드 중...")

            def progress(percent):
                print(f"\r진행률: {percent:.1f}%", end='')

            file_path = updater.download_update(update_info, progress)

            if file_path:
                print(f"\n\n다운로드 완료: {file_path}")
                print("\n업데이트를 설치하려면 애플리케이션을 재시작하세요.")
            else:
                print("\n다운로드 실패")
    else:
        print("\n최신 버전을 사용 중입니다.")
