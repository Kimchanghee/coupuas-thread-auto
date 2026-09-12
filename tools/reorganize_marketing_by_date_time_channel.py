from __future__ import annotations

import csv
import os
import re
import shutil
from collections import defaultdict
from pathlib import Path


SOURCE = Path(r"D:\스레드 마케팅 계획")
STAGE = Path(r"D:\스레드 마케팅 계획_날짜시간채널_제작중")
FINAL = Path(r"D:\스레드 마케팅 계획")

CHANNEL_TEXT = {
    "Threads": "Threads.txt",
    "Instagram": "Instagram.txt",
    "TikTok": "TikTok_캡션.txt",
    "YouTube": "YouTube_제목_설명.txt",
    "Naver Blog": "Naver_Blog.md",
    "Facebook": "Facebook.txt",
    "커뮤니티": "커뮤니티.txt",
    "강의 웹": "강의_웹.md",
}

CHANNEL_FOLDER = {
    "Threads": "Threads",
    "Instagram": "Instagram",
    "TikTok": "TikTok",
    "YouTube": "YouTube_Shorts",
    "Naver Blog": "Naver_Blog",
    "Facebook": "Facebook",
    "커뮤니티": "기타_커뮤니티",
    "강의 웹": "강의_웹",
}


def safe_reset_stage() -> None:
    resolved = STAGE.resolve()
    if resolved.parent != Path("D:\\") or resolved.name != "스레드 마케팅 계획_날짜시간채널_제작중":
        raise RuntimeError(f"Unexpected staging path: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True)


def hardlink_or_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, destination)
    except OSError:
        shutil.copy2(source, destination)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8-sig")


def time_folder(value: str) -> str:
    hour, minute = value.split(":")
    return f"{hour}시{minute}분"


def find_post_folder(day: int, post: int) -> Path:
    day_matches = list(SOURCE.glob(f"*_DAY{day:02d}"))
    if len(day_matches) != 1:
        raise RuntimeError(f"Expected one DAY{day:02d} folder, found {day_matches}")
    post_matches = [path for path in day_matches[0].iterdir() if path.is_dir() and path.name.startswith(f"P{post}_")]
    if len(post_matches) != 1:
        raise RuntimeError(f"Expected one P{post} folder in {day_matches[0]}, found {post_matches}")
    return post_matches[0]


def copy_feed(source_post: Path, channel_dir: Path) -> list[str]:
    output = channel_dir / "02_업로드_이미지_01부터06까지"
    files = sorted((source_post / "CAROUSEL_FEED").glob("*.png"))
    if len(files) != 6:
        raise RuntimeError(f"Expected six feed cards: {source_post}")
    for path in files:
        hardlink_or_copy(path, output / path.name)
    return [f"02_업로드_이미지_01부터06까지/{path.name}" for path in files]


def copy_story(source_post: Path, channel_dir: Path) -> list[str]:
    output = channel_dir / "03_피드직후_스토리_01부터03까지"
    files = sorted((source_post / "STORY").glob("*.png"))
    if len(files) != 3:
        raise RuntimeError(f"Expected three story cards: {source_post}")
    for path in files:
        hardlink_or_copy(path, output / path.name)
    return [f"03_피드직후_스토리_01부터03까지/{path.name}" for path in files]


def copy_video(source_post: Path, channel_dir: Path) -> str:
    source = source_post / "VIDEO" / "릴스_쇼츠_완성본.mp4"
    if not source.exists():
        raise FileNotFoundError(source)
    destination = channel_dir / "02_바로_업로드_영상.mp4"
    hardlink_or_copy(source, destination)
    return destination.name


def build_channel_folder(row: dict[str, str]) -> Path:
    date_value = row["날짜"]
    day = int(row["DAY"])
    post = int(row["POST"])
    channel = row["채널"]
    when = row["업로드시간_KST"]
    source_post = find_post_folder(day, post)
    channel_dir = STAGE / date_value / time_folder(when) / CHANNEL_FOLDER[channel]
    channel_dir.mkdir(parents=True, exist_ok=True)

    source_text = source_post / "TEXT" / CHANNEL_TEXT[channel]
    if not source_text.exists():
        raise FileNotFoundError(source_text)
    target_text = channel_dir / ("01_복사해서_게시할_글.md" if source_text.suffix == ".md" else "01_복사해서_게시할_글.txt")
    hardlink_or_copy(source_text, target_text)

    actions: list[str] = []
    media: list[str] = []
    if channel in {"Threads", "Naver Blog", "커뮤니티", "강의 웹"}:
        media = copy_feed(source_post, channel_dir)
        actions = [
            f"`{target_text.name}` 전체 복사",
            "이미지 폴더에서 01부터 06까지 순서대로 모두 선택",
            "본문을 붙여넣고 게시",
        ]
    elif channel == "Instagram":
        media = copy_feed(source_post, channel_dir)
        story_files = copy_story(source_post, channel_dir)
        media += story_files
        actions = [
            f"`{target_text.name}` 전체 복사",
            "피드 이미지 01부터 06까지 순서대로 선택해 캐러셀 게시",
            "피드 게시 직후 스토리 이미지 01부터 03까지 순서대로 게시",
        ]
    else:
        media = [copy_video(source_post, channel_dir)]
        actions = [
            f"`{target_text.name}` 전체 복사",
            "`02_바로_업로드_영상.mp4` 선택",
            "본문·제목을 붙여넣고 게시",
        ]

    guide = [
        "# 지금 바로 업로드",
        "",
        f"- 날짜: {date_value}",
        f"- 시간: {when} KST",
        f"- 채널: {channel}",
        f"- 콘텐츠: {row['훅']}",
        f"- 댓글 키워드: {row['댓글키워드']}",
        "",
        "## 이 순서 그대로",
        "",
    ]
    guide += [f"{index}. {action}" for index, action in enumerate(actions, 1)]
    guide += ["", "## 이 폴더에서 사용할 파일", ""]
    guide += [f"- {target_text.name}"] + [f"- {item}" for item in media]
    guide += [
        "",
        "## 게시 직전 10초 확인",
        "",
        "- [ ] 올리는 계정이 맞다",
        "- [ ] 이미지 순서 또는 영상이 맞다",
        "- [ ] 제휴 링크를 쓰는 경우 해당 플랫폼 고지·활동 채널 요건을 확인했다",
        "- [ ] 댓글 키워드가 본문과 일치한다",
    ]
    write_text(channel_dir / "00_지금_바로_업로드.md", "\n".join(guide))
    return channel_dir


def build_date_guides(rows: list[dict[str, str]]) -> None:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["날짜"]].append(row)
    for date_value, date_rows in grouped.items():
        date_rows.sort(key=lambda row: (row["업로드시간_KST"], row["채널"]))
        lines = [
            f"# {date_value} 오늘 업로드 순서",
            "",
            "아래 순서대로 시간 폴더를 열고, 그 안의 SNS 채널 폴더에서 `00_지금_바로_업로드.md`를 실행합니다.",
            "",
            "| 순번 | 시간 | 채널 | 콘텐츠 | 폴더 | 완료 |",
            "|---:|---:|---|---|---|---|",
        ]
        for index, row in enumerate(date_rows, 1):
            folder = f"{time_folder(row['업로드시간_KST'])}/{CHANNEL_FOLDER[row['채널']]}"
            lines.append(
                f"| {index} | {row['업로드시간_KST']} | {row['채널']} | {row['훅']} | `{folder}` | [ ] |"
            )
        write_text(STAGE / date_value / "00_오늘_시간순_업로드.md", "\n".join(lines))


def copy_operations() -> None:
    source = SOURCE / "00_전체운영"
    destination = STAGE / "00_전체운영"
    shutil.copytree(source, destination)
    write_text(
        STAGE / "00_README_폴더순서.md",
        """# 폴더 사용 순서

이 폴더는 요청하신 순서로 정리되어 있습니다.

`날짜 → 업로드 시간 → SNS 채널 → 지금 올릴 글·이미지·영상`

예시:

`2026-08-12/08시10분/Threads/`

사용법:

1. 오늘 날짜 폴더를 엽니다.
2. `00_오늘_시간순_업로드.md`를 엽니다.
3. 현재 시간 폴더를 엽니다.
4. SNS 채널 폴더의 `00_지금_바로_업로드.md`만 따라갑니다.

P1·P2·P3 제작 폴더를 찾을 필요가 없습니다. 해당 시간과 채널에 필요한 파일만 들어 있습니다.
""",
    )


def build_manifest(rows: list[dict[str, str]]) -> None:
    path = STAGE / "00_전체운영" / "날짜_시간_SNS채널_폴더_인덱스.csv"
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        writer.writerow(["날짜", "시간_KST", "SNS채널", "콘텐츠", "바로업로드폴더"])
        for row in sorted(rows, key=lambda item: (item["날짜"], item["업로드시간_KST"], item["채널"])):
            folder = FINAL / row["날짜"] / time_folder(row["업로드시간_KST"]) / CHANNEL_FOLDER[row["채널"]]
            writer.writerow([row["날짜"], row["업로드시간_KST"], row["채널"], row["훅"], str(folder)])


def main() -> None:
    schedule = SOURCE / "00_전체운영" / "전체_업로드_스케줄.csv"
    if not schedule.exists():
        raise FileNotFoundError(schedule)
    with schedule.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 240:
        raise RuntimeError(f"Expected 240 scheduled channel uploads, found {len(rows)}")
    safe_reset_stage()
    copy_operations()
    for index, row in enumerate(rows, 1):
        build_channel_folder(row)
        if index % 24 == 0:
            print(f"{index}/240", flush=True)
    build_date_guides(rows)
    build_manifest(rows)
    print(STAGE)


if __name__ == "__main__":
    main()
