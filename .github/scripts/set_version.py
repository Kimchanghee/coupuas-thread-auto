#!/usr/bin/env python3
"""Synchronize the application version across release-time source files."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _normalize_version(value: str) -> tuple[str, str]:
    raw = str(value or "").strip()
    if raw.startswith("refs/tags/"):
        raw = raw.rsplit("/", 1)[-1]
    if not re.fullmatch(r"v?[0-9]{1,5}(?:\.[0-9]{1,5}){2}", raw):
        raise SystemExit(f"Invalid semantic version: {value!r}")
    dotted = raw[1:] if raw.startswith("v") else raw
    return f"v{dotted}", dotted


def _replace(path: str, pattern: str, replacement: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if count != 1:
        raise SystemExit(f"Could not update version in {path}")
    target.write_text(updated, encoding="utf-8")
    print(f"updated {path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("version", help="Version like v3.0.3 or 3.0.3")
    args = parser.parse_args()

    v_prefixed, dotted = _normalize_version(args.version)

    _replace("main.py", r'^\s*VERSION\s*=\s*["\'][^"\']+["\']', f'VERSION = "{v_prefixed}"')
    _replace("login_main.py", r'^\s*VERSION\s*=\s*["\'][^"\']+["\']', f'VERSION = "{v_prefixed}"')
    _replace("src/__init__.py", r'^\s*__version__\s*=\s*["\'][^"\']+["\']', f'__version__ = "{dotted}"')
    _replace("setup.py", r'^\s*version\s*=\s*["\'][^"\']+["\']', f'    version="{dotted}"')

    print(f"VERSION={v_prefixed}")


if __name__ == "__main__":
    main()
