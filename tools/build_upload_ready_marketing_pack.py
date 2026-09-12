from __future__ import annotations

import csv
import math
import os
import re
import shutil
import subprocess
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image as RLImage,
    LongTable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from upload_ready_marketing_data import (
    CAMPAIGN_START,
    LIVE_DATE,
    LIVE_TIME,
    OFFER,
    PLATFORMS,
    POSTS,
    PRICE,
)


ROOT = Path(__file__).resolve().parents[1]
BUILD_ROOT = Path(r"D:\스레드 마케팅 계획_v3_제작중")
PHOTO_ROOT = ROOT / "output" / "upload-ready-v3" / "photos"
PDF_OUTPUT_ROOT = ROOT / "output" / "pdf"

FONT_XB = ROOT / "fonts" / "Pretendard-ExtraBold.ttf"
FONT_SB = ROOT / "fonts" / "Pretendard-SemiBold.ttf"

TTS_SCRIPT = ROOT / "tools" / "synthesize_korean_voice.ps1"
APP_DEMO = ROOT / "output" / "organic-launch-pack" / "sources" / "app-demo.mp4"
SCREENSHOTS = [
    ROOT / "output" / "organic-launch-pack" / "sources" / "app-proof.png",
    ROOT / "output" / "ui-verify" / "run-state-v3.0.48.png",
    ROOT / "output" / "verified-v3.0.65" / "packaged-main.png",
    ROOT / "output" / "verified-v3.0.65" / "packaged-settings-final.png",
    ROOT / "output" / "verified-v3.0.66" / "packaged-login-v3.0.66.png",
]

FEED_SIZE = (1080, 1350)
STORY_SIZE = (1080, 1920)
FEED_SAFE = (84, 82, 996, 1268)
STORY_SAFE = (84, 230, 996, 1640)

INK = "#10131A"
NAVY = "#171B2B"
ROSE = "#F04464"
YELLOW = "#FFD43B"
MINT = "#A9F3D0"
LILAC = "#C9BCFF"
CREAM = "#FFF8EE"
WHITE = "#FFFFFF"
GRAY = "#B7BBC7"
SOFT_GRAY = "#EEF0F5"
GREEN = "#1F8F68"

CHANNELS = [
    "Threads",
    "Instagram",
    "TikTok",
    "YouTube",
    "Naver Blog",
    "Facebook",
    "커뮤니티",
    "강의 웹",
]

CHANNEL_FILES = {
    "Threads": "Threads.txt",
    "Instagram": "Instagram.txt",
    "TikTok": "TikTok_캡션.txt",
    "YouTube": "YouTube_제목_설명.txt",
    "Naver Blog": "Naver_Blog.md",
    "Facebook": "Facebook.txt",
    "커뮤니티": "커뮤니티.txt",
    "강의 웹": "강의_웹.md",
}

CHANNEL_TIMES = {
    "Threads": ["08:10", "13:10", "20:40"],
    "Instagram": ["08:40", "14:10", "21:10"],
    "TikTok": ["09:30", "15:20", "21:50"],
    "YouTube": ["09:10", "15:00", "21:30"],
    "Naver Blog": ["10:00", "16:00", "19:30"],
    "Facebook": ["10:20", "16:20", "20:00"],
    "커뮤니티": ["11:30", "17:30", "22:00"],
    "강의 웹": ["12:00", "18:00", "22:20"],
}

LIVE_DAY_POST3_TIMES = {
    "Threads": "18:40",
    "Instagram": "18:50",
    "TikTok": "19:00",
    "YouTube": "19:10",
    "Naver Blog": "18:30",
    "Facebook": "18:45",
    "커뮤니티": "19:20",
    "강의 웹": "19:30",
}

DISCLOSURE = "※ 프로그램 판매 목적의 홍보 콘텐츠입니다. 수익·조회·구매 전환을 보장하지 않습니다."
TIME_NOTE = "※ 계산 조건: 수작업 1건 30분, 자동화 후 사람 검수 1건 7분, 하루 3건, 연 365일. 실제 절감 시간은 작업 방식과 검수 범위에 따라 달라집니다."
BREAK_EVEN_NOTE = "※ 계산 조건: 시간 차이 69분/일, 시급 15,000원 가정. 하루 17,250원 × 약 41일 ≈ 70만원입니다. 수익 회수가 아닌 시간가치 비교입니다."
HASHTAGS = "#쇼핑제휴 #제휴마케팅 #콘텐츠자동화 #업무자동화 #스레드마케팅 #온라인부업 #THREADAUTO"


def ensure_sources() -> None:
    if len(POSTS) != 30:
        raise RuntimeError(f"Expected 30 posts, found {len(POSTS)}")
    counts = Counter(p["day"] for p in POSTS)
    if counts != Counter({day: 3 for day in range(1, 11)}):
        raise RuntimeError(f"Every day must have three posts: {counts}")
    required = [FONT_XB, FONT_SB, TTS_SCRIPT, APP_DEMO, *SCREENSHOTS]
    required += [PHOTO_ROOT / f"P{i:02d}.png" for i in range(1, 31)]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing build sources:\n" + "\n".join(missing))


def reset_build_root() -> None:
    resolved = BUILD_ROOT.resolve()
    if resolved.name != "스레드 마케팅 계획_v3_제작중" or resolved.parent != Path("D:\\"):
        raise RuntimeError(f"Refusing to reset unexpected directory: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8-sig")


def safe_name(text: str, limit: int = 34) -> str:
    value = re.sub(r'[<>:"/\\|?*\r\n]+', "_", text)
    value = re.sub(r"\s+", "_", value).strip("_")
    return value[:limit]


def campaign_date(day_no: int) -> date:
    return date.fromisoformat(CAMPAIGN_START) + timedelta(days=day_no - 1)


def post_code(post: dict) -> str:
    return f"D{post['day']:02d}_P{post['post']}"


def upload_time(post: dict, channel: str) -> str:
    if post["day"] == 10 and post["post"] == 3:
        return LIVE_DAY_POST3_TIMES[channel]
    return CHANNEL_TIMES[channel][post["post"] - 1]


def is_time_post(post: dict) -> bool:
    return "420" in post["hook"] or "시간" in post["hook"] or "41일" in post["hook"]


def calculation_note(post: dict) -> str:
    if "41일" in post["hook"]:
        return BREAK_EVEN_NOTE
    if "420" in post["hook"] or "시간" in post["hook"]:
        return TIME_NOTE
    return ""


def platform_sentence() -> str:
    return " · ".join(PLATFORMS)


def channel_copy(post: dict, channel: str) -> str:
    hook = post["hook"].replace("\n", " ")
    problems = "\n".join(f"- {item}" for item in post["problem_points"])
    proof = "\n".join(f"- {item}" for item in post["proof_points"])
    takeaway = "\n".join(f"- {item}" for item in post["takeaway_points"])
    calc = calculation_note(post)
    support_line = ""
    if post["day"] == 3 or "7개" in hook or "플랫폼" in hook:
        support_line = f"\n\n현재 지원 범위: {platform_sentence()}"

    if channel == "Threads":
        body = (
            f"{hook}\n\n{post['intro']}\n\n{post['proof_title']}\n{proof}"
            f"{support_line}\n\n{post['cta']}"
        )
    elif channel == "Instagram":
        body = (
            f"{hook}\n\n{post['intro']}\n\n"
            f"오늘 카드에서 확인할 것\n{proof}{support_line}\n\n"
            f"{post['cta']}\n\n{HASHTAGS}"
        )
    elif channel == "TikTok":
        body = (
            f"{hook}\n\n실제 프로그램 흐름까지 영상에 넣었습니다. "
            f"{post['takeaway_title']}\n\n{post['cta']}\n\n"
            "#제휴마케팅 #콘텐츠자동화 #업무자동화 #쇼핑제휴"
        )
    elif channel == "YouTube":
        body = (
            f"제목: {hook} | 쇼핑 제휴 콘텐츠 자동화\n\n"
            f"설명:\n{post['intro']}\n\n{post['proof_title']}\n{proof}"
            f"{support_line}\n\n{post['cta']}\n\n"
            "#쇼핑제휴 #제휴마케팅 #콘텐츠자동화 #THREADAUTO"
        )
    elif channel == "Naver Blog":
        body = (
            f"# {hook}\n\n{post['intro']}\n\n"
            f"## {post['problem_title']}\n{problems}\n\n"
            f"## {post['proof_title']}\n{proof}\n\n"
            f"## {post['takeaway_title']}\n{takeaway}{support_line}\n\n"
            f"{post['cta']}"
        )
    elif channel == "Facebook":
        body = (
            f"{hook}\n\n{post['intro']}\n\n{post['problem_title']}\n{problems}\n\n"
            f"{post['proof_title']}\n{proof}{support_line}\n\n{post['cta']}"
        )
    elif channel == "커뮤니티":
        body = (
            f"제목: {hook}\n\n"
            f"저도 같은 구간에서 계속 시간을 쓰다가 작업 순서를 바꿨습니다. {post['intro']}\n\n"
            f"제가 실제로 확인한 흐름은 이렇습니다.\n{proof}{support_line}\n\n"
            f"광고 문구보다 실제 사용 흐름이 궁금한 분만 {post['cta']}"
        )
    else:
        body = (
            f"# {hook}\n\n{post['intro']}\n\n"
            f"## 실제 제공 방식\n- {OFFER}\n- 판매가: {PRICE}\n"
            f"- 현재 지원 범위: {platform_sentence()}\n\n"
            f"## 이번 콘텐츠의 핵심\n{proof}\n\n{post['cta']}"
        )

    notes = [body, calc, DISCLOSURE]
    return "\n\n".join(item for item in notes if item)


def build_channel_texts(post: dict, text_dir: Path) -> None:
    for channel in CHANNELS:
        write_text(text_dir / CHANNEL_FILES[channel], channel_copy(post, channel))


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_XB if bold else FONT_SB), size)


def wrap_text(draw: ImageDraw.ImageDraw, text: str, face: ImageFont.FreeTypeFont, width: int) -> str:
    wrapped: list[str] = []
    for paragraph in text.split("\n"):
        if paragraph == "":
            wrapped.append("")
            continue
        current = ""
        for char in paragraph:
            trial = current + char
            if current and draw.textbbox((0, 0), trial, font=face)[2] > width:
                wrapped.append(current.rstrip())
                current = char.lstrip()
            else:
                current = trial
        if current:
            wrapped.append(current.rstrip())
    return "\n".join(wrapped)


def fit_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    box: tuple[int, int, int, int],
    max_size: int,
    min_size: int,
    fill: str,
    *,
    bold: bool = False,
    align: str = "left",
    spacing_ratio: float = 0.24,
    anchor: str | None = None,
) -> tuple[int, str, tuple[int, int, int, int]]:
    x1, y1, x2, y2 = box
    width = x2 - x1
    height = y2 - y1
    for size in range(max_size, min_size - 1, -1):
        face = load_font(size, bold)
        wrapped = wrap_text(draw, text, face, width)
        spacing = max(4, int(size * spacing_ratio))
        bbox = draw.multiline_textbbox((0, 0), wrapped, font=face, spacing=spacing, align=align)
        rendered_w = bbox[2] - bbox[0]
        rendered_h = bbox[3] - bbox[1]
        if rendered_w <= width and rendered_h <= height:
            if anchor == "center":
                px = x1 + width // 2
                py = y1 + (height - rendered_h) // 2
                draw.multiline_text(
                    (px, py), wrapped, font=face, fill=fill, spacing=spacing,
                    align="center", anchor="ma",
                )
                placed = (x1, py, x2, py + rendered_h)
            else:
                px = x1
                py = y1 + (height - rendered_h) // 2 if anchor == "middle-left" else y1
                draw.multiline_text(
                    (px, py), wrapped, font=face, fill=fill, spacing=spacing, align=align,
                )
                placed = (px, py, px + rendered_w, py + rendered_h)
            if not (x1 <= placed[0] and y1 <= placed[1] and placed[2] <= x2 and placed[3] <= y2 + 2):
                raise ValueError(f"Placed text escaped box: {text!r}, {placed}, {box}")
            return size, wrapped, placed
    raise ValueError(f"Text does not fit at {min_size}px: {text!r} in {box}")


def photo_fill(path: Path, size: tuple[int, int], brightness: float = 0.88) -> Image.Image:
    photo = Image.open(path).convert("RGB")
    photo = ImageOps.fit(photo, size, Image.Resampling.LANCZOS)
    return ImageEnhance.Brightness(photo).enhance(brightness).convert("RGBA")


def vertical_gradient(size: tuple[int, int], top_alpha: int, bottom_alpha: int) -> Image.Image:
    width, height = size
    layer = Image.new("RGBA", (1, height))
    px = layer.load()
    for y in range(height):
        ratio = y / max(1, height - 1)
        alpha = round(top_alpha + (bottom_alpha - top_alpha) * ratio)
        px[0, y] = (9, 12, 20, alpha)
    return layer.resize((width, height))


def paste_rounded(canvas: Image.Image, image: Image.Image, box: tuple[int, int, int, int], radius: int = 28) -> None:
    x1, y1, x2, y2 = box
    fitted = ImageOps.fit(image.convert("RGB"), (x2 - x1, y2 - y1), Image.Resampling.LANCZOS)
    mask = Image.new("L", fitted.size, 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle((0, 0, fitted.width, fitted.height), radius=radius, fill=255)
    canvas.paste(fitted, (x1, y1), mask)


def brand_tag(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, *, fill: str = YELLOW) -> None:
    x, y = xy
    face = load_font(25, True)
    width = draw.textbbox((0, 0), text, font=face)[2] + 42
    draw.rounded_rectangle((x, y, x + width, y + 54), radius=24, fill=fill)
    text_fill = WHITE if fill.upper() == INK.upper() else INK
    draw.text((x + 21, y + 13), text, font=face, fill=text_fill)


def footer(draw: ImageDraw.ImageDraw, width: int, y: int, dark: bool = False) -> None:
    color = GRAY if dark else "#656A78"
    draw.line((84, y, width - 84, y), fill=color, width=2)
    draw.text((84, y + 17), "THREAD AUTO  ·  쇼핑 제휴 7개 플랫폼 지원", font=load_font(22, True), fill=color)


def photo_source(index: int) -> Path:
    return PHOTO_ROOT / f"P{index:02d}.png"


def screen_source(index: int) -> Path:
    return SCREENSHOTS[(index - 1) % len(SCREENSHOTS)]


def render_cover(post: dict, index: int, out: Path, size: tuple[int, int]) -> None:
    canvas = photo_fill(photo_source(index), size, 0.82)
    canvas = Image.alpha_composite(canvas, vertical_gradient(size, 110, 205))
    draw = ImageDraw.Draw(canvas)
    story = size == STORY_SIZE
    safe = STORY_SAFE if story else FEED_SAFE
    top = safe[1]
    brand_tag(draw, (84, top), f"{post_code(post)} · {campaign_date(post['day']).strftime('%m/%d')}")
    draw.text((84, top + 76), "실사 상황 연출", font=load_font(22, True), fill=WHITE)
    headline_box = (84, top + 145, 996, top + (720 if story else 570))
    fit_text(draw, post["hook"], headline_box, 86 if story else 78, 48, WHITE, bold=True)
    sub_y = top + (790 if story else 700)
    draw.rounded_rectangle((84, sub_y, 996, sub_y + 150), radius=32, fill=(240, 68, 100, 235))
    fit_text(
        draw, post["intro"], (116, sub_y + 26, 964, sub_y + 124),
        31 if story else 28, 22, WHITE, bold=True, anchor="middle-left",
    )
    button_y = safe[3] - 110
    draw.rounded_rectangle((84, button_y, 996, button_y + 82), radius=34, fill=YELLOW)
    fit_text(draw, "밀어서 실제 화면 확인 →", (112, button_y + 12, 968, button_y + 70), 31, 24, INK, bold=True, anchor="center")
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(out, quality=95)


def render_problem(post: dict, index: int, out: Path, size: tuple[int, int]) -> None:
    canvas = Image.new("RGBA", size, CREAM)
    draw = ImageDraw.Draw(canvas)
    story = size == STORY_SIZE
    safe = STORY_SAFE if story else FEED_SAFE
    photo_h = 350 if story else 280
    photo = photo_fill(photo_source(index), (size[0], photo_h), 0.92)
    canvas.alpha_composite(photo, (0, 0 if not story else safe[1] - 80))
    overlay_y = 0 if not story else safe[1] - 80
    canvas.alpha_composite(vertical_gradient((size[0], photo_h), 30, 140), (0, overlay_y))
    brand_tag(draw, (84, safe[1]), "02 · PROBLEM", fill=MINT)
    title_y = safe[1] + (190 if story else 255)
    fit_text(draw, post["problem_title"], (84, title_y, 996, title_y + 190), 58, 36, INK, bold=True)
    card_top = title_y + 230
    card_h = 150 if story else 125
    gap = 28
    for number, point in enumerate(post["problem_points"], 1):
        y = card_top + (number - 1) * (card_h + gap)
        draw.rounded_rectangle((84, y, 996, y + card_h), radius=28, fill=WHITE, outline="#E5E1DA", width=3)
        draw.ellipse((112, y + 35, 174, y + 97), fill=ROSE)
        fit_text(draw, str(number), (112, y + 35, 174, y + 97), 28, 22, WHITE, bold=True, anchor="center")
        fit_text(draw, point, (204, y + 22, 958, y + card_h - 20), 38 if story else 34, 24, INK, bold=True, anchor="middle-left")
    footer(draw, size[0], safe[3] - 70)
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(out, quality=95)


def render_real_screen(post: dict, index: int, out: Path, size: tuple[int, int]) -> None:
    canvas = Image.new("RGBA", size, NAVY)
    draw = ImageDraw.Draw(canvas)
    story = size == STORY_SIZE
    safe = STORY_SAFE if story else FEED_SAFE
    brand_tag(draw, (84, safe[1]), "03 · REAL SCREEN", fill=YELLOW)
    fit_text(draw, post["proof_title"], (84, safe[1] + 82, 996, safe[1] + 230), 51 if story else 45, 32, WHITE, bold=True)
    screen_top = safe[1] + (260 if story else 245)
    screen_bottom = screen_top + (590 if story else 455)
    screen = Image.open(screen_source(index)).convert("RGB")
    contained = ImageOps.contain(screen, (856, screen_bottom - screen_top - 44), Image.Resampling.LANCZOS)
    x = (1080 - contained.width) // 2
    y = screen_top + (screen_bottom - screen_top - contained.height) // 2
    shadow = Image.new("RGBA", size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle((82, screen_top, 998, screen_bottom), radius=30, fill=(0, 0, 0, 150))
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    canvas = Image.alpha_composite(canvas, shadow)
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((72, screen_top - 10, 1008, screen_bottom + 10), radius=30, fill="#F5F5F2")
    canvas.paste(contained, (x, y))
    draw = ImageDraw.Draw(canvas)
    draw.text((84, screen_bottom + 24), "실제 프로그램 화면", font=load_font(23, True), fill=MINT)
    bullet_top = screen_bottom + 76
    bullet_h = 75 if story else 62
    for pos, point in enumerate(post["proof_points"][:4]):
        yb = bullet_top + pos * (bullet_h + 14)
        draw.rounded_rectangle((84, yb, 996, yb + bullet_h), radius=22, fill="#242A3D")
        draw.ellipse((112, yb + 21, 143, yb + 52), fill=MINT)
        fit_text(draw, point, (166, yb + 8, 958, yb + bullet_h - 6), 30 if story else 27, 20, WHITE, bold=True, anchor="middle-left")
    footer(draw, size[0], safe[3] - 70, dark=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(out, quality=95)


def render_before_after(post: dict, out: Path) -> None:
    canvas = Image.new("RGBA", FEED_SIZE, CREAM)
    draw = ImageDraw.Draw(canvas)
    brand_tag(draw, (84, 82), "04 · BEFORE / AFTER", fill=LILAC)
    fit_text(draw, "바뀌는 건 작업 순서입니다", (84, 160, 996, 285), 54, 38, INK, bold=True)
    left = (84, 330, 520, 1120)
    right = (560, 330, 996, 1120)
    draw.rounded_rectangle(left, radius=34, fill="#242735")
    draw.rounded_rectangle(right, radius=34, fill="#E4FFF3")
    fit_text(draw, "BEFORE", (118, 370, 486, 450), 36, 28, WHITE, bold=True, anchor="center")
    fit_text(draw, "AFTER", (594, 370, 962, 450), 36, 28, GREEN, bold=True, anchor="center")
    for items, box, color, mark in (
        (post["before"], left, WHITE, "×"),
        (post["after"], right, INK, "✓"),
    ):
        x1, _, x2, _ = box
        for idx, item in enumerate(items[:4]):
            y = 500 + idx * 135
            draw.text((x1 + 34, y), mark, font=load_font(34, True), fill=ROSE if mark == "×" else GREEN)
            fit_text(draw, item, (x1 + 88, y - 2, x2 - 28, y + 75), 31, 23, color, bold=True, anchor="middle-left")
    fit_text(draw, "자동화가 판단을 대신하는 것이 아니라 반복 단계를 줄입니다.", (84, 1150, 996, 1235), 30, 23, INK, bold=True, anchor="center")
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(out, quality=95)


def render_takeaway(post: dict, out: Path, size: tuple[int, int]) -> None:
    canvas = Image.new("RGBA", size, YELLOW)
    draw = ImageDraw.Draw(canvas)
    story = size == STORY_SIZE
    safe = STORY_SAFE if story else FEED_SAFE
    brand_tag(draw, (84, safe[1]), "05 · CHECK", fill=INK)
    fit_text(draw, post["takeaway_title"], (84, safe[1] + 105, 996, safe[1] + (370 if story else 330)), 66 if story else 58, 38, INK, bold=True)
    top = safe[1] + (430 if story else 390)
    card_h = 155 if story else 145
    for idx, item in enumerate(post["takeaway_points"][:3], 1):
        y = top + (idx - 1) * (card_h + 34)
        draw.rounded_rectangle((84, y, 996, y + card_h), radius=34, fill=WHITE)
        draw.rounded_rectangle((112, y + 37, 182, y + 107), radius=18, fill=INK)
        fit_text(draw, str(idx), (112, y + 37, 182, y + 107), 29, 22, WHITE, bold=True, anchor="center")
        fit_text(draw, item, (216, y + 24, 954, y + card_h - 20), 36 if story else 32, 23, INK, bold=True, anchor="middle-left")
    note = calculation_note(post)
    if note:
        fit_text(draw, note.replace("※ ", ""), (84, safe[3] - 185, 996, safe[3] - 75), 23, 18, INK, bold=False)
    else:
        fit_text(draw, "기능보다 먼저 확인할 것은 내 작업에서 실제로 줄어드는 단계입니다.", (84, safe[3] - 160, 996, safe[3] - 76), 29, 22, INK, bold=True, anchor="center")
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(out, quality=95)


def render_cta(post: dict, index: int, out: Path, size: tuple[int, int]) -> None:
    canvas = photo_fill(photo_source(index), size, 0.58)
    canvas = Image.alpha_composite(canvas, vertical_gradient(size, 170, 225))
    draw = ImageDraw.Draw(canvas)
    story = size == STORY_SIZE
    safe = STORY_SAFE if story else FEED_SAFE
    brand_tag(draw, (84, safe[1]), "06 · NEXT ACTION", fill=ROSE)
    if post["day"] >= 5:
        fit_text(draw, PRICE, (84, safe[1] + 105, 996, safe[1] + 245), 82, 52, YELLOW, bold=True)
        fit_text(draw, OFFER, (84, safe[1] + 255, 996, safe[1] + 420), 39, 27, WHITE, bold=True)
        cta_top = safe[1] + (525 if story else 500)
    else:
        fit_text(draw, "보고 끝내지 말고\n다음 행동 하나만", (84, safe[1] + 135, 996, safe[1] + 440), 72 if story else 65, 45, WHITE, bold=True)
        cta_top = safe[1] + (520 if story else 500)
    draw.rounded_rectangle((84, cta_top, 996, cta_top + (350 if story else 310)), radius=42, fill=(255, 248, 238, 242))
    fit_text(draw, post["cta"], (124, cta_top + 46, 956, cta_top + (294 if story else 262)), 50 if story else 43, 30, INK, bold=True, anchor="center")
    badge_y = safe[3] - 190
    draw.rounded_rectangle((84, badge_y, 996, badge_y + 94), radius=36, fill=YELLOW)
    fit_text(draw, f"댓글 키워드  ·  {post['keyword']}", (112, badge_y + 15, 968, badge_y + 78), 35, 26, INK, bold=True, anchor="center")
    footer(draw, size[0], safe[3] - 65, dark=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(out, quality=95)


def build_carousel_and_story(post: dict, index: int, post_dir: Path) -> dict[str, list[Path] | Path]:
    carousel = post_dir / "CAROUSEL_FEED"
    story = post_dir / "STORY"
    video_frames = post_dir / "VIDEO" / "프레임"
    carousel.mkdir(parents=True, exist_ok=True)
    story.mkdir(parents=True, exist_ok=True)
    video_frames.mkdir(parents=True, exist_ok=True)

    feed_paths = [
        carousel / "01_훅_커버.png",
        carousel / "02_문제.png",
        carousel / "03_실제_프로그램_화면.png",
        carousel / "04_전후_비교.png",
        carousel / "05_적용_포인트.png",
        carousel / "06_CTA.png",
    ]
    render_cover(post, index, feed_paths[0], FEED_SIZE)
    render_problem(post, index, feed_paths[1], FEED_SIZE)
    render_real_screen(post, index, feed_paths[2], FEED_SIZE)
    render_before_after(post, feed_paths[3])
    render_takeaway(post, feed_paths[4], FEED_SIZE)
    render_cta(post, index, feed_paths[5], FEED_SIZE)

    story_paths = [
        story / "01_스토리_훅.png",
        story / "02_스토리_실제화면.png",
        story / "03_스토리_CTA.png",
    ]
    render_cover(post, index, story_paths[0], STORY_SIZE)
    render_real_screen(post, index, story_paths[1], STORY_SIZE)
    render_cta(post, index, story_paths[2], STORY_SIZE)

    problem_vertical = video_frames / "02_문제.png"
    takeaway_vertical = video_frames / "04_적용.png"
    render_problem(post, index, problem_vertical, STORY_SIZE)
    render_takeaway(post, takeaway_vertical, STORY_SIZE)

    return {
        "feed": feed_paths,
        "story": story_paths,
        "video_problem": problem_vertical,
        "video_takeaway": takeaway_vertical,
    }


def narration_text(post: dict) -> str:
    hook = post["hook"].replace("\n", ". ")
    proof = ", ".join(post["proof_points"][:3])
    takeaway = ", ".join(post["takeaway_points"][:2])
    return (
        f"{hook}. {post['proof_title']}. {proof}. "
        f"{post['takeaway_title']}. {takeaway}. {post['cta']}"
    )


def run_quiet(command: list[str], *, cwd: Path | None = None) -> None:
    result = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {' '.join(command)}\n"
            f"STDOUT:\n{result.stdout[-3000:]}\nSTDERR:\n{result.stderr[-3000:]}"
        )


def ffprobe_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def make_demo_overlay(post: dict, out: Path) -> None:
    canvas = Image.new("RGBA", STORY_SIZE, (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((84, 246, 996, 392), radius=32, fill=(16, 19, 26, 230))
    fit_text(draw, post["proof_title"], (120, 274, 960, 364), 39, 28, WHITE, bold=True, anchor="center")
    draw.rounded_rectangle((84, 1470, 996, 1630), radius=32, fill=(255, 212, 59, 238))
    fit_text(draw, "실제 프로그램 작동 화면 · 편집 재현 아님", (116, 1502, 964, 1598), 31, 23, INK, bold=True, anchor="center")
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out)


def make_still_segment(frame: Path, duration: float, out: Path) -> None:
    fade_out = max(0.25, duration - 0.28)
    filters = (
        "scale=1152:2048," 
        "crop=1080:1920:(in_w-1080)/2:(in_h-1920)/2," 
        f"fade=t=in:st=0:d=0.25,fade=t=out:st={fade_out:.3f}:d=0.25," 
        "format=yuv420p"
    )
    run_quiet([
        "ffmpeg", "-y", "-loop", "1", "-t", f"{duration:.3f}", "-i", str(frame),
        "-vf", filters, "-r", "30", "-an", "-c:v", "libx264", "-preset", "ultrafast",
        "-crf", "23", "-pix_fmt", "yuv420p", str(out),
    ])


def make_demo_segment(post: dict, duration: float, out: Path, work_dir: Path) -> None:
    overlay = work_dir / "03_실제화면_자막.png"
    make_demo_overlay(post, overlay)
    fade_out = max(0.25, duration - 0.28)
    filter_complex = (
        "[0:v]scale=1000:-2,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=0x171B2B[base];"
        f"[base][1:v]overlay=0:0,fade=t=in:st=0:d=0.25,fade=t=out:st={fade_out:.3f}:d=0.25,"
        "format=yuv420p[v]"
    )
    run_quiet([
        "ffmpeg", "-y", "-stream_loop", "-1", "-i", str(APP_DEMO),
        "-loop", "1", "-i", str(overlay), "-filter_complex", filter_complex,
        "-map", "[v]", "-t", f"{duration:.3f}", "-r", "30", "-an",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
        "-pix_fmt", "yuv420p", str(out),
    ])


def make_finished_video(post: dict, assets: dict, post_dir: Path) -> Path:
    video_dir = post_dir / "VIDEO"
    work_dir = video_dir / "_제작소스"
    work_dir.mkdir(parents=True, exist_ok=True)
    narration_path = video_dir / "나레이션.txt"
    voice_path = video_dir / "음성.wav"
    write_text(narration_path, narration_text(post))
    run_quiet([
        "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(TTS_SCRIPT),
        "-InputTextFile", str(narration_path), "-OutputWav", str(voice_path),
    ])
    audio_duration = ffprobe_duration(voice_path)
    total_duration = max(22.0, audio_duration + 0.8)
    demo_duration = min(6.0, max(4.6, total_duration * 0.20))
    still_duration = (total_duration - demo_duration) / 4

    segment_paths = [work_dir / f"seg_{idx:02d}.mp4" for idx in range(1, 6)]
    make_still_segment(assets["story"][0], still_duration, segment_paths[0])
    make_still_segment(assets["video_problem"], still_duration, segment_paths[1])
    make_demo_segment(post, demo_duration, segment_paths[2], work_dir)
    make_still_segment(assets["video_takeaway"], still_duration, segment_paths[3])
    make_still_segment(assets["story"][2], still_duration, segment_paths[4])

    concat_file = work_dir / "concat.txt"
    concat_lines = [f"file '{path.as_posix()}'" for path in segment_paths]
    concat_file.write_text("\n".join(concat_lines) + "\n", encoding="utf-8")
    silent_video = work_dir / "silent.mp4"
    run_quiet([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
        "-c", "copy", str(silent_video),
    ])

    final_video = video_dir / "릴스_쇼츠_완성본.mp4"
    run_quiet([
        "ffmpeg", "-y", "-i", str(silent_video), "-i", str(voice_path),
        "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac",
        "-b:a", "160k", "-af", "apad", "-t", f"{total_duration:.3f}",
        "-movflags", "+faststart", str(final_video),
    ])
    return final_video


def post_folder(post: dict) -> Path:
    day_value = campaign_date(post["day"])
    day_dir = BUILD_ROOT / f"{day_value.isoformat()}_DAY{post['day']:02d}"
    return day_dir / f"P{post['post']}_{safe_name(post['hook'].splitlines()[0])}"


def build_post(post: dict, index: int) -> dict[str, str]:
    folder = post_folder(post)
    text_dir = folder / "TEXT"
    text_dir.mkdir(parents=True, exist_ok=True)
    build_channel_texts(post, text_dir)
    assets = build_carousel_and_story(post, index, folder)
    video = make_finished_video(post, assets, folder)

    checklist = [
        f"# {post_code(post)} 게시 체크",
        "",
        f"- 날짜: {campaign_date(post['day']).isoformat()}",
        f"- 훅: {post['hook'].replace(chr(10), ' / ')}",
        f"- 댓글 키워드: {post['keyword']}",
        "- 카드뉴스: `CAROUSEL_FEED`의 01부터 06까지 순서대로 다중 선택",
        "- 스토리: `STORY`의 01부터 03까지 순서대로 업로드",
        "- 릴스/쇼츠: `VIDEO/릴스_쇼츠_완성본.mp4`를 그대로 업로드",
        "",
        "| 채널 | 업로드 시간(KST) | 텍스트 파일 | 완료 |",
        "|---|---:|---|---|",
    ]
    for channel in CHANNELS:
        checklist.append(f"| {channel} | {upload_time(post, channel)} | TEXT/{CHANNEL_FILES[channel]} | [ ] |")
    write_text(folder / "00_업로드_체크리스트.md", "\n".join(checklist))
    return {
        "date": campaign_date(post["day"]).isoformat(),
        "day": str(post["day"]),
        "post": str(post["post"]),
        "hook": post["hook"].replace("\n", " / "),
        "keyword": post["keyword"],
        "folder": str(folder),
        "video": str(video),
    }


def build_day_guides() -> None:
    for day_no in range(1, 11):
        day_posts = [p for p in POSTS if p["day"] == day_no]
        day_dir = post_folder(day_posts[0]).parent
        value = campaign_date(day_no)
        lines = [
            f"# DAY {day_no:02d} · {value.isoformat()}",
            "",
            "## 오늘 3개 콘텐츠",
            "",
        ]
        for post in day_posts:
            lines.append(f"- P{post['post']}: {post['hook'].replace(chr(10), ' / ')}")
        lines += [
            "",
            "## 채널별 업로드 시간(KST)",
            "",
            "| 채널 | P1 | P2 | P3 |",
            "|---|---:|---:|---:|",
        ]
        for channel in CHANNELS:
            times = [upload_time(post, channel) for post in day_posts]
            lines.append(f"| {channel} | {times[0]} | {times[1]} | {times[2]} |")
        if day_no == 10:
            lines += [
                "",
                f"## 최종 라이브 · {LIVE_DATE} {LIVE_TIME}",
                "",
                "- 19:45 화면·음성·결제 동선 최종 점검",
                "- 20:15 송출 대기",
                "- 20:30 라이브 시작",
                "- 21:10 라이브 종료 및 참석/불참 후속 분기",
            ]
        write_text(day_dir / "00_오늘_실행.md", "\n".join(lines))


def build_schedule(index_rows: list[dict[str, str]]) -> None:
    operations = BUILD_ROOT / "00_전체운영"
    operations.mkdir(parents=True, exist_ok=True)
    schedule_path = operations / "전체_업로드_스케줄.csv"
    with schedule_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        writer.writerow(["날짜", "DAY", "POST", "채널", "업로드시간_KST", "훅", "댓글키워드", "라이브전여부"])
        for post in POSTS:
            for channel in CHANNELS:
                when = upload_time(post, channel)
                live_flag = "라이브 전" if post["day"] == 10 and post["post"] == 3 else ""
                writer.writerow([
                    campaign_date(post["day"]).isoformat(), post["day"], post["post"], channel,
                    when, post["hook"].replace("\n", " / "), post["keyword"], live_flag,
                ])

    index_path = operations / "콘텐츠_인덱스.csv"
    with index_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(index_rows[0].keys()))
        writer.writeheader()
        writer.writerows(index_rows)

    tracker = operations / "성과_추적.csv"
    with tracker.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        writer.writerow([
            "날짜", "POST", "채널", "노출", "3초조회", "완주", "저장", "댓글", "프로필클릭",
            "문의", "결제", "환불", "7일실행", "14일실행", "메모",
        ])
        for post in POSTS:
            for channel in CHANNELS:
                writer.writerow([campaign_date(post["day"]).isoformat(), post_code(post), channel] + [""] * 12)


def build_prompt_record() -> None:
    operations = BUILD_ROOT / "00_전체운영"
    topics = [
        "첫 문장을 고민하며 노트북 앞에서 멈춘 한국인 1인 사업자",
        "서로 다른 네 가지 콘텐츠 관점을 비교하는 크리에이터 책상",
        "실제 소프트웨어 대시보드를 확인하는 손과 노트북",
        "프롬프트가 적힌 메모가 쌓였지만 게시물은 없는 책상",
        "아날로그 타이머와 반복 작업 시간을 재는 홈오피스",
        "인쇄된 빠른 시작 PDF와 노트북을 함께 보는 장면",
        "일곱 개 쇼핑 카테고리를 상징하는 실제 제품 플랫레이",
        "하나의 입력에서 여러 결과가 갈라지는 듀얼 모니터 장면",
        "원격 도움을 받는 현실적인 화상 과외 장면",
        "한 상품을 네 시선으로 촬영한 현실적인 제품 콘텐츠 장면",
        "여러 앱을 오가다 한 화면으로 정리된 업무 장면",
        "게시 전 최종 승인 버튼을 사람이 확인하는 장면",
        "1년 사용권·과외·PDF 번들을 상징하는 정돈된 책상",
        "계산기와 작업 시간표로 41일을 계산하는 장면",
        "화면 공유로 막힌 설정을 해결하는 원격 과외 장면",
        "사람의 판단과 자동 반복 작업이 나뉜 협업 장면",
        "오류 로그와 중단 상태를 확인하는 현실적인 노트북 화면",
        "게시 전 네 가지 체크 항목을 점검하는 손",
        "프로그램 설치를 진행하는 현실적인 윈도우 노트북",
        "첫 게시물 완료 알림을 확인하는 사용자",
        "개인 과외에서 화면을 함께 보며 해결하는 장면",
        "전자책 PDF의 첫 페이지를 펴는 장면",
        "여섯 개 PDF 섹션을 실제 인쇄물로 펼쳐둔 장면",
        "초보자가 자주 틀리는 일곱 가지를 체크하는 장면",
        "고객 100명 목표를 시각화한 스튜디오 보드",
        "구매 후 전달·예약·원격지원 동선을 정리한 장면",
        "라이브 하루 전 장비와 데모를 리허설하는 장면",
        "라이브 당일 실제 프로그램 데모를 준비하는 장면",
        "성공 화면과 오류 화면을 동시에 공개하는 장면",
        "최종 라이브 오퍼를 투명하게 설명하는 장면",
    ]
    lines = [
        "# 실사 원본 30장 제작 기록",
        "",
        "- 생성 방식: OpenAI 이미지 생성 도구",
        "- 공통 스타일: photorealistic editorial commercial photography, Korean home-office context, natural skin and hands, realistic lighting, no logos, no watermark, no synthetic UI claims",
        "- 사용 원칙: 인물·책상 사진은 `실사 상황 연출`, 프로그램 캡처는 `실제 프로그램 화면`으로 구분 표기",
        "- 원본 위치: `00_전체운영/실사_원본_30장`",
        "",
        "## 게시물별 장면 프롬프트",
        "",
    ]
    for idx, topic in enumerate(topics, 1):
        lines.append(f"{idx:02d}. {topic}. 세로형 구도, 제목이 들어갈 넉넉한 음영 공간, 자연스러운 한국 홈오피스, 광고 사진 수준의 세부 묘사.")
    write_text(operations / "실사_원본_30장_프롬프트.md", "\n".join(lines))


def copy_master_assets() -> None:
    operations = BUILD_ROOT / "00_전체운영"
    photos = operations / "실사_원본_30장"
    real_ui = operations / "실제_프로그램_증빙"
    photos.mkdir(parents=True, exist_ok=True)
    real_ui.mkdir(parents=True, exist_ok=True)
    for idx in range(1, 31):
        shutil.copy2(photo_source(idx), photos / f"P{idx:02d}_실사_상황연출.png")
    for source in SCREENSHOTS:
        shutil.copy2(source, real_ui / source.name)
    shutil.copy2(APP_DEMO, real_ui / "실제_프로그램_작동영상.mp4")


def build_live_script() -> None:
    operations = BUILD_ROOT / "00_전체운영"
    script = f"""# 최종 라이브 방송 대본

- 일시: {LIVE_DATE} {LIVE_TIME} KST
- 러닝타임: 40분
- 목표: 시청자가 오늘 바로 쓸 4관점 후킹법을 얻고, 실제 프로그램 흐름과 판매 조건을 확인하게 한다.

## 0:00-3:00 오프닝

“오늘은 수익 인증으로 끌지 않겠습니다. 링크 하나가 들어간 뒤 문안, 이미지, 고지 확인, 사람 승인까지 실제 화면으로 보여드리겠습니다. 끝나기 전에 타깃·편의·반전·사용 장면 4가지 첫 문장을 직접 가져가실 수 있습니다.”

대상: 링크는 만들 수 있지만 매일 게시하는 반복에서 멈추는 사람.
비대상: 자동으로 수익이 난다는 보장을 기대하는 사람, 검수 없이 무조건 게시하려는 사람.

## 3:00-7:00 1문항 진단

채팅 질문: “가장 오래 걸리는 구간을 숫자로 남겨주세요. 1 상품 선택 / 2 첫 문장 / 3 이미지 / 4 채널별 수정 / 5 게시.”

받은 답을 2~3개 읽고 이렇게 연결합니다.
“지금 답이 갈리는 이유는 글쓰기 한 단계가 아니라 전체 흐름이 끊기기 때문입니다. 오늘은 가장 많이 나온 구간부터 실제로 줄여보겠습니다.”

## 7:00-13:00 무료 미니 강의 - 한 링크에서 4개 훅

화면에 상품 링크 하나를 띄운 뒤 아래 질문을 씁니다.

1. 타깃: 이걸 가장 급하게 찾는 사람은 누구인가?
2. 편의: 사용 전후 어떤 귀찮음이 줄어드는가?
3. 반전: 사람들이 예상하지 못한 특징은 무엇인가?
4. 사용 장면: 언제, 어디서, 어떤 모습으로 쓰는가?

말할 문장:
“프롬프트를 외우는 게 핵심이 아닙니다. 이 네 질문이 결과를 비교할 기준입니다. 프로그램도 네 관점을 빠르게 만들지만, 최종 선택은 계정 주인이 해야 합니다.”

## 13:00-22:00 실제 프로그램 데모

1. 제휴 링크 입력
2. 상품 정보 확인
3. 후킹 문안 4종 생성 결과 비교
4. 이미지와 고지 문구 확인
5. 계정 선택과 게시 전 사람 승인
6. 오류가 난 경우 중단 상태와 로그 확인

말할 문장:
“성공 화면만 보여드리면 판단이 안 됩니다. 오류가 나면 어디서 멈추고 무엇을 확인하는지도 같이 보겠습니다. 자동화가 대신하는 것은 반복이고, 상품 선택·최종 문장·계정 정책 확인은 사람이 합니다.”

## 22:00-27:00 7개 쇼핑 제휴 적용 범위

{platform_sentence()}

말할 문장:
“쿠팡만 묶인 구조가 아닙니다. 각 플랫폼에서 본인이 발급한 링크를 넣어 같은 제작 흐름을 쓸 수 있습니다. 단, 플랫폼별 가입·링크 발급·활동 채널 등록·대가성 고지는 사용자가 직접 확인해야 합니다.”

## 27:00-32:00 오퍼 공개

- 가격: {PRICE}
- 포함: {OFFER}
- 전달: 결제 확인 후 설치 안내, 개인 강의 일정 확정, PDF 제공, 막힌 구간은 원격으로 지원
- 제외: 수익·노출·계정 안전 보장, 플랫폼 정책 위반 해결 보장, 제휴 플랫폼 승인 대행

말할 문장:
“70만원은 프로그램 파일만의 가격이 아닙니다. 1년 사용, 개인 강의, 사용 중 막힌 구간의 원격 과외, 사용법 PDF까지 묶었습니다. 다만 수익을 보장하거나 계정 제재가 절대 없다고 말하지 않습니다.”

시간가치 비교:
수작업 1건 30분, 자동화 후 사람 검수 1건 7분, 하루 3건을 가정하면 하루 69분, 연간 약 420시간 차이입니다. 본인 시간가치를 시급 15,000원으로 두면 하루 17,250원, 약 41일의 작업 시간가치와 70만원이 비슷해집니다. 이는 수익 회수 기간이 아니라 가정에 따른 시간가치 비교입니다.

## 32:00-40:00 Q&A와 마감

우선 답할 질문: 설치, 지원 PC, 계정 연결 방식, 사람 승인 지점, 오류 중단, 원격 지원 범위, 환불·지원 조건.

반론 답변:
- “완전 자동이면 검수가 왜 필요하죠?” → “반복 실행은 자동화할 수 있어도 상품 적합성, 문맥, 고지, 계정 정책은 사람 책임이라 승인 지점을 남겼습니다.”
- “쿠팡만 되나요?” → “아닙니다. 현재 안내한 7개 쇼핑 제휴 링크를 같은 콘텐츠 제작 흐름에 넣을 수 있습니다.”
- “프롬프트 강의와 뭐가 다른가요?” → “프롬프트를 조립하는 법보다 프로그램 사용과 실제 세팅을 배우는 구성입니다.”
- “수익이 바로 나나요?” → “보장할 수 없습니다. 게시 성공률, 7일·14일 지속률, 클릭과 구매 전환을 분리해서 봐야 합니다.”

마감 문장:
“오늘 보신 화면과 판매하는 프로그램은 같습니다. 조건이 맞는 분은 채팅에 ‘시작’을 남겨주세요. 제공물·지원 범위·환불 조건을 다시 확인한 뒤 결제 안내를 드리겠습니다.”

## 종료 직후

- 참석자: 핵심 요약, Q&A, 오퍼 조건, 신청 방법 발송
- 불참자: 타임스탬프 리플레이와 4관점 후킹표 발송
- 기록: 등록, 출석, 25/50/75% 체류, CTA 클릭, 결제, 7일 취소, 14일 실행률
"""
    write_text(operations / "최종_라이브_40분_대본.md", script)


def pdf_styles() -> dict[str, ParagraphStyle]:
    pdfmetrics.registerFont(TTFont("Pretendard", str(FONT_SB)))
    pdfmetrics.registerFont(TTFont("PretendardXB", str(FONT_XB)))
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "TitleKo", parent=base["Title"], fontName="PretendardXB", fontSize=25,
            leading=32, textColor=colors.HexColor(INK), spaceAfter=9 * mm,
        ),
        "h1": ParagraphStyle(
            "H1Ko", parent=base["Heading1"], fontName="PretendardXB", fontSize=17,
            leading=23, textColor=colors.HexColor(INK), spaceBefore=5 * mm, spaceAfter=4 * mm,
        ),
        "h2": ParagraphStyle(
            "H2Ko", parent=base["Heading2"], fontName="PretendardXB", fontSize=12.5,
            leading=18, textColor=colors.HexColor(ROSE), spaceBefore=4 * mm, spaceAfter=2.5 * mm,
        ),
        "body": ParagraphStyle(
            "BodyKo", parent=base["BodyText"], fontName="Pretendard", fontSize=9.4,
            leading=14.5, textColor=colors.HexColor(INK), spaceAfter=2.2 * mm,
        ),
        "small": ParagraphStyle(
            "SmallKo", parent=base["BodyText"], fontName="Pretendard", fontSize=7.7,
            leading=11.5, textColor=colors.HexColor("#4E5360"),
        ),
        "table": ParagraphStyle(
            "TableKo", parent=base["BodyText"], fontName="Pretendard", fontSize=7.3,
            leading=10.5, textColor=colors.HexColor(INK),
        ),
        "table_head": ParagraphStyle(
            "TableHeadKo", parent=base["BodyText"], fontName="PretendardXB", fontSize=7.4,
            leading=10.5, textColor=colors.white, alignment=TA_CENTER,
        ),
        "cover_sub": ParagraphStyle(
            "CoverSub", parent=base["BodyText"], fontName="PretendardXB", fontSize=13,
            leading=20, textColor=colors.HexColor("#4E5360"),
        ),
        "quote": ParagraphStyle(
            "QuoteKo", parent=base["BodyText"], fontName="PretendardXB", fontSize=12,
            leading=18, textColor=colors.HexColor(INK), backColor=colors.HexColor("#FFF3C8"),
            borderPadding=10, spaceBefore=3 * mm, spaceAfter=5 * mm,
        ),
    }


def p(text: str, style: ParagraphStyle) -> Paragraph:
    escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Paragraph(escaped.replace("\n", "<br/>"), style)


def bullet_paragraph(items: list[str], style: ParagraphStyle) -> Paragraph:
    return p("\n".join(f"• {item}" for item in items), style)


def pdf_header_footer(canvas, document) -> None:
    canvas.saveState()
    width, height = A4
    canvas.setStrokeColor(colors.HexColor("#E5E7EC"))
    canvas.line(18 * mm, 14 * mm, width - 18 * mm, 14 * mm)
    canvas.setFont("Pretendard", 7.5)
    canvas.setFillColor(colors.HexColor("#777C88"))
    canvas.drawString(18 * mm, 9 * mm, "THREAD AUTO · 10일 실전 마케팅 실행서")
    canvas.drawRightString(width - 18 * mm, 9 * mm, str(document.page))
    canvas.restoreState()


def styled_table(data, widths, header=True, repeat_rows=1) -> LongTable:
    table = LongTable(data, colWidths=widths, repeatRows=repeat_rows if header else 0, hAlign="LEFT")
    commands = [
        ("FONTNAME", (0, 0), (-1, -1), "Pretendard"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D7DAE2")),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS", (0, 1 if header else 0), (-1, -1), [colors.white, colors.HexColor("#FAFAFC")]),
    ]
    if header:
        commands += [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(NAVY)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "PretendardXB"),
        ]
    table.setStyle(TableStyle(commands))
    return table


def build_pdf() -> Path:
    styles = pdf_styles()
    operations = BUILD_ROOT / "00_전체운영"
    pdf_path = operations / "최종_통합_마케팅_실행계획_2026-08-12.pdf"
    PDF_OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    mirrored_pdf = PDF_OUTPUT_ROOT / "thread-auto-complete-marketing-plan-2026-08-12-ko.pdf"
    doc = SimpleDocTemplate(
        str(pdf_path), pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm,
        topMargin=18 * mm, bottomMargin=19 * mm, title="THREAD AUTO 10일 실전 마케팅 실행계획",
        author="THREAD AUTO",
    )
    story = []

    story += [
        Spacer(1, 20 * mm),
        p("THREAD AUTO", styles["cover_sub"]),
        p("10일 실전 마케팅\n통합 실행계획", styles["title"]),
        p("2026.08.12 - 2026.08.21 · 최종 라이브 08.21 20:30", styles["cover_sub"]),
        Spacer(1, 12 * mm),
        p("목표 매출 70,000,000원 = 700,000원 패키지 100명", styles["quote"]),
        p(
            "프로그램 1년 사용권, 개인 강의 1회, 사용 중 막힌 구간의 원격 과외, 사용법 전자책 PDF를 하나의 상품으로 판매한다. "
            "10일간 매일 채널별 3개 콘텐츠를 공개하고 마지막 날 한 번의 라이브에서 실제 화면, 적용 범위, 가격과 지원 조건을 투명하게 보여준다.",
            styles["body"],
        ),
        Spacer(1, 6 * mm),
    ]
    representative = [1, 5, 13, 25]
    image_cells = []
    pdf_asset_dir = ROOT / "tmp" / "pdfs" / "marketing-pdf-assets"
    pdf_asset_dir.mkdir(parents=True, exist_ok=True)
    for idx in representative:
        post = POSTS[idx - 1]
        cover = post_folder(post) / "CAROUSEL_FEED" / "01_훅_커버.png"
        compressed_cover = pdf_asset_dir / f"cover-{idx:02d}.jpg"
        source_image = Image.open(cover).convert("RGB")
        source_image.thumbnail((456, 570), Image.Resampling.LANCZOS)
        source_image.save(compressed_cover, quality=82, optimize=True)
        image_cells.append(RLImage(str(compressed_cover), width=38 * mm, height=47.5 * mm))
    grid = Table([image_cells], colWidths=[40 * mm] * 4, hAlign="LEFT")
    grid.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 2)]))
    story += [grid, PageBreak()]

    story += [p("1. 오퍼와 수치 목표", styles["h1"])]
    offer_data = [
        [p("항목", styles["table_head"]), p("확정 내용", styles["table_head"])],
        [p("판매가", styles["table"]), p(PRICE, styles["table"])],
        [p("구성", styles["table"]), p(OFFER, styles["table"])],
        [p("목표", styles["table"]), p("100명 × 700,000원 = 70,000,000원", styles["table"])],
        [p("캠페인", styles["table"]), p("10일 · 2026-08-12부터 2026-08-21까지", styles["table"])],
        [p("라이브", styles["table"]), p("2026-08-21 20:30 KST · 1회", styles["table"])],
    ]
    story += [styled_table(offer_data, [35 * mm, 125 * mm]), Spacer(1, 4 * mm)]
    story += [p("차별화 포지션", styles["h2"])]
    story += [p(
        "다른 상품이 프롬프트 작성법과 이론을 가르치는 데 집중한다면, 이 패키지는 프로그램을 실제로 설치하고 사용하는 흐름에 집중한다. "
        "링크 입력 뒤 문안 생성, 이미지 확인, 고지 검수, 게시 전 승인까지 반복 작업을 줄이는 것이 장점이다. "
        "다만 상품 선택, 최종 문장, 계정 정책과 고지는 사람이 확인해야 한다.",
        styles["body"],
    )]
    story += [p("장점", styles["h2"]), bullet_paragraph([
        "프롬프트를 매번 조합할 필요가 없는 고정된 실행 흐름",
        "1년 사용권과 실제 세팅·개인 강의·원격 지원·PDF가 한 패키지",
        "쿠팡 한 곳이 아니라 7개 쇼핑 제휴 링크에 같은 콘텐츠 제작 흐름 적용",
        "성공 화면뿐 아니라 작업 상태와 오류 중단 지점 확인",
    ], styles["body"])]
    story += [p("단점과 대응", styles["h2"]), bullet_paragraph([
        "검수 없는 무조건 게시 도구가 아니다 → 사람 승인 지점을 명확히 공개",
        "플랫폼 정책과 계정 상태는 바뀔 수 있다 → 지원 범위와 제외 범위를 사전 고지",
        "수익을 보장할 수 없다 → 게시 성공률·지속률·클릭·구매를 분리 측정",
        "초기 설치에서 막힐 수 있다 → 개인 강의와 원격 과외로 첫 게시까지 동행",
    ], styles["body"]), PageBreak()]

    story += [p("2. 시간 절감 가치 - 조건을 함께 보여주기", styles["h1"])]
    time_data = [
        [p("작업", styles["table_head"]), p("수작업 가정", styles["table_head"]), p("자동화+검수 가정", styles["table_head"]), p("차이", styles["table_head"])],
        [p("게시물 1건", styles["table"]), p("30분", styles["table"]), p("7분", styles["table"]), p("23분", styles["table"])],
        [p("하루 3건", styles["table"]), p("90분", styles["table"]), p("21분", styles["table"]), p("69분", styles["table"])],
        [p("1년 365일", styles["table"]), p("547.5시간", styles["table"]), p("127.75시간", styles["table"]), p("약 420시간", styles["table"])],
    ]
    story += [styled_table(time_data, [47 * mm, 38 * mm, 43 * mm, 32 * mm]), Spacer(1, 4 * mm)]
    story += [p(
        "본인 작업가치를 시급 15,000원으로 가정하면 하루 69분은 17,250원 상당이다. 700,000원 ÷ 17,250원은 약 41일이다. "
        "이 값은 수익 회수 기간이 아니라 사용자가 직접 하던 작업 시간의 가정값 비교다. 모든 광고 카드와 라이브에서 조건을 숫자 옆에 함께 표기한다.",
        styles["quote"],
    )]
    story += [p("현재 지원하는 쇼핑 제휴 링크", styles["h2"])]
    platform_data = [[p("번호", styles["table_head"]), p("플랫폼", styles["table_head"]), p("적용 범위", styles["table_head"])]]
    for idx, platform in enumerate(PLATFORMS, 1):
        platform_data.append([p(str(idx), styles["table"]), p(platform, styles["table"]), p("본인이 발급한 제휴 링크를 콘텐츠 제작 흐름에 입력", styles["table"])])
    story += [styled_table(platform_data, [17 * mm, 55 * mm, 88 * mm]), PageBreak()]

    story += [p("3. 10일 채널 실행 일정", styles["h1"])]
    story += [p(
        "모든 시간은 KST다. 한 게시물을 같은 문장으로 복사하지 않고, 동일한 핵심을 채널 문법에 맞춰 별도 파일로 제공한다. "
        "마지막 날 P3는 라이브 시작 전인 18:30-19:30 사이에 모두 배치했다.",
        styles["body"],
    )]
    schedule_data = [[p("날짜", styles["table_head"]), p("P1", styles["table_head"]), p("P2", styles["table_head"]), p("P3", styles["table_head"])]]
    for day_no in range(1, 11):
        day_posts = [post for post in POSTS if post["day"] == day_no]
        row = [p(campaign_date(day_no).strftime("%m/%d"), styles["table"])]
        row += [p(post["hook"].replace("\n", " "), styles["table"]) for post in day_posts]
        schedule_data.append(row)
    story += [styled_table(schedule_data, [20 * mm, 47 * mm, 47 * mm, 47 * mm])]
    story += [Spacer(1, 5 * mm), p("채널별 기본 시간", styles["h2"])]
    time_rows = [[p("채널", styles["table_head"]), p("P1", styles["table_head"]), p("P2", styles["table_head"]), p("P3", styles["table_head"])]]
    for channel in CHANNELS:
        time_rows.append([p(channel, styles["table"])] + [p(t, styles["table"]) for t in CHANNEL_TIMES[channel]])
    story += [styled_table(time_rows, [55 * mm, 35 * mm, 35 * mm, 35 * mm]), PageBreak()]

    story += [p("4. 카드뉴스·스토리·영상 제작 규격", styles["h1"])]
    asset_data = [
        [p("자산", styles["table_head"]), p("규격", styles["table_head"]), p("구성", styles["table_head"])],
        [p("피드 카드뉴스", styles["table"]), p("1080×1350 · 6장", styles["table"]), p("훅 → 문제 → 실제 화면 → 전후 → 적용 포인트 → CTA", styles["table"])],
        [p("스토리", styles["table"]), p("1080×1920 · 3장", styles["table"]), p("훅 → 실제 화면 → CTA", styles["table"])],
        [p("릴스·쇼츠", styles["table"]), p("1080×1920 · H.264/AAC", styles["table"]), p("한국어 음성, 화면 자막, 실제 프로그램 동작 영상 포함", styles["table"])],
        [p("텍스트", styles["table"]), p("게시물당 8개", styles["table"]), p("Threads·Instagram·TikTok·YouTube·Blog·Facebook·커뮤니티·강의 웹", styles["table"])],
    ]
    story += [styled_table(asset_data, [35 * mm, 45 * mm, 80 * mm]), Spacer(1, 4 * mm)]
    story += [p("잘림 방지 규칙", styles["h2"]), bullet_paragraph([
        "피드 좌우 84px, 상단 82px, 하단 82px 이상 안전 여백",
        "스토리 상단 UI 영역 230px, 하단 UI 영역 280px를 비워 핵심 문구 보호",
        "텍스트는 지정 상자 안에서 자동 축소하고 최소 크기에서도 넘치면 빌드 실패",
        "사진은 실사 상황 연출, UI는 실제 프로그램 화면으로 출처 성격을 구분",
    ], styles["body"])]

    story += [p("게시물별 자산", styles["h2"])]
    asset_rows = [[p("코드", styles["table_head"]), p("훅", styles["table_head"]), p("댓글 키워드", styles["table_head"]), p("사진", styles["table_head"]), p("카드/스토리/영상", styles["table_head"])]]
    for idx, post in enumerate(POSTS, 1):
        asset_rows.append([
            p(post_code(post), styles["table"]), p(post["hook"].replace("\n", " "), styles["table"]),
            p(post["keyword"], styles["table"]), p(f"P{idx:02d}", styles["table"]), p("6장 / 3장 / 1편", styles["table"]),
        ])
    story += [styled_table(asset_rows, [23 * mm, 71 * mm, 26 * mm, 17 * mm, 30 * mm]), PageBreak()]

    story += [p("5. 최종 라이브 40분 구성", styles["h1"])]
    live_rows = [
        [p("시간", styles["table_head"]), p("내용", styles["table_head"]), p("시청자 산출물", styles["table_head"])],
        [p("0-3분", styles["table"]), p("약속·대상·비대상", styles["table"]), p("오늘 얻을 것 명확화", styles["table"])],
        [p("3-7분", styles["table"]), p("1문항 진단과 문제 재진술", styles["table"]), p("내 병목 위치 확인", styles["table"])],
        [p("7-13분", styles["table"]), p("한 링크에서 4개 훅 만드는 무료 미니 강의", styles["table"]), p("타깃·편의·반전·사용 장면 질문표", styles["table"])],
        [p("13-22분", styles["table"]), p("실제 프로그램 데모와 오류 중단 공개", styles["table"]), p("입력부터 사람 승인까지 전체 흐름", styles["table"])],
        [p("22-27분", styles["table"]), p("7개 플랫폼 적용 범위", styles["table"]), p("내 플랫폼 적용 가능 여부", styles["table"])],
        [p("27-32분", styles["table"]), p("70만원 오퍼·지원·제외·시간가치", styles["table"]), p("구매 조건 판단", styles["table"])],
        [p("32-40분", styles["table"]), p("Q&A·반론 처리·CTA", styles["table"]), p("신청 또는 보류 결정", styles["table"])],
    ]
    story += [styled_table(live_rows, [25 * mm, 75 * mm, 60 * mm]), Spacer(1, 4 * mm)]
    story += [p(
        "오프닝 핵심 문장: ‘오늘은 수익 인증으로 끌지 않겠습니다. 링크 하나가 들어간 뒤 문안, 이미지, 고지 확인, 사람 승인까지 실제 화면으로 보여드리겠습니다.’",
        styles["quote"],
    )]
    story += [p("라이브 운영 원칙", styles["h2"]), bullet_paragraph([
        "CTA를 마지막 2분에 처음 공개하지 않고 27-32분에 조건과 함께 공개",
        "질문은 시작부터 받되 마지막 구간에서 묶어 답변",
        "성공 화면만 보여주지 않고 오류 중단과 지원 제외도 공개",
        "참석자와 불참자 후속을 분리하고 리플레이 행동을 따로 추적",
    ], styles["body"]), PageBreak()]

    story += [p("6. 측정·정책·표현 안전선", styles["h1"])]
    measure_rows = [
        [p("단계", styles["table_head"]), p("측정 항목", styles["table_head"]), p("판단", styles["table_head"])],
        [p("콘텐츠", styles["table"]), p("노출·3초 조회·완주·저장·댓글", styles["table"]), p("훅과 정보 밀도", styles["table"])],
        [p("관심", styles["table"]), p("프로필 클릭·문의·라이브 등록", styles["table"]), p("CTA 적합성", styles["table"])],
        [p("구매", styles["table"]), p("결제·7일 취소·환불", styles["table"]), p("오퍼 기대 일치", styles["table"])],
        [p("실행", styles["table"]), p("설치 완료·첫 게시 성공·7일·14일 지속", styles["table"]), p("실제 고객 가치", styles["table"])],
    ]
    story += [styled_table(measure_rows, [35 * mm, 67 * mm, 58 * mm]), Spacer(1, 4 * mm)]
    story += [p("반드시 지킬 표현", styles["h2"]), bullet_paragraph([
        "‘자동으로 돈 번다’, ‘계정 안전 보장’, ‘무조건 조회수’ 같은 보장 문구 사용 금지",
        "시간 절감 숫자는 수작업 30분·자동화+검수 7분·하루 3건이라는 조건과 함께 표기",
        "제휴 링크 게시 시 해당 플랫폼의 대가성 고지와 활동 채널 등록 요구 확인",
        "공식 API·허용 권한·게시 빈도·중단 기준·토큰 해제·지원 제외 범위를 구매 전 공개",
        "사례와 후기는 기간·비용·표본·선별 기준 없이 전형적 성과처럼 말하지 않기",
    ], styles["body"])]
    story += [p("참고 근거", styles["h2"])]
    sources = [
        "공정거래위원회 추천·보증 등에 관한 표시·광고 심사지침 개정(2024-12-01 시행): https://www.ftc.go.kr/www/selectBbsNttView.do?bordCd=3&key=12&nttSn=43669",
        "쿠팡파트너스 공식 이용 가이드: https://partners.coupangcdn.com/partners-guide/partners-guide-20240716100922.pdf",
        "YouTube 스팸 정책: https://support.google.com/youtube/answer/2801973",
        "YouTube 인위적 참여 정책: https://support.google.com/youtube/answer/3399767",
        "Instagram 이용약관: https://www.facebook.com/help/instagram/581066165581870",
        "LinkedIn Webinar Planning Guide(30-45분 운영 참고): https://business.linkedin.com/content/dam/me/business/en-us/resource-hub/li-webinar-registration-best-practices-interactive__v3.pdf",
        "Zoom Running Engaging Online Events: https://media.zoom.com/download/assets/Running-Engaging-Online-Events.pdf/09b51194fef311edbaf936dab72dcb97",
        "Goldcast 2026 B2B Webinar Benchmark(2025 플랫폼 관측자료): https://www.goldcast.io/reports/b2b-webinar-benchmark-report-2026",
    ]
    story += [bullet_paragraph(sources, styles["small"])]
    story += [Spacer(1, 5 * mm), p(
        "이 실행안의 10일 길이, 40분 라이브, 콘텐츠 순서는 현재 근거와 제품 조건을 조합한 파일럿 가설이다. 구매율만 보지 말고 환불과 14일 실행률까지 함께 보고 다음 캠페인에서 수정한다.",
        styles["quote"],
    )]

    doc.build(story, onFirstPage=pdf_header_footer, onLaterPages=pdf_header_footer)
    shutil.copy2(pdf_path, mirrored_pdf)
    return pdf_path


def build_readme() -> None:
    readme = f"""# 바로 업로드용 최종 마케팅 패키지

캠페인 기간: {CAMPAIGN_START} - {LIVE_DATE}  
최종 라이브: {LIVE_DATE} {LIVE_TIME} KST  
판매가: {PRICE}  
구성: {OFFER}

## 이 폴더에 들어 있는 완성물

- 30개 게시물 × 채널별 완성 원고 8개
- 30개 게시물 × 피드 카드뉴스 6장 = 180장
- 30개 게시물 × 스토리 3장 = 90장
- 30개 게시물 × 한국어 음성·화면 자막·실제 프로그램 영상 포함 세로 영상 1편 = 30편
- 날짜별 업로드 체크리스트와 전체 CSV 스케줄
- 최종 라이브 40분 대본
- 통합 PDF 실행계획
- 실사 상황 연출 원본 30장과 실제 프로그램 증빙 화면·영상

## 업로드 방법

1. 날짜 폴더의 `00_오늘_실행.md`를 연다.
2. 각 P 폴더 `TEXT`에서 채널에 맞는 글을 그대로 복사한다.
3. 피드는 `CAROUSEL_FEED`의 01부터 06까지 순서대로 다중 선택한다.
4. 스토리는 `STORY`의 01부터 03까지 순서대로 올린다.
5. 릴스·쇼츠·TikTok은 `VIDEO/릴스_쇼츠_완성본.mp4`를 바로 올린다.
6. 업로드 전 계정·링크·대가성 고지·플랫폼 정책을 마지막으로 확인한다.

## 디자인 기준

- 피드 1080×1350, 스토리·영상 1080×1920
- 핵심 문구는 플랫폼 UI 안전 영역 안에만 배치
- 글자가 최소 크기에서도 지정 상자에 들어가지 않으면 생성 실패
- 사진은 `실사 상황 연출`, 프로그램 화면은 `실제 프로그램 화면`으로 구분
- 수익과 계정 안전을 보장하지 않으며 시간 절감 숫자는 계산 조건과 함께 제시
"""
    write_text(BUILD_ROOT / "00_README_먼저보세요.md", readme)


def build_cover_contact_sheet() -> Path:
    columns = 5
    thumb_w, thumb_h = 236, 295
    gap = 18
    header_h = 132
    rows = math.ceil(len(POSTS) / columns)
    canvas_w = columns * thumb_w + (columns + 1) * gap
    canvas_h = header_h + rows * thumb_h + (rows + 1) * gap
    canvas = Image.new("RGB", (canvas_w, canvas_h), CREAM)
    draw = ImageDraw.Draw(canvas)
    draw.text((gap, 26), "30개 카드뉴스 커버 미리보기", font=load_font(42, True), fill=INK)
    draw.text((gap, 82), "2026.08.12 - 08.21 · 각 커버 뒤에 5장의 정보 카드가 이어집니다", font=load_font(23, True), fill="#626876")
    for index, post in enumerate(POSTS):
        row, column = divmod(index, columns)
        x = gap + column * (thumb_w + gap)
        y = header_h + gap + row * (thumb_h + gap)
        cover = post_folder(post) / "CAROUSEL_FEED" / "01_훅_커버.png"
        image = Image.open(cover).convert("RGB").resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
        canvas.paste(image, (x, y))
        draw.rounded_rectangle((x + 8, y + 8, x + 76, y + 34), radius=10, fill=(255, 255, 255))
        draw.text((x + 17, y + 13), post_code(post), font=load_font(13, True), fill=INK)
    out = BUILD_ROOT / "00_전체운영" / "30개_커버_미리보기.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, quality=92, optimize=True)
    return out


def build_all() -> Path:
    ensure_sources()
    reset_build_root()
    build_readme()
    index_rows = []
    for index, post in enumerate(POSTS, 1):
        print(f"[{index:02d}/30] {post_code(post)} {post['hook'].replace(chr(10), ' / ')}", flush=True)
        index_rows.append(build_post(post, index))
    build_day_guides()
    build_schedule(index_rows)
    build_prompt_record()
    copy_master_assets()
    build_live_script()
    build_cover_contact_sheet()
    pdf_path = build_pdf()
    print(f"PDF: {pdf_path}", flush=True)
    print(f"BUILD: {BUILD_ROOT}", flush=True)
    return BUILD_ROOT


if __name__ == "__main__":
    build_all()
