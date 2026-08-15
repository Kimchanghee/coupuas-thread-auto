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

GENERIC_IMPROVEMENT = "각종 오류와 안정성 문제를 개선했습니다."


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


def _subject_parts(subject: str) -> tuple[str, str, str]:
    text = str(subject or "").strip()
    match = re.match(r"^([a-zA-Z]+)(?:\(([^)]*)\))?!?:\s*(.+)$", text)
    if not match:
        return "other", "", text
    return match.group(1).lower(), (match.group(2) or "").lower(), match.group(3).strip()


def user_facing_changes(subjects: list[str]) -> list[str]:
    """Turn internal commit subjects into short, plain Korean release notes."""
    changes: list[str] = []

    def add(message: str) -> None:
        if message and message not in changes:
            changes.append(message)

    for raw in subjects:
        prefix, scope, subject = _subject_parts(raw)
        if not subject or subject.lower().startswith("merge "):
            continue
        searchable = f"{scope} {subject}".casefold()
        if "logout" in searchable:
            add("로그아웃하면 프로그램을 닫지 않고 로그인 화면으로 돌아가도록 개선했습니다.")
        elif any(word in searchable for word in ("notice", "release copy", "release title")):
            add("공지의 어려운 표현과 제목이 겹쳐 보이던 문제를 개선했습니다.")
        elif prefix == "security" or any(
            word in searchable for word in ("credential", "sensitive data", "trusted destination")
        ):
            add("로그인 정보와 이용 기록이 안전하게 처리되도록 보호를 강화했습니다.")
        elif any(word in searchable for word in ("font", "typeface", "typography")):
            add("업데이트 화면의 글자 모양을 다른 화면과 같게 맞췄습니다.")
        elif any(
            word in searchable
            for word in (
                "update",
                "updater",
                "installer",
                "install",
                "signature",
                "signing",
                "authenticode",
                "timestamp",
            )
        ):
            add("업데이트가 끝까지 완료되지 않던 문제를 개선했습니다.")
        elif prefix in {"feat", "feature"} and any(
            word in searchable for word in ("affiliate", "partner", "marketplace", "channel")
        ):
            add("이용할 수 있는 쇼핑 제휴 채널을 늘렸습니다.")
        elif any(word in searchable for word in ("readiness", "service status")):
            add("서비스 연결 상태를 더 빠르게 확인할 수 있도록 개선했습니다.")
        elif any(word in searchable for word in ("login", "signup", "register", "auth")):
            add("로그인과 회원가입 과정에서 불편했던 점을 개선했습니다.")
        elif prefix in {"fix", "bugfix", "security", "reliability", "perf"}:
            add(GENERIC_IMPROVEMENT)
        elif prefix in {"feat", "feature"} and re.search(r"[가-힣]", subject):
            add(subject if subject.endswith((".", "!", "?")) else f"{subject}.")

    add(GENERIC_IMPROVEMENT)
    return changes


def render_release_notes(version: str, subjects: list[str]) -> str:
    normalized_version = str(version or "").strip()
    changes = user_facing_changes(subjects)
    lines = [
        f"# Thread Auto {normalized_version}",
        "",
        "## 이번 버전에서 달라진 점",
        "",
        *(f"- {item}" for item in changes),
    ]
    lines.extend(
        [
            "",
            "## 설치 안내",
            "",
            "- 아래 설치 파일을 받아 실행해 주세요.",
            "- 사용하던 설정과 남은 작업은 그대로 유지됩니다.",
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
