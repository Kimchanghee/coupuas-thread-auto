import re
from pathlib import Path

import pytest

import build_exe
import build_installer
import main
from src import __version__
from src.version import MSIX_VERSION, VERSION, VERSION_TAG
from tools import build_store_msix


ROOT = Path(__file__).resolve().parent


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_runtime_packaging_and_store_share_one_version_value():
    assert __version__ == VERSION
    assert main.VERSION == VERSION_TAG
    assert build_installer._resolve_app_version() == VERSION
    assert build_store_msix.read_app_version(ROOT) == MSIX_VERSION

    assert "from src.version import VERSION_TAG" in _read("main.py")
    assert "from src.version import VERSION_TAG" in _read("login_main.py")
    assert "from src.version import VERSION as __version__" in _read("src/__init__.py")
    assert "version=VERSION" in _read("setup.py")
    assert 'python_requires=">=3.11"' in _read("setup.py")


def test_installer_version_override_must_match_canonical_version(monkeypatch):
    monkeypatch.setenv("COUPUAS_APP_VERSION", VERSION_TAG)
    assert build_installer._resolve_app_version() == VERSION

    monkeypatch.setenv("COUPUAS_APP_VERSION", "9.9.9")
    with pytest.raises(ValueError, match="must exactly match"):
        build_installer._resolve_app_version()


def test_release_preparation_updates_only_the_canonical_version_file():
    script = _read(".github/scripts/set_version.py")
    assert '"src/version.py"' in script
    for obsolete_target in ("main.py", "login_main.py", "src/__init__.py", "setup.py"):
        assert f'_replace("{obsolete_target}"' not in script


def test_store_submission_pack_reads_the_canonical_version_module():
    script = _read("tools/build_store_submission_pack.ps1")
    assert "from src.version import MSIX_VERSION" in script
    assert "src\\__init__.py" not in script
    assert "__version__" not in script

    installer = _read("installer/CoupangThreadAuto.iss")
    assert '#define MyAppVersion "0.0.0"' not in installer
    assert "#error MyAppVersion" in installer


def test_managed_signer_pin_parser_supports_only_current_next_bridge():
    current = "A" * 40
    next_pin = "b" * 40
    assert build_exe._normalize_thumbprints(f"{current}, {next_pin}") == (
        current,
        next_pin.upper(),
    )
    assert build_exe._normalize_thumbprints(f"{current};{current}") == (current,)

    with pytest.raises(RuntimeError, match="Invalid SHA-1"):
        build_exe._normalize_thumbprints("not-a-thumbprint")
    with pytest.raises(RuntimeError, match="At most two"):
        build_exe._normalize_thumbprints(",".join(char * 40 for char in "ABC"))


def test_release_build_fails_if_updater_pin_cannot_be_injected(tmp_path, monkeypatch):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "auto_updater.py").write_text(
        "DEFAULT_TRUSTED_SIGNER_THUMBPRINTS = unexpected_factory()\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(build_exe, "REPO_ROOT", tmp_path)
    monkeypatch.setenv("AZURE_ARTIFACT_SIGNING_CERT_THUMBPRINTS", "A" * 40)

    with pytest.raises(RuntimeError, match="Could not inject the exact updater signer pins"):
        build_exe.pin_updater_signer_thumbprint()


def test_build_restores_updater_source_after_base_exception(tmp_path, monkeypatch):
    source_dir = tmp_path / "src"
    source_dir.mkdir()
    updater_path = source_dir / "auto_updater.py"
    original = "class AutoUpdater:\n    DEFAULT_TRUSTED_SIGNER_THUMBPRINTS = set()\n"
    updater_path.write_text(original, encoding="utf-8")

    monkeypatch.setattr(build_exe, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(build_exe, "BUILD_DIR", tmp_path / "build")
    monkeypatch.setattr(build_exe, "DIST_DIR", tmp_path / "dist")
    monkeypatch.setenv("AZURE_ARTIFACT_SIGNING_CERT_THUMBPRINTS", "A" * 40)
    monkeypatch.setattr(
        build_exe,
        "_build_executable_with_pinned_updater",
        lambda: (_ for _ in ()).throw(KeyboardInterrupt()),
    )

    with pytest.raises(KeyboardInterrupt):
        build_exe.build_exe()

    assert updater_path.read_text(encoding="utf-8") == original


def test_pin_injection_restores_source_if_mutation_raises_after_replace(
    tmp_path, monkeypatch
):
    source_dir = tmp_path / "src"
    source_dir.mkdir()
    updater_path = source_dir / "auto_updater.py"
    original = "class AutoUpdater:\n    DEFAULT_TRUSTED_SIGNER_THUMBPRINTS = set()\n"
    updater_path.write_text(original, encoding="utf-8")
    real_replace = build_exe._atomic_replace_text

    def replace_then_interrupt(path, content):
        real_replace(path, content)
        if content != original:
            raise KeyboardInterrupt()

    monkeypatch.setattr(build_exe, "REPO_ROOT", tmp_path)
    monkeypatch.setenv("AZURE_ARTIFACT_SIGNING_CERT_THUMBPRINTS", "A" * 40)
    monkeypatch.setattr(build_exe, "_atomic_replace_text", replace_then_interrupt)

    with pytest.raises(KeyboardInterrupt):
        build_exe.pin_updater_signer_thumbprint()

    assert updater_path.read_text(encoding="utf-8") == original


def test_build_never_reports_success_when_updater_restore_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(build_exe, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(build_exe, "BUILD_DIR", tmp_path / "build")
    monkeypatch.setattr(build_exe, "DIST_DIR", tmp_path / "dist")

    def restore_failure():
        raise RuntimeError("restore failed")

    monkeypatch.setattr(build_exe, "pin_updater_signer_thumbprint", lambda: restore_failure)
    monkeypatch.setattr(build_exe, "_build_executable_with_pinned_updater", lambda: True)

    with pytest.raises(RuntimeError, match="restore failed"):
        build_exe.build_exe()


def test_build_outputs_are_anchored_to_repository_root():
    assert build_exe.BUILD_DIR == ROOT / "build"
    assert build_exe.DIST_DIR == ROOT / "dist"
    assert build_exe.MAIN_SCRIPT == ROOT / "login_main.py"
    source = _read("build_exe.py")
    assert "resolved.parent != REPO_ROOT" in source
    assert "cwd=REPO_ROOT" in source
    assert 'for folder in (BUILD_DIR, DIST_DIR)' in source
    assert "auto_updater.py is missing; refusing" in source
    assert "Could not inject the exact updater signer pins" in source


def test_docs_are_truthful_about_python_store_channels_and_version_source():
    readme = _read("README.md")
    store_listing = _read("docs/MICROSOFT_STORE_FIRST_SUBMISSION.md")
    update_guide = _read("AUTO_UPDATE_SETUP.md")

    assert "Python 3.11 이상" in readme
    assert "Python 3.9" not in readme
    assert "setup_login.bat" not in readme
    assert "src/version.py" in readme
    assert not re.search(r"현재 버전:\s*v\d", readme)

    assert "Temu" not in store_listing
    for channel in ("쿠팡", "네이버", "토스쇼핑", "오늘의집", "무신사", "컬리", "올리브영", "AliExpress"):
        assert channel in store_listing
    assert "first three version components must match" in store_listing

    assert "PFX" in update_guide
    assert "사용하지" in update_guide
    assert "production-code-signing" in update_guide
    assert "현재지문,다음지문" in update_guide
