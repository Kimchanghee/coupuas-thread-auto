import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).parent / ".github" / "scripts" / "release_notes.py"
SPEC = importlib.util.spec_from_file_location("release_notes", MODULE_PATH)
release_notes = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release_notes)


def test_release_notes_use_plain_korean_instead_of_internal_terms():
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
    assert "## 이번 버전에서 달라진 점" in body
    assert "업데이트가 끝까지 완료되지 않던 문제를 개선했습니다." in body
    assert "각종 오류와 안정성 문제를 개선했습니다." in body
    assert "## 설치 안내" in body
    assert "add notice board" not in body
    assert "checksum" not in body.lower()
    assert "SHA-256" not in body


def test_release_notes_deduplicates_and_has_safe_fallback():
    grouped = release_notes.categorize_subjects(["fix: Same", "fix: Same", "Merge branch main"])
    assert grouped["오류 수정"] == ["Same"]
    assert release_notes.user_facing_changes(["fix: Same", "fix: Same"]) == [
        "각종 오류와 안정성 문제를 개선했습니다."
    ]
    assert "각종 오류와 안정성 문제를 개선했습니다." in release_notes.render_release_notes(
        "v1.0.0", []
    )


def test_release_notes_name_major_user_facing_features():
    body = release_notes.render_release_notes(
        "v3.0.71",
        ["feat(affiliate): integrate seven Korean partner channels"],
    )
    assert "이용할 수 있는 쇼핑 제휴 채널을 늘렸습니다." in body
    assert "partner" not in body.lower()
