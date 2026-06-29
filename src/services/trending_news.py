# -*- coding: utf-8 -*-
"""Lightweight current issue headline fetcher used by post concept 2."""

from __future__ import annotations

import html
import logging
import time
import urllib.request
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)

GOOGLE_NEWS_KR_RSS = "https://news.google.com/rss?hl=ko&gl=KR&ceid=KR:ko"
_CACHE_TTL_SECONDS = 30 * 60
_cached_at = 0.0
_cached_headlines: list[str] = []


def _clean_title(value: str) -> str:
    text = html.unescape(str(value or ""))
    text = " ".join(text.split())
    if " - " in text:
        text = text.rsplit(" - ", 1)[0].strip()
    return text[:120]


def fetch_korean_issue_headlines(limit: int = 8, timeout: float = 4.0) -> list[str]:
    """Return recent Korean Google News headlines.

    This function is deliberately best-effort. Copy generation must continue
    even when Google News, DNS, or the local network is unavailable.
    """
    global _cached_at, _cached_headlines

    now = time.time()
    if _cached_headlines and now - _cached_at < _CACHE_TTL_SECONDS:
        return list(_cached_headlines[:limit])

    try:
        request = urllib.request.Request(
            GOOGLE_NEWS_KR_RSS,
            headers={
                "User-Agent": "Mozilla/5.0 CoupangThreadAuto/1.0",
                "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8",
            },
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(512_000)
        root = ET.fromstring(body)
        headlines: list[str] = []
        for item in root.findall(".//item"):
            title_node = item.find("title")
            title = _clean_title(title_node.text if title_node is not None else "")
            if not title or title in headlines:
                continue
            headlines.append(title)
            if len(headlines) >= max(limit, 1):
                break
        if headlines:
            _cached_at = now
            _cached_headlines = headlines
        return headlines[:limit]
    except Exception:
        logger.debug("Failed to fetch current issue headlines", exc_info=True)
        return list(_cached_headlines[:limit])
