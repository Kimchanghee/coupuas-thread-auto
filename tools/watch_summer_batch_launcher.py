"""Keep the prepared summer batch launcher alive while unfinished work exists."""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER_PATH = ROOT / "tools" / "launch_summer_batch_in_app.py"
RESUME_PATH = Path.home() / ".shorts_thread_maker" / "upload_resume_queue.json"
LOG_PATH = Path.home() / ".shorts_thread_maker" / "logs" / "summer_batch_watchdog.log"
PROCESS_MARKER = "launch_summer_batch_in_app.py"
UNFINISHED_STATUSES = {"pending", "running"}
DEFAULT_CHECK_INTERVAL_SECONDS = 60

LOGGER = logging.getLogger("summer_batch_watchdog")


def load_resume_payload(path: Path = RESUME_PATH) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        LOGGER.exception("Failed to read resume queue: %s", path)
        return {}


def unfinished_count(payload: dict[str, Any]) -> int:
    count = 0
    for item in payload.get("items") or []:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "").strip().lower()
        if status in UNFINISHED_STATUSES:
            count += 1
    return count


def has_unfinished_queue(path: Path = RESUME_PATH) -> bool:
    return unfinished_count(load_resume_payload(path)) > 0


def _run_powershell(script: str) -> str:
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        LOGGER.warning("PowerShell probe failed: %s", result.stderr.strip())
        return ""
    return result.stdout.strip()


def is_launcher_running(marker: str = PROCESS_MARKER) -> bool:
    escaped_marker = marker.replace("'", "''")
    script = (
        "Get-CimInstance Win32_Process | "
        "Where-Object { $_.Name -match '^pythonw?\\.exe$' "
        f"-and $_.CommandLine -like '*{escaped_marker}*' }} | "
        "Select-Object -First 1 -ExpandProperty ProcessId"
    )
    return bool(_run_powershell(script))


def _pythonw_executable() -> Path:
    executable = Path(sys.executable)
    if os.name == "nt" and executable.name.lower() == "python.exe":
        pythonw = executable.with_name("pythonw.exe")
        if pythonw.exists():
            return pythonw
    return executable


def _launcher_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("THREAD_AUTO_DEV_BYPASS_WORK_QUOTA", "1")
    env.setdefault("THREAD_AUTO_LOGIN_WAIT_SECONDS", str(24 * 60 * 60))
    env.setdefault("THREAD_AUTO_DISABLE_ACTIVITY_LOGS", "1")
    env.setdefault("THREAD_AUTO_DISABLE_AUTO_UPDATE", "1")
    env.setdefault("THREAD_AUTO_DISABLE_HEARTBEAT", "1")
    env.setdefault("THREAD_AUTO_DISABLE_RESUME_PROMPT", "1")
    env.setdefault("THREAD_AUTO_FORCE_SINGLE_POST", "1")
    env.setdefault("THREAD_AUTO_STDERR_PRINTS_INFO", "1")
    return env


def start_launcher() -> subprocess.Popen[Any]:
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    return subprocess.Popen(
        [str(_pythonw_executable()), str(LAUNCHER_PATH)],
        cwd=str(ROOT),
        env=_launcher_env(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )


def run_once(path: Path = RESUME_PATH) -> str:
    payload = load_resume_payload(path)
    pending = unfinished_count(payload)
    if pending <= 0:
        LOGGER.info("No unfinished queue items remain; watchdog is idle.")
        return "no_unfinished_queue"
    if is_launcher_running():
        LOGGER.info("Launcher already running; unfinished=%s.", pending)
        return "already_running"

    process = start_launcher()
    LOGGER.warning("Launcher was not running; restarted pid=%s unfinished=%s.", process.pid, pending)
    return "started"


def watch_forever(interval_seconds: int = DEFAULT_CHECK_INTERVAL_SECONDS) -> None:
    while True:
        status = run_once()
        if status == "no_unfinished_queue":
            return
        time.sleep(max(int(interval_seconds), 10))


def setup_logging() -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler(LOG_PATH, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Check once and exit.")
    parser.add_argument(
        "--interval",
        type=int,
        default=DEFAULT_CHECK_INTERVAL_SECONDS,
        help="Watch interval in seconds.",
    )
    args = parser.parse_args(argv)

    setup_logging()
    if args.once:
        run_once()
        return 0
    watch_forever(args.interval)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
