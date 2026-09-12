from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from PIL import Image
from pypdf import PdfReader


ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"D:\스레드 마케팅 계획")


def ffprobe(path: Path) -> dict:
    command = [
        "ffprobe", "-v", "error", "-show_entries",
        "stream=codec_type,codec_name,width,height:format=duration",
        "-of", "json", str(path),
    ]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def main() -> None:
    failures: list[str] = []
    feed = sorted(ROOT.glob("*_DAY*/P*/CAROUSEL_FEED/*.png"))
    stories = sorted(ROOT.glob("*_DAY*/P*/STORY/*.png"))
    videos = sorted(ROOT.glob("*_DAY*/P*/VIDEO/릴스_쇼츠_완성본.mp4"))
    text_files = sorted(ROOT.glob("*_DAY*/P*/TEXT/*"))
    pdfs = sorted((ROOT / "00_전체운영").glob("*.pdf"))

    expected = {"feed": 180, "story": 90, "video": 30, "text": 240, "pdf": 1}
    actual = {"feed": len(feed), "story": len(stories), "video": len(videos), "text": len(text_files), "pdf": len(pdfs)}
    for key, count in expected.items():
        if actual[key] != count:
            failures.append(f"{key}: expected {count}, found {actual[key]}")

    for path in feed:
        with Image.open(path) as image:
            if image.size != (1080, 1350):
                failures.append(f"Feed size {image.size}: {path}")
    for path in stories:
        with Image.open(path) as image:
            if image.size != (1080, 1920):
                failures.append(f"Story size {image.size}: {path}")

    video_rows = []
    for path in videos:
        info = ffprobe(path)
        streams = info.get("streams", [])
        video = next((item for item in streams if item.get("codec_type") == "video"), {})
        audio = next((item for item in streams if item.get("codec_type") == "audio"), {})
        duration = float(info.get("format", {}).get("duration", 0))
        if (video.get("width"), video.get("height")) != (1080, 1920):
            failures.append(f"Video size {video.get('width')}x{video.get('height')}: {path}")
        if video.get("codec_name") != "h264":
            failures.append(f"Video codec {video.get('codec_name')}: {path}")
        if audio.get("codec_name") != "aac":
            failures.append(f"Audio codec {audio.get('codec_name')}: {path}")
        if duration < 20:
            failures.append(f"Video too short {duration:.2f}s: {path}")
        video_rows.append((str(path.relative_to(ROOT)), duration, video.get("codec_name"), audio.get("codec_name")))

    banned = ["[URL", "URL 입력", "예시 이미지", "예시 글", "촬영 지시", "TODO", "PLACEHOLDER"]
    for path in text_files:
        text = path.read_text(encoding="utf-8-sig")
        for token in banned:
            if token.lower() in text.lower():
                failures.append(f"Banned token {token!r}: {path}")

    pdf_pages = 0
    if pdfs:
        reader = PdfReader(str(pdfs[0]))
        pdf_pages = len(reader.pages)
        if pdf_pages < 8:
            failures.append(f"PDF too short: {pdf_pages} pages")

    report = [
        "# 최종 자산 자동 검수 보고서",
        "",
        f"- 카드뉴스: {len(feed)}장 / 1080×1350",
        f"- 스토리: {len(stories)}장 / 1080×1920",
        f"- 완성 영상: {len(videos)}편 / H.264 + AAC / 20초 이상",
        f"- 채널별 게시 원고: {len(text_files)}개",
        f"- 통합 PDF: {len(pdfs)}개 / {pdf_pages}페이지",
        f"- 자동 검수 결과: {'PASS' if not failures else 'FAIL'}",
        "",
        "## 영상 길이",
        "",
        "| 파일 | 길이(초) | 영상 | 음성 |",
        "|---|---:|---|---|",
    ]
    report += [f"| {path} | {duration:.2f} | {vcodec} | {acodec} |" for path, duration, vcodec, acodec in video_rows]
    if failures:
        report += ["", "## 실패 항목", ""] + [f"- {failure}" for failure in failures]
    report_path = ROOT / "00_전체운영" / "최종_QA_보고서.md"
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8-sig")
    print(json.dumps({"counts": actual, "pdf_pages": pdf_pages, "failures": failures}, ensure_ascii=False, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
