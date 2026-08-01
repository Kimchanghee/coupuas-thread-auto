import pytest

from src.services.link_history import LinkHistory


def test_same_url_is_scoped_to_account(tmp_path):
    one = LinkHistory(account_id="one", history_root=tmp_path)
    two = LinkHistory(account_id="two", history_root=tmp_path)
    url = "https://example.test/product/1?tracking=yes"

    one.add_link(url, success=True)

    assert one.is_uploaded("https://example.test/product/1?other=value")
    assert not two.is_uploaded(url)
    two.add_link(url, success=True)
    assert two.is_uploaded(url)
    assert (tmp_path / "one.json").exists()
    assert (tmp_path / "two.json").exists()


def test_default_constructor_and_explicit_legacy_file_keep_legacy_format(tmp_path):
    history = LinkHistory(str(tmp_path / "uploaded_links.json"))
    history.add_link("https://example.test/legacy", success=True)

    restored = LinkHistory(str(tmp_path / "uploaded_links.json"))
    assert restored.is_uploaded("https://example.test/legacy")
    assert "account_id" not in restored._history


def test_account_id_cannot_escape_history_root(tmp_path):
    with pytest.raises(ValueError):
        LinkHistory(account_id="../outside", history_root=tmp_path)
