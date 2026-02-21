"""Application configuration storage."""

import json
import logging
import os
import tempfile
from pathlib import Path

from src.fs_security import secure_dir_permissions, secure_file_permissions
from src.secure_storage import protect_secret, unprotect_secret

logger = logging.getLogger(__name__)


class Config:
    _SECRET_KEYS = ("gemini_api_key", "threads_api_key", "instagram_password")

    def __init__(self):
        self.config_dir = Path.home() / ".shorts_thread_maker"
        self.config_file = self.config_dir / "config.json"
        self.secrets_file = self.config_dir / "secrets.json"
        self.ensure_config_dir()
        self.load()

    def ensure_config_dir(self):
        """Ensure configuration directory exists."""
        if not self.config_dir.exists():
            self.config_dir.mkdir(parents=True, mode=0o700)
        secure_dir_permissions(self.config_dir)

    def load(self):
        """Load config and encrypted secrets."""
        self._set_defaults()
        data = {}
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        data = loaded
            except (json.JSONDecodeError, OSError):
                logger.exception("Failed to load config file")
                data = {}

        self._load_from_dict(data)
        self._load_secrets()

        # Backward-compat migration for old plaintext values.
        migrated = False
        legacy_plaintext_present = False
        for key in self._SECRET_KEYS:
            legacy_value = str(data.get(key, "") or "").strip()
            if legacy_value:
                legacy_plaintext_present = True
            if not getattr(self, key, "") and legacy_value:
                setattr(self, key, legacy_value)
                migrated = True
        if migrated or legacy_plaintext_present:
            self.save()
        elif not self.config_file.exists():
            self.save()

    def _load_from_dict(self, data: dict):
        self.upload_interval = int(data.get("upload_interval", 60) or 60)
        self.instagram_username = str(data.get("instagram_username", "") or "")
        # Password is loaded from secure secrets storage and migrated in load().
        self.instagram_password = ""
        self.media_download_dir = str(data.get("media_download_dir", "media") or "media")
        self.prefer_video = bool(data.get("prefer_video", True))
        self.allow_ai_fallback = bool(data.get("allow_ai_fallback", False))
        self.instruction = str(data.get("instruction", "") or "")
        self.tutorial_shown = bool(data.get("tutorial_shown", False))

    def _set_defaults(self):
        self.gemini_api_key = ""
        self.upload_interval = 60
        self.instagram_username = ""
        self.instagram_password = ""
        self.threads_api_key = ""
        self.media_download_dir = "media"
        self.prefer_video = True
        self.allow_ai_fallback = False
        self.instruction = ""
        self.tutorial_shown = False

    def _load_secrets(self):
        if not self.secrets_file.exists():
            return
        try:
            with open(self.secrets_file, "r", encoding="utf-8") as f:
                payload = json.load(f)
            if not isinstance(payload, dict):
                return
            for key in self._SECRET_KEYS:
                raw_value = payload.get(key)
                if isinstance(raw_value, str):
                    setattr(self, key, unprotect_secret(raw_value))
        except Exception:
            logger.exception("Failed to load secrets file")

    def _save_secrets(self):
        payload = {}
        for key in self._SECRET_KEYS:
            value = str(getattr(self, key, "") or "").strip()
            if not value:
                continue
            protected = protect_secret(value, "shorts_thread_maker")
            if protected is None:
                logger.warning("Skipping secret '%s' because secure storage is unavailable", key)
                continue
            payload[key] = protected

        try:
            if payload:
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    dir=str(self.config_dir),
                    prefix="secrets_",
                    suffix=".tmp",
                    delete=False,
                ) as tmp:
                    json.dump(payload, tmp, ensure_ascii=False, indent=2)
                    temp_path = tmp.name
                secure_file_permissions(temp_path)
                os.replace(temp_path, self.secrets_file)
                secure_file_permissions(self.secrets_file)
            elif self.secrets_file.exists():
                self.secrets_file.unlink()
        except Exception:
            logger.exception("Failed to save secrets file")
            if "temp_path" in locals():
                try:
                    Path(temp_path).unlink(missing_ok=True)
                except Exception:
                    pass

    def save(self):
        """Save non-sensitive config and encrypted secrets."""
        data = {
            "upload_interval": self.upload_interval,
            "instagram_username": self.instagram_username,
            "media_download_dir": self.media_download_dir,
            "prefer_video": self.prefer_video,
            "allow_ai_fallback": self.allow_ai_fallback,
            "instruction": self.instruction,
            "tutorial_shown": self.tutorial_shown,
        }
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=str(self.config_dir),
                prefix="config_",
                suffix=".tmp",
                delete=False,
            ) as tmp:
                json.dump(data, tmp, ensure_ascii=False, indent=2)
                temp_path = tmp.name
            secure_file_permissions(temp_path)
            os.replace(temp_path, self.config_file)
            secure_file_permissions(self.config_file)
        except OSError:
            logger.exception("Failed to save config file")
            if "temp_path" in locals():
                try:
                    Path(temp_path).unlink(missing_ok=True)
                except Exception:
                    pass
        self._save_secrets()


config = Config()
