import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).parent / ".github" / "scripts" / "release_notes.py"
SPEC = importlib.util.spec_from_file_location("release_notes", MODULE_PATH)
release_notes = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release_notes)


def test_release_notes_groups_direct_commit_subjects():
    body = release_notes.render_release_notes(
        "v3.0.56",
        [
            "feat(web): add notice board",
            "fix(updater): resume queues after install",
            "security: verify installer checksum",
            "docs: explain event publishing",
        ],
    )
    assert "# Thread Auto v3.0.56" in body
    assert "## 새 기능" in body
    assert "- add notice board" in body
    assert "## 오류 수정" in body
    assert "- resume queues after install" in body
    assert "## 보안 및 안정성" in body
    assert "## 그 밖의 변경 사항" in body
    assert "CoupangThreadAutoSetup.exe" in body


def test_release_notes_deduplicates_and_has_safe_fallback():
    grouped = release_notes.categorize_subjects(["fix: Same", "fix: Same", "Merge branch main"])
    assert grouped["오류 수정"] == ["Same"]
    assert "안정성과 배포 구성을 개선했습니다." in release_notes.render_release_notes("v1.0.0", [])
