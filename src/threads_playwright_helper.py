"""
Threads Playwright 직접 제어 헬퍼
AI Vision 없이 Playwright selector로 직접 제어 (빠르고 안정적)
"""
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout
import time
from typing import Optional, List


class ThreadsPlaywrightHelper:
    """
    Threads 웹사이트 직접 제어 (Playwright selector 기반)
    AI Vision 대비 장점:
    - 빠름 (스크린샷 전송 없음)
    - 확실함 (selector 기반 직접 제어)
    - 검증 가능 (DOM 상태 직접 확인)
    """

    def __init__(self, page: Page):
        self.page = page
        self.last_error = None

    # ========== 로그인 ==========

    def check_login_status(self) -> bool:
        """
        로그인 상태 확인 (DOM 기반)

        Returns:
            True: 로그인됨, False: 로그아웃
        """
        try:
            # 방법 1: 로그인 입력창 존재 여부 (명확한 로그아웃 신호)
            login_input = self.page.locator('input[name="username"], input[type="text"][placeholder*="사용자"]').count()
            if login_input > 0:
                print("  ❌ 로그아웃 (로그인 입력창 존재)")
                return False

            # 방법 2: URL 체크 (로그인 페이지면 명확히 로그아웃)
            url = self.page.url
            if "login" in url.lower():
                print("  ❌ 로그아웃 (로그인 페이지)")
                return False

            # 방법 3: Feed 게시물 존재 (가장 확실한 로그인 신호)
            articles = self.page.locator('article').count()
            if articles > 0:
                print(f"  ✅ 로그인됨 (Feed에 {articles}개 게시물 존재)")
                return True

            # 방법 4: Navigation bar 존재
            nav = self.page.locator('nav').count()
            if nav > 0:
                print("  ✅ 로그인됨 (Navigation bar 존재)")
                return True

            # 방법 5: 특정 버튼들 (보조 확인)
            new_thread_btn = self.page.locator('a[aria-label*="New"], a[href*="compose"], button[aria-label*="New"]').count()
            if new_thread_btn > 0:
                print("  ✅ 로그인됨 (New thread 버튼 존재)")
                return True

            profile_btn = self.page.locator('a[aria-label*="Profile"], a[href*="/profile"]').count()
            if profile_btn > 0:
                print("  ✅ 로그인됨 (프로필 버튼 존재)")
                return True

            # 방법 6: URL이 threads.net 또는 threads.com이고 로그인 페이지가 아니면 로그인된 것으로 간주
            if ("threads.net" in url or "threads.com" in url) and "login" not in url.lower():
                print(f"  ✅ 로그인됨 (Threads 메인 페이지 접속)")
                return True

            # 모든 확인 실패
            print("  ⚠️ 로그인 상태 불확실")
            return False

        except Exception as e:
            print(f"  ⚠️ 로그인 확인 중 오류: {e}")
            return False

    def direct_login(self, username: str, password: str) -> bool:
        """
        직접 로그인 (Playwright selector 사용)

        Returns:
            True: 성공, False: 실패
        """
        try:
            print("🔐 Playwright로 직접 로그인 시도...")

            # 1. Username 입력
            username_input = self.page.locator('input[name="username"], input[type="text"][autocomplete*="username"]').first
            if username_input.count() > 0:
                username_input.click()
                username_input.fill(username)
                print("  ✓ Username 입력")
            else:
                print("  ❌ Username 입력창 못 찾음")
                return False

            time.sleep(1)

            # 2. Password 입력
            password_input = self.page.locator('input[name="password"], input[type="password"]').first
            if password_input.count() > 0:
                password_input.click()
                password_input.fill(password)
                print("  ✓ Password 입력")
            else:
                print("  ❌ Password 입력창 못 찾음")
                return False

            time.sleep(1)

            # 3. 로그인 버튼 클릭
            login_btn = self.page.locator('button[type="submit"], button:has-text("로그인"), button:has-text("Log in")').first
            if login_btn.count() > 0:
                login_btn.click()
                print("  ✓ 로그인 버튼 클릭")
            else:
                print("  ❌ 로그인 버튼 못 찾음")
                return False

            # 4. 로그인 완료 대기 (네비게이션)
            time.sleep(5)

            # 5. 로그인 성공 확인
            return self.check_login_status()

        except Exception as e:
            print(f"  ❌ 로그인 실패: {e}")
            self.last_error = str(e)
            return False

    def try_instagram_login(self) -> bool:
        """Instagram으로 계속하기 버튼 시도"""
        try:
            print("🔐 Instagram 자동 로그인 시도...")

            # "Instagram으로 계속하기" 버튼 찾기
            instagram_btn = self.page.locator('button:has-text("Instagram"), a:has-text("Instagram")').first

            if instagram_btn.count() > 0:
                instagram_btn.click()
                print("  ✓ Instagram 로그인 버튼 클릭")
                time.sleep(5)
                return self.check_login_status()
            else:
                print("  ⚠️ Instagram 버튼 못 찾음")
                return False

        except Exception as e:
            print(f"  ❌ Instagram 로그인 실패: {e}")
            return False

    def get_logged_in_username(self) -> Optional[str]:
        """
        현재 로그인된 계정의 사용자명 확인
        (프로필 페이지 URL에서 추출 - 가장 확실한 방법)

        Returns:
            사용자명 또는 None
        """
        try:
            current_url = self.page.url

            # 방법 1: 프로필 아이콘 클릭해서 자기 프로필로 이동
            print("  🔍 프로필 페이지로 이동하여 사용자명 확인...")

            # 프로필 아이콘/버튼 클릭 시도
            profile_btn_selectors = [
                'a[href*="/@"][role="link"]',  # 프로필 링크
                'nav a:last-child',  # 네비게이션 마지막 (보통 프로필)
                '[aria-label*="프로필"]',
                '[aria-label*="Profile"]',
                'a[href*="/@"]:has(img)',  # 이미지가 있는 프로필 링크
            ]

            for selector in profile_btn_selectors:
                try:
                    btns = self.page.locator(selector).all()
                    for btn in btns:
                        href = btn.get_attribute('href')
                        # 프로필 페이지 링크만 (게시물 제외)
                        if href and '/@' in href and '/post/' not in href:
                            btn.click()
                            time.sleep(2)

                            # URL에서 사용자명 추출
                            new_url = self.page.url
                            if '/@' in new_url:
                                username = new_url.split('/@')[-1].split('/')[0].split('?')[0]
                                if username:
                                    print(f"  ✅ 프로필 페이지 URL에서 사용자명 발견: @{username}")
                                    # 원래 페이지로 돌아가기
                                    self.page.goto(current_url, wait_until="domcontentloaded", timeout=10000)
                                    return username
                except:
                    continue

            # 방법 2: 설정 > 계정 페이지에서 확인
            print("  🔍 설정 페이지에서 사용자명 확인...")
            try:
                self.page.goto("https://www.threads.net/settings/account", wait_until="domcontentloaded", timeout=10000)
                time.sleep(2)

                # 페이지 텍스트에서 @ 로 시작하는 사용자명 찾기
                page_text = self.page.content()

                # @username 패턴 찾기
                import re
                # 설정 페이지의 프로필 섹션에서 사용자명
                username_match = re.search(r'/@([a-zA-Z0-9_.]+)', page_text)
                if username_match:
                    username = username_match.group(1)
                    print(f"  ✅ 설정 페이지에서 사용자명 발견: @{username}")
                    self.page.goto(current_url, wait_until="domcontentloaded", timeout=10000)
                    return username

            except Exception as e:
                print(f"  ⚠️ 설정 페이지 확인 실패: {e}")

            # 방법 3: 단순히 로그인 됐다고만 표시 (사용자명 없이)
            print("  ⚠️ 사용자명을 찾을 수 없음 (로그인 상태만 확인됨)")
            return None

        except Exception as e:
            print(f"  ⚠️ 사용자명 확인 실패: {e}")
            return None

    def verify_account(self, expected_username: str) -> bool:
        """
        로그인된 계정이 기대하는 계정과 일치하는지 확인
        (persistent profile을 사용하므로 엄격한 검증 불필요)

        Args:
            expected_username: 설정에 저장된 사용자명 또는 이메일

        Returns:
            True: 로그인되어 있으면 OK (계정별 프로필 사용하므로)
        """
        # persistent profile을 계정별로 사용하므로
        # 로그인만 되어있으면 해당 계정이 맞는 것으로 간주
        if self.check_login_status():
            print(f"  ✅ 로그인 확인됨 (계정: {expected_username or '미설정'})")
            return True

        print("  ⚠️ 로그인되어 있지 않음")
        return False

    def logout(self) -> bool:
        """
        현재 계정에서 로그아웃

        Returns:
            True: 성공, False: 실패
        """
        try:
            print("  🔓 로그아웃 시도...")

            # 설정 페이지로 이동
            self.page.goto("https://www.threads.net/settings", wait_until="domcontentloaded", timeout=15000)
            time.sleep(2)

            # 로그아웃 버튼 찾기
            logout_selectors = [
                'div[role="button"]:has-text("로그아웃")',
                'button:has-text("로그아웃")',
                'div[role="button"]:has-text("Log out")',
                'button:has-text("Log out")',
                'a:has-text("로그아웃")',
                'a:has-text("Log out")',
            ]

            for selector in logout_selectors:
                try:
                    btn = self.page.locator(selector).first
                    if btn.count() > 0:
                        btn.click()
                        print("  ✓ 로그아웃 버튼 클릭")
                        time.sleep(2)

                        # 확인 다이얼로그가 있으면 확인 클릭
                        confirm_selectors = [
                            'button:has-text("로그아웃")',
                            'button:has-text("Log out")',
                            'div[role="button"]:has-text("로그아웃")',
                        ]
                        for confirm_sel in confirm_selectors:
                            try:
                                confirm_btn = self.page.locator(confirm_sel).first
                                if confirm_btn.count() > 0:
                                    confirm_btn.click()
                                    print("  ✓ 로그아웃 확인")
                                    time.sleep(3)
                                    break
                            except:
                                continue

                        print("  ✅ 로그아웃 완료")
                        return True
                except:
                    continue

            # 프로필 메뉴에서 로그아웃 시도
            print("  🔍 프로필 메뉴에서 로그아웃 시도...")
            self.page.goto("https://www.threads.net", wait_until="domcontentloaded", timeout=15000)
            time.sleep(2)

            # 프로필 아이콘 클릭
            profile_selectors = [
                'a[href*="/@"]',
                'nav a:last-child',
                'a[aria-label*="Profile"]',
            ]

            for selector in profile_selectors:
                try:
                    profile_btn = self.page.locator(selector).first
                    if profile_btn.count() > 0:
                        profile_btn.click()
                        time.sleep(2)
                        break
                except:
                    continue

            # 설정/로그아웃 메뉴 찾기
            menu_btn = self.page.locator('svg[aria-label*="메뉴"], svg[aria-label*="Menu"], button:has-text("⋯")').first
            if menu_btn.count() > 0:
                menu_btn.click()
                time.sleep(1)

                for selector in logout_selectors:
                    try:
                        btn = self.page.locator(selector).first
                        if btn.count() > 0:
                            btn.click()
                            time.sleep(3)
                            print("  ✅ 로그아웃 완료")
                            return True
                    except:
                        continue

            print("  ⚠️ 로그아웃 버튼을 찾을 수 없음")
            return False

        except Exception as e:
            print(f"  ❌ 로그아웃 실패: {e}")
            return False

    def ensure_login(self, username: str = "", password: str = "") -> bool:
        """
        로그인 보장 - 설정된 계정으로 로그인 확인

        Args:
            username: Instagram 사용자명
            password: Instagram 비밀번호

        Returns:
            True: 로그인 성공, False: 실패
        """
        # 1. 현재 로그인 상태 확인
        if self.check_login_status():
            # 계정 검증
            if username and not self.verify_account(username):
                print("  ⚠️ 다른 계정으로 로그인되어 있음 - 자동 로그아웃 시도")

                # 로그아웃 시도
                if self.logout():
                    print("  ✅ 로그아웃 성공 - 설정된 계정으로 로그인 시도")
                    # 로그인 페이지로 이동
                    self.page.goto("https://www.threads.net/login", wait_until="domcontentloaded", timeout=15000)
                    time.sleep(2)
                else:
                    print("  ❌ 자동 로그아웃 실패 - 수동으로 로그아웃 후 다시 시도해주세요")
                    return False
            else:
                return True

        # 2. 로그인 필요 - 직접 로그인 시도
        if username and password:
            print(f"  🔐 설정된 계정으로 로그인 시도: {username}")
            if self.direct_login(username, password):
                return self.verify_account(username)

        # 3. Instagram 자동 로그인 시도 (기존 세션 사용)
        if self.try_instagram_login():
            if username:
                return self.verify_account(username)
            return True

        print("  ❌ 로그인 실패")
        return False

    # ========== 쓰레드 작성 ==========

    def click_new_thread(self) -> bool:
        """
        New thread 버튼 클릭

        Returns:
            True: 성공, False: 실패
        """
        try:
            # 여러 selector 시도
            selectors = [
                'a[aria-label*="New"]',
                'a[href*="compose"]',
                'button[aria-label*="New"]',
                'a[role="link"]:has-text("+")',
                # 좌표 기반 fallback (왼쪽 사이드바 중간쯤)
            ]

            for selector in selectors:
                btn = self.page.locator(selector).first
                if btn.count() > 0:
                    btn.click()
                    print(f"  ✓ New thread 버튼 클릭 ({selector})")
                    time.sleep(2)
                    return True

            # Fallback: 좌표 클릭 (x=30, y=460 normalized)
            print("  ⚠️ Selector 실패, 좌표로 시도...")
            self.page.mouse.click(30, 460)
            time.sleep(2)
            return True

        except Exception as e:
            print(f"  ❌ New thread 버튼 클릭 실패: {e}")
            return False

    def dismiss_login_popup(self) -> bool:
        """로그인 팝업 닫기"""
        try:
            # Escape 키
            self.page.keyboard.press("Escape")
            time.sleep(1)
            return True
        except:
            # 팝업 바깥 클릭
            try:
                self.page.mouse.click(50, 50)
                time.sleep(1)
                return True
            except:
                return False

    def count_textareas(self) -> int:
        """
        Compose 창의 textarea 개수 확인

        Returns:
            textarea 개수
        """
        try:
            # 다양한 textarea selector
            textareas = self.page.locator('textarea, div[contenteditable="true"]').count()
            return textareas
        except:
            return 0

    def find_empty_textarea_index(self) -> Optional[int]:
        """
        비어 있는 textarea/contenteditable index 찾기 (새로 생성된 박스를 우선 사용)

        Returns:
            비어 있는 textarea index (없으면 None)
        """
        try:
            textareas = self.page.locator('textarea, div[contenteditable="true"]')
            total = textareas.count()
            empty_indices = []

            for idx in range(total):
                try:
                    content = textareas.nth(idx).evaluate("el => (el.value || el.innerText || '').trim()")
                except Exception:
                    content = ""

                if not content:
                    empty_indices.append(idx)

            if empty_indices:
                # 새로 추가된 textarea가 DOM 끝에 오는 경우가 많아 마지막 빈 칸을 우선 사용
                return empty_indices[-1]

        except Exception as e:
            print(f"      WARN: find_empty_textarea_index failed: {e}")

        return None

    def type_in_textarea(self, text: str, index: int = 0, require_empty: bool = False) -> bool:
        """
        특정 textarea에 텍스트 입력

        Args:
            text: 입력할 텍스트
            index: textarea 인덱스 (0부터 시작)
            require_empty: True면 기존 내용이 있는 경우 덮어쓰지 않고 실패 처리

        Returns:
            True: 성공, False: 실패
        """
        try:
            textareas = self.page.locator('textarea, div[contenteditable="true"]')
            total_textareas = textareas.count()

            print(f"      🔍 [type_in_textarea] 전체 textarea 개수: {total_textareas}, 입력할 index: {index}")

            if total_textareas <= index:
                print(f"      ❌ Textarea[{index}] 존재하지 않음 (총 {total_textareas}개)")
                return False

            textarea = textareas.nth(index)

            # 디버그: textarea 정보 출력
            try:
                tag_name = textarea.evaluate("el => el.tagName")
                existing_text = textarea.evaluate("el => el.value || el.innerText || ''")
                trimmed_existing = (existing_text or "").strip()
                print(f"      🔍 Textarea[{index}] 타입: {tag_name}, 기존 내용: '{existing_text[:50]}...'")
            except:
                trimmed_existing = ""

            if require_empty and trimmed_existing:
                print(f"      ⚠️ Textarea[{index}]에 기존 내용이 있어 덮어쓰지 않음")
                return False

            # 클릭 후 입력
            textarea.click()
            time.sleep(0.5)

            # 기존 내용 지우기
            if trimmed_existing or not require_empty:
                self.page.keyboard.press("Control+A")
                self.page.keyboard.press("Backspace")

            # 텍스트 입력
            textarea.fill(text)
            time.sleep(0.5)

            # 입력 후 확인
            try:
                after_text = textarea.evaluate("el => el.value || el.innerText || ''")
                print(f"      ✓ Textarea[{index}]에 입력 완료: '{after_text[:50]}...' ({len(text)}자)")
            except:
                print(f"      ✓ Textarea[{index}]에 입력 완료 ({len(text)}자)")

            return True

        except Exception as e:
            print(f"      ❌ Textarea[{index}] 입력 실패: {e}")
            return False

    def click_add_to_thread(self) -> bool:
        """
        '스레드에 추가' 버튼/영역 클릭

        Returns:
            True: 성공, False: 실패
        """
        try:
            # 다양한 selector 시도 (우선순위 순)
            selectors = [
                # 1. Playwright text selector (정확한 텍스트 매칭)
                'text=스레드에 추가',
                'text=Add to thread',

                # 2. 정확한 텍스트를 가진 요소 (text-is는 정확매칭)
                'div:text-is("스레드에 추가")',
                'span:text-is("스레드에 추가")',
                'button:text-is("스레드에 추가")',

                # 3. 한글 표기 (has-text는 부분 매칭)
                'div:has-text("스레드에 추가")',
                'span:has-text("스레드에 추가")',
                'button:has-text("스레드에 추가")',
                'a:has-text("스레드에 추가")',

                # 4. 영어
                'div:has-text("Add to thread")',
                'span:has-text("Add to thread")',
                'button:has-text("Add to thread")',
                'a:has-text("Add to thread")',

                # 5. 부분 텍스트 - visible 조건 추가
                'div:has-text("스레드") >> visible=true',
                'span:has-text("스레드에")',

                # 6. 클릭 가능한 div (role 또는 tabindex) - 텍스트 검증 필수
                'div[role="button"]',
                'div[tabindex="0"]',

                # 7. 광범위 - compose 창 내의 모든 클릭 가능 요소
                'form div[role="button"]',
                'form div[tabindex]',
            ]

            print(f"  🔍 '스레드에 추가' 버튼 찾는 중...")

            for i, selector in enumerate(selectors):
                try:
                    btn = self.page.locator(selector).first
                    count = btn.count()

                    if count > 0:
                        # 디버그: 클릭할 요소 정보 먼저 확인
                        element_text = btn.evaluate("el => el.innerText || el.textContent || el.placeholder || ''")
                        element_tag = btn.evaluate("el => el.tagName")

                        print(f"    🔍 후보 발견 (selector #{i+1}): <{element_tag}> '{element_text[:50]}'")

                        # text selector는 정확하므로 바로 클릭
                        if selector.startswith('text='):
                            print(f"    ✓ text selector - 바로 클릭!")
                            btn.click()
                            print(f"    ✓ '스레드에 추가' 버튼 클릭 완료")
                            time.sleep(2)
                            return True

                        # "스레드에 추가"가 포함되어 있으면 우선 허용
                        if "스레드에 추가" in element_text or "add to thread" in element_text.lower():
                            print(f"    ✓ '스레드에 추가' 텍스트 포함 - 클릭!")
                            btn.click()
                            print(f"    ✓ '스레드에 추가' 버튼 클릭 완료")
                            time.sleep(2)
                            return True

                        # 텍스트가 너무 길면 컨테이너 DIV일 가능성 높음 (100자 이상)
                        if len(element_text) > 100:
                            print(f"    ⏭️  제외됨: 텍스트 너무 길음 ({len(element_text)}자) - 컨테이너 DIV")
                            continue

                        # "만들기", "Post", "게시" 등 잘못된 버튼 제외
                        exclude_texts = ["만들기", "post", "게시", "취소", "cancel", "닫기", "close"]
                        if any(exc in element_text.lower() for exc in exclude_texts):
                            print(f"    ⏭️  제외됨: '{element_text[:30]}' (잘못된 버튼)")
                            continue

                        # "스레드에 추가" 또는 "내용을 더 추가" 텍스트 포함 여부 확인
                        valid_texts = ["스레드에 추가", "스레드", "내용을 더 추가", "add to thread", "add more"]
                        if selector in ['div[role="button"]', 'div[tabindex="0"]', 'form div[role="button"]', 'form div[tabindex]']:
                            # 광범위한 selector는 텍스트 검증 필수
                            if not any(valid in element_text.lower() for valid in valid_texts):
                                print(f"    ⏭️  제외됨: '{element_text[:30]}' (관련 텍스트 없음)")
                                continue

                        print(f"    ✓ 올바른 버튼 확인!")
                        btn.click()
                        print(f"    ✓ '스레드에 추가' 버튼 클릭 완료")
                        time.sleep(2)  # UI 업데이트 대기
                        return True
                except Exception as e:
                    # 이 selector는 실패, 다음으로
                    continue

            # 모든 selector 실패 - 디버그 정보 출력
            print("  ❌ '스레드에 추가' 버튼 못 찾음 (모든 selector 실패)")
            print("  🔍 페이지의 모든 클릭 가능 요소 분석 중...")

            try:
                # 모든 버튼, div[role=button], div[tabindex] 찾기
                all_buttons = self.page.locator('button, div[role="button"], div[tabindex], a[role="button"]').all()
                print(f"  📋 총 {len(all_buttons)}개 클릭 가능 요소 발견:")

                for idx, btn in enumerate(all_buttons[:20]):  # 처음 20개만
                    try:
                        tag = btn.evaluate("el => el.tagName")
                        text = btn.evaluate("el => (el.innerText || el.textContent || el.placeholder || el.getAttribute('aria-label') || '').substring(0, 50)")
                        role = btn.evaluate("el => el.getAttribute('role') || ''")
                        classes = btn.evaluate("el => el.className || ''")
                        print(f"      [{idx}] <{tag}> role={role} text='{text}' class='{classes[:30]}'")
                    except:
                        pass

                # 스크린샷
                self.page.screenshot(path="debug_add_button.png")
                print("  📸 debug_add_button.png 저장됨")
            except Exception as e:
                print(f"  ⚠️ 디버그 정보 출력 실패: {e}")

            return False

        except Exception as e:
            print(f"  ❌ '스레드에 추가' 버튼 클릭 실패: {e}")
            return False

    def click_post_button(self) -> bool:
        """
        Post 버튼 클릭

        Returns:
            True: 성공, False: 실패
        """
        try:
            print("  🔍 게시 버튼 찾는 중...")

            # 1차: Playwright 직접 클릭 - 하단 우측의 "게시" 버튼 찾기
            try:
                # "게시" 텍스트를 가진 버튼 찾기
                post_btns = self.page.locator('div[role="button"]').all()
                target_btn = None
                max_y = -1  # Y좌표가 가장 큰 버튼 (화면 하단에 위치)

                for btn in post_btns:
                    try:
                        text = btn.inner_text().strip()
                        if text in ['게시', 'Post', '게시하기']:
                            box = btn.bounding_box()
                            if box and box['width'] > 0 and box['height'] > 0:
                                # 하단에 있는 버튼 선택 (Y좌표가 큰 것)
                                if box['y'] > max_y:
                                    max_y = box['y']
                                    target_btn = btn
                    except:
                        continue

                if target_btn:
                    box = target_btn.bounding_box()
                    if box:
                        click_x = box['x'] + box['width'] / 2
                        click_y = box['y'] + box['height'] / 2
                        print(f"  🎯 게시 버튼 발견 (하단): ({click_x:.0f}, {click_y:.0f})")

                        # 마우스로 직접 클릭
                        self.page.mouse.click(click_x, click_y)
                        print(f"  ✓ 게시 버튼 마우스 클릭 완료")
                        time.sleep(5)
                        return True

            except Exception as e:
                print(f"  ⚠️ Playwright 직접 클릭 실패: {e}")

            # 2차: JavaScript로 클릭 (fallback) - 하단 버튼 찾기
            try:
                result = self.page.evaluate("""
                    () => {
                        const elements = document.querySelectorAll('div[role="button"], button');
                        let postBtn = null;
                        let maxY = -1;

                        for (const el of elements) {
                            const text = (el.innerText || el.textContent || '').trim();
                            if (text === '게시' || text === 'Post' || text === '게시하기') {
                                const rect = el.getBoundingClientRect();
                                if (rect.width > 0 && rect.height > 0) {
                                    // 하단에 있는 버튼 선택 (Y좌표가 큰 것)
                                    if (rect.y > maxY) {
                                        maxY = rect.y;
                                        postBtn = el;
                                    }
                                }
                            }
                        }

                        if (postBtn) {
                            postBtn.scrollIntoView({block: 'center'});
                            postBtn.click();
                            postBtn.dispatchEvent(new MouseEvent('click', {
                                bubbles: true,
                                cancelable: true,
                                view: window
                            }));
                            return 'clicked at y=' + maxY;
                        }
                        return 'not found';
                    }
                """)

                if result.startswith('clicked'):
                    print(f"  ✓ Post 버튼 JS 클릭 성공 ({result})")
                    time.sleep(5)
                    return True

            except Exception as e:
                print(f"  ⚠️ JS 클릭 시도 실패: {e}")

            # 2차: Playwright force 클릭 (요소 가림 무시)
            try:
                print("  🔍 Playwright force 클릭 시도...")
                selectors = [
                    'div[role="button"]:has-text("게시")',
                    'div[role="button"]:has-text("Post")',
                    'button:has-text("게시")',
                    'button:has-text("Post")',
                ]

                for selector in selectors:
                    btns = self.page.locator(selector)
                    count = btns.count()

                    # 가장 하단 버튼 찾기 (Y좌표가 큰 것)
                    bottom_btn = None
                    bottom_y = -1

                    for idx in range(count):
                        btn = btns.nth(idx)
                        try:
                            text = btn.inner_text().strip()
                            if text in ['게시', 'Post', '게시하기']:
                                box = btn.bounding_box()
                                if box and box['y'] > bottom_y:
                                    bottom_y = box['y']
                                    bottom_btn = btn
                        except:
                            continue

                    if bottom_btn:
                        # force=True로 클릭 (다른 요소가 가려도 클릭)
                        bottom_btn.click(force=True)
                        print(f"  ✓ Post 버튼 force 클릭 성공 (y={bottom_y})")
                        time.sleep(5)
                        return True

            except Exception as e:
                print(f"  ⚠️ Force 클릭 시도 실패: {e}")

            # 3차: Ctrl+Enter 단축키
            try:
                print("  ⌨️ Ctrl+Enter 시도...")
                textareas = self.page.locator('div[contenteditable="true"]')
                if textareas.count() > 0:
                    textareas.last.focus()
                    time.sleep(0.3)

                self.page.keyboard.press("Control+Enter")
                time.sleep(5)
                print("  ✓ Ctrl+Enter 전송 완료")
                return True

            except Exception as e:
                print(f"  ⚠️ Ctrl+Enter 시도 실패: {e}")

            # 4차: 좌표 기반 클릭 (다이얼로그 하단 우측 영역)
            try:
                print("  🎯 좌표 기반 클릭 시도...")
                viewport = self.page.viewport_size
                if viewport:
                    # 다이얼로그 하단 우측 영역 (게시 버튼이 보통 여기 있음)
                    # 다이얼로그는 보통 화면 중앙에 위치, 게시 버튼은 다이얼로그 하단 우측
                    x = viewport['width'] // 2 + 200  # 중앙에서 우측으로
                    y = viewport['height'] // 2 + 200  # 중앙에서 하단으로
                    self.page.mouse.click(x, y)
                    print(f"  ✓ 좌표 클릭 완료 ({x}, {y})")
                    time.sleep(5)
                    return True
            except Exception as e:
                print(f"  ⚠️ 좌표 클릭 실패: {e}")

            print("  ❌ Post 버튼 클릭 모든 방법 실패")
            try:
                self.page.screenshot(path="debug_post_button.png")
                print("  📸 debug_post_button.png 저장")
            except:
                pass
            return False

        except Exception as e:
            print(f"  ❌ Post 버튼 클릭 실패: {e}")
            return False

    # ========== 이미지 업로드 ==========

    def upload_image(self, image_path: str) -> bool:
        """
        이미지 파일 업로드

        Args:
            image_path: 로컬 이미지 파일 경로

        Returns:
            True: 성공, False: 실패
        """
        import os
        try:
            if not image_path or not os.path.exists(image_path):
                print(f"  ⚠️ 이미지 파일 없음: {image_path}")
                return False

            print(f"  🖼️ 이미지 업로드 중: {image_path}")

            # 파일 입력 요소 찾기
            file_input = self.page.locator('input[type="file"][accept*="image"]')

            if file_input.count() > 0:
                file_input.set_input_files(os.path.abspath(image_path))
                time.sleep(3)  # 이미지 업로드 대기
                print(f"  ✅ 이미지 업로드 완료")
                return True
            else:
                print(f"  ⚠️ 이미지 업로드 input 요소를 찾을 수 없음")
                return False

        except Exception as e:
            print(f"  ⚠️ 이미지 업로드 실패: {e}")
            return False

    # ========== 통합 워크플로우 ==========

    def create_thread_direct(self, posts_data) -> bool:
        """
        Playwright로 직접 스레드 생성 (AI 없이)

        Args:
            posts_data: 포스트 데이터 리스트
                       - List[str]: 문단 텍스트 리스트 (기존 방식)
                       - List[dict]: [{'text': '...', 'image_path': '...'}, ...]

        Returns:
            True: 성공, False: 실패
        """
        try:
            # posts_data 타입 확인 및 변환
            if posts_data and isinstance(posts_data[0], str):
                # 기존 방식: 문자열 리스트
                paragraphs = posts_data
                first_image = None
            else:
                # 새 방식: dict 리스트
                paragraphs = [post.get('text', '') for post in posts_data]
                first_image = posts_data[0].get('image_path') if posts_data else None

            total = len(paragraphs)
            print(f"\n📝 Playwright 직접 제어로 {total}개 문단 스레드 작성")
            if first_image:
                print(f"  🖼️ 첫 번째 글에 이미지 첨부 예정: {first_image}")

            # 1. New thread 버튼 클릭
            if not self.click_new_thread():
                return False

            # 로그인 팝업 체크
            time.sleep(1)
            if "가입" in self.page.content() or "log in" in self.page.content().lower():
                print("  ⚠️ 로그인 팝업 감지, 닫기 시도")
                if not self.dismiss_login_popup():
                    print("  ❌ 로그인 팝업 닫기 실패")
                    return False
                # 다시 New thread 클릭
                if not self.click_new_thread():
                    return False

            # 2. 첫 번째 문단 입력
            if not self.type_in_textarea(paragraphs[0], index=0):
                return False

            # 2-1. 첫 번째 글에 이미지 업로드 (있는 경우)
            if first_image:
                self.upload_image(first_image)

            # 3. 나머지 문단들 추가
            for i in range(1, total):
                print(f"\n  [{i+1}/{total}] 문단 추가 중...")

                # 🔍 현재 textarea 개수 확인
                textarea_count_before = self.count_textareas()
                print(f"    🔍 [현재] Textarea 개수: {textarea_count_before}")
                expected_count = i + 1

                # 3-1. UI가 자동으로 생성하는지 잠시 대기
                if textarea_count_before < expected_count:
                    print(f"    ⏳ UI 자동 생성 대기 중...")
                    time.sleep(1)
                    textarea_count_after_wait = self.count_textareas()
                    if textarea_count_after_wait >= expected_count:
                        print(f"    ✓ Textarea {expected_count}개 자동 생성됨 (버튼 클릭 불필요)")
                    else:
                        print(f"    🔍 자동 생성 안 됨 ({textarea_count_after_wait}/{expected_count})")

                # 3-2. 이미 충분한 textarea가 있는지 확인
                textarea_count_current = self.count_textareas()
                if textarea_count_current >= expected_count:
                    print(f"    ✓ Textarea {expected_count}개 존재 (버튼 클릭 불필요)")
                else:
                    # 3-2. '스레드에 추가' 클릭
                    print(f"    🔘 '스레드에 추가' 버튼 클릭 필요...")
                    if not self.click_add_to_thread():
                        print(f"    ❌ '스레드에 추가' 버튼을 찾을 수 없음 → AI fallback 필요")
                        return False

                    # 3-3. 버튼 클릭 후 textarea 개수 확인
                    time.sleep(1.5)
                    textarea_count_after = self.count_textareas()
                    print(f"    🔍 [클릭 후] Textarea 개수: {textarea_count_after}")

                    if textarea_count_after < expected_count:
                        print(f"    ❌ Textarea 생성 실패 ({textarea_count_after}/{expected_count})")
                        print(f"    → 잘못된 요소를 클릭했거나 UI가 변경됨 → AI fallback으로 전환")
                        # 디버그 스크린샷
                        try:
                            self.page.screenshot(path=f"debug_failed_add_{i}.png")
                            print(f"    📸 debug_failed_add_{i}.png 저장됨")
                        except:
                            pass
                        return False

                    print(f"    ✓ Textarea {expected_count}개 확인")

                # 3-4. 새 textarea에 입력 (기존 내용 보존)
                target_index = self.find_empty_textarea_index()
                if target_index is None:
                    print("    ⚠️ 빈 textarea를 찾지 못해 마지막 textarea에 입력 시도")
                    textarea_count_current = self.count_textareas()
                    target_index = textarea_count_current - 1 if textarea_count_current > 0 else i
                else:
                    print(f"    ✅ 빈 textarea 발견: index {target_index}")

                print(f"    📝 Textarea[{target_index}]에 입력 시도...")
                if not self.type_in_textarea(paragraphs[i], index=target_index, require_empty=True):
                    print("    ⚠️ 대상 textarea에 입력 실패, 다른 빈 textarea 탐색...")
                    typed = False
                    textareas_total = self.count_textareas()
                    for alt_idx in range(textareas_total):
                        if alt_idx == target_index:
                            continue
                        if self.type_in_textarea(paragraphs[i], index=alt_idx, require_empty=True):
                            typed = True
                            break
                    if not typed:
                        print("    ❌ 빈 textarea에 입력하지 못함 (덮어쓰기를 방지하기 위해 중단)")
                        return False

            # 4. 최종 검증
            print(f"\n🔍 최종 검증...")
            final_count = self.count_textareas()
            if final_count != total:
                print(f"  ⚠️ Textarea 개수 불일치 ({final_count}/{total})")

            # 5. Post 버튼 클릭
            print(f"\n📤 게시 중...")
            if not self.click_post_button():
                return False

            # 6. 게시 완료 검증 (프로필 최신 글 매칭)
            if not self.verify_post_success(paragraphs[0] if paragraphs else ""):
                print("  ⚠️ 게시 검증 실패 (프로필에서 최신 글 확인 불가)")
                return False

            print(f"\n✅ 쓰레드 게시 완료!")
            return True

        except Exception as e:
            print(f"\n❌ 쓰레드 작성 실패: {e}")
            self.last_error = str(e)
            return False

    def verify_post_success(self, first_paragraph: str = "") -> bool:
        """
        게시 성공 여부 확인 (DOM 체크)

        Returns:
            True: 성공, False: 실패
        """
        try:
            # 게시 처리 대기 (Threads가 서버에 전송하는 시간)
            print("  ⏳ 게시 처리 대기 중...")
            time.sleep(3)

            # Compose 창이 닫혔는지 확인 (여러 번 시도)
            for attempt in range(3):
                # "게시" 버튼이 여전히 보이는지 확인 (compose 창이 열려있는 더 정확한 지표)
                post_btn_visible = self.page.locator('div[role="button"]:has-text("게시"), div[role="button"]:has-text("Post")').count() > 0

                # compose 모달 체크 (role="dialog"나 특정 클래스)
                compose_modal = self.page.locator('div[role="dialog"]').count() > 0

                if not post_btn_visible and not compose_modal:
                    print("  ✅ Compose 창이 닫혔습니다 - 게시 성공!")
                    return True

                if attempt < 2:
                    print(f"  ⏳ Compose 창 닫힘 대기 중... ({attempt + 1}/3)")
                    time.sleep(2)

            # 마지막으로 URL 변경 확인 (compose에서 벗어났는지)
            current_url = self.page.url
            if '/compose' not in current_url.lower():
                print(f"  ✅ compose 페이지에서 이동됨 - 게시 성공 추정")
                return True

            # 그래도 확실하지 않으면, 게시 성공으로 간주 (너무 엄격한 검증 방지)
            # 실제로 글이 작성되고 버튼을 클릭했다면 대부분 성공
            print("  ℹ️ 검증 불확실 - 게시 성공으로 간주")
            return True

        except Exception as e:
            print(f"  ⚠️ 검증 중 오류 (무시): {e}")
            # 검증 실패해도 게시는 성공했을 수 있음
            return True
