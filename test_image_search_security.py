import hashlib
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from src.services.cancellation import OperationCancelled
from src.services.image_search import ImageSearchService


class _Response:
    def __init__(self, status_code=200, *, headers=None, chunks=None):
        self.status_code = status_code
        self.headers = dict(headers or {})
        self._chunks = list(chunks or [])
        self.closed = False

    def iter_content(self, chunk_size):
        del chunk_size
        yield from self._chunks

    def close(self):
        self.closed = True


def _public_dns(*_args, **_kwargs):
    return [(2, 1, 6, "", ("93.184.216.34", 443))]


@pytest.fixture(autouse=True)
def _secure_test_cache_acl(monkeypatch):
    monkeypatch.setattr(
        "src.services.image_search.secure_dir_permissions",
        lambda _path: True,
    )
    monkeypatch.setattr(
        "src.services.image_search.secure_file_permissions",
        lambda _path: True,
    )


def _valid_jpeg_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (64, 64), (20, 40, 60)).save(output, format="JPEG")
    payload = output.getvalue()
    return payload + (b"\0" * max(0, ImageSearchService.MIN_IMAGE_BYTES - len(payload)))


def _service(tmp_path: Path) -> ImageSearchService:
    service = ImageSearchService.__new__(ImageSearchService)
    service.CACHE_DIR = str(tmp_path)
    return service


def test_image_url_validation_rejects_credentials_ports_and_non_public_dns(monkeypatch):
    assert not ImageSearchService._is_allowed_image_url("http://img.alicdn.com/a.jpg")
    assert not ImageSearchService._is_allowed_image_url("https://user:pw@img.alicdn.com/a.jpg")
    assert not ImageSearchService._is_allowed_image_url("https://img.alicdn.com:444/a.jpg")
    assert not ImageSearchService._is_allowed_image_url("https://alicdn.com.evil.test/a.jpg")

    monkeypatch.setattr(
        "src.services.image_search.socket.getaddrinfo",
        lambda *_args, **_kwargs: [(2, 1, 6, "", ("127.0.0.1", 443))],
    )
    assert not ImageSearchService._is_safe_image_request_url("https://img.alicdn.com/a.jpg")


def test_search_url_validation_rejects_non_1688_credentials_and_ports():
    assert ImageSearchService._is_allowed_search_url(
        "https://s.1688.com/selloffer/offer_search.htm?q=test"
    )
    assert not ImageSearchService._is_allowed_search_url(
        "http://s.1688.com/selloffer/offer_search.htm"
    )
    assert not ImageSearchService._is_allowed_search_url(
        "https://user:pw@s.1688.com/selloffer/offer_search.htm"
    )
    assert not ImageSearchService._is_allowed_search_url(
        "https://s.1688.com:444/selloffer/offer_search.htm"
    )
    assert not ImageSearchService._is_allowed_search_url(
        "https://1688.com.evil.test/selloffer/offer_search.htm"
    )


def test_search_redirect_private_dns_is_blocked_before_second_request(monkeypatch, tmp_path):
    service = _service(tmp_path)
    dns_answers = iter(
        [
            [(2, 1, 6, "", ("93.184.216.34", 443))],
            [(2, 1, 6, "", ("169.254.169.254", 443))],
        ]
    )
    monkeypatch.setattr(
        "src.services.image_search.socket.getaddrinfo",
        lambda *_args, **_kwargs: next(dns_answers),
    )
    first = _Response(
        302,
        headers={"location": "https://redirect.1688.com/internal"},
    )
    calls = []

    def _get(url, **kwargs):
        calls.append((url, kwargs))
        return first

    monkeypatch.setattr(service, "_open_pinned_search_request", _get)

    response = service._request_search_with_safe_redirects(
        "https://s.1688.com/start",
        headers={},
    )

    assert response is None
    assert len(calls) == 1
    assert calls[0][1]["addresses"] == ("93.184.216.34",)
    assert first.closed is True


def test_search_follows_at_most_three_safe_redirects(monkeypatch, tmp_path):
    service = _service(tmp_path)
    monkeypatch.setattr("src.services.image_search.socket.getaddrinfo", _public_dns)
    responses = [
        _Response(302, headers={"location": f"/{index + 1}"})
        for index in range(4)
    ]
    response_iter = iter(responses)
    calls = []

    def _request(url, **_kwargs):
        calls.append(url)
        return next(response_iter)

    monkeypatch.setattr(service, "_open_pinned_search_request", _request)

    assert service._request_search_with_safe_redirects(
        "https://s.1688.com/0",
        headers={},
    ) is None
    assert len(calls) == 4
    assert all(response.closed for response in responses)


def test_search_html_uses_guarded_stream_and_closes_response(monkeypatch, tmp_path):
    service = _service(tmp_path)
    html = "".join(
        f'https://cbu01.alicdn.com/img/{index}.jpg ' for index in range(5)
    ).encode()
    response = _Response(
        200,
        headers={"content-type": "text/html", "content-length": str(len(html))},
        chunks=[html],
    )
    calls = []

    def _request(url, **kwargs):
        calls.append((url, kwargs))
        return response

    monkeypatch.setattr(service, "_request_search_with_safe_redirects", _request)

    urls = service._search_1688_multiple("product")

    assert len(urls) == 5
    assert len(calls) == 1
    assert calls[0][0].startswith("https://s.1688.com/")
    assert response.closed is True


def test_oversized_search_html_is_rejected_and_closed(monkeypatch, tmp_path):
    service = _service(tmp_path)
    responses = [
        _Response(
            200,
            headers={
                "content-type": "text/html",
                "content-length": str(service.MAX_SEARCH_HTML_BYTES + 1),
            },
        )
        for _unused in range(3)
    ]
    response_iter = iter(responses)
    monkeypatch.setattr(
        service,
        "_request_search_with_safe_redirects",
        lambda *_args, **_kwargs: next(response_iter),
    )

    assert service._search_1688_multiple("product") == []
    assert all(response.closed for response in responses)


def test_search_html_cancellation_closes_response(monkeypatch, tmp_path):
    service = _service(tmp_path)
    response = _Response(
        200,
        headers={"content-type": "text/html"},
        chunks=[b"partial"],
    )
    monkeypatch.setattr(
        service,
        "_request_search_with_safe_redirects",
        lambda *_args, **_kwargs: response,
    )
    checks = 0

    def _cancel():
        nonlocal checks
        checks += 1
        return checks >= 4

    with pytest.raises(OperationCancelled):
        service._search_1688_multiple("product", cancel_check=_cancel)

    assert response.closed is True


def test_redirect_target_is_dns_validated_before_second_request(monkeypatch, tmp_path):
    service = _service(tmp_path)
    dns_answers = iter(
        [
            [(2, 1, 6, "", ("93.184.216.34", 443))],
            [(2, 1, 6, "", ("10.0.0.8", 443))],
        ]
    )
    monkeypatch.setattr(
        "src.services.image_search.socket.getaddrinfo",
        lambda *_args, **_kwargs: next(dns_answers),
    )
    first = _Response(302, headers={"location": "/internal.jpg"})
    calls = []

    def _get(url, **kwargs):
        calls.append((url, kwargs))
        return first

    monkeypatch.setattr(service, "_open_pinned_image_request", _get)

    response = service._request_image_with_safe_redirects(
        "https://img.alicdn.com/start.jpg",
        headers={},
    )

    assert response is None
    assert len(calls) == 1
    assert calls[0][1]["addresses"] == ("93.184.216.34",)
    assert first.closed is True


def test_redirect_loop_is_rejected_and_responses_are_closed(monkeypatch, tmp_path):
    service = _service(tmp_path)
    monkeypatch.setattr("src.services.image_search.socket.getaddrinfo", _public_dns)
    first = _Response(302, headers={"location": "/second.jpg"})
    second = _Response(302, headers={"location": "/start.jpg"})
    responses = iter([first, second])
    calls = []

    def _get(url, **kwargs):
        calls.append(url)
        return next(responses)

    monkeypatch.setattr(service, "_open_pinned_image_request", _get)

    result = service._request_image_with_safe_redirects(
        "https://img.alicdn.com/start.jpg",
        headers={},
    )

    assert result is None
    assert len(calls) == 2
    assert first.closed and second.closed


def test_image_download_follows_at_most_three_safe_redirects(monkeypatch, tmp_path):
    service = _service(tmp_path)
    monkeypatch.setattr("src.services.image_search.socket.getaddrinfo", _public_dns)
    image_bytes = _valid_jpeg_bytes()
    responses = [
        _Response(302, headers={"location": "/2.jpg"}),
        _Response(302, headers={"location": "/3.jpg"}),
        _Response(302, headers={"location": "/4.jpg"}),
        _Response(
            200,
            headers={
                "content-type": "image/jpeg",
                "content-length": str(len(image_bytes)),
            },
            chunks=[image_bytes],
        ),
    ]
    response_iter = iter(responses)
    monkeypatch.setattr(service, "_open_pinned_image_request", lambda *_args, **_kwargs: next(response_iter))
    monkeypatch.setattr(service, "_has_sufficient_disk_space", lambda: True)
    monkeypatch.setattr(service, "_prune_cache", lambda: None)

    path = service._download_image("https://img.alicdn.com/1.jpg", "product")

    assert path is not None
    assert Path(path).read_bytes() == image_bytes
    assert all(response.closed for response in responses)


def test_cancellation_after_request_closes_response(monkeypatch, tmp_path):
    service = _service(tmp_path)
    monkeypatch.setattr("src.services.image_search.socket.getaddrinfo", _public_dns)
    response = _Response(200, headers={"content-type": "image/jpeg"})
    monkeypatch.setattr(service, "_open_pinned_image_request", lambda *_args, **_kwargs: response)
    checks = iter([False, True])

    with pytest.raises(OperationCancelled):
        service._request_image_with_safe_redirects(
            "https://img.alicdn.com/a.jpg",
            headers={},
            cancel_check=lambda: next(checks),
        )

    assert response.closed is True


def test_multicast_and_other_special_use_addresses_are_rejected(monkeypatch):
    for address in ("224.0.0.1", "0.0.0.0", "169.254.1.1", "::1", "ff02::1"):
        monkeypatch.setattr(
            "src.services.image_search.socket.getaddrinfo",
            lambda *_args, _address=address, **_kwargs: [(2, 1, 6, "", (_address, 443))],
        )
        assert ImageSearchService._resolve_public_addresses("img.alicdn.com") == ()


def test_request_connects_to_validated_ip_without_second_dns_resolution(monkeypatch, tmp_path):
    service = _service(tmp_path)
    dns_calls = []

    def _dns(*_args, **_kwargs):
        dns_calls.append(True)
        if len(dns_calls) > 1:
            return [(2, 1, 6, "", ("127.0.0.1", 443))]
        return [(2, 1, 6, "", ("93.184.216.34", 443))]

    class _RawResponse:
        status = 200
        headers = {"content-type": "image/jpeg"}

        def stream(self, _chunk_size, decode_content=True):
            del decode_content
            yield b"image"

        def close(self):
            pass

        def release_conn(self):
            pass

    pool_calls = []

    class _Pool:
        def __init__(self, host, **kwargs):
            pool_calls.append((host, kwargs, None))

        def urlopen(self, method, target, **kwargs):
            pool_calls[-1] = (pool_calls[-1][0], pool_calls[-1][1], (method, target, kwargs))
            return _RawResponse()

        def close(self):
            pass

    monkeypatch.setattr("src.services.image_search.socket.getaddrinfo", _dns)
    monkeypatch.setattr("src.services.image_search.HTTPSConnectionPool", _Pool)

    response = service._request_image_with_safe_redirects(
        "https://img.alicdn.com/path/a.jpg?size=large",
        headers={"Accept": "image/*"},
    )

    assert response is not None
    assert len(dns_calls) == 1
    assert pool_calls[0][0] == "93.184.216.34"
    assert pool_calls[0][1]["server_hostname"] == "img.alicdn.com"
    assert pool_calls[0][1]["assert_hostname"] == "img.alicdn.com"
    assert pool_calls[0][1]["retries"] is False
    method, target, request_kwargs = pool_calls[0][2]
    assert (method, target) == ("GET", "/path/a.jpg?size=large")
    assert request_kwargs["headers"]["Host"] == "img.alicdn.com"
    assert request_kwargs["redirect"] is False
    assert request_kwargs["retries"] is False
    response.close()


def test_corrupt_existing_cache_is_removed_and_redownloaded(monkeypatch, tmp_path):
    service = _service(tmp_path)
    url = "https://img.alicdn.com/corrupt.jpg"
    cache_path = tmp_path / f"{hashlib.sha256(url.encode()).hexdigest()}.jpg"
    cache_path.write_bytes(b"not-an-image" * 500)
    image_bytes = _valid_jpeg_bytes()
    response = _Response(
        200,
        headers={"content-type": "image/jpeg"},
        chunks=[image_bytes],
    )
    monkeypatch.setattr(service, "_has_sufficient_disk_space", lambda: True)
    monkeypatch.setattr(
        service,
        "_request_image_with_safe_redirects",
        lambda *_args, **_kwargs: response,
    )

    result = service._download_image(url, "product")

    assert result == str(cache_path)
    assert cache_path.read_bytes() == image_bytes
    assert service._image_file_content_is_valid(cache_path)
    assert response.closed is True


def test_valid_existing_cache_avoids_network_request(monkeypatch, tmp_path):
    service = _service(tmp_path)
    url = "https://img.alicdn.com/already-cached.jpg"
    cache_path = tmp_path / f"{hashlib.sha256(url.encode()).hexdigest()}.jpg"
    cache_path.write_bytes(_valid_jpeg_bytes())
    monkeypatch.setattr(service, "_has_sufficient_disk_space", lambda: True)
    monkeypatch.setattr(
        service,
        "_request_image_with_safe_redirects",
        lambda *_args, **_kwargs: pytest.fail("valid cache must avoid a network request"),
    )

    assert service._download_image(url, "product") == str(cache_path)


def test_symlink_cache_entry_is_never_trusted(monkeypatch, tmp_path):
    service = _service(tmp_path)
    url = "https://img.alicdn.com/symlink.jpg"
    cache_path = tmp_path / f"{hashlib.sha256(url.encode()).hexdigest()}.jpg"
    target = tmp_path / "symlink-target.jpg"
    original_target = _valid_jpeg_bytes()
    target.write_bytes(original_target)
    try:
        cache_path.symlink_to(target)
    except OSError:
        pytest.skip("symlink creation is unavailable")

    replacement = _valid_jpeg_bytes() + b"replacement"
    response = _Response(
        200,
        headers={"content-type": "image/jpeg"},
        chunks=[replacement],
    )
    monkeypatch.setattr(service, "_has_sufficient_disk_space", lambda: True)
    monkeypatch.setattr(
        service,
        "_request_image_with_safe_redirects",
        lambda *_args, **_kwargs: response,
    )

    assert service._download_image(url, "product") == str(cache_path)
    assert not cache_path.is_symlink()
    assert cache_path.read_bytes() == replacement
    assert target.read_bytes() == original_target


def test_invalid_image_payload_is_not_published_and_temp_is_cleaned(monkeypatch, tmp_path):
    service = _service(tmp_path)
    response = _Response(
        200,
        headers={"content-type": "image/jpeg"},
        chunks=[b"x" * service.MIN_IMAGE_BYTES],
    )
    monkeypatch.setattr(service, "_has_sufficient_disk_space", lambda: True)
    monkeypatch.setattr(
        service,
        "_request_image_with_safe_redirects",
        lambda *_args, **_kwargs: response,
    )

    assert service._download_image(
        "https://img.alicdn.com/not-really-an-image.jpg",
        "product",
    ) is None
    assert list(tmp_path.glob("*.tmp")) == []
    assert [path for path in tmp_path.iterdir() if path.is_file()] == []
    assert response.closed is True


def test_cancelled_download_removes_same_directory_temp(monkeypatch, tmp_path):
    service = _service(tmp_path)
    image_bytes = _valid_jpeg_bytes()
    cancelled = threading.Event()

    class _CancellingResponse(_Response):
        def iter_content(self, chunk_size):
            del chunk_size
            midpoint = len(image_bytes) // 2
            yield image_bytes[:midpoint]
            cancelled.set()
            yield image_bytes[midpoint:]

    response = _CancellingResponse(200, headers={"content-type": "image/jpeg"})
    monkeypatch.setattr(service, "_has_sufficient_disk_space", lambda: True)
    monkeypatch.setattr(
        service,
        "_request_image_with_safe_redirects",
        lambda *_args, **_kwargs: response,
    )

    with pytest.raises(OperationCancelled):
        service._download_image(
            "https://img.alicdn.com/cancelled.jpg",
            "product",
            cancel_check=cancelled.is_set,
        )

    assert list(tmp_path.glob("*.tmp")) == []
    assert list(tmp_path.iterdir()) == []
    assert response.closed is True


def test_cancellation_after_decode_prevents_publish(monkeypatch, tmp_path):
    service = _service(tmp_path)
    image_bytes = _valid_jpeg_bytes()
    cancelled = threading.Event()
    response = _Response(
        200,
        headers={"content-type": "image/jpeg"},
        chunks=[image_bytes],
    )
    monkeypatch.setattr(service, "_has_sufficient_disk_space", lambda: True)
    monkeypatch.setattr(
        service,
        "_request_image_with_safe_redirects",
        lambda *_args, **_kwargs: response,
    )

    def _decode_then_cancel(path):
        assert Path(path).exists()
        cancelled.set()
        return True

    monkeypatch.setattr(service, "_image_file_content_is_valid", _decode_then_cancel)

    with pytest.raises(OperationCancelled):
        service._download_image(
            "https://img.alicdn.com/cancelled-after-decode.jpg",
            "product",
            cancel_check=cancelled.is_set,
        )

    assert list(tmp_path.iterdir()) == []
    assert response.closed is True


def test_publish_fsyncs_temp_before_atomic_replace(monkeypatch, tmp_path):
    service = _service(tmp_path)
    image_bytes = _valid_jpeg_bytes()
    response = _Response(
        200,
        headers={"content-type": "image/jpeg"},
        chunks=[image_bytes],
    )
    monkeypatch.setattr(service, "_has_sufficient_disk_space", lambda: True)
    monkeypatch.setattr(
        service,
        "_request_image_with_safe_redirects",
        lambda *_args, **_kwargs: response,
    )
    events = []
    original_fsync = os.fsync
    original_replace = os.replace

    def _fsync(descriptor):
        events.append("fsync")
        return original_fsync(descriptor)

    def _replace(source, destination):
        assert Path(source).parent == Path(destination).parent == tmp_path
        assert events == ["fsync"]
        events.append("replace")
        return original_replace(source, destination)

    monkeypatch.setattr("src.services.image_search.os.fsync", _fsync)
    monkeypatch.setattr("src.services.image_search.os.replace", _replace)

    assert service._download_image(
        "https://img.alicdn.com/atomic.jpg",
        "product",
    ) is not None
    assert events == ["fsync", "replace"]


def test_concurrent_same_url_download_is_published_once(monkeypatch, tmp_path):
    service = _service(tmp_path)
    image_bytes = _valid_jpeg_bytes()
    calls = 0
    call_lock = threading.Lock()

    def _request(*_args, **_kwargs):
        nonlocal calls
        with call_lock:
            calls += 1
        time.sleep(0.05)
        return _Response(
            200,
            headers={"content-type": "image/jpeg"},
            chunks=[image_bytes],
        )

    monkeypatch.setattr(service, "_has_sufficient_disk_space", lambda: True)
    monkeypatch.setattr(service, "_request_image_with_safe_redirects", _request)
    url = "https://img.alicdn.com/concurrent.jpg"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                lambda _unused: service._download_image(url, "product"),
                range(2),
            )
        )

    assert results[0] is not None
    assert results[0] == results[1]
    assert calls == 1
    assert list(tmp_path.glob("*.tmp")) == []


def test_cache_acl_failure_fails_closed_and_cleans_temp(monkeypatch, tmp_path):
    service = _service(tmp_path)
    image_bytes = _valid_jpeg_bytes()
    response = _Response(
        200,
        headers={"content-type": "image/jpeg"},
        chunks=[image_bytes],
    )
    monkeypatch.setattr(service, "_has_sufficient_disk_space", lambda: True)
    monkeypatch.setattr(
        service,
        "_request_image_with_safe_redirects",
        lambda *_args, **_kwargs: response,
    )
    monkeypatch.setattr(
        "src.services.image_search.secure_file_permissions",
        lambda _path: False,
    )

    assert service._download_image(
        "https://img.alicdn.com/acl-failure.jpg",
        "product",
    ) is None
    assert list(tmp_path.iterdir()) == []
    assert response.closed is True


def test_prune_removes_only_stale_cache_temps(monkeypatch, tmp_path):
    service = _service(tmp_path)
    stale = tmp_path / ".stale-image.tmp"
    recent = tmp_path / ".active-image.tmp"
    stale.write_bytes(b"partial")
    recent.write_bytes(b"partial")
    old_timestamp = time.time() - service.STALE_CACHE_TEMP_SECONDS - 10
    os.utime(stale, (old_timestamp, old_timestamp))

    service._prune_cache()

    assert not stale.exists()
    assert recent.exists()
