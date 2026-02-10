"""
업로드 링크 히스토리 관리
중복 업로드 방지를 위해 이미 업로드한 링크를 기록합니다.
"""
import json
import os
from datetime import datetime
from typing import List, Optional, Set


class LinkHistory:
    """업로드된 링크 히스토리 관리"""

    HISTORY_FILE = "uploaded_links.json"

    def __init__(self, history_file: str = None):
        self.history_file = history_file or self.HISTORY_FILE
        self._history: dict = self._load()

    def _load(self) -> dict:
        """히스토리 파일 로드"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"  히스토리 로드 오류: {e}")
        return {"uploaded_links": [], "stats": {"total": 0, "success": 0, "failed": 0}}

    def _save(self):
        """히스토리 파일 저장"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self._history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"  히스토리 저장 오류: {e}")

    def _normalize_url(self, url: str) -> str:
        """URL 정규화 (쿼리 파라미터 제거 등)"""
        # 쿠팡 링크에서 핵심 부분만 추출
        url = url.strip()
        # 트래킹 파라미터 제거
        if '?' in url:
            base = url.split('?')[0]
        else:
            base = url
        return base.lower()

    def is_uploaded(self, url: str) -> bool:
        """이미 업로드된 링크인지 확인"""
        normalized = self._normalize_url(url)
        for item in self._history.get("uploaded_links", []):
            if self._normalize_url(item.get("url", "")) == normalized:
                return True
        return False

    def add_link(self, url: str, product_title: str = "", success: bool = True):
        """업로드된 링크 추가"""
        if self.is_uploaded(url):
            return  # 이미 있으면 스킵

        record = {
            "url": url,
            "title": product_title,
            "uploaded_at": datetime.now().isoformat(),
            "success": success
        }

        self._history["uploaded_links"].append(record)
        self._history["stats"]["total"] += 1
        if success:
            self._history["stats"]["success"] += 1
        else:
            self._history["stats"]["failed"] += 1

        self._save()

    def get_uploaded_urls(self) -> Set[str]:
        """업로드된 URL 목록 반환"""
        return {self._normalize_url(item["url"]) for item in self._history.get("uploaded_links", [])}

    def get_stats(self) -> dict:
        """통계 반환"""
        return self._history.get("stats", {"total": 0, "success": 0, "failed": 0})

    def filter_new_links(self, urls: List[str]) -> List[str]:
        """새로운 링크만 필터링"""
        uploaded = self.get_uploaded_urls()
        new_links = []
        for url in urls:
            if self._normalize_url(url) not in uploaded:
                new_links.append(url)
        return new_links

    def clear_history(self):
        """히스토리 초기화"""
        self._history = {"uploaded_links": [], "stats": {"total": 0, "success": 0, "failed": 0}}
        self._save()


# 싱글톤 인스턴스
_instance: Optional[LinkHistory] = None

def get_link_history() -> LinkHistory:
    """LinkHistory 싱글톤 인스턴스 반환"""
    global _instance
    if _instance is None:
        _instance = LinkHistory()
    return _instance
