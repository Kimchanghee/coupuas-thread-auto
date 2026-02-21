# -*- coding: utf-8 -*-
"""
Threads Playwright 吏곸젒 ?쒖뼱 ?ы띁
AI Vision ?놁씠 Playwright selector濡?吏곸젒 ?쒖뼱 (鍮좊Ⅴ怨??덉젙??
"""
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout

from src.fs_security import secure_dir_permissions, secure_file_permissions


class ThreadsPlaywrightHelper:
    """
    Threads ?뱀궗?댄듃 吏곸젒 ?쒖뼱 (Playwright selector 湲곕컲)
    AI Vision ?鍮??μ젏:
    - 鍮좊쫫 (?ㅽ겕由곗꺑 ?꾩넚 ?놁쓬)
    - ?뺤떎??(selector 湲곕컲 吏곸젒 ?쒖뼱)
    - 寃利?媛??(DOM ?곹깭 吏곸젒 ?뺤씤)
    """

    def __init__(self, page: Page):
        self.page = page
        self.last_error = None

    def _save_debug_screenshot(self, prefix: str) -> Optional[str]:
        if os.getenv("THREAD_AUTO_DEBUG_SCREENSHOTS", "").strip() != "1":
            return None

        debug_dir = Path.home() / ".shorts_thread_maker" / "debug"
        debug_dir.mkdir(parents=True, exist_ok=True)
        secure_dir_permissions(debug_dir)

        stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        screenshot_path = debug_dir / f"{prefix}_{stamp}.png"
        try:
            self.page.screenshot(path=str(screenshot_path))
            secure_file_permissions(screenshot_path)
            return str(screenshot_path)
        except Exception:
            return None

    # ========== 濡쒓렇??==========

    def check_login_status(self) -> bool:
        """濡쒓렇???곹깭 ?뺤씤 (紐낆떆???몄쬆 ?좏샇 湲곕컲)."""
        try:
            # 諛⑸쾿 1: 濡쒓렇???낅젰李?議댁옱 ?щ? (紐낇솗??濡쒓렇?꾩썐 ?좏샇)
            login_input = self.page.locator('input[name="username"], input[type="text"][placeholder*="?ъ슜??]').count()
            if login_input > 0:
                print("  濡쒓렇?꾩썐 ?곹깭 (濡쒓렇???낅젰李?議댁옱)")
                return False

            # 諛⑸쾿 2: URL 泥댄겕 (濡쒓렇???섏씠吏硫?紐낇솗??濡쒓렇?꾩썐)
            url = self.page.url
            if "login" in url.lower():
                print("  濡쒓렇?꾩썐 ?곹깭 (濡쒓렇???섏씠吏)")
                return False

            # 諛⑸쾿 3: Feed 寃뚯떆臾?議댁옱 (媛???뺤떎??濡쒓렇???좏샇)
            articles = self.page.locator('article').count()
            if articles > 0:
                print(f"  濡쒓렇???뺤씤 (?쇰뱶??{articles}媛?寃뚯떆臾?議댁옱)")
                return True

            # 諛⑸쾿 4: Navigation bar 議댁옱
            nav = self.page.locator('nav').count()
            if nav > 0:
                print("  濡쒓렇???뺤씤 (?대퉬寃뚯씠??諛?議댁옱)")
                return True

            # 諛⑸쾿 5: ?뱀젙 踰꾪듉??(蹂댁“ ?뺤씤)
            new_thread_btn = self.page.locator('a[aria-label*="New"], a[href*="compose"], button[aria-label*="New"]').count()
            if new_thread_btn > 0:
                print("  濡쒓렇???뺤씤 (???ㅻ젅??踰꾪듉 議댁옱)")
                return True

            profile_btn = self.page.locator('a[aria-label*="Profile"], a[href*="/profile"]').count()
            if profile_btn > 0:
                print("  濡쒓렇???뺤씤 (?꾨줈??踰꾪듉 議댁옱)")
                return True

            # 紐⑤뱺 ?뺤씤 ?ㅽ뙣
            print("  濡쒓렇???곹깭 遺덊솗??-> 誘몃줈洹몄씤?쇰줈 泥섎━")
            return False

        except Exception as e:
            print(f"  濡쒓렇???뺤씤 以??ㅻ쪟: {e}")
            return False

    def direct_login(self, username: str, password: str) -> bool:
        """
        吏곸젒 濡쒓렇??(Playwright selector ?ъ슜)

        Returns:
            True: ?깃났, False: ?ㅽ뙣
        """
        try:
            print("  Playwright濡?吏곸젒 濡쒓렇???쒕룄...")

            # 1. Username ?낅젰
            username_locator = self.page.locator('input[name="username"], input[type="text"][autocomplete*="username"]')
            if username_locator.count() > 0:
                username_input = username_locator.first
                username_input.click()
                username_input.fill(username)
                print("  ?ъ슜?먮챸 ?낅젰 ?꾨즺")
            else:
                print("  ?ъ슜?먮챸 ?낅젰李쎌쓣 李얠쓣 ???놁쓬")
                return False

            time.sleep(1)

            # 2. Password ?낅젰
            password_locator = self.page.locator('input[name="password"], input[type="password"]')
            if password_locator.count() > 0:
                password_input = password_locator.first
                password_input.click()
                password_input.fill(password)
                print("  鍮꾨?踰덊샇 ?낅젰 ?꾨즺")
            else:
                print("  鍮꾨?踰덊샇 ?낅젰李쎌쓣 李얠쓣 ???놁쓬")
                return False

            time.sleep(1)

            # 3. 濡쒓렇??踰꾪듉 ?대┃
            login_locator = self.page.locator('button[type="submit"], button:has-text("濡쒓렇??), button:has-text("Log in")')
            if login_locator.count() > 0:
                login_btn = login_locator.first
                login_btn.click()
                print("  濡쒓렇??踰꾪듉 ?대┃ ?꾨즺")
            else:
                print("  濡쒓렇??踰꾪듉??李얠쓣 ???놁쓬")
                return False

            # 4. 濡쒓렇???꾨즺 ?湲?(?ㅻ퉬寃뚯씠??
            time.sleep(5)

            # 5. 濡쒓렇???깃났 ?뺤씤
            return self.check_login_status()

        except Exception as e:
            print(f"  濡쒓렇???ㅽ뙣: {e}")
            self.last_error = str(e)
            return False

    def try_instagram_login(self) -> bool:
        """Instagram?쇰줈 怨꾩냽?섍린 踰꾪듉 ?쒕룄"""
        try:
            print("  Instagram ?먮룞 濡쒓렇???쒕룄...")

            # "Instagram?쇰줈 怨꾩냽?섍린" 踰꾪듉 李얘린
            instagram_locator = self.page.locator('button:has-text("Instagram"), a:has-text("Instagram")')

            if instagram_locator.count() > 0:
                instagram_btn = instagram_locator.first
                instagram_btn.click()
                print("  Instagram 濡쒓렇??踰꾪듉 ?대┃ ?꾨즺")
                time.sleep(5)
                return self.check_login_status()
            else:
                print("  Instagram 踰꾪듉??李얠쓣 ???놁쓬")
                return False

        except Exception as e:
            print(f"  Instagram 濡쒓렇???ㅽ뙣: {e}")
            return False

    def get_logged_in_username(self) -> Optional[str]:
        """
        ?꾩옱 濡쒓렇?몃맂 怨꾩젙???ъ슜?먮챸 ?뺤씤
        (?꾨줈???섏씠吏 URL?먯꽌 異붿텧 - 媛???뺤떎??諛⑸쾿)

        Returns:
            ?ъ슜?먮챸 ?먮뒗 None
        """
        try:
            current_url = self.page.url

            # 諛⑸쾿 1: ?꾨줈???꾩씠肄??대┃?댁꽌 ?먭린 ?꾨줈?꾨줈 ?대룞
            print("  ?꾨줈???섏씠吏濡??대룞?섏뿬 ?ъ슜?먮챸 ?뺤씤...")

            # ?꾨줈???꾩씠肄?踰꾪듉 ?대┃ ?쒕룄
            profile_btn_selectors = [
                'a[href*="/@"][role="link"]',  # ?꾨줈??留곹겕
                'nav a:last-child',  # ?ㅻ퉬寃뚯씠??留덉?留?(蹂댄넻 ?꾨줈??
                '[aria-label*="?꾨줈??]',
                '[aria-label*="Profile"]',
                'a[href*="/@"]:has(img)',  # ?대?吏媛 ?덈뒗 ?꾨줈??留곹겕
            ]

            for selector in profile_btn_selectors:
                try:
                    btns = self.page.locator(selector).all()
                    for btn in btns:
                        href = btn.get_attribute('href')
                        # ?꾨줈???섏씠吏 留곹겕留?(寃뚯떆臾??쒖쇅)
                        if href and '/@' in href and '/post/' not in href:
                            btn.click()
                            time.sleep(2)

                            # URL?먯꽌 ?ъ슜?먮챸 異붿텧
                            new_url = self.page.url
                            if '/@' in new_url:
                                username = new_url.split('/@')[-1].split('/')[0].split('?')[0]
                                if username:
                                    print(f"  ?꾨줈???섏씠吏 URL?먯꽌 ?ъ슜?먮챸 諛쒓껄: @{username}")
                                    # ?먮옒 ?섏씠吏濡??뚯븘媛湲?
                                    self.page.goto(current_url, wait_until="domcontentloaded", timeout=10000)
                                    return username
                except Exception:
                    continue

            # 諛⑸쾿 2: ?ㅼ젙 > 怨꾩젙 ?섏씠吏?먯꽌 ?뺤씤
            print("  ?ㅼ젙 ?섏씠吏?먯꽌 ?ъ슜?먮챸 ?뺤씤...")
            try:
                self.page.goto("https://www.threads.net/settings/account", wait_until="domcontentloaded", timeout=10000)
                time.sleep(2)

                # ?섏씠吏 ?띿뒪?몄뿉??@ 濡??쒖옉?섎뒗 ?ъ슜?먮챸 李얘린
                page_text = self.page.content()

                # @username ?⑦꽩 李얘린
                import re
                # ?ㅼ젙 ?섏씠吏???꾨줈???뱀뀡?먯꽌 ?ъ슜?먮챸
                username_match = re.search(r'/@([a-zA-Z0-9_.]+)', page_text)
                if username_match:
                    username = username_match.group(1)
                    print(f"  ?ㅼ젙 ?섏씠吏?먯꽌 ?ъ슜?먮챸 諛쒓껄: @{username}")
                    self.page.goto(current_url, wait_until="domcontentloaded", timeout=10000)
                    return username

            except Exception as e:
                print(f"  ?ㅼ젙 ?섏씠吏 ?뺤씤 ?ㅽ뙣: {e}")

            # 諛⑸쾿 3: ?⑥닚??濡쒓렇???먮떎怨좊쭔 ?쒖떆 (?ъ슜?먮챸 ?놁씠)
            print("  ?ъ슜?먮챸??李얠쓣 ???놁쓬 (濡쒓렇???곹깭留??뺤씤??")
            return None

        except Exception as e:
            print(f"  ?ъ슜?먮챸 ?뺤씤 ?ㅽ뙣: {e}")
            return None

    def verify_account(self, expected_username: str) -> bool:
        """濡쒓렇??怨꾩젙??湲곕? 怨꾩젙怨??ㅼ젣濡??쇱튂?섎뒗吏 ?뺤씤."""
        expected_raw = str(expected_username or "").strip()
        if not expected_raw:
            return self.check_login_status()

        if not self.check_login_status():
            print("  濡쒓렇?몃릺???덉? ?딆쓬")
            return False

        actual_username = self.get_logged_in_username()
        if not actual_username:
            print("  ?꾩옱 濡쒓렇?몃맂 ?ъ슜?먮챸???뺤씤?섏? 紐삵븿")
            return False

        expected_norm = expected_raw.lstrip("@").lower()
        if "@" in expected_norm and "." in expected_norm.split("@")[-1]:
            expected_norm = expected_norm.split("@", 1)[0]

        actual_norm = str(actual_username).lstrip("@").lower()
        matched = actual_norm == expected_norm
        if matched:
            print(f"  怨꾩젙 寃利??깃났: @{actual_norm}")
        else:
            print(f"  怨꾩젙 遺덉씪移? expected=@{expected_norm}, actual=@{actual_norm}")
        return matched

    def logout(self) -> bool:
        """
        ?꾩옱 怨꾩젙?먯꽌 濡쒓렇?꾩썐

        Returns:
            True: ?깃났, False: ?ㅽ뙣
        """
        try:
            print("  濡쒓렇?꾩썐 ?쒕룄...")

            # ?ㅼ젙 ?섏씠吏濡??대룞
            self.page.goto("https://www.threads.net/settings", wait_until="domcontentloaded", timeout=15000)
            time.sleep(2)

            # 濡쒓렇?꾩썐 踰꾪듉 李얘린
            logout_selectors = [
                'div[role="button"]:has-text("濡쒓렇?꾩썐")',
                'button:has-text("濡쒓렇?꾩썐")',
                'div[role="button"]:has-text("Log out")',
                'button:has-text("Log out")',
                'a:has-text("濡쒓렇?꾩썐")',
                'a:has-text("Log out")',
            ]

            for selector in logout_selectors:
                try:
                    btn = self.page.locator(selector).first
                    if btn.count() > 0:
                        btn.click()
                        print("  濡쒓렇?꾩썐 踰꾪듉 ?대┃ ?꾨즺")
                        time.sleep(2)

                        # ?뺤씤 ?ㅼ씠?쇰줈洹멸? ?덉쑝硫??뺤씤 ?대┃
                        confirm_selectors = [
                            'button:has-text("濡쒓렇?꾩썐")',
                            'button:has-text("Log out")',
                            'div[role="button"]:has-text("濡쒓렇?꾩썐")',
                        ]
                        for confirm_sel in confirm_selectors:
                            try:
                                confirm_btn = self.page.locator(confirm_sel).first
                                if confirm_btn.count() > 0:
                                    confirm_btn.click()
                                    print("  濡쒓렇?꾩썐 ?뺤씤 ?꾨즺")
                                    time.sleep(3)
                                    break
                            except Exception:
                                continue

                        print("  濡쒓렇?꾩썐 ?꾨즺")
                        return True
                except Exception:
                    continue

            # ?꾨줈??硫붾돱?먯꽌 濡쒓렇?꾩썐 ?쒕룄
            print("  ?꾨줈??硫붾돱?먯꽌 濡쒓렇?꾩썐 ?쒕룄...")
            self.page.goto("https://www.threads.net", wait_until="domcontentloaded", timeout=15000)
            time.sleep(2)

            # ?꾨줈???꾩씠肄??대┃
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
                except Exception:
                    continue

            # ?ㅼ젙/濡쒓렇?꾩썐 硫붾돱 李얘린
            menu_btn = self.page.locator('svg[aria-label*="硫붾돱"], svg[aria-label*="Menu"], button:has-text("??)').first
            if menu_btn.count() > 0:
                menu_btn.click()
                time.sleep(1)

                for selector in logout_selectors:
                    try:
                        btn = self.page.locator(selector).first
                        if btn.count() > 0:
                            btn.click()
                            time.sleep(3)
                            print("  濡쒓렇?꾩썐 ?꾨즺")
                            return True
                    except Exception:
                        continue

            print("  濡쒓렇?꾩썐 踰꾪듉??李얠쓣 ???놁쓬")
            return False

        except Exception as e:
            print(f"  濡쒓렇?꾩썐 ?ㅽ뙣: {e}")
            return False

    def ensure_login(self, username: str = "", password: str = "") -> bool:
        """
        濡쒓렇??蹂댁옣 - ?ㅼ젙??怨꾩젙?쇰줈 濡쒓렇???뺤씤

        Args:
            username: Instagram ?ъ슜?먮챸
            password: Instagram 鍮꾨?踰덊샇

        Returns:
            True: 濡쒓렇???깃났, False: ?ㅽ뙣
        """
        # 1. ?꾩옱 濡쒓렇???곹깭 ?뺤씤
        if self.check_login_status():
            # 怨꾩젙 寃利?
            if username and not self.verify_account(username):
                print("  ?ㅻⅨ 怨꾩젙?쇰줈 濡쒓렇?몃릺???덉쓬 - ?먮룞 濡쒓렇?꾩썐 ?쒕룄")

                # 濡쒓렇?꾩썐 ?쒕룄
                if self.logout():
                    print("  濡쒓렇?꾩썐 ?깃났 - ?ㅼ젙??怨꾩젙?쇰줈 濡쒓렇???쒕룄")
                    # 濡쒓렇???섏씠吏濡??대룞
                    self.page.goto("https://www.threads.net/login", wait_until="domcontentloaded", timeout=15000)
                    time.sleep(2)
                else:
                    print("  ?먮룞 濡쒓렇?꾩썐 ?ㅽ뙣 - ?섎룞?쇰줈 濡쒓렇?꾩썐 ???ㅼ떆 ?쒕룄?댁＜?몄슂")
                    return False
            else:
                return True

        # 2. 濡쒓렇???꾩슂 - 吏곸젒 濡쒓렇???쒕룄
        if username and password:
            print(f"  ?ㅼ젙??怨꾩젙?쇰줈 濡쒓렇???쒕룄: {username}")
            if self.direct_login(username, password):
                return self.verify_account(username)

        # 3. Instagram ?먮룞 濡쒓렇???쒕룄 (湲곗〈 ?몄뀡 ?ъ슜)
        if self.try_instagram_login():
            if username:
                return self.verify_account(username)
            return True

        print("  濡쒓렇???ㅽ뙣")
        return False

    # ========== ?곕젅???묒꽦 ==========

    def click_new_thread(self) -> bool:
        """
        New thread 踰꾪듉 ?대┃

        Returns:
            True: ?깃났, False: ?ㅽ뙣
        """
        try:
            # ?щ윭 selector ?쒕룄
            selectors = [
                'a[aria-label*="New"]',
                'a[href*="compose"]',
                'button[aria-label*="New"]',
                'a[role="link"]:has-text("+")',
                # 醫뚰몴 湲곕컲 fallback (?쇱そ ?ъ씠?쒕컮 以묎컙易?
            ]

            for selector in selectors:
                btn = self.page.locator(selector).first
                if btn.count() > 0:
                    btn.click()
                    print(f"  ???ㅻ젅??踰꾪듉 ?대┃ ?꾨즺 ({selector})")
                    time.sleep(2)
                    return True

            # Fallback: 醫뚰몴 ?대┃ (x=30, y=460 normalized)
            print("  ?좏깮???ㅽ뙣, 醫뚰몴濡??쒕룄...")
            self.page.mouse.click(30, 460)
            time.sleep(2)
            return True

        except Exception as e:
            print(f"  ???ㅻ젅??踰꾪듉 ?대┃ ?ㅽ뙣: {e}")
            return False

    def dismiss_login_popup(self) -> bool:
        """濡쒓렇???앹뾽 ?リ린"""
        try:
            # Escape ??
            self.page.keyboard.press("Escape")
            time.sleep(1)
            return True
        except Exception:
            # ?앹뾽 諛붽묑 ?대┃
            try:
                self.page.mouse.click(50, 50)
                time.sleep(1)
                return True
            except Exception:
                return False

    def count_textareas(self) -> int:
        """
        Compose 李쎌쓽 textarea 媛쒖닔 ?뺤씤

        Returns:
            textarea 媛쒖닔
        """
        try:
            # ?ㅼ뼇??textarea selector
            textareas = self.page.locator('textarea, div[contenteditable="true"]').count()
            return textareas
        except Exception:
            return 0

    def find_empty_textarea_index(self) -> Optional[int]:
        """
        鍮꾩뼱 ?덈뒗 textarea/contenteditable index 李얘린 (?덈줈 ?앹꽦??諛뺤뒪瑜??곗꽑 ?ъ슜)

        Returns:
            鍮꾩뼱 ?덈뒗 textarea index (?놁쑝硫?None)
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
                # ?덈줈 異붽???textarea媛 DOM ?앹뿉 ?ㅻ뒗 寃쎌슦媛 留롮븘 留덉?留?鍮?移몄쓣 ?곗꽑 ?ъ슜
                return empty_indices[-1]

        except Exception as e:
            print(f"      WARN: find_empty_textarea_index failed: {e}")

        return None

    def type_in_textarea(self, text: str, index: int = 0, require_empty: bool = False) -> bool:
        """
        ?뱀젙 textarea???띿뒪???낅젰

        Args:
            text: ?낅젰???띿뒪??
            index: textarea ?몃뜳??(0遺???쒖옉)
            require_empty: True硫?湲곗〈 ?댁슜???덈뒗 寃쎌슦 ??뼱?곗? ?딄퀬 ?ㅽ뙣 泥섎━

        Returns:
            True: ?깃났, False: ?ㅽ뙣
        """
        try:
            textareas = self.page.locator('textarea, div[contenteditable="true"]')
            total_textareas = textareas.count()

            print(f"      [type_in_textarea] ?꾩껜 textarea 媛쒖닔: {total_textareas}, ?낅젰??index: {index}")

            if total_textareas <= index:
                print(f"      Textarea[{index}] 議댁옱?섏? ?딆쓬 (珥?{total_textareas}媛?")
                return False

            textarea = textareas.nth(index)

            # ?붾쾭洹? textarea ?뺣낫 異쒕젰
            try:
                tag_name = textarea.evaluate("el => el.tagName")
                existing_text = textarea.evaluate("el => el.value || el.innerText || ''")
                trimmed_existing = (existing_text or "").strip()
                print(
                    f"      Textarea[{index}] tag={tag_name}, existing_len={len(trimmed_existing)}"
                )
            except Exception:
                trimmed_existing = ""

            if require_empty and trimmed_existing:
                print(f"      Textarea[{index}]??湲곗〈 ?댁슜???덉뼱 ??뼱?곗? ?딆쓬")
                return False

            # ?대┃ ???낅젰
            textarea.click()
            time.sleep(0.5)

            # 湲곗〈 ?댁슜 吏?곌린
            if trimmed_existing or not require_empty:
                self.page.keyboard.press("Control+A")
                self.page.keyboard.press("Backspace")

            # ?띿뒪???낅젰
            textarea.fill(text)
            time.sleep(0.5)

            # ?낅젰 ???뺤씤
            try:
                after_text = textarea.evaluate("el => el.value || el.innerText || ''")
                print(f"      Textarea[{index}]???낅젰 ?꾨즺 (?낅젰 {len(text)}?? ?꾩옱 {len(str(after_text or ''))}??")
            except Exception:
                print(f"      Textarea[{index}]???낅젰 ?꾨즺 ({len(text)}??")

            return True

        except Exception as e:
            print(f"      Textarea[{index}] ?낅젰 ?ㅽ뙣: {e}")
            return False

    def click_add_to_thread(self) -> bool:
        """
        '?ㅻ젅?쒖뿉 異붽?' 踰꾪듉/?곸뿭 ?대┃

        Returns:
            True: ?깃났, False: ?ㅽ뙣
        """
        try:
            # ?ㅼ뼇??selector ?쒕룄 (?곗꽑?쒖쐞 ??
            selectors = [
                # 1. Playwright text selector (?뺥솗???띿뒪??留ㅼ묶)
                'text=?ㅻ젅?쒖뿉 異붽?',
                'text=Add to thread',

                # 2. ?뺥솗???띿뒪?몃? 媛吏??붿냼 (text-is???뺥솗留ㅼ묶)
                'div:text-is("?ㅻ젅?쒖뿉 異붽?")',
                'span:text-is("?ㅻ젅?쒖뿉 異붽?")',
                'button:text-is("?ㅻ젅?쒖뿉 異붽?")',

                # 3. ?쒓? ?쒓린 (has-text??遺遺?留ㅼ묶)
                'div:has-text("?ㅻ젅?쒖뿉 異붽?")',
                'span:has-text("?ㅻ젅?쒖뿉 異붽?")',
                'button:has-text("?ㅻ젅?쒖뿉 異붽?")',
                'a:has-text("?ㅻ젅?쒖뿉 異붽?")',

                # 4. ?곸뼱
                'div:has-text("Add to thread")',
                'span:has-text("Add to thread")',
                'button:has-text("Add to thread")',
                'a:has-text("Add to thread")',

                # 5. 遺遺??띿뒪??- visible 議곌굔 異붽?
                'div:has-text("?ㅻ젅??) >> visible=true',
                'span:has-text("?ㅻ젅?쒖뿉")',

                # 6. ?대┃ 媛?ν븳 div (role ?먮뒗 tabindex) - ?띿뒪??寃利??꾩닔
                'div[role="button"]',
                'div[tabindex="0"]',

                # 7. 愿묐쾾??- compose 李??댁쓽 紐⑤뱺 ?대┃ 媛???붿냼
                'form div[role="button"]',
                'form div[tabindex]',
            ]

            print(f"  '?ㅻ젅?쒖뿉 異붽?' 踰꾪듉 李얜뒗 以?..")

            for i, selector in enumerate(selectors):
                try:
                    btn = self.page.locator(selector).first
                    count = btn.count()

                    if count > 0:
                        # ?붾쾭洹? ?대┃???붿냼 ?뺣낫 癒쇱? ?뺤씤
                        element_text = btn.evaluate("el => el.innerText || el.textContent || el.placeholder || ''")
                        element_tag = btn.evaluate("el => el.tagName")

                        print(f"    ?꾨낫 諛쒓껄 (selector #{i+1}): <{element_tag}> '{element_text[:50]}'")

                        # text selector???뺥솗?섎?濡?諛붾줈 ?대┃
                        if selector.startswith('text='):
                            print(f"    text selector - 諛붾줈 ?대┃")
                            btn.click()
                            print(f"    '?ㅻ젅?쒖뿉 異붽?' 踰꾪듉 ?대┃ ?꾨즺")
                            time.sleep(2)
                            return True

                        # "?ㅻ젅?쒖뿉 異붽?"媛 ?ы븿?섏뼱 ?덉쑝硫??곗꽑 ?덉슜
                        if "?ㅻ젅?쒖뿉 異붽?" in element_text or "add to thread" in element_text.lower():
                            print(f"    '?ㅻ젅?쒖뿉 異붽?' ?띿뒪???ы븿 - ?대┃")
                            btn.click()
                            print(f"    '?ㅻ젅?쒖뿉 異붽?' 踰꾪듉 ?대┃ ?꾨즺")
                            time.sleep(2)
                            return True

                        # ?띿뒪?멸? ?덈Т 湲몃㈃ 而⑦뀒?대꼫 DIV??媛?μ꽦 ?믪쓬 (100???댁긽)
                        if len(element_text) > 100:
                            print(f"    ?쒖쇅?? ?띿뒪???덈Т 湲몄쓬 ({len(element_text)}?? - 而⑦뀒?대꼫 DIV")
                            continue

                        # Exclude obvious non-target action buttons.
                        exclude_texts = ["create", "post", "publish", "cancel", "close"]
                        if any(exc in element_text.lower() for exc in exclude_texts):
                            print(f"    ?쒖쇅?? '{element_text[:30]}' (?섎せ??踰꾪듉)")
                            continue

                        # "?ㅻ젅?쒖뿉 異붽?" ?먮뒗 "?댁슜????異붽?" ?띿뒪???ы븿 ?щ? ?뺤씤
                        valid_texts = ["add to thread", "add more", "thread", "add"]
                        if selector in ['div[role="button"]', 'div[tabindex="0"]', 'form div[role="button"]', 'form div[tabindex]']:
                            # 愿묐쾾?꾪븳 selector???띿뒪??寃利??꾩닔
                            if not any(valid in element_text.lower() for valid in valid_texts):
                                print(f"    ?쒖쇅?? '{element_text[:30]}' (愿???띿뒪???놁쓬)")
                                continue

                        print(f"    ?щ컮瑜?踰꾪듉 ?뺤씤")
                        btn.click()
                        print(f"    '?ㅻ젅?쒖뿉 異붽?' 踰꾪듉 ?대┃ ?꾨즺")
                        time.sleep(2)  # UI ?낅뜲?댄듃 ?湲?
                        return True
                except Exception as e:
                    # ??selector???ㅽ뙣, ?ㅼ쓬?쇰줈
                    continue

            # 紐⑤뱺 selector ?ㅽ뙣 - ?붾쾭洹??뺣낫 異쒕젰
            print("  '?ㅻ젅?쒖뿉 異붽?' 踰꾪듉??李얠쓣 ???놁쓬 (紐⑤뱺 selector ?ㅽ뙣)")
            print("  ?섏씠吏??紐⑤뱺 ?대┃ 媛???붿냼 遺꾩꽍 以?..")

            try:
                # 紐⑤뱺 踰꾪듉, div[role=button], div[tabindex] 李얘린
                all_buttons = self.page.locator('button, div[role="button"], div[tabindex], a[role="button"]').all()
                print(f"  珥?{len(all_buttons)}媛??대┃ 媛???붿냼 諛쒓껄:")

                for idx, btn in enumerate(all_buttons[:20]):  # 泥섏쓬 20媛쒕쭔
                    try:
                        tag = btn.evaluate("el => el.tagName")
                        text = btn.evaluate("el => (el.innerText || el.textContent || el.placeholder || el.getAttribute('aria-label') || '').substring(0, 50)")
                        role = btn.evaluate("el => el.getAttribute('role') || ''")
                        classes = btn.evaluate("el => el.className || ''")
                        print(f"      [{idx}] <{tag}> role={role} text='{text}' class='{classes[:30]}'")
                    except Exception:
                        pass

                debug_path = self._save_debug_screenshot("debug_add_button")
                if debug_path:
                    print(f"  Debug screenshot saved: {debug_path}")
            except Exception as e:
                print(f"  ?붾쾭洹??뺣낫 異쒕젰 ?ㅽ뙣: {e}")

            return False

        except Exception as e:
            print(f"  '?ㅻ젅?쒖뿉 異붽?' 踰꾪듉 ?대┃ ?ㅽ뙣: {e}")
            return False

    def click_post_button(self) -> bool:
        """
        Post 踰꾪듉 ?대┃

        Returns:
            True: ?깃났, False: ?ㅽ뙣
        """
        try:
            print("  寃뚯떆 踰꾪듉 李얜뒗 以?..")

            # 1李? Playwright 吏곸젒 ?대┃ - ?섎떒 ?곗륫??"寃뚯떆" 踰꾪듉 李얘린
            try:
                # "寃뚯떆" ?띿뒪?몃? 媛吏?踰꾪듉 李얘린
                post_btns = self.page.locator('div[role="button"]').all()
                target_btn = None
                max_y = -1  # Y醫뚰몴媛 媛????踰꾪듉 (?붾㈃ ?섎떒???꾩튂)

                for btn in post_btns:
                    try:
                        text = btn.inner_text().strip()
                        if text in ['寃뚯떆', 'Post', '寃뚯떆?섍린']:
                            box = btn.bounding_box()
                            if box and box['width'] > 0 and box['height'] > 0:
                                # ?섎떒???덈뒗 踰꾪듉 ?좏깮 (Y醫뚰몴媛 ??寃?
                                if box['y'] > max_y:
                                    max_y = box['y']
                                    target_btn = btn
                    except Exception:
                        continue

                if target_btn:
                    box = target_btn.bounding_box()
                    if box:
                        click_x = box['x'] + box['width'] / 2
                        click_y = box['y'] + box['height'] / 2
                        print(f"  寃뚯떆 踰꾪듉 諛쒓껄 (?섎떒): ({click_x:.0f}, {click_y:.0f})")

                        # 留덉슦?ㅻ줈 吏곸젒 ?대┃
                        self.page.mouse.click(click_x, click_y)
                        print(f"  寃뚯떆 踰꾪듉 留덉슦???대┃ ?꾨즺")
                        time.sleep(5)
                        return True

            except Exception as e:
                print(f"  Playwright 吏곸젒 ?대┃ ?ㅽ뙣: {e}")

            # 2李? JavaScript濡??대┃ (fallback) - ?섎떒 踰꾪듉 李얘린
            try:
                result = self.page.evaluate("""
                    () => {
                        const elements = document.querySelectorAll('div[role="button"], button');
                        let postBtn = null;
                        let maxY = -1;

                        for (const el of elements) {
                            const text = (el.innerText || el.textContent || '').trim();
                            if (text === '寃뚯떆' || text === 'Post' || text === '寃뚯떆?섍린') {
                                const rect = el.getBoundingClientRect();
                                if (rect.width > 0 && rect.height > 0) {
                                    // ?섎떒???덈뒗 踰꾪듉 ?좏깮 (Y醫뚰몴媛 ??寃?
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
                    print(f"  寃뚯떆 踰꾪듉 JS ?대┃ ?깃났 ({result})")
                    time.sleep(5)
                    return True

            except Exception as e:
                print(f"  JS ?대┃ ?쒕룄 ?ㅽ뙣: {e}")

            # 2李? Playwright force ?대┃ (?붿냼 媛由?臾댁떆)
            try:
                print("  Playwright force ?대┃ ?쒕룄...")
                selectors = [
                    'div[role="button"]:has-text("寃뚯떆")',
                    'div[role="button"]:has-text("Post")',
                    'button:has-text("寃뚯떆")',
                    'button:has-text("Post")',
                ]

                for selector in selectors:
                    btns = self.page.locator(selector)
                    count = btns.count()

                    # 媛???섎떒 踰꾪듉 李얘린 (Y醫뚰몴媛 ??寃?
                    bottom_btn = None
                    bottom_y = -1

                    for idx in range(count):
                        btn = btns.nth(idx)
                        try:
                            text = btn.inner_text().strip()
                            if text in ['寃뚯떆', 'Post', '寃뚯떆?섍린']:
                                box = btn.bounding_box()
                                if box and box['y'] > bottom_y:
                                    bottom_y = box['y']
                                    bottom_btn = btn
                        except Exception:
                            continue

                    if bottom_btn:
                        # force=True濡??대┃ (?ㅻⅨ ?붿냼媛 媛?ㅻ룄 ?대┃)
                        bottom_btn.click(force=True)
                        print(f"  寃뚯떆 踰꾪듉 force ?대┃ ?깃났 (y={bottom_y})")
                        time.sleep(5)
                        return True

            except Exception as e:
                print(f"  Force ?대┃ ?쒕룄 ?ㅽ뙣: {e}")

            # 3李? Ctrl+Enter ?⑥텞??
            try:
                print("  Ctrl+Enter ?쒕룄...")
                textareas = self.page.locator('div[contenteditable="true"]')
                if textareas.count() > 0:
                    textareas.last.focus()
                    time.sleep(0.3)

                self.page.keyboard.press("Control+Enter")
                time.sleep(5)
                print("  Ctrl+Enter ?꾩넚 ?꾨즺")
                return True

            except Exception as e:
                print(f"  Ctrl+Enter ?쒕룄 ?ㅽ뙣: {e}")

            # 4李? 醫뚰몴 湲곕컲 ?대┃ (?ㅼ씠?쇰줈洹??섎떒 ?곗륫 ?곸뿭)
            try:
                print("  醫뚰몴 湲곕컲 ?대┃ ?쒕룄...")
                viewport = self.page.viewport_size
                if viewport:
                    # ?ㅼ씠?쇰줈洹??섎떒 ?곗륫 ?곸뿭 (寃뚯떆 踰꾪듉??蹂댄넻 ?ш린 ?덉쓬)
                    # ?ㅼ씠?쇰줈洹몃뒗 蹂댄넻 ?붾㈃ 以묒븰???꾩튂, 寃뚯떆 踰꾪듉? ?ㅼ씠?쇰줈洹??섎떒 ?곗륫
                    x = viewport['width'] // 2 + 200  # 以묒븰?먯꽌 ?곗륫?쇰줈
                    y = viewport['height'] // 2 + 200  # 以묒븰?먯꽌 ?섎떒?쇰줈
                    self.page.mouse.click(x, y)
                    print(f"  醫뚰몴 ?대┃ ?꾨즺 ({x}, {y})")
                    time.sleep(5)
                    return True
            except Exception as e:
                print(f"  醫뚰몴 ?대┃ ?ㅽ뙣: {e}")

            print("  寃뚯떆 踰꾪듉 ?대┃ 紐⑤뱺 諛⑸쾿 ?ㅽ뙣")
            try:
                debug_path = self._save_debug_screenshot("debug_post_button")
                if debug_path:
                    print(f"  Debug screenshot saved: {debug_path}")
            except Exception:
                pass
            return False

        except Exception as e:
            print(f"  寃뚯떆 踰꾪듉 ?대┃ ?ㅽ뙣: {e}")
            return False

    # ========== ?대?吏 ?낅줈??==========

    def upload_image(self, image_path: str) -> bool:
        """
        ?대?吏 ?뚯씪 ?낅줈??

        Args:
            image_path: 濡쒖뺄 ?대?吏 ?뚯씪 寃쎈줈

        Returns:
            True: ?깃났, False: ?ㅽ뙣
        """
        import os
        try:
            if not image_path or not os.path.exists(image_path):
                print(f"  ?대?吏 ?뚯씪 ?놁쓬: {image_path}")
                return False

            print(f"  ?대?吏 ?낅줈??以? {image_path}")

            # ?뚯씪 ?낅젰 ?붿냼 李얘린
            file_input = self.page.locator('input[type="file"][accept*="image"]')

            if file_input.count() > 0:
                file_input.set_input_files(os.path.abspath(image_path))
                time.sleep(3)  # ?대?吏 ?낅줈???湲?
                print(f"  ?대?吏 ?낅줈???꾨즺")
                return True
            else:
                print(f"  ?대?吏 ?낅줈??input ?붿냼瑜?李얠쓣 ???놁쓬")
                return False

        except Exception as e:
            print(f"  ?대?吏 ?낅줈???ㅽ뙣: {e}")
            return False

    # ========== ?듯빀 ?뚰겕?뚮줈??==========

    def create_thread_direct(self, posts_data) -> bool:
        """
        Playwright濡?吏곸젒 ?ㅻ젅???앹꽦 (AI ?놁씠)

        Args:
            posts_data: ?ъ뒪???곗씠??由ъ뒪??
                       - List[str]: 臾몃떒 ?띿뒪??由ъ뒪??(湲곗〈 諛⑹떇)
                       - List[dict]: [{'text': '...', 'image_path': '...'}, ...]

        Returns:
            True: ?깃났, False: ?ㅽ뙣
        """
        try:
            # posts_data ????뺤씤 諛?蹂??
            if posts_data and isinstance(posts_data[0], str):
                # 湲곗〈 諛⑹떇: 臾몄옄??由ъ뒪??
                paragraphs = posts_data
                first_image = None
            else:
                # ??諛⑹떇: dict 由ъ뒪??
                paragraphs = [post.get('text', '') for post in posts_data]
                first_image = posts_data[0].get('image_path') if posts_data else None

            total = len(paragraphs)
            print(f"\n  Playwright濡?{total}媛?臾몃떒 ?ㅻ젅???묒꽦 ?쒖옉")
            if first_image:
                print(f"  泥?踰덉㎏ 湲???대?吏 泥⑤? ?덉젙: {first_image}")

            # 1. New thread 踰꾪듉 ?대┃
            if not self.click_new_thread():
                return False

            # 濡쒓렇???앹뾽 泥댄겕
            time.sleep(1)
            page_text = self.page.content().lower()
            if "log in" in page_text or "login" in page_text or "sign in" in page_text:
                print("  濡쒓렇???앹뾽 媛먯?, ?リ린 ?쒕룄")
                if not self.dismiss_login_popup():
                    print("  濡쒓렇???앹뾽 ?リ린 ?ㅽ뙣")
                    return False
                # ?ㅼ떆 New thread ?대┃
                if not self.click_new_thread():
                    return False

            # 2. 泥?踰덉㎏ 臾몃떒 ?낅젰
            if not self.type_in_textarea(paragraphs[0], index=0):
                return False

            # 2-1. 泥?踰덉㎏ 湲???대?吏 ?낅줈??(?덈뒗 寃쎌슦)
            if first_image:
                self.upload_image(first_image)

            # 3. ?섎㉧吏 臾몃떒??異붽?
            for i in range(1, total):
                print(f"\n  [{i+1}/{total}] 臾몃떒 異붽? 以?..")

                # ?꾩옱 textarea 媛쒖닔 ?뺤씤
                textarea_count_before = self.count_textareas()
                print(f"    [?꾩옱] Textarea 媛쒖닔: {textarea_count_before}")
                expected_count = i + 1

                # 3-1. UI媛 ?먮룞?쇰줈 ?앹꽦?섎뒗吏 ?좎떆 ?湲?
                if textarea_count_before < expected_count:
                    print(f"    UI ?먮룞 ?앹꽦 ?湲?以?..")
                    time.sleep(1)
                    textarea_count_after_wait = self.count_textareas()
                    if textarea_count_after_wait >= expected_count:
                        print(f"    Textarea {expected_count}媛??먮룞 ?앹꽦??(踰꾪듉 ?대┃ 遺덊븘??")
                    else:
                        print(f"    ?먮룞 ?앹꽦 ????({textarea_count_after_wait}/{expected_count})")

                # 3-2. ?대? 異⑸텇??textarea媛 ?덈뒗吏 ?뺤씤
                textarea_count_current = self.count_textareas()
                if textarea_count_current >= expected_count:
                    print(f"    Textarea {expected_count}媛?議댁옱 (踰꾪듉 ?대┃ 遺덊븘??")
                else:
                    # 3-2. '?ㅻ젅?쒖뿉 異붽?' ?대┃
                    print(f"    '?ㅻ젅?쒖뿉 異붽?' 踰꾪듉 ?대┃ ?꾩슂...")
                    if not self.click_add_to_thread():
                        print(f"    '?ㅻ젅?쒖뿉 異붽?' 踰꾪듉??李얠쓣 ???놁쓬")
                        return False

                    # 3-3. 踰꾪듉 ?대┃ ??textarea 媛쒖닔 ?뺤씤
                    time.sleep(1.5)
                    textarea_count_after = self.count_textareas()
                    print(f"    [?대┃ ?? Textarea 媛쒖닔: {textarea_count_after}")

                    if textarea_count_after < expected_count:
                        print(f"    Textarea ?앹꽦 ?ㅽ뙣 ({textarea_count_after}/{expected_count})")
                        print(f"    ?섎せ???붿냼瑜??대┃?덇굅??UI媛 蹂寃쎈맖")
                        # ?붾쾭洹??ㅽ겕由곗꺑
                        try:
                            debug_path = self._save_debug_screenshot(f"debug_failed_add_{i}")
                            if debug_path:
                                print(f"    Debug screenshot saved: {debug_path}")
                        except Exception:
                            pass
                        return False

                    print(f"    Textarea {expected_count}媛??뺤씤")

                # 3-4. ??textarea???낅젰 (湲곗〈 ?댁슜 蹂댁〈)
                target_index = self.find_empty_textarea_index()
                if target_index is None:
                    print("    鍮?textarea瑜?李얠? 紐삵빐 留덉?留?textarea???낅젰 ?쒕룄")
                    textarea_count_current = self.count_textareas()
                    target_index = textarea_count_current - 1 if textarea_count_current > 0 else i
                else:
                    print(f"    鍮?textarea 諛쒓껄: index {target_index}")

                print(f"    Textarea[{target_index}]???낅젰 ?쒕룄...")
                if not self.type_in_textarea(paragraphs[i], index=target_index, require_empty=True):
                    print("    ???textarea???낅젰 ?ㅽ뙣, ?ㅻⅨ 鍮?textarea ?먯깋...")
                    typed = False
                    textareas_total = self.count_textareas()
                    for alt_idx in range(textareas_total):
                        if alt_idx == target_index:
                            continue
                        if self.type_in_textarea(paragraphs[i], index=alt_idx, require_empty=True):
                            typed = True
                            break
                    if not typed:
                        print("    鍮?textarea???낅젰?섏? 紐삵븿 (??뼱?곌린瑜?諛⑹??섍린 ?꾪빐 以묐떒)")
                        return False

            # 4. 理쒖쥌 寃利?
            print(f"\n  理쒖쥌 寃利?..")
            final_count = self.count_textareas()
            if final_count != total:
                print(f"  Textarea 媛쒖닔 遺덉씪移?({final_count}/{total})")

            # 5. Post 踰꾪듉 ?대┃
            print(f"\n  寃뚯떆 以?..")
            if not self.click_post_button():
                return False

            # 6. 寃뚯떆 ?꾨즺 寃利?(?꾨줈??理쒖떊 湲 留ㅼ묶)
            if not self.verify_post_success(paragraphs[0] if paragraphs else ""):
                print("  寃뚯떆 寃利??ㅽ뙣 (?꾨줈?꾩뿉??理쒖떊 湲 ?뺤씤 遺덇?)")
                return False

            print(f"\n  ?ㅻ젅??寃뚯떆 ?꾨즺")
            return True

        except Exception as e:
            print(f"\n  ?ㅻ젅???묒꽦 ?ㅽ뙣: {e}")
            self.last_error = str(e)
            return False

    def verify_post_success(self, first_paragraph: str = "") -> bool:
        """
        寃뚯떆 ?깃났 ?щ? ?뺤씤 (DOM 泥댄겕)

        Returns:
            True: ?깃났, False: ?ㅽ뙣
        """
        try:
            # 寃뚯떆 泥섎━ ?湲?(Threads媛 ?쒕쾭???꾩넚?섎뒗 ?쒓컙)
            print("  寃뚯떆 泥섎━ ?湲?以?..")
            time.sleep(3)

            # Compose 李쎌씠 ?ロ삍?붿? ?뺤씤 (?щ윭 踰??쒕룄)
            for attempt in range(3):
                # "寃뚯떆" 踰꾪듉???ъ쟾??蹂댁씠?붿? ?뺤씤 (compose 李쎌씠 ?대젮?덈뒗 ???뺥솗??吏??
                post_btn_visible = self.page.locator('div[role="button"]:has-text("寃뚯떆"), div[role="button"]:has-text("Post")').count() > 0

                # compose 紐⑤떖 泥댄겕 (role="dialog"???뱀젙 ?대옒??
                compose_modal = self.page.locator('div[role="dialog"]').count() > 0

                if not post_btn_visible and not compose_modal:
                    print("  Compose 李쎌씠 ?ロ삍?듬땲??- 寃뚯떆 ?깃났")
                    return True

                if attempt < 2:
                    print(f"  Compose 李??ロ옒 ?湲?以?.. ({attempt + 1}/3)")
                    time.sleep(2)

            # 留덉?留됱쑝濡?URL 蹂寃??뺤씤 (compose?먯꽌 踰쀬뼱?щ뒗吏)
            current_url = self.page.url
            if '/compose' not in current_url.lower():
                print(f"  compose ?섏씠吏?먯꽌 ?대룞??- 寃뚯떆 ?깃났 異붿젙")
                return True

            # compose ?곹깭媛 ?좎??섎㈃ ?ㅼ젣 寃뚯떆 ?ㅽ뙣濡??먮떒
            print("  compose ?곹깭媛 ?좎???- 寃뚯떆 ?ㅽ뙣濡??먮떒")
            return False

        except Exception as e:
            print(f"  寃利?以??ㅻ쪟: {e}")
            return False

