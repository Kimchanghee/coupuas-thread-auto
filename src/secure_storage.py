"""Small helper for protecting secrets at rest."""

from __future__ import annotations

import base64
import getpass
import os
import tempfile
from pathlib import Path
from typing import Optional

from src.fs_security import secure_dir_permissions, secure_file_permissions

_DEFAULT_DPAPI_ENTROPY_PREFIX = "coupuas-thread-auto-v3"
_LEGACY_DPAPI_ENTROPY = b"coupuas-thread-auto-v2-entropy"
_FERNET_PREFIX = "fernet:"
_FERNET_KEY_FILENAME = ".secure_storage.key"


def _entropy_candidates() -> list[bytes]:
    """Return DPAPI entropy candidates (primary first, then legacy fallback)."""
    env_value = os.getenv("COUPUAS_DPAPI_ENTROPY", "").strip()
    if env_value:
        return [env_value.encode("utf-8")]

    username = str(os.getenv("USERNAME") or getpass.getuser() or "unknown").strip().lower()
    primary = f"{_DEFAULT_DPAPI_ENTROPY_PREFIX}:{username}".encode("utf-8")
    return [primary, _LEGACY_DPAPI_ENTROPY]


def _key_root_dir() -> Path:
    root = Path.home() / ".shorts_thread_maker"
    root.mkdir(parents=True, exist_ok=True)
    secure_dir_permissions(root)
    return root


def _load_or_create_fernet_key() -> Optional[bytes]:
    try:
        from cryptography.fernet import Fernet
    except Exception:
        return None

    try:
        key_path = _key_root_dir() / _FERNET_KEY_FILENAME
        if key_path.exists():
            raw = key_path.read_text(encoding="utf-8").strip().encode("ascii")
            if raw:
                # Validate format before returning.
                Fernet(raw)
                return raw

        raw = Fernet.generate_key()
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=str(key_path.parent),
            prefix="sec_key_",
            suffix=".tmp",
            delete=False,
        ) as tmp:
            tmp.write(raw.decode("ascii"))
            temp_path = Path(tmp.name)
        secure_file_permissions(temp_path)
        os.replace(temp_path, key_path)
        secure_file_permissions(key_path)
        return raw
    except Exception:
        if "temp_path" in locals():
            try:
                Path(temp_path).unlink(missing_ok=True)
            except Exception:
                pass
        return None


def _protect_with_fernet(value: str) -> Optional[str]:
    key = _load_or_create_fernet_key()
    if not key:
        return None
    try:
        from cryptography.fernet import Fernet

        token = Fernet(key).encrypt(value.encode("utf-8")).decode("ascii")
        return f"{_FERNET_PREFIX}{token}"
    except Exception:
        return None


def _unprotect_with_fernet(value: str) -> str:
    if not isinstance(value, str) or not value.startswith(_FERNET_PREFIX):
        return value

    key = _load_or_create_fernet_key()
    if not key:
        return ""

    token = value[len(_FERNET_PREFIX) :]
    try:
        from cryptography.fernet import Fernet

        return Fernet(key).decrypt(token.encode("ascii")).decode("utf-8")
    except Exception:
        return ""


def protect_secret(value: str, purpose: str = "coupuas-thread-auto") -> Optional[str]:
    """Return protected secret.

    Uses DPAPI on Windows, and Fernet fallback on non-Windows platforms.
    Returns None when no protection backend is available.
    """
    if not isinstance(value, str) or not value:
        return value
    if value.startswith("dpapi:") or value.startswith(_FERNET_PREFIX):
        return value
    if os.name == "nt":
        try:
            import ctypes

            class DATA_BLOB(ctypes.Structure):
                _fields_ = [
                    ("cbData", ctypes.c_uint32),
                    ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
                ]

            crypt32 = ctypes.windll.crypt32
            kernel32 = ctypes.windll.kernel32

            plain_bytes = value.encode("utf-8")
            entropy_bytes = _entropy_candidates()[0]
            in_buffer = ctypes.create_string_buffer(plain_bytes, len(plain_bytes))
            entropy_buffer = ctypes.create_string_buffer(entropy_bytes, len(entropy_bytes))
            in_blob = DATA_BLOB(
                len(plain_bytes),
                ctypes.cast(in_buffer, ctypes.POINTER(ctypes.c_ubyte)),
            )
            entropy_blob = DATA_BLOB(
                len(entropy_bytes),
                ctypes.cast(entropy_buffer, ctypes.POINTER(ctypes.c_ubyte)),
            )
            out_blob = DATA_BLOB()

            if not crypt32.CryptProtectData(
                ctypes.byref(in_blob),
                purpose,
                ctypes.byref(entropy_blob),
                None,
                None,
                0,
                ctypes.byref(out_blob),
            ):
                raise ctypes.WinError()

            try:
                protected = ctypes.string_at(out_blob.pbData, out_blob.cbData)
            finally:
                kernel32.LocalFree(out_blob.pbData)

            return f"dpapi:{base64.b64encode(protected).decode('ascii')}"
        except Exception:
            pass

    return _protect_with_fernet(value)


def unprotect_secret(value: str) -> str:
    """Return plain secret from DPAPI wrapper."""
    if not isinstance(value, str) or not value:
        return value

    if value.startswith(_FERNET_PREFIX):
        return _unprotect_with_fernet(value)

    if not value.startswith("dpapi:"):
        return value
    if os.name != "nt":
        return ""

    try:
        import ctypes

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [
                ("cbData", ctypes.c_uint32),
                ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
            ]

        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32

        encoded = value.split(":", 1)[1]
        protected = base64.b64decode(encoded.encode("ascii"))
        in_buffer = ctypes.create_string_buffer(protected, len(protected))
        in_blob = DATA_BLOB(
            len(protected),
            ctypes.cast(in_buffer, ctypes.POINTER(ctypes.c_ubyte)),
        )

        last_error = None
        for entropy_bytes in _entropy_candidates():
            entropy_buffer = ctypes.create_string_buffer(entropy_bytes, len(entropy_bytes))
            entropy_blob = DATA_BLOB(
                len(entropy_bytes),
                ctypes.cast(entropy_buffer, ctypes.POINTER(ctypes.c_ubyte)),
            )
            out_blob = DATA_BLOB()
            if not crypt32.CryptUnprotectData(
                ctypes.byref(in_blob),
                None,
                ctypes.byref(entropy_blob),
                None,
                None,
                0,
                ctypes.byref(out_blob),
            ):
                last_error = ctypes.get_last_error()
                continue

            try:
                return ctypes.string_at(out_blob.pbData, out_blob.cbData).decode("utf-8")
            finally:
                kernel32.LocalFree(out_blob.pbData)

        if last_error is not None:
            raise ctypes.WinError(last_error)
        raise ValueError("Failed to unprotect secret")
    except Exception:
        return ""
