"""Use the official Grok Build CLI as a free, user-authenticated text provider."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

from src.system_process import resolve_system_executable, run_process


GROK_INSTALL_URL = "https://x.ai/cli"
_ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
_AUTH_ERROR_MARKERS = (
    "not logged in",
    "login required",
    "run `grok login`",
    "run grok login",
    "unauthorized",
    "authentication required",
    "authenticate",
)
_FREE_LIMIT_MARKERS = (
    "free-usage",
    "free usage",
    "usage limit",
    "limit reached",
    "upgrade",
    "buy credits",
    "credit limit",
)


class GrokCliError(RuntimeError):
    """A classified Grok CLI failure."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class GrokCliStatus:
    code: str
    message: str
    executable: str = ""
    version: str = ""

    @property
    def ready(self) -> bool:
        return self.code == "ready"


def find_grok_cli() -> str:
    """Find a supported Grok CLI executable without reading its credentials."""
    configured = str(os.environ.get("GROK_CLI_PATH", "") or "").strip()
    candidates = [
        configured,
        shutil.which("grok.exe") or "",
        shutil.which("grok") or "",
    ]

    if os.name == "nt":
        user_home = Path.home()
        app_data = Path(os.environ.get("APPDATA", user_home / "AppData" / "Roaming"))
        local_app_data = Path(
            os.environ.get("LOCALAPPDATA", user_home / "AppData" / "Local")
        )
        candidates.extend(
            [
                str(app_data / "npm" / "grok.cmd"),
                str(app_data / "npm" / "grok.exe"),
                str(user_home / ".local" / "bin" / "grok.exe"),
                str(local_app_data / "Programs" / "grok" / "grok.exe"),
            ]
        )

    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate).expanduser()
        if path.is_file():
            return str(path.resolve())
    return ""


def _command_prefix(executable: str) -> list[str]:
    path = Path(executable)
    if os.name == "nt" and path.suffix.lower() in {".cmd", ".bat"}:
        command_processor = resolve_system_executable("cmd.exe")
        return [command_processor, "/d", "/s", "/c", str(path)]
    return [str(path)]


def _classify_failure(output: str, return_code: int) -> GrokCliError:
    normalized = str(output or "").strip()
    lowered = normalized.lower()
    if any(marker in lowered for marker in _FREE_LIMIT_MARKERS):
        return GrokCliError(
            "free_limit",
            "Grok 무료 사용량이 끝났습니다. 템플릿 문구로 계속합니다.",
        )
    if any(marker in lowered for marker in _AUTH_ERROR_MARKERS):
        return GrokCliError(
            "not_logged_in",
            "Grok 로그인이 필요합니다. 설정에서 Grok 로그인을 진행해주세요.",
        )
    if "timed out" in lowered or "timeout" in lowered:
        return GrokCliError("timeout", "Grok 응답 시간이 초과되었습니다.")
    if any(marker in lowered for marker in ("network", "connection", "dns", "tls")):
        return GrokCliError("network", "Grok 서버에 연결할 수 없습니다.")
    detail = normalized[-500:] if normalized else f"exit code {return_code}"
    return GrokCliError("process_error", f"Grok CLI 실행 실패: {detail}")


class GrokCliProvider:
    """Run short text prompts through a locally authenticated Grok Build CLI."""

    def __init__(self, executable: Optional[str] = None, timeout_seconds: int = 60):
        self.executable = str(executable or find_grok_cli() or "")
        self.timeout_seconds = max(10, int(timeout_seconds))
        self._lock = threading.Lock()
        self._workspace = Path(tempfile.gettempdir()) / "shorts_thread_maker_grok"

    def _run(
        self,
        args: Sequence[str],
        *,
        timeout: Optional[int] = None,
    ) -> subprocess.CompletedProcess:
        executable = self.executable or find_grok_cli()
        if not executable:
            raise GrokCliError(
                "not_installed",
                "Grok CLI가 설치되지 않았습니다. 설정에서 설치 안내를 확인해주세요.",
            )
        self.executable = executable
        self._workspace.mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        env.update(
            {
                "NO_COLOR": "1",
                "TERM": "dumb",
                "GROK_CLIPBOARD_NO_OSC52": "1",
            }
        )
        command = _command_prefix(executable) + list(args)
        try:
            return run_process(
                command,
                operation="grok_cli.run",
                cwd=str(self._workspace),
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout or self.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise GrokCliError("timeout", "Grok 응답 시간이 초과되었습니다.") from exc
        except OSError as exc:
            raise GrokCliError("process_error", f"Grok CLI를 실행할 수 없습니다: {exc}") from exc

    def status(self) -> GrokCliStatus:
        executable = self.executable or find_grok_cli()
        if not executable:
            return GrokCliStatus(
                "not_installed",
                "Grok CLI 미설치",
            )
        self.executable = executable

        try:
            version_result = self._run(["version"], timeout=10)
        except GrokCliError as exc:
            return GrokCliStatus(exc.code, str(exc), executable=executable)

        version_output = _ANSI_ESCAPE.sub(
            "",
            f"{version_result.stdout}\n{version_result.stderr}",
        ).strip()
        if version_result.returncode != 0:
            error = _classify_failure(version_output, version_result.returncode)
            return GrokCliStatus(error.code, str(error), executable=executable)

        try:
            auth_result = self._run(["sessions", "list", "-n", "1"], timeout=20)
        except GrokCliError as exc:
            return GrokCliStatus(
                exc.code,
                str(exc),
                executable=executable,
                version=version_output,
            )

        auth_output = _ANSI_ESCAPE.sub(
            "",
            f"{auth_result.stdout}\n{auth_result.stderr}",
        ).strip()
        auth_lowered = auth_output.lower()
        if any(marker in auth_lowered for marker in _AUTH_ERROR_MARKERS):
            error = _classify_failure(auth_output, auth_result.returncode)
            return GrokCliStatus(
                error.code,
                str(error),
                executable=executable,
                version=version_output,
            )
        if auth_result.returncode == 0:
            return GrokCliStatus(
                "ready",
                "Grok CLI 로그인됨 · 무료 사용 가능",
                executable=executable,
                version=version_output,
            )

        error = _classify_failure(auth_output, auth_result.returncode)
        return GrokCliStatus(
            error.code,
            str(error),
            executable=executable,
            version=version_output,
        )

    def login(self, timeout_seconds: int = 300) -> GrokCliStatus:
        """Open the official Grok browser login flow and wait for completion."""
        result = self._run(["login", "--oauth"], timeout=max(60, int(timeout_seconds)))
        output = _ANSI_ESCAPE.sub("", f"{result.stdout}\n{result.stderr}").strip()
        if result.returncode != 0:
            raise _classify_failure(output, result.returncode)
        return self.status()

    def generate_text(self, prompt: str) -> str:
        prompt_text = str(prompt or "").strip()
        if not prompt_text:
            return ""

        self._workspace.mkdir(parents=True, exist_ok=True)
        prompt_file = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=str(self._workspace),
                prefix="prompt_",
                suffix=".txt",
                delete=False,
            ) as handle:
                handle.write(prompt_text)
                prompt_file = Path(handle.name)

            with self._lock:
                result = self._run(
                    [
                        "--no-auto-update",
                        "--disable-web-search",
                        "--no-memory",
                        "--no-subagents",
                        "--tools",
                        "",
                        "--max-turns",
                        "1",
                        "--permission-mode",
                        "dontAsk",
                        "--verbatim",
                        "--cwd",
                        str(self._workspace),
                        "--prompt-file",
                        str(prompt_file),
                        "--output-format",
                        "plain",
                    ]
                )
        finally:
            if prompt_file is not None:
                try:
                    prompt_file.unlink(missing_ok=True)
                except OSError:
                    pass

        output = _ANSI_ESCAPE.sub("", str(result.stdout or "")).strip()
        error_output = _ANSI_ESCAPE.sub("", str(result.stderr or "")).strip()
        if result.returncode != 0:
            raise _classify_failure(
                "\n".join(part for part in (output, error_output) if part),
                result.returncode,
            )
        if not output:
            raise GrokCliError("empty_output", "Grok이 빈 응답을 반환했습니다.")
        return output


def get_grok_cli_status() -> GrokCliStatus:
    return GrokCliProvider().status()


def login_to_grok_cli() -> GrokCliStatus:
    return GrokCliProvider().login()
