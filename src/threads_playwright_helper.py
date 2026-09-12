# -*- coding: utf-8 -*-
"""
Threads Playwright 직접 제어 헬퍼
AI Vision 없이 Playwright selector로 직접 제어 (빠르고 안정적)
"""
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

try:
    from playwright.sync_api import Page
except ModuleNotFoundError:
    Page = Any  # type: ignore[assignment]

from src.fs_security import secure_dir_permissions, secure_file_permissions
from src.threads_navigation import goto_threads_with_fallback


class ThreadsPlaywrightHelper:
    """
    Threads 웹사이트 직접 제어 (Playwright selector 기반)
    AI Vision 대비 장점:
    - 빠름 (스크린샷 전송 없음)
    - 확실함 (selector 기반 직접 제어)
    - 검증 가능 (DOM 상태 직접 확인)
    """

    # Identity evidence is intentionally restricted to controls whose accessible
    # name explicitly identifies the signed-in user's own profile navigation.
    # Generic /@ links, feed authors, page text and public profile URLs must never
    # be used to prove which account owns the current browser session.
    _SELF_PROFILE_LINK_SELECTORS = (
        'nav a[aria-label="Profile"][href*="/@"]',
        'nav a[aria-label="프로필"][href*="/@"]',
        'nav a[aria-label="Your profile"][href*="/@"]',
        'nav a[aria-label="내 프로필"][href*="/@"]',
        'nav a[href*="/@"]:has(svg[aria-label="Profile"])',
        'nav a[href*="/@"]:has(svg[aria-label="프로필"])',
        'a[data-testid="nav-profile"][href*="/@"]',
    )
    _THREADS_PROFILE_HOSTS = {
        "threads.net",
        "www.threads.net",
        "threads.com",
        "www.threads.com",
    }
    _THREADS_USERNAME_PATTERN = re.compile(r"[A-Za-z0-9._]{1,30}")
    _COMPOSE_CONTAINER_SELECTORS = (
        'div[role="dialog"]',
        'form',
        '[data-testid*="composer"]',
        '[data-testid*="compose"]',
    )
    _COMPOSE_EDITOR_SELECTOR = 'textarea, div[contenteditable="true"]'
    _COMPOSE_POST_CONTROL_SELECTOR = 'button, div[role="button"]'
    _COMPOSE_POST_LABELS = frozenset({"게시", "post", "게시하기"})
    _COMPOSE_ADD_LABELS = frozenset(
        {"스레드에 추가", "add to thread", "내용을 더 추가", "add more"}
    )
    _MEDIA_PREVIEW_SELECTOR = (
        'img[src], video[src], [data-testid*="media-preview"], '
        '[data-testid*="attachment"], [aria-label*="Remove attachment" i], '
        '[aria-label*="첨부 파일 삭제"]'
    )
    _MEDIA_PROCESSING_SELECTOR = (
        '[role="progressbar"], [aria-busy="true"], '
        '[data-testid*="progress"], [data-testid*="processing"]'
    )
    _MEDIA_ERROR_SELECTOR = (
        '[role="alert"], [data-testid*="upload-error"], '
        '[aria-label*="upload failed" i], [aria-label*="업로드 실패"]'
    )

    def __init__(self, page: Page):
        self.page = page
        self.last_error: Optional[str] = None
        self.external_post_attempted = False

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

    # ========== 로그인 ==========

    def _check_login_status_legacy(self) -> bool:
        """로그인 상태 확인 (명시적 인증 신호 기반)."""
        try:
            # 방법 1: 로그인 입력창 존재 여부 (명확한 로그아웃 신호)
            login_input = self.page.locator('input[name="username"], input[type="text"][placeholder*="사용자"]').count()
            if login_input > 0:
                print("  로그아웃 상태 (로그인 입력창 존재)")
                return False

            # 방법 2: URL 체크 (로그인 페이지면 명확히 로그아웃)
            url = self.page.url
            if "login" in url.lower():
                print("  로그아웃 상태 (로그인 페이지)")
                return False

            # 방법 3: Feed 게시물 존재 (가장 확실한 로그인 신호)
            articles = self.page.locator('article').count()
            if articles > 0:
                print(f"  로그인 확인 (피드에 {articles}개 게시물 존재)")
                return True

            # 방법 4: Navigation bar 존재
            nav = self.page.locator('nav').count()
            if nav > 0:
                print("  로그인 확인 (내비게이션 바 존재)")
                return True

            # 방법 5: 특정 버튼들 (보조 확인)
            new_thread_btn = self.page.locator('a[aria-label*="New"], a[href*="compose"], button[aria-label*="New"]').count()
            if new_thread_btn > 0:
                print("  로그인 확인 (새 스레드 버튼 존재)")
                return True

            profile_btn = self.page.locator('a[aria-label*="Profile"], a[href*="/profile"]').count()
            if profile_btn > 0:
                print("  로그인 확인 (프로필 버튼 존재)")
                return True

            # 모든 확인 실패
            print("  로그인 상태 불확실 -> 미로그인으로 처리")
            return False

        except Exception as e:
            print(f"  로그인 확인 중 오류: {e}")
            return False

    @staticmethod
    def _is_trusted_session_cookie_domain(value: str) -> bool:
        domain = str(value or "").strip().lower().lstrip(".")
        return any(
            domain == root or domain.endswith(f".{root}")
            for root in ("threads.net", "threads.com", "instagram.com")
        )

    def _has_auth_cookie(self) -> bool:
        """Return True when browser context has authenticated session cookies."""
        try:
            cookies = self.page.context.cookies()
        except Exception:
            return False

        if not isinstance(cookies, list):
            return False

        auth_cookie_names = {"sessionid", "ds_user_id"}
        for cookie in cookies:
            if not isinstance(cookie, dict):
                continue
            name = str(cookie.get("name") or "").strip().lower()
            trusted_domain = self._is_trusted_session_cookie_domain(
                str(cookie.get("domain") or "")
            )
            if name in auth_cookie_names and trusted_domain:
                return True
        return False

    def _locator_has_visible_match(self, locator, max_matches: int = 5) -> bool:
        """Return True when a Playwright locator has at least one visible match."""
        try:
            count = locator.count()
        except Exception:
            return False

        for index in range(min(count, max_matches)):
            try:
                item = locator.nth(index)
            except Exception:
                item = locator

            try:
                if item.is_visible(timeout=500):
                    return True
            except TypeError:
                try:
                    if item.is_visible():
                        return True
                except Exception:
                    continue
            except Exception:
                continue
        return False

    def _has_login_or_continue_prompt(self) -> bool:
        """Return True when Threads is showing a login/continue gate."""
        try:
            prompt_patterns = (
                "Threads에서 소통해보세요",
                "Instagram으로 계속하기",
                "사용자 이름으로 로그인",
                "Continue with Instagram",
                "Log in with Instagram",
            )
            for text in prompt_patterns:
                if self._locator_has_visible_match(self.page.get_by_text(text)):
                    return True

            login_inputs = self.page.locator(
                'input[name="username"], input[type="password"], input[autocomplete*="username"]'
            )
            if self._locator_has_visible_match(login_inputs):
                return True

            url = str(self.page.url or "").lower()
            if "login" in url or "/accounts/" in url:
                login_actions = self.page.locator(
                    'a[href*="/login"], button:has-text("Log in"), button:has-text("로그인"), '
                    'div[role="button"]:has-text("Log in"), div[role="button"]:has-text("로그인")'
                )
                if self._locator_has_visible_match(login_actions):
                    return True

            dialog_login_actions = self.page.locator(
                'div[role="dialog"] a[href*="/login"], '
                'div[role="dialog"] button:has-text("Log in"), '
                'div[role="dialog"] button:has-text("로그인"), '
                'div[role="dialog"] div[role="button"]:has-text("Log in"), '
                'div[role="dialog"] div[role="button"]:has-text("로그인")'
            )
            if self._locator_has_visible_match(dialog_login_actions):
                return True
        except Exception:
            return False
        return False

    def check_login_status(self) -> bool:
        """Check login status with retries to reduce false negatives."""
        try:
            for attempt in range(5):
                try:
                    self.page.wait_for_load_state("domcontentloaded", timeout=3000)
                except Exception:
                    pass

                if self._has_login_or_continue_prompt():
                    print("  not logged in (login/continue prompt detected)")
                    return False

                if self._has_auth_cookie():
                    print("  로그인 확인 (세션 쿠키 감지)")
                    return True

                url = str(self.page.url or "").lower()
                login_input = self.page.locator(
                    'input[name="username"], input[type="password"], input[autocomplete*="username"]'
                ).count()
                if login_input > 0 and ("login" in url or "/accounts/" in url):
                    print("  미로그인 상태 (로그인 입력창 감지)")
                    return False

                if self.page.locator("article").count() > 0:
                    print("  로그인 확인 (피드 article 감지)")
                    return True
                if self.page.locator("nav").count() > 0:
                    print("  로그인 확인 (네비게이션 감지)")
                    return True
                if self.page.locator('a[href*="/compose"], button[aria-label*="New"], a[aria-label*="Profile"]').count() > 0:
                    print("  로그인 확인 (작성/프로필 UI 감지)")
                    return True

                if attempt < 4:
                    time.sleep(1.2)

            if self._has_auth_cookie():
                if self._has_login_or_continue_prompt():
                    print("  not logged in (login/continue prompt detected)")
                    return False
                print("  로그인 확인 (재시도 후 쿠키 감지)")
                return True

            print("  로그인 상태 불확실 -> 미로그인으로 처리")
            return False

        except Exception as e:
            print(f"  로그인 상태 확인 중 오류: {e}")
            return False

    def direct_login(self, username: str, password: str) -> bool:
        """
        직접 로그인 (Playwright selector 사용)

        Returns:
            True: 성공, False: 실패
        """
        try:
            print("  Playwright로 직접 로그인 시도...")

            # 1. Username 입력
            username_input = self.page.locator('input[name="username"], input[type="text"][autocomplete*="username"]').first
            if username_input.count() > 0:
                username_input.click()
                username_input.fill(username)
                print("  사용자명 입력 완료")
            else:
                print("  사용자명 입력창을 찾을 수 없음")
                return False

            time.sleep(1)

            # 2. Password 입력
            password_input = self.page.locator('input[name="password"], input[type="password"]').first
            if password_input.count() > 0:
                password_input.click()
                password_input.fill(password)
                print("  비밀번호 입력 완료")
            else:
                print("  비밀번호 입력창을 찾을 수 없음")
                return False

            time.sleep(1)

            # 3. 로그인 버튼 클릭
            login_locator = self.page.locator(
                'button[type="submit"], button:has-text("Log in"), button:has-text("Login")'
            )
            if login_locator.count() > 0:
                login_btn = login_locator.first
                login_btn.click()
                print("  로그인 버튼 클릭 완료")
            else:
                print("  로그인 버튼을 찾을 수 없음")
                return False

            # 4. 로그인 완료 대기 (네비게이션)
            time.sleep(5)

            # 5. 로그인 성공 확인
            return self.check_login_status()

        except Exception as e:
            print(f"  로그인 실패: {e}")
            self.last_error = str(e)
            return False

    def try_instagram_login(self) -> bool:
        """Instagram으로 계속하기 버튼 시도"""
        try:
            print("  Instagram 자동 로그인 시도...")

            # "Instagram으로 계속하기" 버튼 찾기
            instagram_btn = self.page.locator('button:has-text("Instagram"), a:has-text("Instagram")').first

            if instagram_btn.count() > 0:
                instagram_btn.click()
                print("  Instagram 로그인 버튼 클릭 완료")
                time.sleep(5)
                return self.check_login_status()
            else:
                print("  Instagram 버튼을 찾을 수 없음")
                return False

        except Exception as e:
            print(f"  Instagram 로그인 실패: {e}")
            return False

    @classmethod
    def _username_from_self_profile_href(cls, raw_href: Any) -> Optional[str]:
        href = str(raw_href or "").strip()
        if not href:
            return None
        try:
            parsed = urlparse(href)
        except (TypeError, ValueError):
            return None

        if parsed.scheme or parsed.netloc:
            if parsed.scheme != "https" or (parsed.hostname or "").lower() not in cls._THREADS_PROFILE_HOSTS:
                return None
        match = re.fullmatch(r"/@([^/]+)/?", parsed.path or "")
        if not match:
            return None
        username = match.group(1)
        if not cls._THREADS_USERNAME_PATTERN.fullmatch(username):
            return None
        return username

    def _authoritative_self_profile_usernames(self) -> set[str]:
        self.last_error = None
        usernames: set[str] = set()
        for selector in self._SELF_PROFILE_LINK_SELECTORS:
            try:
                locator = self.page.locator(selector)
                count = locator.count()
            except Exception:
                continue

            # A self-navigation selector should resolve to at most a handful of
            # responsive-layout duplicates. An excessive result is unexpected
            # and therefore not safe identity evidence.
            if count > 8:
                self.last_error = "self_identity_ambiguous"
                return set()

            for index in range(count):
                try:
                    item = locator.nth(index)
                    if not item.is_visible(timeout=500):
                        continue
                    # Even an exact accessible label is not evidence when it is
                    # rendered inside a feed article. Treat DOM-inspection
                    # failure as unknown rather than trusting the link.
                    outside_feed = item.evaluate(
                        "el => !Boolean(el.closest('article'))"
                    )
                    if outside_feed is not True:
                        continue
                    username = self._username_from_self_profile_href(
                        item.get_attribute("href")
                    )
                except Exception:
                    continue
                if username:
                    usernames.add(username.lower())
        return usernames

    def get_logged_in_username(self) -> Optional[str]:
        """Return the unambiguous username from authoritative self-account UI."""
        try:
            usernames = self._authoritative_self_profile_usernames()
        except Exception as exc:
            print(f"  사용자명 확인 실패: {exc}")
            self.last_error = "self_identity_unknown"
            return None

        if len(usernames) == 1:
            username = next(iter(usernames))
            self.last_error = None
            print(f"  자기 프로필 내비게이션에서 사용자명 확인: @{username}")
            return username
        if len(usernames) > 1:
            self.last_error = "self_identity_conflict"
            print("  자기 계정 UI에서 충돌하는 사용자명이 발견되어 검증을 중단합니다.")
            return None

        if self.last_error != "self_identity_ambiguous":
            self.last_error = "self_identity_unknown"
        print("  자기 계정 UI에서 사용자명을 확인하지 못했습니다.")
        return None

    def verify_account(self, expected_username: str) -> bool:
        """로그인 계정이 기대 계정과 실제로 일치하는지 확인."""
        expected_raw = str(expected_username or "").strip()
        if not expected_raw:
            self.last_error = "expected_identity_missing"
            print("  검증할 Threads 사용자명이 설정되지 않아 안전상 중단합니다.")
            return False

        if not self.check_login_status():
            print("  로그인되어 있지 않음")
            return False

        actual_username = self.get_logged_in_username()
        if not actual_username:
            print("  현재 로그인된 사용자명을 확인하지 못함")
            return False

        expected_norm = expected_raw.lstrip("@").lower()
        if "@" in expected_norm and "." in expected_norm.split("@")[-1]:
            expected_norm = expected_norm.split("@", 1)[0]

        actual_norm = str(actual_username).lstrip("@").lower()
        matched = actual_norm == expected_norm
        if matched:
            print(f"  계정 검증 성공: @{actual_norm}")
        else:
            print(f"  계정 불일치: expected=@{expected_norm}, actual=@{actual_norm}")
        return matched

    def logout(self) -> bool:
        """
        현재 계정에서 로그아웃

        Returns:
            True: 성공, False: 실패
        """
        try:
            print("  로그아웃 시도...")

            # 설정 페이지로 이동
            goto_threads_with_fallback(
                self.page,
                path="/settings",
                timeout=15000,
                retries_per_url=1,
            )
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
                        print("  로그아웃 버튼 클릭 완료")
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
                                    print("  로그아웃 확인 완료")
                                    time.sleep(3)
                                    break
                            except Exception:
                                continue

                        print("  로그아웃 완료")
                        return True
                except Exception:
                    continue

            # 프로필 메뉴에서 로그아웃 시도
            print("  프로필 메뉴에서 로그아웃 시도...")
            goto_threads_with_fallback(
                self.page,
                path="/",
                timeout=15000,
                retries_per_url=1,
            )
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
                except Exception:
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
                            print("  로그아웃 완료")
                            return True
                    except Exception:
                        continue

            print("  로그아웃 버튼을 찾을 수 없음")
            return False

        except Exception as e:
            print(f"  로그아웃 실패: {e}")
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
            if not username:
                self.last_error = "expected_identity_missing"
                print("  검증할 Threads 사용자명이 없어 로그인 사용을 중단합니다.")
                return False
            # 계정 검증
            if not self.verify_account(username):
                print("  다른 계정으로 로그인되어 있음 - 자동 로그아웃 시도")

                # 로그아웃 시도
                if self.logout():
                    print("  로그아웃 성공 - 설정된 계정으로 로그인 시도")
                    # 로그인 페이지로 이동
                    goto_threads_with_fallback(
                        self.page,
                        path="/login",
                        timeout=15000,
                        retries_per_url=1,
                    )
                    time.sleep(2)
                else:
                    print("  자동 로그아웃 실패 - 수동으로 로그아웃 후 다시 시도해주세요")
                    return False
            else:
                return True

        # 2. 로그인 필요 - 직접 로그인 시도
        if username and password:
            print(f"  설정된 계정으로 로그인 시도: {username}")
            if self.direct_login(username, password):
                return self.verify_account(username)

        # 3. Instagram 자동 로그인 시도 (기존 세션 사용)
        if self.try_instagram_login():
            if username:
                return self.verify_account(username)
            self.last_error = "expected_identity_missing"
            print("  검증할 Threads 사용자명이 없어 로그인 사용을 중단합니다.")
            return False

        print("  로그인 실패")
        return False

    # ========== 쓰레드 작성 ==========

    @staticmethod
    def _normalize_compose_text(value: Any) -> str:
        """Normalize only whitespace while preserving all meaningful text."""
        return " ".join(str(value or "").split())

    @staticmethod
    def _element_is_visible(element) -> bool:
        try:
            return bool(element.is_visible(timeout=500))
        except TypeError:
            try:
                return bool(element.is_visible())
            except Exception:
                return False
        except Exception:
            return False

    def _visible_editor_handles(self, container) -> list:
        """Return visible editors that belong to one verified compose surface."""
        try:
            handles = container.locator(
                self._COMPOSE_EDITOR_SELECTOR
            ).element_handles()
        except Exception:
            return []
        return [handle for handle in handles if self._element_is_visible(handle)]

    def _visible_controls_with_labels(self, container, labels: frozenset[str]) -> list:
        """Return exact-label, visible controls within one compose surface."""
        try:
            controls = container.locator(self._COMPOSE_POST_CONTROL_SELECTOR)
            count = controls.count()
        except Exception:
            return []

        matches = []
        for index in range(count):
            try:
                control = controls.nth(index)
                if not self._element_is_visible(control):
                    continue
                label = self._normalize_compose_text(control.inner_text()).casefold()
                if label in labels:
                    matches.append(control)
            except Exception:
                continue
        return matches

    def _visible_post_controls(self, container) -> list:
        """Return exact-label, visible Post controls within a compose surface."""
        return self._visible_controls_with_labels(
            container,
            self._COMPOSE_POST_LABELS,
        )

    def _active_compose_container(self):
        """Locate one unambiguous visible compose container, never the page root."""
        selectors = list(self._COMPOSE_CONTAINER_SELECTORS)
        try:
            path = urlparse(str(self.page.url or "")).path.casefold()
        except Exception:
            path = ""
        if path.rstrip("/").endswith(("/compose", "/intent/post")):
            # Direct compose routes sometimes render without a dialog or form.
            # `main` is permitted only on those dedicated routes.
            selectors.append("main")

        for selector in selectors:
            try:
                candidates = self.page.locator(selector)
                candidate_count = candidates.count()
            except Exception:
                continue

            qualified = []
            for index in range(candidate_count):
                try:
                    candidate = candidates.nth(index)
                    if not self._element_is_visible(candidate):
                        continue
                    if not self._visible_editor_handles(candidate):
                        continue
                    if not self._visible_post_controls(candidate):
                        continue
                    qualified.append(candidate)
                except Exception:
                    continue

            if len(qualified) == 1:
                return qualified[0]
            if len(qualified) > 1:
                self.last_error = "compose_scope_ambiguous"
                return None

        return None

    def _compose_editor_handles(self) -> list:
        container = self._active_compose_container()
        if container is None:
            return []
        return self._visible_editor_handles(container)

    def _read_compose_editor_texts(self) -> Optional[list[str]]:
        """Read visible editor contents from the active compose surface only."""
        handles = self._compose_editor_handles()
        if not handles:
            return None

        contents = []
        for handle in handles:
            try:
                contents.append(
                    str(
                        handle.evaluate(
                            """el => {
                                if ('value' in el && el.value !== undefined && el.value !== null) {
                                    return el.value;
                                }
                                return el.innerText || el.textContent || '';
                            }"""
                        )
                        or ""
                    )
                )
            except Exception:
                return None
        return contents

    def _verify_compose_paragraphs(self, paragraphs: list[str]) -> bool:
        """Require an exact whitespace-normalized editor/payload match."""
        observed = self._read_compose_editor_texts()
        if observed is None or len(observed) != len(paragraphs):
            self.last_error = "thread_structure_unverified"
            return False

        expected_normalized = [
            self._normalize_compose_text(paragraph) for paragraph in paragraphs
        ]
        observed_normalized = [
            self._normalize_compose_text(content) for content in observed
        ]
        if observed_normalized != expected_normalized:
            self.last_error = "thread_content_unverified"
            return False
        return True

    def _compose_editor_available(self) -> bool:
        """Return True when a Threads compose editor is visible."""
        try:
            return bool(self._compose_editor_handles())
        except Exception:
            return False

    def _open_compose_directly(self) -> bool:
        """Open the Threads compose surface through stable direct routes."""
        route_paths = ("/intent/post", "/compose")
        for path in route_paths:
            try:
                goto_threads_with_fallback(
                    self.page,
                    path=path,
                    timeout=15000,
                    retries_per_url=1,
                )
                time.sleep(2)

                if self._has_login_or_continue_prompt():
                    print(f"  직접 작성 경로 로그인 화면 감지 ({path})")
                    self.last_error = "login_prompt"
                    return False

                if self._compose_editor_available():
                    print(f"  새 스레드 작성창 열림 (direct {path})")
                    return True
            except Exception as exc:
                print(f"  직접 작성 경로 실패 ({path}): {str(exc)[:120]}")

        return False

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
                'div[aria-label*="Create"]',
                'div[aria-label*="만들기"]',
                'button[aria-label*="Create"]',
                'button[aria-label*="만들기"]',
                'a[aria-label*="Create"]',
                'a[aria-label*="만들기"]',
                'a[aria-label*="Write"]',
                'a[aria-label*="작성"]',
                'a[aria-label*="새"]',
                'div[aria-label*="작성"]',
                'button[aria-label*="작성"]',
                'div[aria-label*="새"]',
                'button[aria-label*="새"]',
                'a[href*="intent/post"]',
                'a[role="link"]:has-text("+")',
                # 좌표 기반 fallback (왼쪽 사이드바 중간쯤)
            ]

            for selector in selectors:
                btn = self.page.locator(selector).first
                if btn.count() > 0:
                    btn.click()
                    print(f"  새 스레드 버튼 클릭 완료 ({selector})")
                    time.sleep(2)
                    return True

            # Fallback: 좌표 클릭 (x=30, y=460 normalized)
            print("  선택자 실패, 좌표로 시도...")
            try:
                clicked = self.page.evaluate(
                    """() => {
                        const labels = ['만들기', 'Create', 'New thread', '새 스레드'];
                        const elements = Array.from(document.querySelectorAll('div[role="button"], button, a'));
                        const target = elements.find((el) => {
                            const text = `${el.innerText || ''} ${el.getAttribute('aria-label') || ''}`.trim();
                            return labels.some((label) => text.includes(label));
                        });
                        if (!target) return false;
                        target.click();
                        return true;
                    }"""
                )
                if clicked:
                    print("  새 스레드 버튼 클릭 완료 (text fallback)")
                    time.sleep(2)
                    return True
            except Exception as text_click_error:
                print(f"  text fallback 클릭 실패: {text_click_error}")

            print("  직접 작성 경로로 전환...")
            if self._open_compose_directly():
                return True

            self.last_error = "compose_button_not_found"
            print("  새 스레드 버튼을 찾지 못해 좌표 클릭 없이 중단")
            return False

        except Exception as e:
            print(f"  새 스레드 버튼 클릭 실패: {e}")
            self.last_error = str(e)
            return False

    def dismiss_login_popup(self) -> bool:
        """로그인 팝업 닫기"""
        try:
            # Escape 키
            self.page.keyboard.press("Escape")
            time.sleep(1)
            return True
        except Exception:
            # 팝업 바깥 클릭
            try:
                self.page.mouse.click(50, 50)
                time.sleep(1)
                return True
            except Exception:
                return False

    def count_textareas(self) -> int:
        """
        Compose 창의 textarea 개수 확인

        Returns:
            textarea 개수
        """
        try:
            return len(self._compose_editor_handles())
        except Exception:
            return 0

    def find_empty_textarea_index(self) -> Optional[int]:
        """
        비어 있는 textarea/contenteditable index 찾기 (새로 생성된 박스를 우선 사용)

        Returns:
            비어 있는 textarea index (없으면 None)
        """
        try:
            textareas = self._compose_editor_handles()
            total = len(textareas)
            empty_indices = []

            for idx in range(total):
                try:
                    content = textareas[idx].evaluate("el => (el.value || el.innerText || '').trim()")
                except Exception:
                    # An unreadable editor is not evidence that it is empty.
                    continue

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
            textareas = self._compose_editor_handles()
            total_textareas = len(textareas)

            print(f"      [type_in_textarea] 전체 textarea 개수: {total_textareas}, 입력할 index: {index}")

            if total_textareas <= index:
                print(f"      Textarea[{index}] 존재하지 않음 (총 {total_textareas}개)")
                self.last_error = "textarea_missing"
                return False

            def textarea_handles():
                return self._compose_editor_handles()

            handles = textarea_handles()
            if len(handles) <= index:
                print(f"      Textarea[{index}] element handle 없음 (현재 {len(handles)}개)")
                self.last_error = "textarea_missing"
                return False

            textarea = handles[index]

            # 디버그: textarea 정보 출력
            try:
                tag_name = textarea.evaluate("el => el.tagName")
                existing_text = textarea.evaluate("el => el.value || el.innerText || ''")
                trimmed_existing = (existing_text or "").strip()
                print(f"      Textarea[{index}] 타입: {tag_name}, 기존 내용 길이: {len(trimmed_existing)}자")
            except Exception:
                self.last_error = "textarea_state_unknown"
                return False

            if require_empty and trimmed_existing:
                print(f"      Textarea[{index}]에 기존 내용이 있어 덮어쓰지 않음")
                self.last_error = "textarea_not_empty"
                return False

            def current_textarea():
                nonlocal textarea
                try:
                    if textarea.evaluate("el => !!el.isConnected"):
                        return textarea
                    raise RuntimeError("textarea handle detached")
                except Exception:
                    handles_now = textarea_handles()
                    if len(handles_now) > index:
                        textarea = handles_now[index]
                    return textarea

            def read_text() -> str:
                try:
                    return str(
                        current_textarea().evaluate(
                            """el => {
                                if ('value' in el && el.value !== undefined && el.value !== null) {
                                    return el.value;
                                }
                                return el.innerText || el.textContent || '';
                            }"""
                        )
                        or ""
                    )
                except Exception:
                    return ""

            def content_matches(actual: str) -> bool:
                expected = self._normalize_compose_text(text)
                observed = self._normalize_compose_text(actual)
                return observed == expected

            def focus_target() -> None:
                current_textarea().click(timeout=5000)
                time.sleep(0.2)

            def clear_existing() -> None:
                focus_target()
                self.page.keyboard.press("Control+A")
                self.page.keyboard.press("Backspace")
                time.sleep(0.2)

            # 1차: Playwright fill
            try:
                clear_existing()
                current_textarea().fill(text, timeout=5000)
                time.sleep(0.5)
                after_text = read_text()
                print(f"      Textarea[{index}] fill 후 확인 (입력 {len(text)}자, 현재 {len(after_text)}자)")
                if content_matches(after_text):
                    return True
            except Exception as fill_error:
                print(f"      Textarea[{index}] fill 실패, keyboard 입력으로 재시도: {fill_error}")

            # 2차: 실제 키보드 입력 경로. Threads contenteditable에서 fill 이벤트가
            # React 상태에 반영되지 않는 경우가 있어 사용자 입력에 가까운 경로로 재시도한다.
            print(f"      Textarea[{index}] fill 검증 실패, keyboard.insert_text 재시도")
            try:
                clear_existing()
                self.page.keyboard.insert_text(text)
                time.sleep(0.8)
                after_text = read_text()
                print(f"      Textarea[{index}] insert_text 후 확인 (입력 {len(text)}자, 현재 {len(after_text)}자)")
                if content_matches(after_text):
                    return True
            except Exception as keyboard_error:
                print(f"      Textarea[{index}] keyboard 입력 실패, DOM 입력으로 재시도: {keyboard_error}")

            # 3차: DOM 입력 이벤트 fallback.
            print(f"      Textarea[{index}] keyboard 입력 검증 실패, DOM input 이벤트 재시도")
            try:
                current_textarea().evaluate(
                    """(el, value) => {
                        el.focus();
                        if ('value' in el && el.value !== undefined) {
                            el.value = value;
                        } else {
                            el.textContent = value;
                        }
                        el.dispatchEvent(new InputEvent('input', {
                            bubbles: true,
                            cancelable: true,
                            inputType: 'insertText',
                            data: value
                        }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                    }""",
                    text,
                )
                time.sleep(0.8)
            except Exception as js_error:
                print(f"      Textarea[{index}] DOM 입력 이벤트 실패: {js_error}")

            after_text = read_text()
            print(f"      Textarea[{index}] 최종 확인 (입력 {len(text)}자, 현재 {len(after_text)}자)")
            if content_matches(after_text):
                return True

            self.last_error = "textarea_input_not_applied"
            print(f"      Textarea[{index}] 입력 검증 실패")
            return False

        except Exception as e:
            print(f"      Textarea[{index}] 입력 실패: {e}")
            self.last_error = str(e)
            return False

    def click_add_to_thread(self) -> bool:
        """Click one exact Add-to-thread control in the active composer."""
        container = self._active_compose_container()
        if container is None:
            self.last_error = self.last_error or "compose_scope_unverified"
            return False

        controls = self._visible_controls_with_labels(
            container,
            self._COMPOSE_ADD_LABELS,
        )
        if len(controls) != 1:
            self.last_error = (
                "add_thread_button_missing"
                if not controls
                else "add_thread_button_ambiguous"
            )
            return False

        try:
            controls[0].click()
            time.sleep(2)
            return True
        except Exception:
            self.last_error = "add_thread_button_click_failed"
            return False
    def click_post_button(self) -> bool:
        """Click exactly one visible Post control in the active compose surface."""
        print("  게시 버튼 찾는 중...")
        container = self._active_compose_container()
        if container is None:
            self.last_error = self.last_error or "compose_scope_unverified"
            print("  활성 작성창을 확인하지 못해 게시를 중단합니다")
            return False

        controls = self._visible_post_controls(container)
        if len(controls) != 1:
            self.last_error = (
                "post_button_missing" if not controls else "post_button_ambiguous"
            )
            print(f"  활성 작성창의 게시 버튼을 하나로 확정하지 못했습니다 ({len(controls)}개)")
            return False

        try:
            # One normal Playwright click only. Force, JavaScript dispatch,
            # keyboard shortcuts, and coordinate fallbacks can target unrelated
            # UI or replay a non-idempotent mutation, so they are prohibited.
            # From this exact point onward a dispatch may have happened even if
            # Playwright later raises (for example during navigation teardown).
            self.external_post_attempted = True
            controls[0].click()
            print("  활성 작성창의 게시 버튼 클릭 완료")
            return True
        except Exception as exc:
            self.last_error = "post_button_click_failed"
            print(f"  게시 버튼 클릭 실패: {type(exc).__name__}")
            return False

    # ========== 이미지 업로드 ==========

    @staticmethod
    def _file_input_has_expected_attachment(file_input, expected_name: str) -> bool:
        try:
            state = file_input.evaluate(
                """el => ({
                    count: el.files ? el.files.length : 0,
                    names: el.files ? Array.from(el.files, file => file.name) : []
                })"""
            )
        except Exception:
            return False
        if not isinstance(state, dict):
            return False
        names = state.get("names")
        return state.get("count") == 1 and names == [expected_name]

    def _compose_row_handle(self, container, editor):
        """Resolve the smallest visible-editor subtree for one composer row."""
        try:
            container_handle = container.element_handle()
            if container_handle is None:
                return None
            row_handle = editor.evaluate_handle(
                """(editor, composer) => {
                    const selector = 'textarea, div[contenteditable="true"]';
                    const visible = el => {
                        const style = window.getComputedStyle(el);
                        const rect = el.getBoundingClientRect();
                        return style.visibility !== 'hidden' &&
                            style.display !== 'none' && rect.width > 0 && rect.height > 0;
                    };
                    let row = editor;
                    while (row.parentElement && row.parentElement !== composer) {
                        const parent = row.parentElement;
                        const editors = Array.from(parent.querySelectorAll(selector))
                            .filter(visible);
                        if (editors.length > 1) break;
                        row = parent;
                    }
                    return row === editor ? null : row;
                }""",
                container_handle,
            )
            return row_handle.as_element()
        except Exception:
            return None

    def _visible_descendants(self, scope, selector: str) -> list:
        try:
            if hasattr(scope, "query_selector_all"):
                handles = scope.query_selector_all(selector)
            else:
                handles = scope.locator(selector).element_handles()
        except Exception:
            return []
        return [handle for handle in handles if self._element_is_visible(handle)]

    def _media_row_state(self, row) -> tuple[int, bool, bool]:
        previews = len(self._visible_descendants(row, self._MEDIA_PREVIEW_SELECTOR))
        processing = bool(
            self._visible_descendants(row, self._MEDIA_PROCESSING_SELECTOR)
        )
        error = bool(self._visible_descendants(row, self._MEDIA_ERROR_SELECTOR))
        return previews, processing, error

    def upload_image(self, image_path: str, *, post_index: int = 0) -> bool:
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
                print("  이미지 파일 없음")
                self.last_error = "media_file_missing"
                return False

            print("  이미지 업로드 중")
            container = self._active_compose_container()
            editors = (
                self._visible_editor_handles(container)
                if container is not None
                else []
            )
            if container is None or not (0 <= post_index < len(editors)):
                self.last_error = "media_compose_scope_unverified"
                print("  이미지 대상 작성 행을 확인하지 못했습니다")
                return False

            # All file inputs must be descendants of the verified active
            # composer. When Threads exposes one shared input, focus the exact
            # row first so the input is bound to that row. Any other cardinality
            # is ambiguous and therefore fails closed.
            file_inputs = container.locator('input[type="file"]')
            input_count = file_inputs.count()
            if input_count == len(editors):
                file_input = file_inputs.nth(post_index)
            elif input_count == 1:
                editors[post_index].click()
                file_input = file_inputs.first
            else:
                self.last_error = "media_input_ambiguous"
                print(f"  작성 행과 이미지 입력을 안전하게 연결할 수 없습니다 ({input_count}개)")
                return False

            target_row = self._compose_row_handle(container, editors[post_index])
            if target_row is None:
                self.last_error = "media_row_unverified"
                print("  이미지 첨부 대상 작성 행을 확인하지 못했습니다")
                return False
            baseline_previews, _baseline_processing, baseline_error = (
                self._media_row_state(target_row)
            )
            if baseline_error:
                self.last_error = "media_attachment_rejected"
                return False

            expected_name = os.path.basename(os.path.abspath(image_path))
            file_input.set_input_files(os.path.abspath(image_path))
            try:
                verify_polls = int(
                    os.getenv("THREAD_AUTO_MEDIA_VERIFY_POLLS", "60") or "60"
                )
            except ValueError:
                verify_polls = 60
            verify_polls = max(1, min(verify_polls, 120))
            expected_file_state_seen = False

            for _attempt in range(verify_polls):
                preview_count, processing, upload_error = self._media_row_state(
                    target_row
                )
                if upload_error:
                    self.last_error = "media_attachment_rejected"
                    print("  이미지 첨부 오류가 표시되어 중단합니다")
                    return False
                expected_file_state_seen = (
                    expected_file_state_seen
                    or self._file_input_has_expected_attachment(
                        file_input,
                        expected_name,
                    )
                )
                if (
                    expected_file_state_seen
                    and preview_count > baseline_previews
                    and not processing
                ):
                    print("  이미지 미리보기와 처리 완료 상태 확인")
                    return True
                time.sleep(0.5)

            self.last_error = "media_attachment_unverified"
            print("  이미지 미리보기 또는 처리 완료 상태를 확인하지 못했습니다")
            return False

        except Exception as e:
            self.last_error = "media_upload_failed"
            print(f"  이미지 업로드 실패: {type(e).__name__}")
            return False

    # ========== 통합 워크플로우 ==========

    def create_thread_direct(self, posts_data, *, expected_username: str) -> bool:
        """
        Playwright로 직접 스레드 생성 (AI 없이)

        Args:
            posts_data: 포스트 데이터 리스트
                       - List[str]: 문단 텍스트 리스트 (기존 방식)
                       - List[dict]: [{'text': '...', 'image_path': '...'}, ...]
            expected_username: 게시 직전 다시 검증할 Threads 사용자명

        Returns:
            True: 성공, False: 실패
        """
        self.external_post_attempted = False
        expected_identity = str(expected_username or "").strip()
        if not expected_identity:
            self.last_error = "expected_identity_missing"
            print("  게시할 Threads 사용자명이 없어 안전상 중단합니다.")
            return False

        try:
            total_timeout_seconds = int(os.getenv("THREAD_AUTO_PLAYWRIGHT_TOTAL_TIMEOUT_SEC", "180") or "180")
            deadline = time.monotonic() + max(total_timeout_seconds, 30)

            def is_timed_out(stage: str) -> bool:
                if time.monotonic() <= deadline:
                    return False
                print(f"  전체 타임아웃({total_timeout_seconds}초) 초과: {stage}")
                self.last_error = f"timeout: {stage}"
                return True

            # Publishing structure is intentionally immutable: one root post
            # followed by one product comment. Do not merge these even when a
            # legacy environment variable requests a single post.
            if not isinstance(posts_data, (list, tuple)) or len(posts_data) != 2:
                print("  업로드 구조 오류: 본문 1개와 상품 댓글 1개가 필요합니다")
                self.last_error = "invalid_thread_structure"
                return False

            if all(isinstance(post, str) for post in posts_data):
                paragraphs = [str(post).strip() for post in posts_data]
                media_paths = [None, None]
            elif all(isinstance(post, dict) for post in posts_data):
                paragraphs = [
                    str(post.get("text") or "").strip() for post in posts_data
                ]
                media_paths = [post.get("image_path") for post in posts_data]
            else:
                paragraphs = []
                media_paths = []

            if len(paragraphs) != 2 or any(not text for text in paragraphs):
                print("  업로드 구조 오류: 두 문단 모두 비어 있지 않아야 합니다")
                self.last_error = "invalid_thread_structure"
                return False

            total = len(paragraphs)
            print("\n  Playwright로 본문 1개 + 상품 댓글 1개 스레드 작성 시작")
            for index, media_path in enumerate(media_paths):
                if media_path:
                    print(f"  {index + 1}번째 글에 미디어 첨부 예정: {media_path}")

            if self._has_login_or_continue_prompt():
                print("  로그인/계속하기 화면 감지, 게시를 중단합니다")
                self.last_error = "login_prompt"
                return False

            # 1. New thread 버튼 클릭
            if is_timed_out("before_click_new_thread"):
                return False
            if not self.click_new_thread():
                return False

            # 로그인 팝업 체크. 전체 HTML 문자열에는 로그인된 화면에서도 가입/로그인
            # 문구가 남을 수 있으므로 실제 작성창과 보이는 게이트만 확인한다.
            time.sleep(1)
            if not self._compose_editor_available() and self._has_login_or_continue_prompt():
                print("  로그인 팝업 감지, 닫기 후 작성창을 다시 확인합니다")
                self.dismiss_login_popup()
                time.sleep(1)
                if not self._compose_editor_available():
                    print("  로그인 팝업 감지, 게시를 중단합니다")
                    self.last_error = "login_popup"
                    return False

            # 2. 첫 번째 문단 입력
            if is_timed_out("before_first_textarea"):
                return False
            if not self.type_in_textarea(paragraphs[0], index=0):
                return False

            # 2-1. 첫 번째 글에 미디어 업로드 (있는 경우). A requested
            # attachment is part of the post contract, so failure must abort.
            if media_paths[0] and not self.upload_image(media_paths[0], post_index=0):
                self.last_error = "media_upload_failed:0"
                return False

            # 3. 나머지 문단들 추가
            for i in range(1, total):
                if is_timed_out(f"before_paragraph_{i+1}"):
                    return False
                print(f"\n  [{i+1}/{total}] 문단 추가 중...")

                # 현재 textarea 개수 확인
                textarea_count_before = self.count_textareas()
                print(f"    [현재] Textarea 개수: {textarea_count_before}")
                expected_count = i + 1

                # 3-1. UI가 자동으로 생성하는지 잠시 대기
                if textarea_count_before < expected_count:
                    print("    UI 자동 생성 대기 중...")
                    time.sleep(1)
                    textarea_count_after_wait = self.count_textareas()
                    if textarea_count_after_wait >= expected_count:
                        print(f"    Textarea {expected_count}개 자동 생성됨 (버튼 클릭 불필요)")
                    else:
                        print(f"    자동 생성 안 됨 ({textarea_count_after_wait}/{expected_count})")

                # 3-2. 이미 충분한 textarea가 있는지 확인
                textarea_count_current = self.count_textareas()
                if textarea_count_current >= expected_count:
                    print(f"    Textarea {expected_count}개 존재 (버튼 클릭 불필요)")
                else:
                    # 3-2. '스레드에 추가' 클릭
                    print("    '스레드에 추가' 버튼 클릭 필요...")
                    if not self.click_add_to_thread():
                        print("    '스레드에 추가' 버튼을 찾을 수 없음")
                        return False

                    # 3-3. 버튼 클릭 후 textarea 개수 확인
                    time.sleep(1.5)
                    textarea_count_after = self.count_textareas()
                    print(f"    [클릭 후] Textarea 개수: {textarea_count_after}")

                    if textarea_count_after < expected_count:
                        print(f"    Textarea 생성 실패 ({textarea_count_after}/{expected_count})")
                        print("    잘못된 요소를 클릭했거나 UI가 변경됨")
                        # 디버그 스크린샷
                        try:
                            debug_path = self._save_debug_screenshot(f"debug_failed_add_{i}")
                            if debug_path:
                                print(f"    Debug screenshot saved: {debug_path}")
                        except Exception:
                            pass
                        return False

                    print(f"    Textarea {expected_count}개 확인")

                # 3-4. 새 textarea에 입력 (기존 내용 보존)
                target_index = self.find_empty_textarea_index()
                if target_index is None:
                    print("    빈 textarea를 찾지 못해 마지막 textarea에 입력 시도")
                    textarea_count_current = self.count_textareas()
                    target_index = textarea_count_current - 1 if textarea_count_current > 0 else i
                else:
                    print(f"    빈 textarea 발견: index {target_index}")

                print(f"    Textarea[{target_index}]에 입력 시도...")
                if not self.type_in_textarea(paragraphs[i], index=target_index, require_empty=True):
                    print("    대상 textarea에 입력 실패, 다른 빈 textarea 탐색...")
                    typed = False
                    textareas_total = self.count_textareas()
                    for alt_idx in range(textareas_total):
                        if alt_idx == target_index:
                            continue
                        if self.type_in_textarea(paragraphs[i], index=alt_idx, require_empty=True):
                            typed = True
                            break
                    if not typed:
                        print("    빈 textarea에 입력하지 못함 (덮어쓰기를 방지하기 위해 중단)")
                        return False

                if media_paths[i] and not self.upload_image(
                    media_paths[i],
                    post_index=target_index,
                ):
                    self.last_error = f"media_upload_failed:{i}"
                    return False

            # 4. Post 버튼 클릭 직전 계정과 작성 내용을 모두 재검증한다.
            # 계정 검증 도중 DOM이 다시 렌더링될 수 있으므로 내용 검증이 반드시
            # identity 검증 뒤, 외부 게시 시도 플래그를 세우기 전에 위치해야 한다.
            print("\n  최종 검증...")
            if is_timed_out("before_click_post"):
                return False
            if not self.verify_account(expected_identity):
                self.last_error = "account_identity_unverified"
                print("  게시 직전 Threads 계정을 확인하지 못해 안전상 중단합니다.")
                return False
            if not self._verify_compose_paragraphs(paragraphs):
                if self.last_error == "thread_structure_unverified":
                    actual_count = self.count_textareas()
                    print(f"  활성 작성창 편집기 개수 불일치 ({actual_count}/{total})")
                else:
                    print("  활성 작성창 내용이 입력 문단과 정확히 일치하지 않습니다")
                return False

            # 5. Post 버튼 클릭
            print("\n  게시 중...")
            attempted_after = time.time()
            if not self.click_post_button():
                return False

            # 6. 게시 완료 검증 (프로필 최신 글 매칭)
            if is_timed_out("before_verify_post"):
                return False
            if not self.verify_post_success(
                paragraphs[0],
                expected_username=expected_identity,
                attempted_after=attempted_after,
            ):
                print("  게시 검증 실패 (프로필에서 최신 글 확인 불가)")
                return False

            print("\n  스레드 게시 완료")
            return True

        except Exception as e:
            print(f"\n  스레드 작성 실패: {e}")
            self.last_error = str(e)
            return False

    @classmethod
    def _is_expected_post_permalink(cls, raw_href: Any, username: str) -> bool:
        try:
            parsed = urlparse(str(raw_href or "").strip())
        except (TypeError, ValueError):
            return False
        if parsed.scheme or parsed.netloc:
            if parsed.scheme != "https":
                return False
            if (parsed.hostname or "").casefold() not in cls._THREADS_PROFILE_HOSTS:
                return False
        return bool(
            re.fullmatch(
                rf"/@{re.escape(username)}/post/[^/]+/?",
                parsed.path or "",
                flags=re.IGNORECASE,
            )
        )

    @staticmethod
    def _parse_threads_timestamp(raw_value: Any) -> Optional[float]:
        value = str(raw_value or "").strip()
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()

    def _profile_article_proves_post(
        self,
        article,
        *,
        expected_text: str,
        expected_username: str,
        attempted_after: float,
    ) -> bool:
        expected_normalized = self._normalize_compose_text(expected_text)
        if not expected_normalized:
            return False

        exact_text_found = False
        try:
            text_nodes = article.locator(
                '[data-testid="post-text"], div[dir="auto"], span[dir="auto"]'
            )
            for index in range(min(text_nodes.count(), 40)):
                node = text_nodes.nth(index)
                if not self._element_is_visible(node):
                    continue
                if self._normalize_compose_text(node.inner_text()) == expected_normalized:
                    exact_text_found = True
                    break
        except Exception:
            return False
        if not exact_text_found:
            return False

        recent_timestamp_found = False
        try:
            timestamps = article.locator("time[datetime]")
            for index in range(min(timestamps.count(), 5)):
                post_timestamp = self._parse_threads_timestamp(
                    timestamps.nth(index).get_attribute("datetime")
                )
                # Allow only a small clock-skew margin; an older matching post
                # must never be accepted as evidence for this attempt.
                if post_timestamp is not None and post_timestamp + 5 >= attempted_after:
                    recent_timestamp_found = True
                    break
        except Exception:
            return False
        if not recent_timestamp_found:
            return False

        try:
            permalinks = article.locator('a[href*="/post/"]')
            for index in range(min(permalinks.count(), 10)):
                if self._is_expected_post_permalink(
                    permalinks.nth(index).get_attribute("href"),
                    expected_username,
                ):
                    return True
        except Exception:
            return False
        return False

    def verify_post_success(
        self,
        first_paragraph: str,
        *,
        expected_username: str,
        attempted_after: float,
    ) -> bool:
        """Require fresh, attributable evidence on the authoritative self profile."""
        expected_text = str(first_paragraph or "").strip()
        expected_raw = str(expected_username or "").strip().lstrip("@").casefold()
        if "@" in expected_raw and "." in expected_raw.split("@")[-1]:
            expected_raw = expected_raw.split("@", 1)[0]
        if (
            not expected_text
            or not self._THREADS_USERNAME_PATTERN.fullmatch(expected_raw)
            or not isinstance(attempted_after, (int, float))
            or attempted_after <= 0
        ):
            self.last_error = "posting_unknown"
            return False

        print("  자기 프로필에서 새 게시물 증거 확인 중...")
        profile_path = f"/@{expected_raw}"
        for attempt in range(4):
            try:
                goto_threads_with_fallback(
                    self.page,
                    path=profile_path,
                    timeout=15000,
                    retries_per_url=1,
                )
                time.sleep(2)
                if not self.verify_account(expected_raw):
                    self.last_error = "posting_unknown"
                    return False

                articles = self.page.locator("article")
                for index in range(min(articles.count(), 5)):
                    article = articles.nth(index)
                    if not self._element_is_visible(article):
                        continue
                    if self._profile_article_proves_post(
                        article,
                        expected_text=expected_text,
                        expected_username=expected_raw,
                        attempted_after=float(attempted_after),
                    ):
                        self.last_error = None
                        print("  새 게시물 permalink, 내용, 시각 확인 완료")
                        return True
            except Exception:
                pass
            if attempt < 3:
                time.sleep(2)

        self.last_error = "posting_unknown"
        print("  이번 게시 시도에서 생성된 새 게시물을 증명하지 못했습니다")
        return False
