"""
Experimental Gemini Computer Use agent (browser control via Playwright).

This module wires up the official Computer Use preview model
(`gemini-2.5-computer-use-preview-10-2025`) with a simple action executor that
runs inside Playwright. It is intentionally sandboxed and opt-in; it does NOT
run anywhere in the main app flow by default.
"""
from __future__ import annotations

import json
import ipaddress
import logging
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from google import genai
from google.genai import types
from google.genai.types import Content, Part
from playwright.sync_api import Page, sync_playwright

from src.fs_security import secure_dir_permissions, secure_file_permissions
from src.secure_storage import protect_secret, unprotect_secret


SCREEN_WIDTH = 1440
SCREEN_HEIGHT = 900
logger = logging.getLogger(__name__)


def _denormalize_x(x: int, screen_width: int) -> int:
    return int(x / 1000 * screen_width)


def _denormalize_y(y: int, screen_height: int) -> int:
    return int(y / 1000 * screen_height)


@dataclass
class ExecutedAction:
    name: str
    result: Dict[str, Any]


class ComputerUseAgent:
    ALLOWED_NAVIGATION_HOSTS = {
        "threads.net",
        "www.threads.net",
        "instagram.com",
        "www.instagram.com",
        "facebook.com",
        "www.facebook.com",
        "www.google.com",
    }
    MAX_TYPE_TEXT_LENGTH = 4000
    ALLOWED_SAFE_KEYS = {
        "ENTER",
        "TAB",
        "SHIFT+TAB",
        "BACKSPACE",
        "DELETE",
        "ESCAPE",
        "ARROWUP",
        "ARROWDOWN",
        "ARROWLEFT",
        "ARROWRIGHT",
        "HOME",
        "END",
        "PAGEUP",
        "PAGEDOWN",
        "CONTROL+A",
        "CONTROL+C",
        "CONTROL+V",
        "CONTROL+X",
        "CONTROL+ENTER",
    }
    PLAYWRIGHT_INSTALL_TIMEOUT_SEC = 300

    def __init__(self, api_key: Optional[str] = None, headless: bool = False, profile_dir: str = ".threads_profile"):
        """
        Args:
            api_key: Google API key
            headless: whether to run browser in headless mode
            profile_dir: logical profile id (used to derive encrypted session path)
        """
        resolved_api_key = str(api_key or os.environ.get("GOOGLE_API_KEY") or "").strip()
        if resolved_api_key and resolved_api_key != "dummy-key-for-session-setup":
            self.client = genai.Client(api_key=resolved_api_key)
        else:
            self.client = None
        # Avoid keeping plaintext API key as a long-lived instance field.
        self.api_key = ""
        resolved_api_key = ""

        self.playwright = None
        self.browser = None
        self.context = None
        self.page: Optional[Page] = None
        self.headless = headless

        self.profile_name = self._normalize_profile_name(profile_dir)
        self.profile_path = self._resolve_profile_path(self.profile_name)
        self.legacy_profile_path = Path(os.path.abspath(profile_dir))
        self.profile_dir = str(self.profile_path)

    @classmethod
    def _is_allowed_navigation_url(cls, raw_url: str) -> bool:
        text = str(raw_url or "").strip()
        if not text:
            return False
        if text == "about:blank":
            return True

        try:
            parsed = urlparse(text)
        except Exception:
            return False

        if parsed.scheme != "https":
            return False
        host = (parsed.hostname or "").strip().lower()
        if not host:
            return False
        if host in {"localhost", "127.0.0.1", "::1"}:
            return False

        try:
            ip = ipaddress.ip_address(host)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return False
        except ValueError:
            # Not an IP literal. Continue domain checks.
            pass

        return host in cls.ALLOWED_NAVIGATION_HOSTS

    @classmethod
    def _sanitize_type_text(cls, value: Any) -> str:
        text = str(value or "")
        if len(text) > cls.MAX_TYPE_TEXT_LENGTH:
            raise ValueError("Input text exceeds maximum allowed length")
        if any(ord(ch) < 32 and ch not in {"\n", "\r", "\t"} for ch in text):
            raise ValueError("Input text contains disallowed control characters")
        return text

    @classmethod
    def _normalize_keys(cls, keys: str) -> str:
        text = re.sub(r"\s+", "", str(keys or "").upper())
        text = text.replace("CTRL", "CONTROL")
        return text

    @staticmethod
    def _normalize_profile_name(value: str) -> str:
        raw = str(value or "default").strip().replace("\\", "_").replace("/", "_")
        raw = raw.replace(" ", "_").replace(".", "_")
        safe = "".join(ch for ch in raw if ch.isalnum() or ch in {"_", "-"})
        return safe or "default"

    @staticmethod
    def _resolve_profile_path(profile_name: str) -> Path:
        root = Path.home() / ".shorts_thread_maker" / "sessions"
        root.mkdir(parents=True, exist_ok=True)
        secure_dir_permissions(root)

        profile_path = root / profile_name
        profile_path.mkdir(parents=True, exist_ok=True)
        secure_dir_permissions(profile_path)
        return profile_path

    def _get_storage_state_path(self) -> str:
        return str(self.profile_path / "storage_state.sec")

    def _load_storage_state(self) -> Optional[Dict[str, Any]]:
        secure_path = Path(self._get_storage_state_path())
        if secure_path.exists():
            try:
                payload = secure_path.read_text(encoding="utf-8")
                plain = unprotect_secret(payload)
                if plain:
                    data = json.loads(plain)
                    if isinstance(data, dict):
                        return data
            except Exception:
                pass

        # Legacy plaintext migration path.
        legacy_path = self.legacy_profile_path / "storage_state.json"
        if legacy_path.exists():
            try:
                data = json.loads(legacy_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    # Migrate immediately so plaintext session does not linger.
                    self._write_storage_state(data)
                    return data
            except Exception:
                pass

        return None

    def _write_storage_state(self, state: Dict[str, Any]) -> bool:
        secure_path = Path(self._get_storage_state_path())
        legacy_path = self.legacy_profile_path / "storage_state.json"
        payload = json.dumps(state, ensure_ascii=False)
        protected = protect_secret(payload, f"shorts_thread_maker.session.{self.profile_name}")
        if not protected:
            # Fail closed: remove legacy plaintext even when secure storage is unavailable.
            if legacy_path.exists():
                try:
                    legacy_path.unlink()
                except OSError:
                    pass
            return False

        secure_path.write_text(protected, encoding="utf-8")
        secure_file_permissions(secure_path)

        # Remove legacy plaintext if present.
        if legacy_path.exists():
            try:
                legacy_path.unlink()
            except OSError:
                pass
        return True

    # ------------------------------------------------------------------ setup
    def _launch_browser(self, channel: Optional[str] = None, executable_path: Optional[str] = None):
        launch_kwargs: Dict[str, Any] = {
            "headless": self.headless,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
        }
        if channel:
            launch_kwargs["channel"] = channel
        if executable_path:
            launch_kwargs["executable_path"] = executable_path
        return self.playwright.chromium.launch(**launch_kwargs)

    @staticmethod
    def _candidate_browser_paths() -> List[str]:
        env_candidates = [
            os.getenv("THREAD_AUTO_BROWSER_PATH", "").strip(),
            os.getenv("CHROME_PATH", "").strip(),
        ]
        default_candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            str(Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "Application" / "chrome.exe"),
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        ]

        unique_paths: List[str] = []
        seen: set[str] = set()
        for raw in [*env_candidates, *default_candidates]:
            if not raw:
                continue
            path = Path(raw).expanduser()
            if not path.exists() or not path.is_file():
                continue
            resolved = str(path.resolve())
            lowered = resolved.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            unique_paths.append(resolved)
        return unique_paths

    @classmethod
    def _iter_browser_candidates(cls) -> List[Dict[str, Optional[str]]]:
        candidates: List[Dict[str, Optional[str]]] = [
            {"channel": "chrome", "executable_path": None, "label": "chrome"},
            {"channel": "msedge", "executable_path": None, "label": "msedge"},
        ]
        for path in cls._candidate_browser_paths():
            candidates.append({"channel": None, "executable_path": path, "label": path})
        candidates.append({"channel": None, "executable_path": None, "label": "chromium"})
        return candidates
    @staticmethod
    def _is_missing_browser_error(exc: Exception) -> bool:
        text = str(exc or "").lower()
        markers = (
            "executable doesn't exist",
            "browser executable",
            "ms-playwright",
            "playwright install",
            "failed to launch",
        )
        return any(marker in text for marker in markers)

    @classmethod
    def _install_playwright_chromium(cls) -> bool:
        if getattr(sys, "frozen", False):
            return False

        try:
            completed = subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                capture_output=True,
                text=True,
                timeout=cls.PLAYWRIGHT_INSTALL_TIMEOUT_SEC,
                check=True,
            )
            stdout_text = str(completed.stdout or "").strip()
            if stdout_text:
                logger.info("Playwright ?ㅼ튂 異쒕젰: %s", stdout_text[:300])
            return True
        except Exception as exc:
            logger.warning("Playwright ?먮룞 ?ㅼ튂???ㅽ뙣?덉뒿?덈떎: %s", exc)
            return False

    def start_browser(self):
        if self.context:
            return

        self.playwright = sync_playwright().start()
        launch_errors: List[Exception] = []
        browser = None

        for candidate in self._iter_browser_candidates():
            channel = candidate.get("channel")
            executable_path = candidate.get("executable_path")
            label = str(candidate.get("label") or channel or "chromium")
            try:
                browser = self._launch_browser(channel=channel, executable_path=executable_path)
                logger.info("브라우저 실행 성공: %s", label)
                break
            except Exception as exc:
                launch_errors.append(exc)
                logger.warning("브라우저 실행 실패 (%s): %s", label, exc)

        missing_browser_error = any(self._is_missing_browser_error(err) for err in launch_errors)
        if browser is None and launch_errors and missing_browser_error:
            if self._install_playwright_chromium():
                try:
                    browser = self._launch_browser(channel=None, executable_path=None)
                    logger.info("Playwright Chromium 설치 후 브라우저 실행을 복구했습니다.")
                except Exception as exc:
                    launch_errors.append(exc)

        if browser is None:
            try:
                self.playwright.stop()
            except Exception:
                pass
            self.playwright = None

            last_error = launch_errors[-1] if launch_errors else RuntimeError("알 수 없는 브라우저 실행 실패")
            hint = (
                "Google Chrome 설치 상태를 확인하고, 개발 환경이라면 "
                "`python -m playwright install chromium` 명령을 실행해주세요."
                if missing_browser_error
                else "브라우저 보안 정책 또는 실행 권한을 확인해주세요."
            )
            raise RuntimeError(f"브라우저 시작에 실패했습니다. {hint} 원인: {last_error}") from last_error

        self.browser = browser

        context_kwargs: Dict[str, Any] = {
            "viewport": {"width": SCREEN_WIDTH, "height": SCREEN_HEIGHT},
        }
        storage_state = self._load_storage_state()
        if storage_state:
            context_kwargs["storage_state"] = storage_state

        self.context = self.browser.new_context(**context_kwargs)
        self.page = self.context.new_page()

    def save_session(self):
        """Persist storage state encrypted at rest."""
        if not self.context:
            return
        try:
            state = self.context.storage_state()
            if isinstance(state, dict):
                self._write_storage_state(state)
        except Exception:
            pass

    def clear_saved_session(self) -> None:
        """Delete persisted browser session state for this profile."""
        secure_path = Path(self._get_storage_state_path())
        legacy_path = self.legacy_profile_path / "storage_state.json"
        for path in (secure_path, legacy_path):
            try:
                if path.exists():
                    path.unlink()
            except OSError:
                pass

    def close(self):
        """Close browser and persist storage state."""
        try:
            self.save_session()
        except Exception:
            pass

        try:
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
        except Exception:
            pass
        finally:
            self.page = None
            self.browser = None
            self.context = None
            self.playwright = None

    # ---------------------------------------------------------- action runner
    @staticmethod
    def _safe_action_args(args: Dict[str, Any]) -> str:
        if not isinstance(args, dict) or not args:
            return ""

        sensitive_keys = {
            "text",
            "password",
            "passwd",
            "pwd",
            "token",
            "access_token",
            "refresh_token",
            "api_key",
            "authorization",
            "cookie",
        }

        items = []
        for key, value in args.items():
            key_text = str(key)
            if key_text.lower() in sensitive_keys:
                items.append(f"{key_text}=[REDACTED]")
                continue

            if isinstance(value, str):
                preview = value if len(value) <= 60 else value[:57] + "..."
                items.append(f"{key_text}={preview!r}")
            else:
                items.append(f"{key_text}={value!r}")

        return ", ".join(items[:8]) + (" ..." if len(items) > 8 else "")

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
            print(f"  execute: {fname} ({self._safe_action_args(args)})")

            safety = args.get("safety_decision")
            if safety:
                extra_fields["safety_acknowledgement"] = True

            try:
                if fname == "open_web_browser":
                    pass
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
                        if not self._is_allowed_navigation_url(str(url)):
                            raise ValueError(f"蹂댁븞 ?뺤콉?쇰줈 ?대룞??李⑤떒??URL?낅땲?? {url}")
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
                    text = self._sanitize_type_text(args.get("text", ""))
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
                        normalized = self._normalize_keys(str(keys))
                        if normalized not in self.ALLOWED_SAFE_KEYS:
                            raise ValueError(f"蹂댁븞 ?뺤콉?쇰줈 李⑤떒????議고빀?낅땲?? {keys}")
                        page.keyboard.press(keys)
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
            except Exception as e:
                print(f"  execution error ({fname}): {e}")
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
        if self.client is None:
            print("Google API client is not configured.")
            return None
        if os.getenv("THREAD_AUTO_ALLOW_AI_SCREENSHOTS", "").strip() != "1":
            print(
                "AI screenshot transfer is disabled. "
                "Set THREAD_AUTO_ALLOW_AI_SCREENSHOTS=1 to enable."
            )
            return None

        self.start_browser()
        assert self.page

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
                            data=initial_screenshot,
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

            if not response.candidates or len(response.candidates) == 0:
                print("No API candidates returned")
                return None

            candidate = response.candidates[0]
            contents.append(candidate.content)

            has_fc = any(getattr(p, "function_call", None) for p in candidate.content.parts)
            if not has_fc:
                final_text = " ".join(
                    [p.text for p in candidate.content.parts if getattr(p, "text", None)]
                )
                print(f"Task complete: {final_text}")
                return final_text

            results = self._execute_function_calls(candidate, self.page, SCREEN_WIDTH, SCREEN_HEIGHT)
            responses = self._get_function_responses(self.page, results)

            contents.append(
                Content(
                    role="user",
                    parts=[Part(function_response=r) for r in responses],
                )
            )

        print("Turn limit reached")
        return None


def main(argv: List[str]):
    if len(argv) < 2:
        print('Usage: python -m src.computer_use_agent "<goal text>"')
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
