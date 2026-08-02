"""Generate deterministic Korean release notes from commits since the last tag."""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path


GROUPS = (
    ("새 기능", ("feat", "feature")),
    ("오류 수정", ("fix", "bugfix")),
    ("보안 및 안정성", ("security", "reliability", "perf")),
)


def normalize_subject(subject: str) -> tuple[str, str]:
    text = str(subject or "").strip()
    match = re.match(r"^([a-zA-Z]+)(?:\([^)]*\))?!?:\s*(.+)$", text)
    if not match:
        return "other", text
    return match.group(1).lower(), match.group(2).strip()


def categorize_subjects(subjects: list[str]) -> dict[str, list[str]]:
    result = {title: [] for title, _prefixes in GROUPS}
    result["그 밖의 변경 사항"] = []
    seen = set()
    for raw in subjects:
        prefix, subject = normalize_subject(raw)
        if not subject or subject.lower().startswith("merge "):
            continue
        key = subject.casefold()
        if key in seen:
            continue
        seen.add(key)
        target = "그 밖의 변경 사항"
        for title, prefixes in GROUPS:
            if prefix in prefixes:
                target = title
                break
        result[target].append(subject)
    return result


def render_release_notes(version: str, subjects: list[str]) -> str:
    normalized_version = str(version or "").strip()
    sections = categorize_subjects(subjects)
    lines = [
        f"# Thread Auto {normalized_version}",
        "",
        "이번 버전에 포함된 주요 변경 사항입니다.",
    ]
    wrote_change = False
    for title, _prefixes in (*GROUPS, ("그 밖의 변경 사항", ())):
        items = sections[title]
        if not items:
            continue
        wrote_change = True
        lines.extend(["", f"## {title}", ""])
        lines.extend(f"- {item}" for item in items)
    if not wrote_change:
        lines.extend(["", "## 주요 변경 사항", "", "- 안정성과 배포 구성을 개선했습니다."])
    lines.extend(
        [
            "",
            "## Windows 설치",
            "",
            "- 권장 설치 파일: `CoupangThreadAutoSetup.exe`",
            "- 각 실행 파일의 SHA-256 체크섬을 함께 제공합니다.",
            "- 기존 설정과 계정별 대기열은 업데이트 후에도 유지됩니다.",
            "",
        ]
    )
    return "\n".join(lines)


def git_subjects(version: str) -> list[str]:
    tags = subprocess.run(
        ["git", "tag", "--list", "v*", "--sort=-v:refname"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.splitlines()
    previous = next((tag.strip() for tag in tags if tag.strip() and tag.strip() != version), "")
    revision = f"{previous}..HEAD" if previous else "HEAD"
    output = subprocess.run(
        ["git", "log", revision, "--format=%s"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout
    return [line.strip() for line in output.splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        render_release_notes(args.version, git_subjects(args.version)),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
