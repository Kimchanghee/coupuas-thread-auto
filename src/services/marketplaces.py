"""Affiliate marketplace capabilities and safe product-link helpers."""

from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import re
from typing import Iterable
from urllib.parse import urlparse


COUPANG_DISCLOSURE = (
    "이 포스팅은 쿠팡 파트너스 활동의 일환으로, "
    "이에 따른 일정액의 수수료를 제공받습니다."
)
NAVER_DISCLOSURE = (
    "이 포스팅은 네이버 쇼핑 커넥트 활동의 일환으로, "
    "판매 발생 시 수수료를 제공받습니다."
)
TOSS_DISCLOSURE = (
    "이 포스팅은 토스쇼핑 쉐어링크 활동의 일환으로, "
    "이에 따른 일정액의 수수료를 제공받습니다."
)
OHOUSE_DISCLOSURE = (
    "이 포스팅은 오늘의집 큐레이터 활동의 일환으로, "
    "구매시 이에 따른 일정액의 수수료를 제공받습니다."
)
MUSINSA_DISCLOSURE = (
    "이 포스팅은 무신사 큐레이터 활동의 일환으로, "
    "구매 발생 시 일정 수수료를 제공받습니다."
)
KURLY_DISCLOSURE = (
    "이 포스팅은 컬리 큐레이터 활동의 일환으로, "
    "구매 시 이에 따른 일정액의 수수료를 제공받습니다."
)
OLIVEYOUNG_DISCLOSURE = (
    "이 포스팅은 올리브영 쇼핑 큐레이터 활동의 일환으로, "
    "구매 시 일정 금액의 수수료를 제공받습니다."
)
GENERAL_AFFILIATE_DISCLOSURE = (
    "이 게시물에는 광고·제휴 링크가 포함될 수 있으며, "
    "구매 시 작성자가 일정액의 수수료를 제공받을 수 있습니다."
)


@dataclass(frozen=True)
class Marketplace:
    """Declarative trust and parsing rules for one commerce provider."""

    marketplace_id: str
    label: str
    hosts: tuple[str, ...]
    disclosure: str = GENERAL_AFFILIATE_DISCLOSURE
    redirect_hosts: tuple[str, ...] = ()
    allow_subdomains: bool = False
    entry_url_patterns: tuple[str, ...] = ()
    product_id_patterns: tuple[str, ...] = ()
    disclosure_source: str = ""

    @staticmethod
    def _host_matches(host: str, allowed_hosts: tuple[str, ...], allow_subdomains: bool) -> bool:
        normalized = str(host or "").strip().lower().rstrip(".")
        if normalized in allowed_hosts:
            return True
        if not allow_subdomains:
            return False
        return any(normalized.endswith(f".{allowed}") for allowed in allowed_hosts)

    def matches_host(self, host: str) -> bool:
        """Return whether *host* is a permitted user-entry host."""
        return self._host_matches(host, self.hosts, self.allow_subdomains)

    def matches_url(self, url: str) -> bool:
        try:
            parsed = urlparse(str(url or ""))
        except ValueError:
            return False
        if not self.matches_host(parsed.hostname or ""):
            return False
        if not self.entry_url_patterns:
            return True
        return any(re.search(pattern, str(url or ""), re.IGNORECASE) for pattern in self.entry_url_patterns)

    def allows_redirect_url(self, url: str) -> bool:
        """Validate a fetch/redirect destination inside this provider's trust graph."""
        normalized = normalize_product_url(url)
        if not normalized:
            return False
        host = urlparse(normalized).hostname or ""
        allowed = self.hosts + self.redirect_hosts
        return self._host_matches(host, allowed, self.allow_subdomains)

    def product_id_from_url(self, url: str) -> str:
        for pattern in self.product_id_patterns:
            match = re.search(pattern, str(url or ""), re.IGNORECASE)
            if match:
                return str(match.group(1) or "")
        return ""


@dataclass(frozen=True)
class ProductLinkInputAnalysis:
    """One visible input item and the reason it will or will not be processed."""

    line_number: int
    source_text: str
    url: str
    normalized_url: str
    marketplace: Marketplace | None
    status: str
    reason: str

    @property
    def is_processable(self) -> bool:
        return self.status == "supported"


MARKETPLACES = (
    Marketplace(
        marketplace_id="coupang",
        label="쿠팡 파트너스",
        hosts=("coupang.com",),
        disclosure=COUPANG_DISCLOSURE,
        allow_subdomains=True,
        product_id_patterns=(r"/products/(\d+)",),
        disclosure_source="https://partners.coupang.com/",
    ),
    Marketplace(
        marketplace_id="naver",
        label="네이버 쇼핑커넥트",
        hosts=(
            "shopping.naver.com",
            "smartstore.naver.com",
            "brand.naver.com",
            "shoppinglive.naver.com",
            "brandconnect.naver.com",
            "naver.me",
        ),
        disclosure=NAVER_DISCLOSURE,
        product_id_patterns=(
            r"/products/(\d+)",
            r"/catalog/(\d+)",
            r"[?&]channelProductNo=(\d+)",
            r"[?&]productNo=(\d+)",
        ),
        disclosure_source="https://help.naver.com/service/30027/contents/24104?osType=COMMONOS",
    ),
    Marketplace(
        marketplace_id="toss",
        label="토스쇼핑 쉐어링크",
        hosts=(
            "shopping.toss.im",
            "shopping-view.toss.im",
            "link.toss.im",
            "toss.im",
            "toss.shopping",
            "www.toss.shopping",
        ),
        redirect_hosts=("service.toss.im",),
        entry_url_patterns=(
            r"https://toss\.im/_m/",
            r"https://(?:www\.)?toss\.shopping/(?:i|t|products?)/",
            r"https://shopping\.toss\.im/products?/",
            r"https://shopping-view\.toss\.im/",
            r"https://link\.toss\.im/",
        ),
        disclosure=TOSS_DISCLOSURE,
        product_id_patterns=(
            r"/(?:i|products?)/(\d+)",
            r"/shopping/c/(\d+)",
            r"[?&]productId=(\d+)",
        ),
        disclosure_source="https://sharelink.toss.im/",
    ),
    Marketplace(
        marketplace_id="ohouse",
        label="오늘의집 큐레이터",
        hosts=("ohou.se", "m.ohou.se", "store.ohou.se", "ozip.me", "link.ohou.se"),
        disclosure=OHOUSE_DISCLOSURE,
        entry_url_patterns=(
            r"https://(?:m\.|store\.)?ohou\.se/(?:productions|goods)/",
            r"https://ozip\.me/",
            r"https://link\.ohou\.se/@ohouse/affiliate",
        ),
        product_id_patterns=(r"/(?:productions|goods)/(\d+)",),
        disclosure_source="https://ohouse-ad.oopy.io/curator_consumerrule",
    ),
    Marketplace(
        marketplace_id="musinsa",
        label="무신사 큐레이터",
        hosts=("musinsa.com", "www.musinsa.com", "musinsa.onelink.me"),
        disclosure=MUSINSA_DISCLOSURE,
        entry_url_patterns=(
            r"https://(?:www\.)?musinsa\.com/(?:curator|products?)/",
            r"https://musinsa\.onelink\.me/",
        ),
        product_id_patterns=(r"/products?/(\d+)",),
        disclosure_source="https://www.musinsa.com/curator/terms",
    ),
    Marketplace(
        marketplace_id="kurly",
        label="컬리 큐레이터",
        hosts=("kurly.com", "www.kurly.com", "lounge.kurly.com"),
        disclosure=KURLY_DISCLOSURE,
        entry_url_patterns=(
            r"https://lounge\.kurly\.com/link/",
            r"https://(?:www\.)?kurly\.com/goods/",
        ),
        product_id_patterns=(r"/goods/(\d+)",),
        disclosure_source="https://lounge.kurly.com/curator-program",
    ),
    Marketplace(
        marketplace_id="oliveyoung",
        label="올리브영 쇼핑 큐레이터",
        hosts=("oy.run", "m.oliveyoung.co.kr", "www.oliveyoung.co.kr"),
        disclosure=OLIVEYOUNG_DISCLOSURE,
        entry_url_patterns=(
            r"https://oy\.run/",
            r"https://(?:m\.|www\.)oliveyoung\.co\.kr/(?:m/|store/)?goods/",
        ),
        product_id_patterns=(r"[?&]goodsNo=([A-Za-z0-9_-]+)",),
        disclosure_source="https://m.oliveyoung.co.kr/m/mtn/affiliate/guide",
    ),
    Marketplace(
        marketplace_id="aliexpress",
        label="AliExpress",
        hosts=("aliexpress.com",),
        allow_subdomains=True,
        product_id_patterns=(r"/item/(\d+)\.html", r"[?&]productId=(\d+)"),
    ),
)
MARKETPLACES_BY_ID = {item.marketplace_id: item for item in MARKETPLACES}

_URL_PATTERN = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_TRAILING_URL_PUNCTUATION = ".,;:!?)]}〉》」』”’"
_CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x1f\x7f]")
MAX_PUBLIC_URL_LENGTH = 2048


def normalize_product_url(value: object) -> str:
    """Normalize a public HTTPS URL without accepting unsafe authority syntax."""
    raw = str(value or "").strip()
    if not raw or len(raw) > MAX_PUBLIC_URL_LENGTH or _CONTROL_CHAR_PATTERN.search(raw):
        return ""
    lowered = raw.lower()
    if lowered.startswith("http://"):
        return ""
    if not lowered.startswith("https://"):
        raw = f"https://{raw}"
    try:
        parsed = urlparse(raw)
        if parsed.scheme != "https" or not parsed.hostname:
            return ""
        if parsed.username or parsed.password:
            return ""
        if parsed.port not in (None, 443):
            return ""
        host = parsed.hostname.rstrip(".")
        try:
            ipaddress.ip_address(host)
            return ""
        except ValueError:
            pass
        host.encode("ascii")
    except (TypeError, ValueError, UnicodeError):
        return ""
    return raw


def marketplace_for_url(value: object) -> Marketplace | None:
    normalized = normalize_product_url(value)
    if not normalized:
        return None
    return next((item for item in MARKETPLACES if item.matches_url(normalized)), None)


def marketplace_for_redirect_url(value: object, marketplace_id: str) -> Marketplace | None:
    """Return the expected marketplace only when *value* is an allowed fetch target."""
    marketplace = MARKETPLACES_BY_ID.get(str(marketplace_id or ""))
    if marketplace is None:
        return None
    return marketplace if marketplace.allows_redirect_url(str(value or "")) else None


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


def analyze_product_link_input(text: object) -> list[ProductLinkInputAnalysis]:
    """Classify every visible URL or invalid non-empty line for input feedback.

    This is intentionally presentation-oriented. The upload extractor remains the
    source of truth for processable URLs, while this function also preserves the
    lines that would otherwise disappear as unsupported, unsafe, or malformed.
    """
    analyses: list[ProductLinkInputAnalysis] = []
    seen_supported: set[str] = set()

    for line_number, raw_line in enumerate(str(text or "").splitlines(), start=1):
        source_text = raw_line.strip()
        if not source_text:
            continue

        matches = _URL_PATTERN.findall(source_text)
        if not matches:
            analyses.append(
                ProductLinkInputAnalysis(
                    line_number=line_number,
                    source_text=source_text,
                    url="",
                    normalized_url="",
                    marketplace=None,
                    status="invalid",
                    reason="URL 형식을 확인해 주세요.",
                )
            )
            continue

        for match in matches:
            candidate = match.rstrip(_TRAILING_URL_PUNCTUATION)
            normalized = normalize_product_url(candidate)
            if not normalized:
                analyses.append(
                    ProductLinkInputAnalysis(
                        line_number=line_number,
                        source_text=source_text,
                        url=candidate,
                        normalized_url="",
                        marketplace=None,
                        status="invalid",
                        reason="안전한 HTTPS 링크인지 확인해 주세요.",
                    )
                )
                continue

            marketplace = marketplace_for_url(normalized)
            if marketplace is None:
                analyses.append(
                    ProductLinkInputAnalysis(
                        line_number=line_number,
                        source_text=source_text,
                        url=candidate,
                        normalized_url=normalized,
                        marketplace=None,
                        status="unsupported",
                        reason="현재 지원하지 않는 쇼핑 채널입니다.",
                    )
                )
                continue

            is_duplicate = normalized in seen_supported
            if not is_duplicate:
                seen_supported.add(normalized)
            analyses.append(
                ProductLinkInputAnalysis(
                    line_number=line_number,
                    source_text=source_text,
                    url=candidate,
                    normalized_url=normalized,
                    marketplace=marketplace,
                    status="duplicate" if is_duplicate else "supported",
                    reason=(
                        "앞에서 입력한 링크와 중복되어 제외됩니다."
                        if is_duplicate
                        else f"{marketplace.label} 링크로 인식했습니다."
                    ),
                )
            )

    return analyses


def supported_marketplace_labels() -> tuple[str, ...]:
    return tuple(item.label for item in MARKETPLACES)


def marketplace_ids(values: Iterable[object]) -> set[str]:
    return {
        marketplace.marketplace_id
        for value in values
        if (marketplace := marketplace_for_url(value)) is not None
    }
