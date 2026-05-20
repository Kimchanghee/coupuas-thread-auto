from src.computer_use_agent import ComputerUseAgent


def test_allowed_navigation_supports_threads_and_meta_subdomains():
    assert ComputerUseAgent._is_allowed_navigation_url("https://www.threads.com/@banguaseok_ai")
    assert ComputerUseAgent._is_allowed_navigation_url("https://secure.instagram.com/accounts/login/")
    assert ComputerUseAgent._is_allowed_navigation_url("https://m.facebook.com/login/")


def test_allowed_navigation_blocks_non_https_and_untrusted_hosts():
    assert not ComputerUseAgent._is_allowed_navigation_url("http://www.threads.com/login")
    assert not ComputerUseAgent._is_allowed_navigation_url("https://localhost:3000/")
    assert not ComputerUseAgent._is_allowed_navigation_url("https://threads.com.evil.tld/")

