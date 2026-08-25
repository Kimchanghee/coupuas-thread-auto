"""Interactive helper to bootstrap a Threads login session."""

import os
import sys
import time

from src.computer_use_agent import ComputerUseAgent
from src.threads_playwright_helper import ThreadsPlaywrightHelper


if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def main() -> None:
    print("=" * 60)
    print("Threads 최초 로그인 설정")
    print("=" * 60)
    print("암호화된 로컬 브라우저 세션을 저장하기 위해 한 번만 실행합니다.")
    print()

    google_api_key = os.environ.get("GOOGLE_API_KEY") or "dummy-key-for-session-setup"
    agent = ComputerUseAgent(
        api_key=google_api_key,
        headless=False,
        profile_dir=".threads_profile",
    )

    try:
        print("브라우저를 시작합니다...")
        agent.start_browser()

        print("Threads를 엽니다...")
        agent.page.goto("https://www.threads.net", wait_until="domcontentloaded")

        print()
        print("1. 브라우저 창에서 Instagram 계정으로 로그인하세요.")
        print("2. Threads 피드가 보이는지 확인하세요.")
        print("3. 이 창으로 돌아와 Enter 키를 누르세요.")
        input("로그인을 마쳤으면 Enter 키를 누르세요...")

        print("로그인 상태를 확인합니다...")
        time.sleep(2)
        current_url = agent.page.url
        print(f"현재 주소: {current_url}")

        helper = ThreadsPlaywrightHelper(agent.page)
        if not helper.check_login_status():
            print("실제 Threads 인증 상태를 확인하지 못했습니다.")
            print("브라우저에서 로그인을 완료한 뒤 setup_login.py를 다시 실행해주세요.")
            return

        print("암호화된 세션을 저장합니다...")
        if not agent.save_session():
            raise RuntimeError("브라우저 세션 저장 결과를 확인하지 못했습니다.")

        storage_path = agent._get_storage_state_path()
        if os.path.exists(storage_path):
            file_size = os.path.getsize(storage_path)
            print(f"세션 파일: {storage_path}")
            print(f"크기: {file_size:,}바이트")
            print("세션 파일은 Windows DPAPI로 암호화되어 저장됩니다.")

        print()
        print("설정이 완료되었습니다.")
        print("이제 다음 명령을 실행하세요: python login_main.py")

    except Exception:
        print()
        print("설정 중 문제가 발생했습니다.")
        print("네트워크와 브라우저 접근 상태를 확인한 뒤 다시 시도해주세요.")

    finally:
        print()
        print("브라우저를 닫습니다...")
        # Session setup explicitly persists only after robust authentication.
        # Never let cleanup overwrite an existing valid session after failure.
        agent.close(save_session=False)
        print("완료")


if __name__ == "__main__":
    main()
