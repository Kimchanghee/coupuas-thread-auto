"""
설정 관리 모듈
쿠팡 파트너스 Threads 자동화 설정을 관리합니다.
"""

import json
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class Config:
    def __init__(self):
        self.config_dir = Path.home() / ".shorts_thread_maker"
        self.config_file = self.config_dir / "config.json"
        self.ensure_config_dir()
        self.load()

    def ensure_config_dir(self):
        """설정 디렉토리가 없으면 생성 (owner-only 권한)."""
        if not self.config_dir.exists():
            self.config_dir.mkdir(parents=True, mode=0o700)

    def load(self):
        """설정 파일을 로드합니다."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._load_from_dict(data)
            except (json.JSONDecodeError, OSError):
                logger.exception("Failed to load config file")
                self._set_defaults()
                self.save()
        else:
            self._set_defaults()
            self.save()

    def _load_from_dict(self, data: dict):
        """딕셔너리에서 설정을 로드합니다."""
        # 필수 설정
        self.gemini_api_key = data.get('gemini_api_key', '')

        # 업로드 설정
        self.upload_interval = data.get('upload_interval', 60)

        # 브라우저 자동화용 (선택)
        self.instagram_username = data.get('instagram_username', '')
        # 호환성: 이전 버전에서 저장된 비밀번호 로드 (더 이상 디스크에 저장하지 않음)
        self.instagram_password = data.get('instagram_password', '')

        # Threads API (선택)
        self.threads_api_key = data.get('threads_api_key', '')

        # 텔레그램 알림 (선택)
        self.telegram_bot_token = data.get('telegram_bot_token', '')
        self.telegram_chat_id = data.get('telegram_chat_id', '')
        self.telegram_enabled = data.get('telegram_enabled', False)

        # 미디어 설정
        self.media_download_dir = data.get('media_download_dir', 'media')
        self.prefer_video = data.get('prefer_video', True)

        # 호환성: 이전 버전 설정
        self.instruction = data.get('instruction', '')

        # 튜토리얼
        self.tutorial_shown = data.get('tutorial_shown', False)

    def _set_defaults(self):
        """기본값을 설정합니다."""
        self.gemini_api_key = ''
        self.upload_interval = 60
        self.instagram_username = ''
        self.instagram_password = ''
        self.threads_api_key = ''
        self.telegram_bot_token = ''
        self.telegram_chat_id = ''
        self.telegram_enabled = False
        self.media_download_dir = 'media'
        self.prefer_video = True
        self.instruction = ''
        self.tutorial_shown = False

    def save(self):
        """설정 파일 저장 (민감 정보 파일 권한 제한)."""
        data = {
            'gemini_api_key': self.gemini_api_key,
            'upload_interval': self.upload_interval,
            'instagram_username': self.instagram_username,
            'threads_api_key': self.threads_api_key,
            'telegram_bot_token': self.telegram_bot_token,
            'telegram_chat_id': self.telegram_chat_id,
            'telegram_enabled': self.telegram_enabled,
            'media_download_dir': self.media_download_dir,
            'prefer_video': self.prefer_video,
            'instruction': self.instruction,
            'tutorial_shown': self.tutorial_shown,
        }
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            # owner-only read/write (Unix: 0o600, Windows: best-effort)
            try:
                os.chmod(self.config_file, 0o600)
            except OSError:
                pass
        except OSError:
            logger.exception("Failed to save config file")


# 전역 설정 객체
config = Config()
