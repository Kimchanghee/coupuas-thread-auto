from src import single_instance


def test_is_app_window_title_matches_known_windows():
    assert single_instance._is_app_window_title("Coupang Partners Thread Automation")
    assert single_instance._is_app_window_title("쇼츠스레드메이커 - 로그인")
    assert single_instance._is_app_window_title("Thread Auto - 멀티 쇼핑 자동화")
    assert not single_instance._is_app_window_title("C:\\Python\\python.exe")


def test_acquire_guard_blocks_existing_window(monkeypatch):
    monkeypatch.setattr(single_instance, "_find_existing_app_window", lambda: (1234, "Coupang Partners Thread Automation"))
    monkeypatch.setattr(
        single_instance,
        "_create_windows_mutex",
        lambda: (_ for _ in ()).throw(AssertionError("mutex should not be touched")),
    )

    guard = single_instance.acquire_single_instance_guard()

    assert guard.already_running is True
    assert guard.existing_hwnd == 1234
    assert guard.reason == "window:Coupang Partners Thread Automation"


def test_acquire_guard_blocks_existing_mutex(monkeypatch):
    calls = []

    def find_window(*, allow_process_match=False):
        calls.append(allow_process_match)
        return (9876, "renamed main window") if allow_process_match else None

    monkeypatch.setattr(single_instance, "_find_existing_app_window", find_window)
    monkeypatch.setattr(single_instance, "_create_windows_mutex", lambda: (False, None))

    guard = single_instance.acquire_single_instance_guard()

    assert guard.already_running is True
    assert guard.existing_hwnd == 9876
    assert guard.reason == "mutex"
    assert calls == [False, True]


def test_acquire_guard_keeps_mutex_handle(monkeypatch):
    monkeypatch.setattr(single_instance, "_find_existing_app_window", lambda: None)
    monkeypatch.setattr(single_instance, "_create_windows_mutex", lambda: (True, 5678))

    guard = single_instance.acquire_single_instance_guard()

    assert guard.already_running is False
    assert guard._mutex_handle == 5678
