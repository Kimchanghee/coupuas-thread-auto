from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent


def test_installer_uses_current_product_brand():
    script = (REPO_ROOT / "installer" / "CoupangThreadAuto.iss").read_text(
        encoding="utf-8"
    )

    assert "AppName=스레드 쇼핑 자동화" in script
    assert "VersionInfoProductName=스레드 쇼핑 자동화" in script
    assert "Shorts Thread Maker" not in script
