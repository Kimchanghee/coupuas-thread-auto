from types import SimpleNamespace

import setup_login
from src.computer_use_agent import ComputerUseAgent


def test_setup_login_requires_verified_threads_authentication(monkeypatch, capsys):
    events = []

    class FakePage:
        url = "https://www.threads.net/"

        def goto(self, *_args, **_kwargs):
            events.append("goto")

    class FakeAgent:
        page = FakePage()

        def __init__(self, **_kwargs):
            pass

        def start_browser(self):
            events.append("start")

        def save_session(self):
            raise AssertionError("unverified auth must never be persisted")

        def close(self, *, save_session=True):
            events.append(("close", save_session))

    class FakeHelper:
        def __init__(self, page):
            assert page is FakeAgent.page

        def check_login_status(self):
            return False

    monkeypatch.setattr(setup_login, "ComputerUseAgent", FakeAgent)
    monkeypatch.setattr(setup_login, "ThreadsPlaywrightHelper", FakeHelper)
    monkeypatch.setattr("builtins.input", lambda _prompt: "")
    monkeypatch.setattr(setup_login.time, "sleep", lambda *_args: None)

    setup_login.main()

    assert events == ["start", "goto", ("close", False)]
    output = capsys.readouterr().out
    assert "실제 Threads 인증 상태를 확인하지 못했습니다" in output
    assert "설정이 완료되었습니다" not in output


def test_setup_login_failed_auth_real_agent_preserves_existing_session(
    monkeypatch,
    tmp_path,
):
    events = []
    secure_path = tmp_path / "storage_state.sec"
    secure_path.write_text("verified-session", encoding="utf-8")
    page = SimpleNamespace(
        url="https://www.threads.net/",
        goto=lambda *_args, **_kwargs: None,
    )
    agent = object.__new__(ComputerUseAgent)
    agent.profile_name = "test-profile"
    agent.profile_path = tmp_path
    agent.legacy_profile_path = None
    agent.page = page
    agent.context = SimpleNamespace(close=lambda: events.append("context_close"))
    agent.browser = SimpleNamespace(close=lambda: events.append("browser_close"))
    agent.playwright = SimpleNamespace(stop=lambda: events.append("playwright_stop"))
    agent.start_browser = lambda: None
    agent.save_session = lambda: events.append("save_session") or True

    class FailedAuthHelper:
        def __init__(self, actual_page):
            assert actual_page is page

        def check_login_status(self):
            return False

    monkeypatch.setattr(setup_login, "ComputerUseAgent", lambda **_kwargs: agent)
    monkeypatch.setattr(setup_login, "ThreadsPlaywrightHelper", FailedAuthHelper)
    monkeypatch.setattr("builtins.input", lambda _prompt: "")
    monkeypatch.setattr(setup_login.time, "sleep", lambda *_args: None)

    setup_login.main()

    assert "save_session" not in events
    assert events == ["context_close", "browser_close", "playwright_stop"]
    assert secure_path.read_text(encoding="utf-8") == "verified-session"
