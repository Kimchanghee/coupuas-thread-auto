"""Interactive helper to bootstrap a Threads login session."""

import os
import sys
import time

from src.computer_use_agent import ComputerUseAgent


if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def main() -> None:
    print("=" * 60)
    print("Threads Initial Login Setup")
    print("=" * 60)
    print("Run once to store an encrypted local browser session.")
    print()

    google_api_key = os.environ.get("GOOGLE_API_KEY") or "dummy-key-for-session-setup"
    agent = ComputerUseAgent(
        api_key=google_api_key,
        headless=False,
        profile_dir=".threads_profile",
    )

    try:
        print("Starting browser...")
        agent.start_browser()

        print("Opening Threads...")
        agent.page.goto("https://www.threads.net", wait_until="domcontentloaded")

        print()
        print("1. Log in with your Instagram account in the browser window.")
        print("2. Confirm the Threads feed is visible.")
        print("3. Return here and press Enter.")
        input("Press Enter after login completes...")

        print("Verifying login state...")
        time.sleep(2)
        current_url = agent.page.url
        print(f"Current URL: {current_url}")

        is_logged_in = False
        try:
            if agent.page.locator("article").count() > 0:
                is_logged_in = True
            if not is_logged_in and agent.page.locator('a[href*="compose"], button[aria-label*="New"]').count() > 0:
                is_logged_in = True
            if not is_logged_in and "login" not in current_url.lower():
                is_logged_in = True
        except Exception as exc:
            print(f"Login verification warning: {exc}")

        if not is_logged_in:
            confirm = input("Could not verify automatically. Continue anyway? (y/n): ").strip().lower()
            if confirm != "y":
                print("Cancelled. Run setup_login.py again.")
                return

        print("Saving encrypted session...")
        agent.save_session()

        storage_path = agent._get_storage_state_path()
        if os.path.exists(storage_path):
            file_size = os.path.getsize(storage_path)
            print(f"Session file: {storage_path}")
            print(f"Size: {file_size:,} bytes")
            print("Session file is encrypted at rest (DPAPI).")

        print()
        print("Setup complete.")
        print("Now run: python main.py")

    except Exception as exc:
        print()
        print(f"Error: {exc}")
        print("Try again after checking network/browser access.")

    finally:
        print()
        print("Closing browser...")
        agent.close()
        print("Done")


if __name__ == "__main__":
    main()
