"""
Coupang Partners Thread Auto - EXE 빌드 스크립트
PyInstaller를 사용하여 exe 파일을 생성합니다.
"""
import os
import sys
import shutil
import subprocess

# 빌드 설정
APP_NAME = "CoupangThreadAuto"
MAIN_SCRIPT = "main.py"
ICON_PATH = None  # 아이콘 파일이 있으면 경로 지정 (예: "icon.ico")

# 숨겨진 임포트 (PyInstaller가 자동으로 찾지 못하는 모듈)
HIDDEN_IMPORTS = [
    # Google AI
    "google.generativeai",
    "google.ai.generativelanguage",
    "google.api_core",
    "google.auth",
    "google.protobuf",
    "grpc",

    # PyQt6
    "PyQt6",
    "PyQt6.QtWidgets",
    "PyQt6.QtCore",
    "PyQt6.QtGui",
    "PyQt6.sip",

    # Playwright
    "playwright",
    "playwright.sync_api",
    "playwright.async_api",
    "playwright._impl",

    # 이미지 처리
    "PIL",
    "PIL.Image",

    # 네트워크
    "requests",
    "urllib3",

    # 기타
    "json",
    "hashlib",
    "re",
    "asyncio",

    # 자동 업데이트
    "packaging",
    "packaging.version",
    "packaging.specifiers",

    # 프로젝트 모듈
    "src",
    "src.main_window",
    "src.config",
    "src.coupang_uploader",
    "src.settings_dialog",
    "src.threads_playwright_helper",
    "src.computer_use_agent",
    "src.auto_updater",
    "src.update_dialog",
    "src.login_window",
    "src.auth_client",
    "src.theme",
    "src.events",
    "src.tutorial",
    "src.services",
    "src.services.aggro_generator",
    "src.services.image_search",
    "src.services.link_history",
    "src.services.coupang_parser",
    "src.services.telegram_service",
]

# 포함할 데이터 파일 및 폴더
DATAS = [
    # (소스 경로, 대상 폴더)
    ("src", "src"),
    ("fonts", "fonts"),
]

# 제외할 모듈
EXCLUDES = [
    "matplotlib",
    "numpy",
    "pandas",
    "scipy",
    "tkinter",
    "test",
    "unittest",
]


def get_playwright_path():
    """Playwright 브라우저 경로 찾기"""
    try:
        import playwright
        playwright_path = os.path.dirname(playwright.__file__)
        driver_path = os.path.join(playwright_path, "driver")
        if os.path.exists(driver_path):
            return driver_path
    except:
        pass
    return None


def build_exe():
    """EXE 빌드 실행"""
    print("=" * 60)
    print("Coupang Partners Thread Auto - EXE 빌드")
    print("=" * 60)

    # 1. 이전 빌드 정리
    print("\n[1/5] 이전 빌드 파일 정리...")
    for folder in ["build", "dist"]:
        if os.path.exists(folder):
            shutil.rmtree(folder)
            print(f"  - {folder} 폴더 삭제됨")

    # 2. PyInstaller 명령 구성
    print("\n[2/5] PyInstaller 명령 구성...")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", APP_NAME,
        "--onefile",  # 단일 exe 파일
        "--windowed",  # 콘솔 창 숨김 (GUI 앱)
        "--clean",  # 캐시 정리
        "--noconfirm",  # 기존 파일 덮어쓰기
    ]

    # 아이콘
    if ICON_PATH and os.path.exists(ICON_PATH):
        cmd.extend(["--icon", ICON_PATH])

    # 숨겨진 임포트
    for hidden in HIDDEN_IMPORTS:
        cmd.extend(["--hidden-import", hidden])

    # 데이터 파일
    for src, dst in DATAS:
        if os.path.exists(src):
            cmd.extend(["--add-data", f"{src};{dst}"])

    # 제외 모듈
    for exclude in EXCLUDES:
        cmd.extend(["--exclude-module", exclude])

    # Playwright 드라이버 포함
    playwright_driver = get_playwright_path()
    if playwright_driver:
        cmd.extend(["--add-data", f"{playwright_driver};playwright/driver"])
        print(f"  - Playwright 드라이버 포함: {playwright_driver}")

    # 메인 스크립트
    cmd.append(MAIN_SCRIPT)

    # 3. 빌드 실행
    print("\n[3/5] PyInstaller 빌드 실행...")
    print(f"  명령: {' '.join(cmd[:10])}...")

    try:
        subprocess.run(cmd, check=True)
        print("  - 빌드 성공!")
    except subprocess.CalledProcessError as e:
        print(f"  - 빌드 실패: {e}")
        return False

    # 4. 추가 파일 복사
    print("\n[4/5] 추가 파일 복사...")
    dist_folder = os.path.join("dist")

    # media 폴더 생성
    media_folder = os.path.join(dist_folder, "media")
    os.makedirs(media_folder, exist_ok=True)
    os.makedirs(os.path.join(media_folder, "cache"), exist_ok=True)
    print(f"  - media/cache 폴더 생성됨")

    # user_data 폴더 생성
    user_data_folder = os.path.join(dist_folder, "user_data")
    os.makedirs(user_data_folder, exist_ok=True)
    print(f"  - user_data 폴더 생성됨")

    # 설정 파일 템플릿 (있으면 복사)
    if os.path.exists("settings.json"):
        shutil.copy("settings.json", dist_folder)
        print(f"  - settings.json 복사됨")

    # 5. 결과 확인 및 버전 정보 출력
    print("\n[5/5] 빌드 결과 확인...")
    exe_path = os.path.join(dist_folder, f"{APP_NAME}.exe")

    if os.path.exists(exe_path):
        size_mb = os.path.getsize(exe_path) / (1024 * 1024)

        # 버전 정보 읽기
        try:
            with open("main.py", "r", encoding="utf-8") as f:
                for line in f:
                    if "VERSION =" in line:
                        version = line.split("=")[1].strip().strip('"').strip("'")
                        print(f"  - 버전: {version}")
                        break
        except:
            pass

        print(f"  - EXE 파일: {exe_path}")
        print(f"  - 파일 크기: {size_mb:.1f} MB")
        print("\n" + "=" * 60)
        print("빌드 완료!")
        print(f"실행 파일: {os.path.abspath(exe_path)}")
        print("\n다음 단계:")
        print("1. 생성된 EXE 파일을 테스트하세요")
        print("2. Git 태그를 생성하여 릴리즈를 트리거하세요:")
        print(f"   git tag v2.x.x")
        print(f"   git push origin v2.x.x")
        print("=" * 60)
        return True
    else:
        print("  - EXE 파일을 찾을 수 없습니다.")
        return False


def install_playwright_browsers():
    """Playwright 브라우저 설치"""
    print("\n[사전 준비] Playwright 브라우저 설치...")
    try:
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
        print("  - Chromium 브라우저 설치 완료")
    except Exception as e:
        print(f"  - 브라우저 설치 실패: {e}")


if __name__ == "__main__":
    # Playwright 브라우저 설치 확인
    install_playwright_browsers()

    # 빌드 실행
    success = build_exe()

    if not success:
        print("\n빌드에 실패했습니다. 로그를 확인해주세요.")
        sys.exit(1)
