import json
from pathlib import Path
from types import SimpleNamespace

from tools import watch_summer_batch_launcher as watchdog


def _write_queue(path: Path, statuses: list[str]) -> None:
    path.write_text(
        json.dumps({"items": [{"url": f"https://example.com/{idx}", "status": status} for idx, status in enumerate(statuses)]}),
        encoding="utf-8",
    )


def test_has_unfinished_queue_counts_pending_and_running(tmp_path):
    queue_path = tmp_path / "upload_resume_queue.json"
    _write_queue(queue_path, ["completed", "pending", "running", "failed"])

    payload = watchdog.load_resume_payload(queue_path)

    assert watchdog.unfinished_count(payload) == 2
    assert watchdog.has_unfinished_queue(queue_path) is True


def test_missing_or_completed_queue_is_idle(tmp_path):
    missing_path = tmp_path / "missing.json"
    completed_path = tmp_path / "upload_resume_queue.json"
    _write_queue(completed_path, ["completed", "failed"])

    assert watchdog.has_unfinished_queue(missing_path) is False
    assert watchdog.run_once(completed_path) == "no_unfinished_queue"


def test_run_once_starts_launcher_when_queue_unfinished(monkeypatch, tmp_path):
    queue_path = tmp_path / "upload_resume_queue.json"
    _write_queue(queue_path, ["pending"])
    started = []

    monkeypatch.setattr(watchdog, "is_launcher_running", lambda: False)
    monkeypatch.setattr(watchdog, "start_launcher", lambda: started.append(True) or SimpleNamespace(pid=1234))

    assert watchdog.run_once(queue_path) == "started"
    assert started == [True]


def test_run_once_does_not_start_duplicate_launcher(monkeypatch, tmp_path):
    queue_path = tmp_path / "upload_resume_queue.json"
    _write_queue(queue_path, ["running"])

    monkeypatch.setattr(watchdog, "is_launcher_running", lambda: True)
    monkeypatch.setattr(watchdog, "start_launcher", lambda: (_ for _ in ()).throw(AssertionError("duplicate start")))

    assert watchdog.run_once(queue_path) == "already_running"


def test_powershell_probe_uses_hidden_window_flags(monkeypatch):
    captured = {}

    def fake_run(*args, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(returncode=0, stdout="1234\n", stderr="")

    monkeypatch.setattr(watchdog.subprocess, "run", fake_run)

    assert watchdog._run_powershell("Write-Output 1234") == "1234"

    if watchdog.os.name == "nt":
        assert captured["creationflags"] & watchdog.subprocess.CREATE_NO_WINDOW
        assert captured["startupinfo"].wShowWindow == watchdog.subprocess.SW_HIDE


def test_start_launcher_does_not_hide_gui_window(monkeypatch):
    captured = {}

    def fake_popen(*args, **kwargs):
        captured["args"] = args
        captured.update(kwargs)
        return SimpleNamespace(pid=1234)

    monkeypatch.setattr(watchdog.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(watchdog, "_pythonw_executable", lambda: Path("pythonw.exe"))

    process = watchdog.start_launcher()

    assert process.pid == 1234
    assert "startupinfo" not in captured
    if watchdog.os.name == "nt":
        assert captured["creationflags"] & watchdog.subprocess.CREATE_NEW_PROCESS_GROUP
        assert not (captured["creationflags"] & watchdog.subprocess.CREATE_NO_WINDOW)
        assert not (captured["creationflags"] & watchdog.subprocess.DETACHED_PROCESS)
