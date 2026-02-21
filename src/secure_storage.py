"""Small helper for protecting secrets at rest."""

from __future__ import annotations

import base64
import getpass
import os
from typing import Optional

_DEFAULT_DPAPI_ENTROPY_PREFIX = "coupuas-thread-auto-v3"
_LEGACY_DPAPI_ENTROPY = b"coupuas-thread-auto-v2-entropy"


def _entropy_candidates() -> list[bytes]:
    """Return DPAPI entropy candidates (primary first, then legacy fallback)."""
    env_value = os.getenv("COUPUAS_DPAPI_ENTROPY", "").strip()
    if env_value:
        return [env_value.encode("utf-8")]

    username = str(os.getenv("USERNAME") or getpass.getuser() or "unknown").strip().lower()
    primary = f"{_DEFAULT_DPAPI_ENTROPY_PREFIX}:{username}".encode("utf-8")
    return [primary, _LEGACY_DPAPI_ENTROPY]


def protect_secret(value: str, purpose: str = "coupuas-thread-auto") -> Optional[str]:
    """Return DPAPI-protected secret on Windows. Returns None when unavailable."""
    if not isinstance(value, str) or not value:
        return value
    if value.startswith("dpapi:"):
        return value
    if os.name != "nt":
        return None

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
        return None


def unprotect_secret(value: str) -> str:
    """Return plain secret from DPAPI wrapper."""
    if not isinstance(value, str) or not value.startswith("dpapi:"):
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
