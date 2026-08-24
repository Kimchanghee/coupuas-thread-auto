import pytest

from src.services.link_history import LinkHistory


def test_same_url_is_scoped_to_account(tmp_path):
    one = LinkHistory(account_id="one", history_root=tmp_path)
    two = LinkHistory(account_id="two", history_root=tmp_path)
    url = "https://example.test/product/1?tracking=yes"

    one.add_link(url, success=True)

    assert one.is_uploaded("https://EXAMPLE.test/product/1?tracking=yes#ignored")
    assert not one.is_uploaded("https://example.test/product/1?other=value")
    assert not two.is_uploaded(url)
    two.add_link(url, success=True)
    assert two.is_uploaded(url)
    assert (tmp_path / "one.json").exists()
    assert (tmp_path / "two.json").exists()


def test_affiliate_query_values_are_distinct_history_entries(tmp_path):
    history = LinkHistory(account_id="creator", history_root=tmp_path)
    first = "https://ohou.se/productions/123/selling?af=creator-one"
    second = "https://ohou.se/productions/123/selling?af=creator-two"

    history.add_link(first, success=True)

    assert history.is_uploaded(first)
    assert not history.is_uploaded(second)
    assert history.filter_new_links([first, second]) == [second]


def test_default_constructor_and_explicit_legacy_file_keep_legacy_format(tmp_path):
    history = LinkHistory(str(tmp_path / "uploaded_links.json"))
    history.add_link("https://example.test/legacy", success=True)

    restored = LinkHistory(str(tmp_path / "uploaded_links.json"))
    assert restored.is_uploaded("https://example.test/legacy")
    assert "account_id" not in restored._history


def test_account_id_cannot_escape_history_root(tmp_path):
    with pytest.raises(ValueError):
        LinkHistory(account_id="../outside", history_root=tmp_path)


def test_history_records_are_read_only_copies_for_ui(tmp_path):
    history = LinkHistory(account_id="creator", history_root=tmp_path)
    history.add_link(
        "https://example.test/product/1?affiliate=creator",
        "테스트 상품",
        success=False,
    )

    records = history.get_records()
    assert records[0]["title"] == "테스트 상품"
    records[0]["title"] = "변경 시도"

    assert history.get_records()[0]["title"] == "테스트 상품"
