import contextlib
import logging
import subprocess
from pathlib import Path

import pytest

from src import system_process


def test_resolve_system_executable_uses_absolute_system32_paths():
    if system_process.os.name != "nt":
        pytest.skip("Windows-only executable resolution")

    tasklist = Path(system_process.resolve_system_executable("tasklist"))
    powershell = Path(system_process.resolve_system_executable("powershell"))

    assert tasklist.is_absolute()
    assert tasklist.name.lower() == "tasklist.exe"
    assert tasklist.parent.name.lower() == "system32"
    assert powershell.is_absolute()
    assert powershell.name.lower() == "powershell.exe"
    assert powershell.parts[-3:-1] == ("WindowsPowerShell", "v1.0")


def test_system_executable_resolution_ignores_environment_and_rejects_paths(
    monkeypatch, tmp_path
):
    if system_process.os.name != "nt":
        pytest.skip("Windows-only executable resolution")

    monkeypatch.setenv("SystemRoot", str(tmp_path))
    resolved = Path(system_process.resolve_system_executable("cmd.exe"))

    assert tmp_path not in resolved.parents
    assert resolved.parent.name.lower() == "system32"
    with pytest.raises(ValueError):
        system_process.resolve_system_executable(str(tmp_path / "cmd.exe"))


def test_sanitized_environment_removes_python_and_pyinstaller_state(monkeypatch, tmp_path):
    monkeypatch.setattr(system_process.sys, "_MEIPASS", str(tmp_path), raising=False)
    env = {
        "PATH": f"{tmp_path}{system_process.os.pathsep}C:\\Windows\\System32",
        "PYTHONHOME": "bundle-python",
        "_PYI_APPLICATION_HOME_DIR": "bundle",
        "PYINSTALLER_RESET_ENVIRONMENT": "1",
        "SAFE_VALUE": "kept",
    }

    cleaned = system_process.sanitized_environment(env)

    assert cleaned["SAFE_VALUE"] == "kept"
    assert "PYTHONHOME" not in cleaned
    assert "_PYI_APPLICATION_HOME_DIR" not in cleaned
    assert "PYINSTALLER_RESET_ENVIRONMENT" not in cleaned
    assert str(tmp_path) not in cleaned["PATH"]


def test_run_process_forces_hidden_shell_free_execution_and_logs_failure(monkeypatch, caplog):
    captured = {}

    class FakeProcess:
        returncode = 7

        def communicate(self, input=None, timeout=None):
            return "out", "err"

        def poll(self):
            return self.returncode

    def fake_popen(command, **kwargs):
        captured.update(command=command, kwargs=kwargs)
        return FakeProcess()

    monkeypatch.setattr(system_process.subprocess, "Popen", fake_popen)
    with caplog.at_level(logging.WARNING):
        result = system_process.run_process(
            ["tasklist", "/nh"],
            system_command=True,
            capture_output=True,
            text=True,
            shell=True,
            operation="test.tasklist",
        )

    assert result.returncode == 7
    assert Path(captured["command"][0]).is_absolute()
    assert captured["kwargs"]["shell"] is False
    assert captured["kwargs"]["creationflags"] == subprocess.CREATE_NO_WINDOW
    assert captured["kwargs"]["startupinfo"].wShowWindow == subprocess.SW_HIDE
    assert "encoding" not in captured["kwargs"]
    record = next(
        record for record in caplog.records
        if record.getMessage().startswith("external_process_failed ")
    )
    assert record.process_operation == "test.tasklist"
    assert record.process_return_code == 7
    assert record.process_return_code_hex == "0x00000007"
    assert record.process_stdout == "out"
    assert record.process_stderr == "err"
    assert record.process_duration_ms >= 0
    assert record.process_arguments == ["/nh"]
    assert record.process_correlation_id
    assert '"operation":"test.tasklist"' in record.getMessage()
    assert '"return_code":7' in record.getMessage()
    assert '"return_code_hex":"0x00000007"' in record.getMessage()


def test_popen_process_applies_same_spawn_policy(monkeypatch):
    captured = {}

    class FakeProcess:
        pass

    process = FakeProcess()

    def fake_popen(command, **kwargs):
        captured.update(command=command, kwargs=kwargs)
        return process

    monkeypatch.setattr(system_process.subprocess, "Popen", fake_popen)
    result = system_process.popen_process(
        ["powershell", "-NoProfile"],
        system_command=True,
        shell=True,
    )

    assert result is process
    assert Path(captured["command"][0]).name.lower() == "powershell.exe"
    assert captured["kwargs"]["shell"] is False
    assert captured["kwargs"]["creationflags"] == subprocess.CREATE_NO_WINDOW
    assert captured["kwargs"]["startupinfo"].wShowWindow == subprocess.SW_HIDE


def test_run_process_restores_loader_state_before_waiting(monkeypatch, caplog):
    loader_state = {"clean": False}

    @contextlib.contextmanager
    def clean_loader_state():
        loader_state["clean"] = True
        try:
            yield
        finally:
            loader_state["clean"] = False

    class FakeProcess:
        returncode = -1073741502  # 0xC0000142

        def communicate(self, input=None, timeout=None):
            assert loader_state["clean"] is False
            return "token=supersecret", "한글 오류 Authorization: Bearer another-secret"

        def poll(self):
            return self.returncode

    def fake_popen(command, **kwargs):
        assert loader_state["clean"] is True
        return FakeProcess()

    monkeypatch.setattr(system_process, "_clean_windows_dll_directory", clean_loader_state)
    monkeypatch.setattr(system_process.subprocess, "Popen", fake_popen)

    with caplog.at_level(logging.WARNING):
        result = system_process.run_process(
            ["tool.exe", "--token", "cli-secret", r"C:\사용자\target.txt"],
            capture_output=True,
            text=True,
            operation="test.ntstatus",
        )

    assert result.returncode == -1073741502
    log_text = caplog.text
    assert "test.ntstatus" in log_text
    assert "0xC0000142" in log_text
    assert "[REDACTED]" in log_text
    assert "supersecret" not in log_text
    assert "another-secret" not in log_text
    assert "cli-secret" not in log_text
    assert "한글 오류" in log_text
    assert r"C:\\사용자\\target.txt" in log_text


def test_frozen_windows_loader_and_error_modes_are_restored(monkeypatch):
    calls = []

    class FakeKernel32:
        def GetDllDirectoryW(self, size, buffer):
            if buffer is None:
                return len(r"C:\\bundle")
            buffer.value = r"C:\\bundle"
            return len(buffer.value)

        def SetDllDirectoryW(self, value):
            calls.append(("dll", value))
            return 1

        def GetErrorMode(self):
            return 0x0001

        def SetErrorMode(self, value):
            calls.append(("error", value))
            return 0x0001

    monkeypatch.setattr(system_process.sys, "frozen", True, raising=False)
    monkeypatch.setattr(
        system_process.ctypes,
        "windll",
        type("FakeWindll", (), {"kernel32": FakeKernel32()})(),
    )

    with system_process._clean_windows_dll_directory():
        assert calls == [("dll", None), ("error", 0x0003)]

    assert calls[-2:] == [("error", 0x0001), ("dll", r"C:\\bundle")]
