"""
Threads 초기 로그인 설정 스크립트

한 번만 실행하여 세션을 저장하면, 이후 자동 업로드 시 로그인이 유지됩니다.

사용법:
    python setup_login.py

실행 후:
    1. 브라우저가 자동으로 열립니다
    2. Threads 로그인을 수동으로 진행하세요 (Instagram OAuth 사용)
    3. 피드가 보이면 터미널에서 Enter를 누르세요
    4. 세션이 .threads_profile/storage_state.json에 저장됩니다
    5. 이후 main.py 실행 시 자동으로 로그인 상태가 유지됩니다
"""
import os
import sys

# Windows 터미널 UTF-8 인코딩 설정
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass

from src.computer_use_agent import ComputerUseAgent


def main():
    print("=" * 60)
    print("🔐 Threads 초기 로그인 설정")
    print("=" * 60)
    print()
    print("이 스크립트는 한 번만 실행하면 됩니다.")
    print("로그인 세션을 저장하여 이후 자동 업로드 시 로그인이 유지됩니다.")
    print()

    # API 키 확인 (세션 저장에는 불필요)
    google_api_key = os.environ.get("GOOGLE_API_KEY")
    if not google_api_key:
        print("ℹ️ 알림: GOOGLE_API_KEY 환경변수가 설정되지 않았습니다.")
        print("   세션 저장에는 영향 없습니다. (Computer Use 사용 시에만 필요)")
        print()
        # 세션 저장용 더미 키 (실제 API 호출 안 함)
        google_api_key = "dummy-key-for-session-setup"

    # Agent 생성
    agent = ComputerUseAgent(
        api_key=google_api_key,
        headless=False,
        profile_dir=".threads_profile"
    )

    try:
        # 브라우저 시작
        print("🌐 브라우저 시작 중...")
        agent.start_browser()

        # Threads 페이지 열기
        print("📱 Threads 페이지로 이동 중...")
        agent.page.goto("https://www.threads.net", wait_until="domcontentloaded")
        print()

        print("=" * 60)
        print("👉 다음 단계를 수행하세요:")
        print("=" * 60)
        print("1. 브라우저에서 Instagram 계정으로 로그인하세요")
        print("2. 로그인 후 피드가 정상적으로 보이는지 확인하세요")
        print("3. 피드가 보이면 이 터미널로 돌아와서 Enter를 누르세요")
        print("=" * 60)
        print()

        # 사용자 입력 대기
        input("✅ 로그인이 완료되었으면 Enter를 누르세요...")

        # 로그인 상태 확인
        print()
        print("📍 로그인 상태 확인 중...")
        import time
        time.sleep(2)

        current_url = agent.page.url
        print(f"   현재 URL: {current_url}")

        # 로그인 여부 확인 (여러 indicator)
        is_logged_in = False
        try:
            # Indicator 1: Feed 게시물 확인
            posts = agent.page.locator('article').count()
            if posts > 0:
                print(f"   ✅ Feed에서 {posts}개 게시물 감지 → 로그인 완료!")
                is_logged_in = True

            # Indicator 2: Compose 버튼 확인
            if not is_logged_in:
                compose = agent.page.locator('a[href*="compose"], button[aria-label*="New"]').count()
                if compose > 0:
                    print("   ✅ Compose 버튼 감지 → 로그인 완료!")
                    is_logged_in = True

            # Indicator 3: URL 확인
            if not is_logged_in and "login" not in current_url.lower():
                print("   ✅ URL 확인 → 로그인 완료!")
                is_logged_in = True

        except Exception as e:
            print(f"   ⚠️ 확인 중 오류: {e}")

        if not is_logged_in:
            print("   ⚠️ 로그인 상태 확실하지 않습니다.")
            print("   Threads 홈피드가 보이는지 브라우저에서 확인해주세요.")
            confirmed = input("   로그인이 완료되었나요? (y/n): ").strip().lower()
            if confirmed != 'y':
                print("\n❌ 로그인이 필요합니다. 다시 시도해주세요.")
                return

        # 세션 저장
        print()
        print("💾 세션 저장 중...")
        agent.save_session()

        # 세션 파일 상세 정보 표시
        storage_path = agent._get_storage_state_path()
        if os.path.exists(storage_path):
            import json
            file_size = os.path.getsize(storage_path)
            print(f"   ✅ 파일 저장: {storage_path}")
            print(f"   📦 파일 크기: {file_size:,} bytes")

            # 쿠키 정보 표시
            try:
                with open(storage_path, 'r', encoding='utf-8') as f:
                    storage_state = json.load(f)

                if storage_state.get('cookies'):
                    total_cookies = len(storage_state['cookies'])
                    print(f"   🍪 쿠키 개수: {total_cookies}")

                    # Instagram 관련 쿠키 확인
                    ig_cookies = [c for c in storage_state['cookies']
                                 if 'instagram' in c.get('domain', '').lower()]
                    if ig_cookies:
                        print(f"   📱 Instagram 쿠키: {len(ig_cookies)}개 ✓")
            except:
                pass

        print()
        print("=" * 60)
        print("✅ 초기 설정 완료!")
        print("=" * 60)
        print()
        print("🎉 이제 main.py를 실행하면 로그인 없이 자동으로 업로드됩니다!")
        print("   $ python main.py")
        print()

    except Exception as e:
        print()
        print(f"❌ 오류 발생: {e}")
        print()
        print("문제 해결 방법:")
        print("1. 인터넷 연결 확인")
        print("2. Threads 웹사이트 접속 가능 여부 확인")
        print("3. 다시 시도: python setup_login.py")

    finally:
        # 브라우저 닫기
        print()
        print("🔄 브라우저 종료 중...")
        agent.close()
        print("✅ 완료")


if __name__ == "__main__":
    main()
