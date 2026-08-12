import subprocess
import logging

from tools import windows_child_process_smoke


def test_smoke_exercises_absolute_system_commands_and_acl(monkeypatch, tmp_path):
    monkeypatch.setattr(windows_child_process_smoke.os, "name", "nt")
    calls = []

    def fake_run(executable, args, **kwargs):
        calls.append((executable, args, kwargs))
        returncode = 7 if executable == "cmd.exe" else 0
        if executable == "cmd.exe":
            logging.getLogger("src.system_process").warning(
                'external_process_failed {"operation":"packaged_smoke.expected_failure",'
                '"executable":"C:/Windows/System32/cmd.exe","return_code":7,'
                '"return_code_hex":"0x00000007","stderr":"token=[REDACTED]"}'
            )
        return subprocess.CompletedProcess(
            [f"C:/Windows/System32/{executable}", *args], returncode, "ok", ""
        )

    monkeypatch.setattr(windows_child_process_smoke, "run_system_command", fake_run)
    monkeypatch.setattr(windows_child_process_smoke, "secure_file_permissions", lambda _path: True)
    monkeypatch.setattr(windows_child_process_smoke.sys, "frozen", True, raising=False)
    output_path = tmp_path / "result.json"
    monkeypatch.setattr(windows_child_process_smoke.sys, "argv", ["smoke", str(output_path)])

    assert windows_child_process_smoke.main() == 0
    output = output_path.read_text(encoding="utf-8")
    assert '"passed": true' in output
    assert [call[0] for call in calls] == [
        "whoami.exe",
        "tasklist.exe",
        "icacls.exe",
        "cmd.exe",
    ]
