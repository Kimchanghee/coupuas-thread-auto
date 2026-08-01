"""Application configuration storage."""

import json
import logging
import os
import re
import tempfile
import threading
from pathlib import Path
from urllib.parse import unquote, urlparse

from src.ai_provider import (
    AI_PROVIDER_GEMINI,
    AI_PROVIDER_GROK_CLI,
    AI_PROVIDER_MANAGED,
    normalize_ai_provider,
)
from src.fs_security import secure_dir_permissions, secure_file_permissions
from src.secure_storage import protect_secret, unprotect_secret
from src.services.post_concepts import DEFAULT_POST_CONCEPT_ID, normalize_concept_id
from src.models.threads_account import ThreadsAccount, normalize_threads_username

logger = logging.getLogger(__name__)


class Config:
    _SECRET_KEYS = ("gemini_api_key", "gemini_api_keys", "threads_api_key", "instagram_password")
    _MAX_GEMINI_KEYS = 10
    _MAX_THREADS_ACCOUNTS = 10

    def __init__(self):
        self._lock = threading.RLock()
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
        with self._lock:
            self._set_defaults()
            data = {}
            if self.config_file.exists():
                try:
                    with open(self.config_file, "r", encoding="utf-8") as f:
                        loaded = json.load(f)
                        if isinstance(loaded, dict):
                            data = loaded
                except (json.JSONDecodeError, OSError):
                    logger.exception("설정 파일을 불러오지 못했습니다.")
                    data = {}

            self._load_from_dict(data)
            accounts_migrated = self._migrate_threads_accounts(data)
            self._load_secrets()
            self._sync_gemini_key_state()
            if (
                self._local_ai_providers_enabled()
                and "ai_provider" not in data
                and self.gemini_api_keys
            ):
                # Preserve existing installations until the user explicitly selects Grok.
                self.ai_provider = AI_PROVIDER_GEMINI

            # Backward-compat migration for old plaintext values.
            migrated = False
            legacy_plaintext_present = False
            for key in self._SECRET_KEYS:
                if key == "gemini_api_keys":
                    legacy_values = self._normalize_gemini_keys(data.get(key))
                    if legacy_values:
                        legacy_plaintext_present = True
                    if not self.gemini_api_keys and legacy_values:
                        self.gemini_api_keys = legacy_values
                        migrated = True
                    continue
                legacy_value = str(data.get(key, "") or "").strip()
                if legacy_value:
                    legacy_plaintext_present = True
                if not getattr(self, key, "") and legacy_value:
                    setattr(self, key, legacy_value)
                    migrated = True
            self._sync_gemini_key_state()
            if migrated or legacy_plaintext_present or accounts_migrated:
                self.save()
            elif not self.config_file.exists():
                self.save()

    def _load_from_dict(self, data: dict):
        self.upload_interval = int(data.get("upload_interval", 60) or 60)
        self.instagram_username = str(data.get("instagram_username", "") or "")
        self.threads_accounts = self._deserialize_threads_accounts(data.get("threads_accounts"))
        self.active_threads_account_id = str(data.get("active_threads_account_id", "") or "")
        self.ai_provider = (
            normalize_ai_provider(data.get("ai_provider"), default=AI_PROVIDER_MANAGED)
            if self._local_ai_providers_enabled()
            else AI_PROVIDER_MANAGED
        )
        # Password is loaded from secure secrets storage and migrated in load().
        self.instagram_password = ""
        self.gemini_api_keys = self._normalize_gemini_keys(data.get("gemini_api_keys"))
        self.media_download_dir = str(data.get("media_download_dir", "media") or "media")
        self.prefer_video = bool(data.get("prefer_video", True))
        self.allow_ai_fallback = bool(data.get("allow_ai_fallback", False))
        self.auto_start_enabled = bool(data.get("auto_start_enabled", True))
        self.instruction = str(data.get("instruction", "") or "")
        self.post_concept = normalize_concept_id(data.get("post_concept"))
        self.tutorial_shown = bool(data.get("tutorial_shown", False))

    @staticmethod
    def _legacy_profile_id(legacy_value: str, normalized_username: str) -> str:
        # Matches the value the single-account UI historically passed to
        # ComputerUseAgent, preserving its encrypted session location.
        candidate = str(legacy_value or "").strip()
        if "://" in candidate or candidate.lower().startswith("www."):
            try:
                parsed = urlparse(candidate if "://" in candidate else f"https://{candidate}")
                segments = [part.strip() for part in unquote(parsed.path).split("/") if part.strip()]
                candidate = segments[-1] if segments else str(parsed.netloc or "")
            except ValueError:
                candidate = normalized_username
        if "/" in candidate:
            candidate = candidate.rsplit("/", 1)[-1]
        candidate = candidate.split("?", 1)[0].split("#", 1)[0].strip().removeprefix("@")
        candidate = re.sub(r"[^A-Za-z0-9._]", "", candidate)[:30] or normalized_username
        return ".threads_profile_" + candidate

    @classmethod
    def _deserialize_threads_accounts(cls, raw_accounts):
        if not isinstance(raw_accounts, list):
            return []
        accounts = []
        ids = set()
        profiles = set()
        for raw in raw_accounts:
            if len(accounts) >= cls._MAX_THREADS_ACCOUNTS:
                break
            try:
                account = ThreadsAccount.from_dict(raw)
            except (TypeError, ValueError):
                logger.warning("Invalid Threads account entry ignored while loading configuration.")
                continue
            if account.account_id in ids or account.profile_id in profiles:
                logger.warning("Duplicate Threads account identifier ignored while loading configuration.")
                continue
            ids.add(account.account_id)
            profiles.add(account.profile_id)
            accounts.append(account)
        return accounts

    def _migrate_threads_accounts(self, data: dict) -> bool:
        """Create the first account from legacy config without copying secrets."""
        if self.threads_accounts:
            if self.active_threads_account_id not in {a.account_id for a in self.threads_accounts}:
                self.active_threads_account_id = self.threads_accounts[0].account_id
                return True
            return False
        legacy = str(data.get("instagram_username", "") or "").strip()
        if not legacy:
            return False
        try:
            username = normalize_threads_username(legacy)
        except ValueError:
            logger.warning("Legacy Instagram username could not be migrated as a Threads account.")
            return False
        account = ThreadsAccount.create(
            expected_username=username,
            display_name=username,
            profile_id=self._legacy_profile_id(legacy, username),
            upload_interval=self.upload_interval,
        )
        self.threads_accounts = [account]
        self.active_threads_account_id = account.account_id
        return True

    def _set_defaults(self):
        self.gemini_api_key = ""
        self.gemini_api_keys = []
        self.ai_provider = AI_PROVIDER_MANAGED
        self.upload_interval = 60
        self.instagram_username = ""
        self.threads_accounts = []
        self.active_threads_account_id = ""
        self.instagram_password = ""
        self.threads_api_key = ""
        self.media_download_dir = "media"
        self.prefer_video = True
        self.allow_ai_fallback = False
        self.auto_start_enabled = True
        self.instruction = ""
        self.post_concept = DEFAULT_POST_CONCEPT_ID
        self.tutorial_shown = False

    @staticmethod
    def _local_ai_providers_enabled() -> bool:
        value = str(os.getenv("THREAD_AUTO_ALLOW_LOCAL_AI_PROVIDERS", "") or "")
        return value.strip().lower() in {"1", "true", "yes", "on"}

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
                if key == "gemini_api_keys":
                    if isinstance(raw_value, list):
                        plain_keys = []
                        for item in raw_value:
                            if not isinstance(item, str):
                                continue
                            plain = unprotect_secret(item).strip()
                            if plain:
                                plain_keys.append(plain)
                        self.gemini_api_keys = self._normalize_gemini_keys(plain_keys)
                    elif isinstance(raw_value, str):
                        plain = unprotect_secret(raw_value).strip()
                        self.gemini_api_keys = self._normalize_gemini_keys([plain])
                    continue
                if isinstance(raw_value, str):
                    setattr(self, key, unprotect_secret(raw_value))
        except Exception:
            logger.exception("보안 설정 파일을 불러오지 못했습니다.")
        self._sync_gemini_key_state()

    def _save_secrets(self):
        payload = {}
        for key in self._SECRET_KEYS:
            if key == "gemini_api_keys":
                values = self._normalize_gemini_keys(getattr(self, key, []))
                if not values:
                    continue
                protected_values = []
                for value in values:
                    protected = protect_secret(value, "shorts_thread_maker")
                    if protected is None:
                        logger.warning("보안 저장소를 사용할 수 없어 비밀값 '%s' 저장을 건너뜁니다.", key)
                        protected_values = []
                        break
                    protected_values.append(protected)
                if protected_values:
                    payload[key] = protected_values
                continue

            value = str(getattr(self, key, "") or "").strip()
            if not value:
                continue
            protected = protect_secret(value, "shorts_thread_maker")
            if protected is None:
                logger.warning("보안 저장소를 사용할 수 없어 비밀값 '%s' 저장을 건너뜁니다.", key)
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
            logger.exception("보안 설정 파일 저장에 실패했습니다.")
            if "temp_path" in locals():
                try:
                    Path(temp_path).unlink(missing_ok=True)
                except Exception:
                    pass

    def save(self):
        """Save non-sensitive config and encrypted secrets."""
        with self._lock:
            self._sync_gemini_key_state()
            data = {
                "upload_interval": self.upload_interval,
                "instagram_username": self.instagram_username,
                "threads_accounts": [account.to_dict() for account in self.threads_accounts],
                "active_threads_account_id": self.active_threads_account_id,
                "ai_provider": normalize_ai_provider(getattr(self, "ai_provider", "")),
                "media_download_dir": self.media_download_dir,
                "prefer_video": self.prefer_video,
                "allow_ai_fallback": self.allow_ai_fallback,
                "auto_start_enabled": self.auto_start_enabled,
                "instruction": self.instruction,
                "post_concept": normalize_concept_id(getattr(self, "post_concept", "")),
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
                logger.exception("설정 파일 저장에 실패했습니다.")
                if "temp_path" in locals():
                    try:
                        Path(temp_path).unlink(missing_ok=True)
                    except Exception:
                        pass
            self._save_secrets()

    @classmethod
    def _normalize_gemini_keys(cls, values):
        if isinstance(values, str):
            source = [values]
        elif isinstance(values, (list, tuple)):
            source = list(values)
        else:
            source = []

        normalized = []
        seen = set()
        for value in source:
            key = str(value or "").strip()
            if not key or key in seen:
                continue
            seen.add(key)
            normalized.append(key)
            if len(normalized) >= cls._MAX_GEMINI_KEYS:
                break
        return normalized

    def _sync_gemini_key_state(self):
        keys = self._normalize_gemini_keys(getattr(self, "gemini_api_keys", []))
        primary = str(getattr(self, "gemini_api_key", "") or "").strip()
        if primary and primary not in keys:
            keys.insert(0, primary)
        keys = self._normalize_gemini_keys(keys)
        self.gemini_api_keys = keys
        self.gemini_api_key = keys[0] if keys else ""

    def get_gemini_api_keys(self):
        with self._lock:
            self._sync_gemini_key_state()
            return list(self.gemini_api_keys)

    def set_gemini_api_keys(self, keys):
        with self._lock:
            self.gemini_api_keys = self._normalize_gemini_keys(keys)
            self.gemini_api_key = self.gemini_api_keys[0] if self.gemini_api_keys else ""

    def get_threads_accounts(self):
        with self._lock:
            return list(self.threads_accounts)

    def get_threads_account(self, account_id):
        with self._lock:
            target = str(account_id or "")
            return next((account for account in self.threads_accounts if account.account_id == target), None)

    def get_active_threads_account(self):
        with self._lock:
            return self.get_threads_account(self.active_threads_account_id)

    def add_threads_account(self, expected_username, **values):
        with self._lock:
            if len(self.threads_accounts) >= self._MAX_THREADS_ACCOUNTS:
                raise ValueError("A maximum of 10 Threads accounts is supported")
            account = ThreadsAccount.create(expected_username, **values)
            if any(
                existing.expected_username == account.expected_username
                for existing in self.threads_accounts
            ):
                raise ValueError("This Threads username is already configured")
            if any(existing.profile_id == account.profile_id for existing in self.threads_accounts):
                raise ValueError("profile_id is already in use")
            self.threads_accounts.append(account)
            if not self.active_threads_account_id:
                self.active_threads_account_id = account.account_id
            return account

    def update_threads_account(self, account_id, **changes):
        with self._lock:
            for index, account in enumerate(self.threads_accounts):
                if account.account_id == str(account_id or ""):
                    updated = account.updated(**changes)
                    if any(
                        existing.account_id != account.account_id
                        and existing.expected_username == updated.expected_username
                        for existing in self.threads_accounts
                    ):
                        raise ValueError("This Threads username is already configured")
                    self.threads_accounts[index] = updated
                    return updated
            raise KeyError("Threads account was not found")

    def remove_threads_account(self, account_id):
        with self._lock:
            target = str(account_id or "")
            remaining = [account for account in self.threads_accounts if account.account_id != target]
            if len(remaining) == len(self.threads_accounts):
                raise KeyError("Threads account was not found")
            self.threads_accounts = remaining
            if self.active_threads_account_id == target:
                self.active_threads_account_id = remaining[0].account_id if remaining else ""

    def set_active_threads_account(self, account_id):
        with self._lock:
            account = self.get_threads_account(account_id)
            if account is None:
                raise KeyError("Threads account was not found")
            self.active_threads_account_id = account.account_id
            return account


config = Config()
