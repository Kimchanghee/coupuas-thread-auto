# -*- coding: utf-8 -*-
"""Thread-safe upload link history with atomic persistence."""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set

from src.fs_security import secure_dir_permissions, secure_file_permissions

logger = logging.getLogger(__name__)


class LinkHistory:
    """Store uploaded links to prevent duplicate uploads."""

    DEFAULT_HISTORY_FILE = Path.home() / ".shorts_thread_maker" / "uploaded_links.json"

    def __init__(self, history_file: Optional[str] = None):
        self._lock = threading.RLock()
        self.history_file = Path(history_file).expanduser() if history_file else self.DEFAULT_HISTORY_FILE
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        secure_dir_permissions(self.history_file.parent)
        self._history = self._load()
        self._uploaded_set = self._build_uploaded_set()

    def _default_payload(self) -> dict:
        return {"uploaded_links": [], "stats": {"total": 0, "success": 0, "failed": 0}}

    def _load(self) -> dict:
        if not self.history_file.exists():
            return self._default_payload()
        try:
            with self.history_file.open("r", encoding="utf-8") as handle:
                loaded = json.load(handle)
            if not isinstance(loaded, dict):
                return self._default_payload()
            loaded.setdefault("uploaded_links", [])
            loaded.setdefault("stats", {"total": 0, "success": 0, "failed": 0})
            return loaded
        except Exception:
            logger.exception("Failed to load link history")
            return self._default_payload()

    def _save(self) -> None:
        temp_path: Optional[str] = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=str(self.history_file.parent),
                prefix="uploaded_links_",
                suffix=".tmp",
                delete=False,
            ) as tmp:
                json.dump(self._history, tmp, ensure_ascii=False, indent=2)
                temp_path = tmp.name
            secure_file_permissions(temp_path)
            os.replace(temp_path, self.history_file)
            secure_file_permissions(self.history_file)
        except Exception:
            logger.exception("Failed to save link history")
            if temp_path:
                try:
                    Path(temp_path).unlink(missing_ok=True)
                except Exception:
                    pass

    def _normalize_url(self, url: str) -> str:
        url_text = str(url or "").strip()
        base = url_text.split("?", 1)[0]
        return base.lower()

    def _build_uploaded_set(self) -> Set[str]:
        uploaded = set()
        for item in self._history.get("uploaded_links", []):
            if isinstance(item, dict):
                uploaded.add(self._normalize_url(item.get("url", "")))
        return uploaded

    def is_uploaded(self, url: str) -> bool:
        normalized = self._normalize_url(url)
        with self._lock:
            return normalized in self._uploaded_set

    def add_link(self, url: str, product_title: str = "", success: bool = True) -> None:
        normalized = self._normalize_url(url)
        if not normalized:
            return

        with self._lock:
            if normalized in self._uploaded_set:
                return

            record = {
                "url": str(url or "").strip(),
                "title": str(product_title or ""),
                "uploaded_at": datetime.now().isoformat(),
                "success": bool(success),
            }
            self._history["uploaded_links"].append(record)
            stats = self._history.setdefault("stats", {"total": 0, "success": 0, "failed": 0})
            stats["total"] = int(stats.get("total", 0)) + 1
            if success:
                stats["success"] = int(stats.get("success", 0)) + 1
            else:
                stats["failed"] = int(stats.get("failed", 0)) + 1
            self._uploaded_set.add(normalized)
            self._save()

    def get_uploaded_urls(self) -> Set[str]:
        with self._lock:
            return set(self._uploaded_set)

    def get_stats(self) -> dict:
        with self._lock:
            stats = self._history.get("stats", {})
            return {
                "total": int(stats.get("total", 0)),
                "success": int(stats.get("success", 0)),
                "failed": int(stats.get("failed", 0)),
            }

    def filter_new_links(self, urls: List[str]) -> List[str]:
        with self._lock:
            uploaded = set(self._uploaded_set)
        return [url for url in urls if self._normalize_url(url) not in uploaded]

    def clear_history(self) -> None:
        with self._lock:
            self._history = self._default_payload()
            self._uploaded_set.clear()
            self._save()


_instance: Optional[LinkHistory] = None
_instance_lock = threading.Lock()


def get_link_history() -> LinkHistory:
    """Return process-wide singleton LinkHistory instance."""
    global _instance
    if _instance is not None:
        return _instance
    with _instance_lock:
        if _instance is None:
            _instance = LinkHistory()
    return _instance
