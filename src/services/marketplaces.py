"""Supported commerce marketplaces and safe product-link helpers."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable
from urllib.parse import urlparse


COUPANG_DISCLOSURE = (
    "이 포스팅은 쿠팡 파트너스 활동의 일환으로, "
    "이에 따른 일정액의 수수료를 제공받습니다."
)
GENERAL_AFFILIATE_DISCLOSURE = (
    "이 게시물에는 광고·제휴 링크가 포함될 수 있으며, "
    "구매 시 작성자가 일정액의 수수료를 제공받을 수 있습니다."
)


@dataclass(frozen=True)
class Marketplace:
    marketplace_id: str
    label: str
    hosts: tuple[str, ...]
    disclosure: str = GENERAL_AFFILIATE_DISCLOSURE

    def matches_host(self, host: str) -> bool:
        normalized = str(host or "").strip().lower().rstrip(".")
        if normalized in self.hosts:
            return True
        if self.marketplace_id not in {"coupang", "aliexpress"}:
            return False
        return any(normalized.endswith(f".{allowed}") for allowed in self.hosts)


MARKETPLACES = (
    Marketplace(
        marketplace_id="coupang",
        label="쿠팡",
        hosts=("coupang.com",),
        disclosure=COUPANG_DISCLOSURE,
    ),
    Marketplace(
        marketplace_id="naver",
        label="네이버쇼핑",
        hosts=(
            "shopping.naver.com",
            "smartstore.naver.com",
            "brand.naver.com",
            "shoppinglive.naver.com",
            "naver.me",
        ),
    ),
    Marketplace(
        marketplace_id="toss",
        label="토스쇼핑",
        hosts=("shopping.toss.im", "shopping-view.toss.im", "link.toss.im", "toss.im"),
    ),
    Marketplace(
        marketplace_id="aliexpress",
        label="AliExpress",
        hosts=("aliexpress.com",),
    ),
)
MARKETPLACES_BY_ID = {item.marketplace_id: item for item in MARKETPLACES}

_URL_PATTERN = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_TRAILING_URL_PUNCTUATION = ".,;:!?)]}〉》」』”’"


def normalize_product_url(value: object) -> str:
    """Normalize a public HTTPS URL without accepting credentials or custom ports."""
    raw = str(value or "").strip()
    if not raw:
        return ""
    if not raw.startswith(("http://", "https://")):
        raw = f"https://{raw}"
    if raw.startswith("http://"):
        raw = "https://" + raw[len("http://") :]
    try:
        parsed = urlparse(raw)
        if parsed.scheme != "https" or not parsed.hostname:
            return ""
        if parsed.username or parsed.password:
            return ""
        if parsed.port not in (None, 443):
            return ""
    except (TypeError, ValueError):
        return ""
    return raw


def marketplace_for_url(value: object) -> Marketplace | None:
    normalized = normalize_product_url(value)
    if not normalized:
        return None
    host = (urlparse(normalized).hostname or "").lower()
    return next((item for item in MARKETPLACES if item.matches_host(host)), None)


def is_supported_product_url(value: object) -> bool:
    return marketplace_for_url(value) is not None


def extract_supported_product_links(text: object) -> list[str]:
    links: list[str] = []
    seen: set[str] = set()
    for match in _URL_PATTERN.findall(str(text or "")):
        candidate = match.rstrip(_TRAILING_URL_PUNCTUATION)
        normalized = normalize_product_url(candidate)
        if not normalized or normalized in seen or not is_supported_product_url(normalized):
            continue
        seen.add(normalized)
        links.append(normalized)
    return links


def supported_marketplace_labels() -> tuple[str, ...]:
    return tuple(item.label for item in MARKETPLACES)


def marketplace_ids(values: Iterable[object]) -> set[str]:
    return {
        marketplace.marketplace_id
        for value in values
        if (marketplace := marketplace_for_url(value)) is not None
    }
