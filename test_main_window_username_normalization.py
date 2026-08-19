from src.main_window import MainWindow


def test_normalize_threads_username_from_profile_url_with_at():
    assert (
        MainWindow._normalize_threads_username("https://www.threads.com/@banguaseok_ai")
        == "banguaseok_ai"
    )


def test_normalize_threads_username_from_profile_url_without_at():
    assert (
        MainWindow._normalize_threads_username("https://www.threads.com/banguaseok_ai")
        == "banguaseok_ai"
    )


def test_normalize_threads_username_from_plain_handle():
    assert MainWindow._normalize_threads_username("@banguaseok_ai") == "banguaseok_ai"


def test_invalid_username_is_rejected_instead_of_silently_changed():
    assert MainWindow._normalize_threads_username("john-doe") == ""
    assert MainWindow._normalize_threads_username("https://evil.example/john") == ""
    assert MainWindow._normalize_threads_username("https://threads.net/@john/post/123") == ""

