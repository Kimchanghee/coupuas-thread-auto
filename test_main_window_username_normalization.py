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

