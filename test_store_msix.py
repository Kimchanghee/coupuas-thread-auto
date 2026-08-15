import xml.etree.ElementTree as ET
from pathlib import Path
import subprocess
import sys

import pytest
from PIL import Image

from tools import build_store_msix


FOUNDATION_NS = "http://schemas.microsoft.com/appx/manifest/foundation/windows10"
UAP10_NS = "http://schemas.microsoft.com/appx/manifest/uap/windows10/10"
RESCAP_NS = (
    "http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities"
)
REPO_ROOT = Path(__file__).resolve().parent


def test_normalize_msix_version_requires_four_numeric_parts():
    assert build_store_msix.normalize_msix_version("v3.0.62") == "3.0.62.0"
    assert build_store_msix.normalize_msix_version("3.0.62.4") == "3.0.62.4"

    with pytest.raises(ValueError):
        build_store_msix.normalize_msix_version("3.0.beta")


def test_build_manifest_uses_partner_center_identity():
    manifest = build_store_msix.build_manifest("3.0.62.0")
    root = ET.fromstring(manifest)

    identity = root.find(f"{{{FOUNDATION_NS}}}Identity")
    assert identity is not None
    assert identity.attrib == {
        "Name": "YMcompany.30069A065C875",
        "Publisher": "CN=447AAE61-8C19-4267-91D6-45419445A405",
        "Version": "3.0.62.0",
        "ProcessorArchitecture": "x64",
    }

    application = root.find(
        f"{{{FOUNDATION_NS}}}Applications/{{{FOUNDATION_NS}}}Application"
    )
    assert application is not None
    assert application.attrib["Executable"] == "CoupangThreadAuto.exe"
    assert application.attrib[f"{{{UAP10_NS}}}RuntimeBehavior"] == "packagedClassicApp"
    assert application.attrib[f"{{{UAP10_NS}}}TrustLevel"] == "mediumIL"

    capability = root.find(
        f"{{{FOUNDATION_NS}}}Capabilities/{{{RESCAP_NS}}}Capability"
    )
    assert capability is not None
    assert capability.attrib["Name"] == "runFullTrust"


def test_prepare_package_layout_copies_executable_and_generates_assets(tmp_path):
    executable = tmp_path / "source.exe"
    executable.write_bytes(b"store-executable")
    staging = tmp_path / "package"

    build_store_msix.prepare_package_layout(
        executable_path=executable,
        staging_dir=staging,
        icon_path=REPO_ROOT / "images" / "app_icon.ico",
        version="3.0.62.0",
    )

    assert (staging / "CoupangThreadAuto.exe").read_bytes() == b"store-executable"
    assert "YMcompany.30069A065C875" in (staging / "AppxManifest.xml").read_text(
        encoding="utf-8"
    )
    expected_sizes = {
        "StoreLogo.png": (50, 50),
        "Square44x44Logo.png": (44, 44),
        "Square150x150Logo.png": (150, 150),
    }
    for filename, size in expected_sizes.items():
        with Image.open(staging / "Assets" / filename) as image:
            assert image.size == size


def test_build_pyinstaller_command_keeps_store_artifacts_isolated(tmp_path):
    work_dir = tmp_path / "work"
    dist_dir = tmp_path / "dist"

    command = build_store_msix.build_pyinstaller_command(
        repo_root=REPO_ROOT,
        work_dir=work_dir,
        dist_dir=dist_dir,
    )

    assert command[:3] == [sys.executable, "-m", "PyInstaller"]
    assert command[command.index("--workpath") + 1] == str(work_dir.resolve())
    assert command[command.index("--distpath") + 1] == str(dist_dir.resolve())
    assert command[-1] == str((REPO_ROOT / "login_main.py").resolve())
    assert "--clean" in command
    assert "--noconfirm" in command


def test_find_makeappx_prefers_x64_sdk_tool(tmp_path):
    x86_tool = tmp_path / "bin" / "10.0.26100.0" / "x86" / "makeappx.exe"
    x64_tool = tmp_path / "bin" / "10.0.26100.0" / "x64" / "makeappx.exe"
    x86_tool.parent.mkdir(parents=True)
    x64_tool.parent.mkdir(parents=True)
    x86_tool.write_bytes(b"x86")
    x64_tool.write_bytes(b"x64")

    assert build_store_msix.find_makeappx([tmp_path]) == x64_tool


def test_build_store_package_runs_isolated_exe_and_msix_build(monkeypatch, tmp_path):
    makeappx = tmp_path / "sdk" / "x64" / "makeappx.exe"
    makeappx.parent.mkdir(parents=True)
    makeappx.write_bytes(b"tool")
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        if command[:3] == [sys.executable, "-m", "PyInstaller"]:
            dist_dir = Path(command[command.index("--distpath") + 1])
            dist_dir.mkdir(parents=True, exist_ok=True)
            (dist_dir / "CoupangThreadAuto.exe").write_bytes(b"store-executable")
        else:
            output_path = Path(command[command.index("/p") + 1])
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"msix")

    monkeypatch.setattr(build_store_msix.subprocess, "run", fake_run)

    output = build_store_msix.build_store_package(
        repo_root=REPO_ROOT,
        makeappx_path=makeappx,
        build_root=tmp_path / "build",
        output_dir=tmp_path / "output",
        version="v3.0.62",
    )

    assert output.name == "ThreadShoppingAutomation_3.0.62.0_x64.msix"
    assert output.read_bytes() == b"msix"
    pyinstaller_calls = [
        call
        for call in calls
        if call[0][:3] == [sys.executable, "-m", "PyInstaller"]
    ]
    assert len(pyinstaller_calls) == 1
    makeappx_calls = [
        call for call in calls if call[0] and call[0][0] == str(makeappx.resolve())
    ]
    assert len(makeappx_calls) == 1
    assert makeappx_calls[0][0][1] == "pack"
    assert makeappx_calls[0][1]["check"] is True


def test_read_app_version_from_login_entrypoint(tmp_path):
    entrypoint = tmp_path / "login_main.py"
    entrypoint.write_text('VERSION = "v3.0.62"\n', encoding="utf-8")

    assert build_store_msix.read_app_version(entrypoint) == "3.0.62.0"


def test_main_builds_with_explicit_makeappx_path(monkeypatch, tmp_path, capsys):
    makeappx = tmp_path / "makeappx.exe"
    makeappx.write_bytes(b"tool")
    captured = {}

    def fake_build_store_package(**kwargs):
        captured.update(kwargs)
        output = Path(kwargs["output_dir"]) / "package.msix"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"msix")
        return output

    monkeypatch.setattr(
        build_store_msix,
        "build_store_package",
        fake_build_store_package,
    )

    result = build_store_msix.main(
        ["--makeappx", str(makeappx), "--output-dir", str(tmp_path / "out")],
        repo_root=REPO_ROOT,
    )

    assert result == 0
    assert captured["makeappx_path"] == makeappx.resolve()
    assert captured["version"] == "3.0.73.0"
    assert "package.msix" in capsys.readouterr().out


def test_main_accepts_explicit_store_version(monkeypatch, tmp_path):
    makeappx = tmp_path / "makeappx.exe"
    makeappx.write_bytes(b"tool")
    captured = {}

    def fake_build_store_package(**kwargs):
        captured.update(kwargs)
        output = Path(kwargs["output_dir"]) / "package.msix"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"msix")
        return output

    monkeypatch.setattr(
        build_store_msix,
        "build_store_package",
        fake_build_store_package,
    )

    result = build_store_msix.main(
        [
            "--makeappx",
            str(makeappx),
            "--output-dir",
            str(tmp_path / "out"),
            "--version",
            "v3.0.73",
        ],
        repo_root=REPO_ROOT,
    )

    assert result == 0
    assert captured["version"] == "3.0.73.0"


def test_store_build_script_can_be_invoked_directly():
    completed = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "build_store_msix.py"), "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "--makeappx" in completed.stdout
