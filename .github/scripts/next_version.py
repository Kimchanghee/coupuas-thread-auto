#!/usr/bin/env python3
"""Resolve the release version for GitHub Actions.

Priority:
1. explicit workflow_dispatch input
2. pushed tag
3. latest semver tag + requested bump
"""

from __future__ import annotations

import argparse
import re
import subprocess


SEMVER_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def _run_git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def _normalize(value: str) -> str:
    raw = str(value or "").strip()
    if raw.startswith("refs/tags/"):
        raw = raw.rsplit("/", 1)[-1]
    match = SEMVER_RE.fullmatch(raw)
    if not match:
        raise SystemExit(f"Invalid semantic version: {value!r}")
    return f"v{match.group(1)}.{match.group(2)}.{match.group(3)}"


def _latest_tag() -> str:
    tags = _run_git("tag", "--list", "v*.*.*", "--sort=-v:refname").splitlines()
    for tag in tags:
        if SEMVER_RE.fullmatch(tag.strip()):
            return _normalize(tag)
    return "v0.0.0"


def _bump(version: str, bump: str) -> str:
    match = SEMVER_RE.fullmatch(version)
    if not match:
        raise SystemExit(f"Invalid latest version: {version!r}")
    major, minor, patch = (int(match.group(i)) for i in range(1, 4))
    if bump == "major":
        major, minor, patch = major + 1, 0, 0
    elif bump == "minor":
        minor, patch = minor + 1, 0
    else:
        patch += 1
    return f"v{major}.{minor}.{patch}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--explicit", default="")
    parser.add_argument("--ref", default="")
    parser.add_argument("--bump", choices=("patch", "minor", "major"), default="patch")
    args = parser.parse_args()

    if args.explicit.strip():
        version = _normalize(args.explicit)
    elif args.ref.startswith("refs/tags/"):
        version = _normalize(args.ref)
    else:
        version = _bump(_latest_tag(), args.bump)

    print(version)


if __name__ == "__main__":
    main()
