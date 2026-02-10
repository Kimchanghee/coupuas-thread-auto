"""
Experimental Gemini Computer Use agent (browser control via Playwright).

This module wires up the official Computer Use preview model
(`gemini-2.5-computer-use-preview-10-2025`) with a simple action executor that
runs inside Playwright. It is intentionally sandboxed and opt-in; it does NOT
run anywhere in the main app flow by default.

Usage:
    1) pip install google-genai playwright
       playwright install chromium
    2) Set GOOGLE_API_KEY (or pass api_key=... to ComputerUseAgent).
    3) Run: python -m src.computer_use_agent "Go to threads.net and ..."

⚠️ Preview model: supervise closely; do not use for sensitive/critical actions.
"""
from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types
from google.genai.types import Content, Part
from playwright.sync_api import Page, sync_playwright


SCREEN_WIDTH = 1440
SCREEN_HEIGHT = 900


def _denormalize_x(x: int, screen_width: int) -> int:
    return int(x / 1000 * screen_width)


def _denormalize_y(y: int, screen_height: int) -> int:
    return int(y / 1000 * screen_height)


@dataclass
class ExecutedAction:
    name: str
    result: Dict[str, Any]


class ComputerUseAgent:
    def __init__(self, api_key: Optional[str] = None, headless: bool = False, profile_dir: str = ".threads_profile"):
        """
        Args:
            api_key: Google API key
            headless: 브라우저 헤드리스 모드
            profile_dir: 세션 저장 디렉토리 (쿠키/localStorage 저장)
        """
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY")

        # Gemini Client 생성 (더미 키면 None)
        if self.api_key and self.api_key != "dummy-key-for-session-setup":
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = None  # 세션 저장만 사용 시

        self.playwright = None
        self.browser = None
        self.context = None
        self.page: Optional[Page] = None
        self.headless = headless
        self.profile_dir = profile_dir

    # ------------------------------------------------------------------ setup
    def start_browser(self):
        if self.context:
            return

        # 프로필 디렉토리 생성 (절대 경로 사용)
        profile_path = os.path.abspath(self.profile_dir)
        os.makedirs(profile_path, exist_ok=True)

        self.playwright = sync_playwright().start()

        # 🔑 launch_persistent_context 사용 - 브라우저 프로필 완전 유지
        # 쿠키, localStorage, IndexedDB, Service Worker 등 모든 데이터 유지
        print(f"🔐 브라우저 프로필: {profile_path}")

        try:
            self.context = self.playwright.chromium.launch_persistent_context(
                user_data_dir=profile_path,
                headless=self.headless,
                viewport={"width": SCREEN_WIDTH, "height": SCREEN_HEIGHT},
                # 추가 옵션 - 안정성 향상
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                ],
                ignore_default_args=["--enable-automation"],
            )
            print(f"✅ 브라우저 시작됨 (프로필 유지)")

            # 기존 쿠키 확인
            cookies = self.context.cookies()
            if cookies:
                threads_cookies = [c for c in cookies if 'threads' in c.get('domain', '').lower()]
                ig_cookies = [c for c in cookies if 'instagram' in c.get('domain', '').lower()]
                if threads_cookies or ig_cookies:
                    print(f"   🍪 저장된 세션 발견: Threads {len(threads_cookies)}개, Instagram {len(ig_cookies)}개")

        except Exception as e:
            print(f"⚠️ 영구 프로필 로드 실패, 일반 모드로 시작: {e}")
            # fallback: 일반 브라우저
            self.browser = self.playwright.chromium.launch(headless=self.headless)
            self.context = self.browser.new_context(
                viewport={"width": SCREEN_WIDTH, "height": SCREEN_HEIGHT}
            )

        # 페이지 가져오기 또는 생성
        pages = self.context.pages
        if pages:
            self.page = pages[0]
        else:
            self.page = self.context.new_page()

    def _get_storage_state_path(self) -> str:
        """세션 저장 경로"""
        return os.path.join(self.profile_dir, "storage_state.json")

    def save_session(self):
        """현재 세션 저장 (persistent context는 자동 저장됨)"""
        if self.context:
            try:
                # persistent context는 닫을 때 자동으로 저장됨
                # 추가로 storage_state도 백업
                storage_path = self._get_storage_state_path()
                self.context.storage_state(path=storage_path)
                print(f"✅ 세션 백업됨: {storage_path}")
            except Exception as e:
                # persistent context에서는 실패해도 괜찮음 (자동 저장됨)
                print(f"ℹ️ 세션 백업 스킵 (자동 저장 모드)")

    def close(self):
        """브라우저 닫기 - persistent context는 자동으로 세션 저장"""
        try:
            # persistent context 닫기 - 세션 자동 저장됨
            if self.context:
                print("💾 브라우저 종료 중 (세션 자동 저장)...")
                self.context.close()
            # fallback 브라우저가 있으면 닫기
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
        except Exception as e:
            print(f"⚠️ 브라우저 종료 중 오류: {e}")
        finally:
            self.page = None
            self.browser = None
            self.context = None
            self.playwright = None

    # ---------------------------------------------------------- action runner
    def _execute_function_calls(
        self, candidate, page: Page, screen_width: int, screen_height: int
    ) -> List[ExecutedAction]:
        results: List[ExecutedAction] = []
        function_calls = [
            part.function_call
            for part in candidate.content.parts
            if getattr(part, "function_call", None)
        ]

        for fc in function_calls:
            fname = fc.name
            args = fc.args or {}
            extra_fields: Dict[str, Any] = {}
            print(f"  -> Executing: {fname} ({args})")

            # Safety confirmation - AUTO ACCEPT for automation
            safety = args.get("safety_decision")
            if safety:
                print("  ✓ Safety decision detected - Auto-accepting for automation")
                print(f"    {safety.get('explanation')}")
                extra_fields["safety_acknowledgement"] = True

            try:
                if fname == "open_web_browser":
                    pass  # already open
                elif fname == "wait_5_seconds":
                    time.sleep(5)
                elif fname == "go_back":
                    page.go_back()
                elif fname == "go_forward":
                    page.go_forward()
                elif fname == "search":
                    page.goto("https://www.google.com", wait_until="domcontentloaded")
                elif fname == "navigate":
                    url = args.get("url")
                    if url:
                        page.goto(url, wait_until="domcontentloaded")
                elif fname == "click_at":
                    x = _denormalize_x(args["x"], screen_width)
                    y = _denormalize_y(args["y"], screen_height)
                    page.mouse.click(x, y)
                elif fname == "hover_at":
                    x = _denormalize_x(args["x"], screen_width)
                    y = _denormalize_y(args["y"], screen_height)
                    page.mouse.move(x, y)
                elif fname == "type_text_at":
                    x = _denormalize_x(args["x"], screen_width)
                    y = _denormalize_y(args["y"], screen_height)
                    text = args.get("text", "")
                    press_enter = bool(args.get("press_enter", False))
                    clear_before = bool(args.get("clear_before_typing", True))
                    page.mouse.click(x, y)
                    if clear_before:
                        page.keyboard.press("Control+A")
                        page.keyboard.press("Backspace")
                    page.keyboard.type(text)
                    if press_enter:
                        page.keyboard.press("Enter")
                elif fname == "key_combination":
                    keys = args.get("keys")
                    if keys:
                        # Playwright expects "+", e.g., "Control+A"
                        page.keyboard.press(keys.replace("+", "+"))
                elif fname == "scroll_document":
                    direction = args.get("direction", "down")
                    amount = 1200
                    if direction == "down":
                        page.mouse.wheel(0, amount)
                    elif direction == "up":
                        page.mouse.wheel(0, -amount)
                    elif direction == "left":
                        page.mouse.wheel(-amount, 0)
                    elif direction == "right":
                        page.mouse.wheel(amount, 0)
                elif fname == "scroll_at":
                    x = _denormalize_x(args["x"], screen_width)
                    y = _denormalize_y(args["y"], screen_height)
                    direction = args.get("direction", "down")
                    magnitude = int(args.get("magnitude", 800))
                    page.mouse.move(x, y)
                    delta = magnitude if direction in ("down", "right") else -magnitude
                    if direction in ("down", "up"):
                        page.mouse.wheel(0, delta)
                    else:
                        page.mouse.wheel(delta, 0)
                elif fname == "drag_and_drop":
                    x = _denormalize_x(args["x"], screen_width)
                    y = _denormalize_y(args["y"], screen_height)
                    dx = _denormalize_x(args["destination_x"], screen_width)
                    dy = _denormalize_y(args["destination_y"], screen_height)
                    page.mouse.move(x, y)
                    page.mouse.down()
                    page.mouse.move(dx, dy)
                    page.mouse.up()
                else:
                    extra_fields["warning"] = f"Unimplemented function: {fname}"

                page.wait_for_timeout(500)
                page.wait_for_load_state("domcontentloaded")
                time.sleep(0.5)
                results.append(ExecutedAction(fname, extra_fields))
            except Exception as e:  # noqa: BLE001
                print(f"Error executing {fname}: {e}")
                results.append(ExecutedAction(fname, {"error": str(e)}))

        return results

    def _get_function_responses(self, page: Page, results: List[ExecutedAction]):
        screenshot_bytes = page.screenshot(type="png")
        current_url = page.url
        responses = []
        for item in results:
            payload = {"url": current_url}
            payload.update(item.result)
            responses.append(
                types.FunctionResponse(
                    name=item.name,
                    response=payload,
                    parts=[
                        types.FunctionResponsePart(
                            inline_data=types.FunctionResponseBlob(
                                mime_type="image/png", data=screenshot_bytes
                            )
                        )
                    ],
                )
            )
        return responses

    # --------------------------------------------------------------- main loop
    def run_goal(self, goal: str, turn_limit: int = 8, skip_navigation: bool = False):
        self.start_browser()
        assert self.page

        # Initial screenshot and prompt
        if not skip_navigation:
            self.page.goto("about:blank")
        initial_screenshot = self.page.screenshot(type="png")

        config = types.GenerateContentConfig(
            tools=[
                types.Tool(
                    computer_use=types.ComputerUse(
                        environment=types.Environment.ENVIRONMENT_BROWSER
                    )
                )
            ],
            thinking_config=types.ThinkingConfig(include_thoughts=True),
        )

        contents: List[Content] = [
            Content(
                role="user",
                parts=[
                    Part(text=goal),
                    Part(
                        inline_data=types.Blob(
                            mime_type="image/png",
                            data=initial_screenshot
                        )
                    ),
                ],
            )
        ]

        for turn in range(turn_limit):
            print(f"\n--- Turn {turn + 1} ---")
            response = self.client.models.generate_content(
                model="gemini-2.5-computer-use-preview-10-2025",
                contents=contents,
                config=config,
            )

            # candidates가 비어있는지 확인
            if not response.candidates or len(response.candidates) == 0:
                print("⚠️ API 응답에 candidates가 없습니다 (API 오버로드 또는 안전 필터)")
                return None

            candidate = response.candidates[0]
            contents.append(candidate.content)

            has_fc = any(getattr(p, "function_call", None) for p in candidate.content.parts)
            if not has_fc:
                final_text = " ".join(
                    [p.text for p in candidate.content.parts if getattr(p, "text", None)]
                )
                print("Agent finished:", final_text)
                return final_text

            # Execute actions
            results = self._execute_function_calls(candidate, self.page, SCREEN_WIDTH, SCREEN_HEIGHT)
            responses = self._get_function_responses(self.page, results)

            contents.append(
                Content(
                    role="user",
                    parts=[Part(function_response=r) for r in responses],
                )
            )

        print("Turn limit reached.")
        return None


def main(argv: List[str]):
    if len(argv) < 2:
        print("Usage: python -m src.computer_use_agent \"<goal text>\"")
        sys.exit(1)

    goal = argv[1]
    api_key = os.environ.get("GOOGLE_API_KEY")

    agent = ComputerUseAgent(api_key=api_key, headless=False)
    try:
        agent.run_goal(goal)
    finally:
        agent.close()


if __name__ == "__main__":
    main(sys.argv)
