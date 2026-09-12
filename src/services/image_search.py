# -*- coding: utf-8 -*-
"""Search and download product images from 1688 with guarded network I/O."""

from __future__ import annotations

import hashlib
import ipaddress
import os
import random
import re
import shutil
import socket
import ssl
import stat
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable, List, Optional, Sequence
from urllib.parse import quote, urljoin, urlparse

from PIL import Image
from urllib3 import HTTPSConnectionPool, Timeout

from src.fs_security import secure_dir_permissions, secure_file_permissions
from src.gemini_keys import DEFAULT_GEMINI_MODEL, generate_content_with_model_fallback
from src.services.cancellation import check_cancelled, is_cancelled_exception


_CACHE_LOCK = threading.RLock()


class _PinnedImageResponse:
    """Small streaming facade that also owns its direct-IP connection pool."""

    def __init__(self, response, pool: HTTPSConnectionPool):
        self._response = response
        self._pool = pool
        self.status_code = int(response.status)
        self.headers = response.headers
        self._closed = False

    def iter_content(self, chunk_size: int):
        yield from self._response.stream(int(chunk_size), decode_content=True)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._response.close()
        finally:
            try:
                self._response.release_conn()
            finally:
                self._pool.close()


class ImageSearchService:
    """1688 image search service with retry and fallback query generation."""

    CACHE_DIR = str(Path.home() / ".shorts_thread_maker" / "media_cache")
    MAX_RETRIES = 10
    TARGET_IMAGES = 2
    MAX_IMAGE_BYTES = 8 * 1024 * 1024
    MIN_IMAGE_BYTES = 5 * 1024
    MAX_IMAGE_PIXELS = 40_000_000
    MAX_SEARCH_HTML_BYTES = 2 * 1024 * 1024
    DOWNLOAD_CHUNK_SIZE = 64 * 1024
    MIN_FREE_DISK_BYTES = 200 * 1024 * 1024
    MAX_CACHE_FILES = 500
    MAX_CACHE_BYTES = 1 * 1024 * 1024 * 1024
    STALE_CACHE_TEMP_SECONDS = 60 * 60
    ALLOWED_IMAGE_HOST_SUFFIXES = ("alicdn.com",)
    ALLOWED_SEARCH_HOST_SUFFIXES = ("1688.com",)
    MAX_IMAGE_REDIRECTS = 3
    MAX_SEARCH_REDIRECTS = 3
    IMAGE_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})

    def __init__(self):
        os.makedirs(self.CACHE_DIR, exist_ok=True)
        self._gemini_client = None
        self._gemini_key_fingerprint = ""
        self._model_name = os.environ.get("GOOGLE_GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
        if self._ensure_cache_dir_secure():
            self._prune_cache()

    def _get_gemini_client(self, api_key: str):
        """Lazily initialize Gemini client for translation/query variation."""
        normalized_key = str(api_key or "").strip()
        if not normalized_key:
            return None

        key_fingerprint = hashlib.sha256(normalized_key.encode("utf-8")).hexdigest()
        if self._gemini_client is None or self._gemini_key_fingerprint != key_fingerprint:
            from google import genai

            self._gemini_client = genai.Client(api_key=normalized_key)
            self._gemini_key_fingerprint = key_fingerprint
        return self._gemini_client

    def _has_sufficient_disk_space(self) -> bool:
        try:
            usage = shutil.disk_usage(self.CACHE_DIR)
            return usage.free >= self.MIN_FREE_DISK_BYTES
        except Exception:
            return True

    def _ensure_cache_dir_secure(self) -> bool:
        cache_dir = Path(self.CACHE_DIR)
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
            return (
                cache_dir.is_dir()
                and not cache_dir.is_symlink()
                and secure_dir_permissions(cache_dir)
            )
        except (OSError, RuntimeError):
            return False

    @staticmethod
    def _is_regular_non_symlink(path: Path) -> bool:
        try:
            path_stat = path.lstat()
            return (
                stat.S_ISREG(path_stat.st_mode)
                and path_stat.st_nlink == 1
                and not path.is_symlink()
            )
        except OSError:
            return False

    @staticmethod
    def _remove_cache_entry(path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass

    def _prune_cache(self) -> None:
        with _CACHE_LOCK:
            try:
                cache_dir = Path(self.CACHE_DIR)
                if not cache_dir.exists() or cache_dir.is_symlink():
                    return

                stale_before = time.time() - self.STALE_CACHE_TEMP_SECONDS
                for temp_path in cache_dir.glob(".*.tmp"):
                    try:
                        if (
                            self._is_regular_non_symlink(temp_path)
                            and temp_path.stat().st_mtime <= stale_before
                        ):
                            temp_path.unlink(missing_ok=True)
                    except OSError:
                        continue

                files = [
                    path
                    for path in cache_dir.glob("*")
                    if self._is_regular_non_symlink(path)
                    and not path.name.endswith(".tmp")
                ]
                if not files:
                    return

                file_stats = []
                for path in files:
                    try:
                        path_stat = path.stat()
                    except OSError:
                        continue
                    file_stats.append((path_stat.st_mtime, path_stat.st_size, path))
                file_stats.sort(key=lambda item: item[0])
                total_bytes = sum(item[1] for item in file_stats)

                while file_stats and (
                    len(file_stats) > self.MAX_CACHE_FILES
                    or total_bytes > self.MAX_CACHE_BYTES
                ):
                    _modified, size, oldest = file_stats.pop(0)
                    try:
                        oldest.unlink(missing_ok=True)
                    except OSError:
                        break
                    total_bytes -= size
            except (OSError, RuntimeError):
                return

    def _generate_gemini_text(
        self,
        prompt: str,
        api_key: str,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> str:
        check_cancelled(cancel_check)
        client = self._get_gemini_client(api_key)
        if client is None:
            return ""
        response, _model = generate_content_with_model_fallback(
            client,
            preferred_model=self._model_name,
            contents=prompt,
        )
        check_cancelled(cancel_check)
        text = str(getattr(response, "text", "") or "").strip()
        if text:
            return text

        candidates = getattr(response, "candidates", None) or []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", None) or []
            for part in parts:
                part_text = str(getattr(part, "text", "") or "").strip()
                if part_text:
                    return part_text
        return ""

    def search_product_images(
        self,
        product_info: dict,
        api_key: str = "",
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> List[str]:
        """Return up to TARGET_IMAGES local image paths for the given product."""
        check_cancelled(cancel_check)
        title = str(product_info.get("title", "") or "")
        keywords = str(product_info.get("search_keywords", "") or "")

        if not title and not keywords:
            print("  상품명/키워드가 없습니다.")
            return []

        images: List[str] = []
        tried_keywords = set()
        retry_count = 0
        search_variants = self._generate_search_variants(title, keywords, api_key, cancel_check)

        print(
            f"  1688 이미지 검색 시작 (목표: {self.TARGET_IMAGES}개, 최대 {self.MAX_RETRIES}회 시도)"
        )

        while len(images) < self.TARGET_IMAGES and retry_count < self.MAX_RETRIES:
            check_cancelled(cancel_check)
            retry_count += 1

            search_term = None
            for variant in search_variants:
                if variant not in tried_keywords:
                    search_term = variant
                    tried_keywords.add(variant)
                    break

            if search_term is None:
                search_term = self._generate_random_variant(
                    title,
                    keywords,
                    api_key,
                    retry_count,
                    cancel_check,
                )
                tried_keywords.add(search_term)

            print(f"  [{retry_count}/{self.MAX_RETRIES}] 검색: {search_term[:30]}...")
            found_urls = self._search_1688_multiple(search_term, cancel_check)

            for url in found_urls:
                check_cancelled(cancel_check)
                if len(images) >= self.TARGET_IMAGES:
                    break

                url_hash = hashlib.sha256(url.encode()).hexdigest()[:8]
                if any(url_hash in img for img in images):
                    continue

                local_path = self._download_image(url, title, cancel_check)
                if local_path:
                    images.append(local_path)
                    print(f"  이미지 {len(images)}개 확보: {local_path}")

            if len(images) < self.TARGET_IMAGES and retry_count < self.MAX_RETRIES:
                sleep_until = time.monotonic() + random.uniform(0.5, 1.5)
                while time.monotonic() < sleep_until:
                    check_cancelled(cancel_check)
                    remaining_sleep = sleep_until - time.monotonic()
                    if remaining_sleep <= 0:
                        break
                    time.sleep(min(0.2, remaining_sleep))

        if images:
            print(f"  1688 이미지 검색 완료: {len(images)}개 확보")
        else:
            print(f"  1688 이미지 검색 실패 ({self.MAX_RETRIES}회 시도)")

        return images

    def search_product_image(
        self,
        product_info: dict,
        api_key: str = "",
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> Optional[str]:
        """Compatibility helper: return a single image path."""
        images = self.search_product_images(product_info, api_key, cancel_check)
        return images[0] if images else None

    def _generate_search_variants(
        self,
        title: str,
        keywords: str,
        api_key: str,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> List[str]:
        """Generate prioritized query variants."""
        variants: List[str] = []

        chinese = self._translate_to_chinese(title or keywords, api_key, cancel_check)
        if chinese:
            variants.append(chinese)

        if keywords and keywords != title:
            chinese_kw = self._translate_to_chinese(keywords, api_key, cancel_check)
            if chinese_kw and chinese_kw not in variants:
                variants.append(chinese_kw)

        words = (title or keywords).split()
        if len(words) > 2:
            core_words = " ".join(words[:3])
            chinese_core = self._translate_to_chinese(core_words, api_key, cancel_check)
            if chinese_core and chinese_core not in variants:
                variants.append(chinese_core)

        english = self._translate_to_english(title or keywords, api_key, cancel_check)
        if english and english not in variants:
            variants.append(english)

        if title and title not in variants:
            variants.append(title)
        if keywords and keywords not in variants:
            variants.append(keywords)

        return variants

    def _generate_random_variant(
        self,
        title: str,
        keywords: str,
        api_key: str,
        attempt: int,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> str:
        """Generate additional variant for retries."""
        check_cancelled(cancel_check)
        base = (title or keywords or "").strip()
        client = self._get_gemini_client(api_key)

        if client and base and attempt <= 5:
            try:
                prompt = (
                    f"Return one short 1688 Chinese search keyword phrase for: {base}. "
                    "Output phrase only."
                )
                result = self._generate_gemini_text(prompt, api_key, cancel_check).strip().strip("\"'")
                if result:
                    return result
            except Exception as exc:
                if is_cancelled_exception(exc):
                    raise
                pass

        words = base.split()
        if len(words) > 1:
            random.shuffle(words)
            return " ".join(words[: min(3, len(words))])
        return base or "product"

    def _translate_to_chinese(
        self,
        text: str,
        api_key: str,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> Optional[str]:
        """Translate product keyword to Chinese for 1688 search."""
        check_cancelled(cancel_check)
        client = self._get_gemini_client(api_key)
        if not client or not text:
            return None

        try:
            prompt = (
                f"Translate this into concise Chinese search terms for 1688: {text}. "
                "Output terms only."
            )
            result = self._generate_gemini_text(prompt, api_key, cancel_check).strip()
            result = re.sub(r"[\"'\n]", "", result)
            if re.search(r"[\u4e00-\u9fff]", result):
                return result
            return None
        except Exception as exc:
            if is_cancelled_exception(exc):
                raise
            print(f"  번역 오류: {exc}")
            return None

    def _translate_to_english(
        self,
        text: str,
        api_key: str,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> Optional[str]:
        """Translate product keyword to English fallback query."""
        check_cancelled(cancel_check)
        client = self._get_gemini_client(api_key)
        if not client or not text:
            return None

        try:
            prompt = (
                f"Translate this into concise English product search terms: {text}. "
                "Output terms only."
            )
            result = self._generate_gemini_text(prompt, api_key, cancel_check).strip().strip("\"'")
            return result if result else None
        except Exception as exc:
            if is_cancelled_exception(exc):
                raise
            return None

    def _search_1688_multiple(
        self,
        keyword: str,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> List[str]:
        """Search 1688 pages and extract candidate image URLs."""
        urls: List[str] = []

        try:
            check_cancelled(cancel_check)
            encoded_keyword = quote(keyword)
            search_urls = [
                f"https://s.1688.com/selloffer/offer_search.htm?keywords={encoded_keyword}",
                f"https://s.1688.com/selloffer/offer_search.htm?keywords={encoded_keyword}&sortType=va",
                f"https://s.1688.com/pic/offer_search.htm?keywords={encoded_keyword}",
            ]

            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,ko;q=0.8,en;q=0.7",
                "Referer": "https://www.1688.com/",
            }

            patterns = [
                r"(https://cbu01\.alicdn\.com/img/[^\"'>\s]+\.(?:jpg|jpeg|png|webp))",
                r"(https://img\.alicdn\.com/[^\"'>\s]+\.(?:jpg|jpeg|png|webp))",
                r"(https://cbu\d+\.alicdn\.com/[^\"'>\s]+\.(?:jpg|jpeg|png|webp))",
                r"(https://gw\.alicdn\.com/[^\"'>\s]+\.(?:jpg|jpeg|png|webp))",
            ]

            for search_url in search_urls:
                check_cancelled(cancel_check)
                if len(urls) >= 5:
                    break
                response = None
                try:
                    response = self._request_search_with_safe_redirects(
                        search_url,
                        headers=headers,
                        cancel_check=cancel_check,
                    )
                    if response is None or response.status_code != 200:
                        continue
                    check_cancelled(cancel_check)
                    content_type = str(response.headers.get("content-type", "") or "").lower()
                    if content_type and not (
                        content_type.startswith("text/html")
                        or content_type.startswith("application/xhtml+xml")
                    ):
                        continue
                    body = self._read_bounded_response(
                        response,
                        max_bytes=self.MAX_SEARCH_HTML_BYTES,
                        cancel_check=cancel_check,
                    )
                    if body is None:
                        continue
                    text = body.decode("utf-8", errors="ignore")
                    for pattern in patterns:
                        matches = re.findall(pattern, text, re.IGNORECASE)
                        for match in matches:
                            clean_url = re.sub(r"_\d+x\d+\.", ".", match)
                            clean_url = re.sub(r"\?.+$", "", clean_url)
                            if "_60x60" in match or "_80x80" in match or "avatar" in match.lower():
                                continue
                            if clean_url not in urls:
                                urls.append(clean_url)
                            if len(urls) >= 10:
                                break
                        if len(urls) >= 10:
                            break
                except Exception as exc:
                    if is_cancelled_exception(exc):
                        raise
                    continue
                finally:
                    if response is not None:
                        self._close_response(response)
        except Exception as exc:
            if is_cancelled_exception(exc):
                raise
            print("  1688 검색 오류")

        return urls

    @staticmethod
    def _read_bounded_response(
        response,
        *,
        max_bytes: int,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> Optional[bytes]:
        content_length = str(response.headers.get("content-length", "") or "").strip()
        if content_length.isdigit() and int(content_length) > max_bytes:
            return None

        chunks = bytearray()
        for chunk in response.iter_content(chunk_size=ImageSearchService.DOWNLOAD_CHUNK_SIZE):
            check_cancelled(cancel_check)
            if not chunk:
                continue
            if len(chunks) + len(chunk) > max_bytes:
                return None
            chunks.extend(chunk)
        check_cancelled(cancel_check)
        return bytes(chunks)

    @staticmethod
    def _is_allowed_https_url(url: str, allowed_host_suffixes: Sequence[str]) -> bool:
        try:
            raw_url = str(url or "")
            if "\\" in raw_url or any(
                ord(character) < 32 or ord(character) == 127
                for character in raw_url
            ):
                return False
            parsed = urlparse(raw_url)
            if parsed.scheme != "https":
                return False
            if parsed.username or parsed.password:
                return False
            if parsed.port not in {None, 443}:
                return False
            host = (parsed.hostname or "").lower().strip()
            if not host or host.endswith("."):
                return False
            return any(
                host == suffix or host.endswith(f".{suffix}")
                for suffix in allowed_host_suffixes
            )
        except Exception:
            return False

    @classmethod
    def _is_allowed_image_url(cls, url: str) -> bool:
        return cls._is_allowed_https_url(url, cls.ALLOWED_IMAGE_HOST_SUFFIXES)

    @classmethod
    def _is_allowed_search_url(cls, url: str) -> bool:
        return cls._is_allowed_https_url(url, cls.ALLOWED_SEARCH_HOST_SUFFIXES)

    @staticmethod
    def _is_public_destination_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
        """Reject every special-use address class, even if stdlib flags change."""
        return bool(
            address.is_global
            and not address.is_private
            and not address.is_loopback
            and not address.is_link_local
            and not address.is_multicast
            and not address.is_unspecified
            and not address.is_reserved
        )

    @classmethod
    def _resolve_public_addresses(cls, host: str) -> tuple[str, ...]:
        """Resolve once and return only when every DNS answer is a public IP."""
        try:
            answers = socket.getaddrinfo(
                str(host or "").strip(),
                443,
                type=socket.SOCK_STREAM,
            )
        except (OSError, TypeError, ValueError):
            return ()
        if not answers:
            return ()
        try:
            addresses = tuple(dict.fromkeys(
                str(ipaddress.ip_address(str(sockaddr[0]).split("%", 1)[0]))
                for _family, _socktype, _proto, _canonname, sockaddr in answers
            ))
        except (IndexError, TypeError, ValueError):
            return ()
        if not addresses:
            return ()
        if not all(cls._is_public_destination_address(ipaddress.ip_address(item)) for item in addresses):
            return ()
        return addresses

    @classmethod
    def _host_resolves_only_to_public_addresses(cls, host: str) -> bool:
        """Compatibility predicate for callers that only need a safety answer."""
        return bool(cls._resolve_public_addresses(host))

    @classmethod
    def _is_safe_image_request_url(cls, url: str) -> bool:
        if not cls._is_allowed_image_url(url):
            return False
        try:
            host = (urlparse(str(url or "")).hostname or "").strip().lower()
        except Exception:
            return False
        return cls._host_resolves_only_to_public_addresses(host)

    @staticmethod
    def _request_target(parsed) -> str:
        target = parsed.path or "/"
        if parsed.params:
            target = f"{target};{parsed.params}"
        if parsed.query:
            target = f"{target}?{parsed.query}"
        return target

    def _open_pinned_https_request(
        self,
        normalized_url: str,
        *,
        headers: dict,
        addresses: Sequence[str],
        cancel_check: Optional[Callable[[], bool]] = None,
    ):
        """Connect directly to a validated IP while preserving TLS/HTTP hostname."""
        parsed = urlparse(normalized_url)
        hostname = (parsed.hostname or "").strip().lower()
        request_headers = dict(headers)
        request_headers["Host"] = hostname
        target = self._request_target(parsed)

        for address in addresses:
            check_cancelled(cancel_check)
            pool = HTTPSConnectionPool(
                str(address),
                port=443,
                timeout=Timeout(connect=15, read=15),
                maxsize=1,
                block=True,
                retries=False,
                cert_reqs=ssl.CERT_REQUIRED,
                assert_hostname=hostname,
                server_hostname=hostname,
            )
            try:
                raw_response = pool.urlopen(
                    "GET",
                    target,
                    headers=request_headers,
                    redirect=False,
                    retries=False,
                    preload_content=False,
                    decode_content=False,
                )
                return _PinnedImageResponse(raw_response, pool)
            except Exception as exc:
                pool.close()
                if is_cancelled_exception(exc):
                    raise
                continue
        return None

    def _open_pinned_image_request(
        self,
        normalized_url: str,
        *,
        headers: dict,
        addresses: Sequence[str],
        cancel_check: Optional[Callable[[], bool]] = None,
    ):
        return self._open_pinned_https_request(
            normalized_url,
            headers=headers,
            addresses=addresses,
            cancel_check=cancel_check,
        )

    def _open_pinned_search_request(
        self,
        normalized_url: str,
        *,
        headers: dict,
        addresses: Sequence[str],
        cancel_check: Optional[Callable[[], bool]] = None,
    ):
        return self._open_pinned_https_request(
            normalized_url,
            headers=headers,
            addresses=addresses,
            cancel_check=cancel_check,
        )

    @staticmethod
    def _close_response(response) -> None:
        close = getattr(response, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                pass

    def _request_with_safe_redirects(
        self,
        url: str,
        *,
        headers: dict,
        url_validator: Callable[[str], bool],
        request_opener: Callable,
        max_redirects: int,
        cancel_check: Optional[Callable[[], bool]] = None,
    ):
        """Follow a bounded redirect chain only after validating every target."""
        current_url = str(url or "").strip()
        visited = set()

        for redirect_count in range(max_redirects + 1):
            check_cancelled(cancel_check)
            try:
                parsed = urlparse(current_url)
                normalized_url = parsed._replace(fragment="").geturl()
            except Exception:
                return None
            if not normalized_url or normalized_url in visited:
                return None
            visited.add(normalized_url)
            if not url_validator(normalized_url):
                return None
            host = (urlparse(normalized_url).hostname or "").strip().lower()
            addresses = self._resolve_public_addresses(host)
            if not addresses:
                return None

            response = request_opener(
                normalized_url,
                headers=headers,
                addresses=addresses,
                cancel_check=cancel_check,
            )
            if response is None:
                return None
            try:
                check_cancelled(cancel_check)
            except Exception:
                self._close_response(response)
                raise
            if response.status_code not in self.IMAGE_REDIRECT_STATUSES:
                return response

            try:
                location = str(response.headers.get("location", "") or "").strip()
            finally:
                self._close_response(response)
            if not location or redirect_count >= max_redirects:
                return None
            current_url = urljoin(normalized_url, location)

        return None

    def _request_image_with_safe_redirects(
        self,
        url: str,
        *,
        headers: dict,
        cancel_check: Optional[Callable[[], bool]] = None,
    ):
        return self._request_with_safe_redirects(
            url,
            headers=headers,
            url_validator=self._is_allowed_image_url,
            request_opener=self._open_pinned_image_request,
            max_redirects=self.MAX_IMAGE_REDIRECTS,
            cancel_check=cancel_check,
        )

    def _request_search_with_safe_redirects(
        self,
        url: str,
        *,
        headers: dict,
        cancel_check: Optional[Callable[[], bool]] = None,
    ):
        return self._request_with_safe_redirects(
            url,
            headers=headers,
            url_validator=self._is_allowed_search_url,
            request_opener=self._open_pinned_search_request,
            max_redirects=self.MAX_SEARCH_REDIRECTS,
            cancel_check=cancel_check,
        )

    def _image_file_content_is_valid(self, path: Path) -> bool:
        if not self._is_regular_non_symlink(path):
            return False
        try:
            size = path.stat().st_size
            if size < self.MIN_IMAGE_BYTES or size > self.MAX_IMAGE_BYTES:
                return False
            with Image.open(path) as candidate:
                if candidate.format not in {"JPEG", "PNG", "WEBP", "GIF"}:
                    return False
                candidate.verify()
            with Image.open(path) as decoded:
                width, height = decoded.size
                if (
                    width <= 0
                    or height <= 0
                    or width * height > self.MAX_IMAGE_PIXELS
                ):
                    return False
                decoded.load()
            return True
        except Exception:
            return False

    def _existing_cache_is_valid(self, path: Path) -> bool:
        if not self._image_file_content_is_valid(path):
            return False
        try:
            return bool(secure_file_permissions(path))
        except Exception:
            return False

    def _stream_image_to_temp(
        self,
        response,
        cache_dir: Path,
        filename: str,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> Path:
        descriptor, raw_temp_path = tempfile.mkstemp(
            dir=cache_dir,
            prefix=f".{filename}.",
            suffix=".tmp",
        )
        temp_path = Path(raw_temp_path)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                descriptor = -1
                if not secure_file_permissions(temp_path):
                    raise PermissionError("Unable to secure image cache temporary file")
                total_written = 0
                for chunk in response.iter_content(chunk_size=self.DOWNLOAD_CHUNK_SIZE):
                    check_cancelled(cancel_check)
                    if not chunk:
                        continue
                    total_written += len(chunk)
                    if total_written > self.MAX_IMAGE_BYTES:
                        raise ValueError("Image exceeds maximum allowed size")
                    handle.write(chunk)
                check_cancelled(cancel_check)
                if total_written < self.MIN_IMAGE_BYTES:
                    raise ValueError("Image is smaller than the minimum allowed size")
                handle.flush()
                os.fsync(handle.fileno())
            return temp_path
        except Exception:
            if descriptor >= 0:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
            self._remove_cache_entry(temp_path)
            raise

    def _download_image(
        self,
        url: str,
        product_name: str,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> Optional[str]:
        """Download and atomically publish a verified image in the local cache."""
        del product_name
        response = None
        temp_path: Optional[Path] = None
        try:
            check_cancelled(cancel_check)
            if not self._is_allowed_image_url(url):
                return None
            with _CACHE_LOCK:
                check_cancelled(cancel_check)
                if not self._ensure_cache_dir_secure():
                    return None
                if not self._has_sufficient_disk_space():
                    return None

                parsed = urlparse(url)
                ext = Path(parsed.path).suffix.lower().lstrip(".")
                if ext not in {"jpg", "jpeg", "png", "webp", "gif"}:
                    ext = "jpg"
                hash_name = hashlib.sha256(url.encode("utf-8")).hexdigest()
                filename = f"{hash_name}.{ext}"
                cache_dir = Path(self.CACHE_DIR)
                filepath = cache_dir / filename

                if os.path.lexists(filepath):
                    if self._existing_cache_is_valid(filepath):
                        return str(filepath)
                    self._remove_cache_entry(filepath)
                    if os.path.lexists(filepath):
                        return None

                headers = {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36"
                    ),
                    "Referer": "https://www.1688.com/",
                    "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
                }
                response = self._request_image_with_safe_redirects(
                    url,
                    headers=headers,
                    cancel_check=cancel_check,
                )
                if response is None or response.status_code != 200:
                    return None
                check_cancelled(cancel_check)

                content_type = str(response.headers.get("content-type", "") or "").lower()
                if not content_type.startswith("image/"):
                    return None
                content_length = str(
                    response.headers.get("content-length", "") or ""
                ).strip()
                if content_length.isdigit() and int(content_length) > self.MAX_IMAGE_BYTES:
                    return None

                temp_path = self._stream_image_to_temp(
                    response,
                    cache_dir,
                    filename,
                    cancel_check,
                )
                if not self._image_file_content_is_valid(temp_path):
                    return None
                check_cancelled(cancel_check)
                os.replace(temp_path, filepath)
                temp_path = None
                try:
                    final_acl_is_secure = bool(secure_file_permissions(filepath))
                except Exception:
                    final_acl_is_secure = False
                if not final_acl_is_secure:
                    self._remove_cache_entry(filepath)
                    return None
                self._prune_cache()
                return str(filepath)
        except Exception as exc:
            if is_cancelled_exception(exc):
                raise
            return None
        finally:
            if temp_path is not None:
                self._remove_cache_entry(temp_path)
            if response is not None:
                self._close_response(response)


_instance: Optional[ImageSearchService] = None


def get_image_search() -> ImageSearchService:
    """Return singleton ImageSearchService instance."""
    global _instance
    if _instance is None:
        _instance = ImageSearchService()
    return _instance
