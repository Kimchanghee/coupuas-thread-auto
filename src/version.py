"""Canonical application version.

This is the only file in the repository that stores the current application
version.  Runtime entrypoints, packaging tools, and release workflows consume
these derived constants instead of carrying independent version literals.
"""

from __future__ import annotations

import re


VERSION = "3.2.4"

if not re.fullmatch(r"[0-9]{1,5}(?:\.[0-9]{1,5}){2}", VERSION):
    raise RuntimeError("VERSION must use major.minor.patch numeric components")

VERSION_TAG = f"v{VERSION}"
MSIX_VERSION = f"{VERSION}.0"
