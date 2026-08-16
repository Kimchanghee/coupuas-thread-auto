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


def test_release_notes_name_logout_return_without_development_terms():
    body = release_notes.render_release_notes(
        "v3.0.72",
        [
            "fix(auth): return to login screen after logout",
            "chore(release): prepare v3.0.72",
        ],
    )

    assert "로그아웃하면 프로그램을 닫지 않고 로그인 화면으로 돌아가도록 개선했습니다." in body
    assert "각종 오류와 안정성 문제를 개선했습니다." in body
    assert "auth" not in body.lower()
    assert "release" not in body.lower()
    assert "return to login" not in body.lower()
    assert "업데이트가 끝까지 완료되지 않던 문제를 개선했습니다." not in body


def test_release_notes_describe_security_notices_and_status_in_plain_korean():
    body = release_notes.render_release_notes(
        "v3.0.73",
        [
            "security(auth): restrict credential destinations",
            "fix(web): simplify legacy release notices",
            "feat(ops): add production readiness check",
        ],
    )

    assert "로그인 정보와 이용 기록이 안전하게 처리되도록 보호를 강화했습니다." in body
    assert "공지의 어려운 표현과 제목이 겹쳐 보이던 문제를 개선했습니다." in body
    assert "서비스 연결 상태를 더 빠르게 확인할 수 있도록 개선했습니다." in body
    for internal_term in ("credential", "legacy", "readiness", "auth", "ops"):
        assert internal_term not in body.lower()


def test_release_notes_name_manual_installer_fallback_in_plain_korean():
    body = release_notes.render_release_notes(
        "v3.0.74",
        ["feat(updater): offer verified manual download fallback"],
    )

    assert "업데이트가 완료되지 않을 때 공식 설치 파일을 바로 받을 수 있게 했습니다." in body
    for internal_term in ("updater", "verified", "fallback"):
        assert internal_term not in body.lower()


def test_release_notes_name_duplicate_login_protection_in_plain_korean():
    body = release_notes.render_release_notes(
        "v3.0.75",
        ["feat(auth): prevent concurrent account login"],
    )

    assert "한 계정을 여러 곳에서 동시에 사용할 수 없도록 로그인 보호를 강화했습니다." in body
    for internal_term in ("auth", "concurrent", "account"):
        assert internal_term not in body.lower()


def test_release_notes_explain_program_scope_and_faster_account_flow_plainly():
    body = release_notes.render_release_notes(
        "v3.0.76",
        [
            "fix(auth): scope duplicate login protection by program",
            "perf(auth): speed up login registration and username checks",
            "fix(auth): enter app after registration",
        ],
    )

    assert "같은 프로그램에서는 한 계정을 여러 곳에서 동시에 사용할 수 없도록 하고, 다른 프로그램은 함께 사용할 수 있게 개선했습니다." in body
    assert "로그인, 회원가입, 아이디 확인이 더 빠르게 끝나도록 개선했습니다." in body
    assert "회원가입이 끝나면 다시 로그인하지 않고 바로 사용할 수 있게 개선했습니다." in body
    for internal_term in ("auth", "scope", "program", "username"):
        assert internal_term not in body.lower()
