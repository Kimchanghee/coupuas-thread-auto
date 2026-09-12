from __future__ import annotations

import json
import math
import random
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
V1 = ROOT / "output" / "organic-launch-pack"
OUT = ROOT / "output" / "organic-launch-pack-v2"
FONT_DIR = ROOT / "fonts"

PAPER = "#FFF8F0"
INK = "#15151A"
ROSE = "#E11D48"
PINK = "#FB7185"
BLUE = "#2563EB"
YELLOW = "#FFD84D"
LILAC = "#C4B5FD"
MINT = "#A7F3D0"
WHITE = "#FFFFFF"
MUTED = "#6B6670"

FONTS = {
    "bold": FONT_DIR / "Pretendard-ExtraBold.ttf",
    "semibold": FONT_DIR / "Pretendard-SemiBold.ttf",
    "body": FONT_DIR / "Pretendard-SemiBold.ttf",
}

random.seed(42)


def font(kind: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS[kind]), size=size)


def hex_rgba(value: str, alpha: int = 255) -> tuple[int, int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4)) + (alpha,)


def canvas(size: tuple[int, int], color: str = PAPER, texture: bool = True) -> Image.Image:
    image = Image.new("RGBA", size, hex_rgba(color))
    if texture:
        noise = Image.effect_noise(size, 7).convert("L")
        noise = ImageEnhance.Contrast(noise).enhance(0.22)
        tint = Image.new("RGBA", size, (42, 27, 18, 0))
        tint.putalpha(noise.point(lambda p: 8 + p // 28))
        image = Image.alpha_composite(image, tint)
    return image


def cover(path: Path, size: tuple[int, int], darken: float = 1.0) -> Image.Image:
    source = Image.open(path).convert("RGB")
    sw, sh = source.size
    tw, th = size
    scale = max(tw / sw, th / sh)
    resized = source.resize((math.ceil(sw * scale), math.ceil(sh * scale)), Image.Resampling.LANCZOS)
    left = (resized.width - tw) // 2
    top = (resized.height - th) // 2
    result = resized.crop((left, top, left + tw, top + th)).convert("RGBA")
    if darken != 1.0:
        result = ImageEnhance.Brightness(result).enhance(darken)
    return result


def rounded_image(path: Path, size: tuple[int, int], radius: int = 34) -> Image.Image:
    image = cover(path, size)
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0], size[1]), radius=radius, fill=255)
    image.putalpha(mask)
    return image


def paste_shadow(
    base: Image.Image,
    item: Image.Image,
    xy: tuple[int, int],
    radius: int = 30,
    offset: tuple[int, int] = (13, 15),
    shadow: str = INK,
    border: int = 0,
    border_color: str = INK,
) -> None:
    x, y = xy
    shadow_layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow_layer)
    sd.rounded_rectangle(
        (x + offset[0], y + offset[1], x + item.width + offset[0], y + item.height + offset[1]),
        radius=radius,
        fill=hex_rgba(shadow, 220),
    )
    base.alpha_composite(shadow_layer)
    base.alpha_composite(item, (x, y))
    if border:
        ImageDraw.Draw(base).rounded_rectangle(
            (x, y, x + item.width, y + item.height), radius=radius, outline=border_color, width=border
        )


def gradient_overlay(size: tuple[int, int], top_alpha: int, bottom_alpha: int, color: str = INK) -> Image.Image:
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    px = layer.load()
    rgb = hex_rgba(color)[:3]
    for y in range(size[1]):
        t = y / max(1, size[1] - 1)
        alpha = int(top_alpha + (bottom_alpha - top_alpha) * t)
        for x in range(size[0]):
            px[x, y] = (*rgb, alpha)
    return layer


def wrap(draw: ImageDraw.ImageDraw, text: str, face: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        if not paragraph:
            lines.append("")
            continue
        words = paragraph.split(" ")
        current = words[0]
        for word in words[1:]:
            trial = f"{current} {word}"
            if draw.textlength(trial, font=face) <= max_width:
                current = trial
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def multiline(
    image: Image.Image,
    xy: tuple[int, int],
    text: str,
    face: ImageFont.FreeTypeFont,
    color: str = INK,
    max_width: int | None = None,
    spacing: int = 10,
    align: str = "left",
    stroke: int = 0,
    stroke_fill: str = INK,
) -> tuple[int, int]:
    draw = ImageDraw.Draw(image)
    lines = wrap(draw, text, face, max_width) if max_width else text.split("\n")
    ascent, descent = face.getmetrics()
    line_height = ascent + descent + spacing
    x, y = xy
    longest = 0
    for index, line in enumerate(lines):
        width = int(draw.textlength(line, font=face))
        longest = max(longest, width)
        tx = x
        if align == "center" and max_width:
            tx = x + (max_width - width) // 2
        elif align == "right" and max_width:
            tx = x + max_width - width
        draw.text(
            (tx, y + index * line_height),
            line,
            font=face,
            fill=color,
            stroke_width=stroke,
            stroke_fill=stroke_fill,
        )
    return longest, len(lines) * line_height - spacing


def badge(
    image: Image.Image,
    xy: tuple[int, int],
    text: str,
    bg: str = YELLOW,
    fg: str = INK,
    size: int = 26,
    padding: tuple[int, int] = (20, 11),
    rotate: float = 0,
    border: int = 3,
) -> Image.Image:
    face = font("bold", size)
    d = ImageDraw.Draw(image)
    tw = int(d.textlength(text, font=face))
    th = face.getbbox(text)[3] - face.getbbox(text)[1]
    item = Image.new("RGBA", (tw + padding[0] * 2, th + padding[1] * 2 + 4), (0, 0, 0, 0))
    idraw = ImageDraw.Draw(item)
    idraw.rounded_rectangle(
        (1, 1, item.width - 2, item.height - 2), radius=item.height // 2, fill=bg, outline=INK, width=border
    )
    idraw.text((padding[0], padding[1] - 2), text, font=face, fill=fg)
    if rotate:
        item = item.rotate(rotate, expand=True, resample=Image.Resampling.BICUBIC)
    image.alpha_composite(item, xy)
    return item


def brand(image: Image.Image, y: int = 44, inverse: bool = False) -> None:
    d = ImageDraw.Draw(image)
    color = WHITE if inverse else INK
    d.ellipse((52, y + 7, 68, y + 23), fill=ROSE)
    d.text((80, y), "SHORTS × THREADS", font=font("bold", 22), fill=color)
    d.text((80, y + 29), "MAKER LAB", font=font("semibold", 15), fill=PINK if inverse else ROSE)


def disclosure(image: Image.Image, inverse: bool = False) -> None:
    color = (255, 255, 255, 185) if inverse else hex_rgba(MUTED, 190)
    ImageDraw.Draw(image).text((image.width - 164, image.height - 38), "AI 연출 이미지", font=font("body", 15), fill=color)


def page_no(image: Image.Image, current: int, total: int = 6, inverse: bool = False) -> None:
    color = WHITE if inverse else INK
    ImageDraw.Draw(image).text((image.width - 108, 52), f"{current:02d} / {total:02d}", font=font("semibold", 19), fill=color)


def line_scribble(image: Image.Image, points: list[tuple[int, int]], color: str = ROSE, width: int = 8) -> None:
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.line(points, fill=color, width=width, joint="curve")
    image.alpha_composite(layer)


def app_card(image: Image.Image, app_path: Path, box: tuple[int, int, int, int], rotate: float = 0) -> None:
    x, y, w, h = box
    app = Image.open(app_path).convert("RGBA")
    app.thumbnail((w, h), Image.Resampling.LANCZOS)
    frame = Image.new("RGBA", (app.width + 24, app.height + 24), WHITE)
    mask = Image.new("L", frame.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, frame.width, frame.height), radius=24, fill=255)
    frame.putalpha(mask)
    frame.alpha_composite(app, (12, 12))
    if rotate:
        frame = frame.rotate(rotate, expand=True, resample=Image.Resampling.BICUBIC)
    paste_shadow(image, frame, (x, y), radius=24, offset=(16, 18), shadow="#7C2D48", border=3)


def save(image: Image.Image, directory: str, name: str) -> Path:
    target_dir = OUT / directory
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / name
    image.convert("RGB").save(target, quality=96)
    return target


def ig_carousel(sources: dict[str, Path]) -> list[Path]:
    outputs: list[Path] = []
    w, h = 1080, 1350

    # 1 — cinematic photo + oversized editorial headline
    im = cover(sources["night"], (w, h), 0.92)
    im.alpha_composite(gradient_overlay((w, h), 10, 235, INK))
    brand(im, inverse=True)
    page_no(im, 1, inverse=True)
    badge(im, (58, 720), "매일 반복되는 40분", bg=YELLOW, rotate=-3)
    multiline(im, (58, 820), "링크는 골랐는데\n첫 문장에서\n멈췄다면?", font("bold", 80), WHITE, 900, spacing=2)
    line_scribble(im, [(58, 1170), (300, 1154), (505, 1172), (716, 1155)], PINK, 8)
    multiline(im, (60, 1200), "문제는 글솜씨보다 반복 과정일 수 있습니다", font("semibold", 26), WHITE, 900)
    disclosure(im, inverse=True)
    outputs.append(save(im, "instagram", "ig-carousel-01-cover.png"))

    # 2 — magazine process
    im = canvas((w, h), PAPER)
    brand(im)
    page_no(im, 2)
    badge(im, (55, 160), "BEFORE", bg=LILAC, rotate=-3)
    multiline(im, (55, 235), "매일 이걸\n다 하고 있었어요", font("bold", 69), INK, 760, spacing=2)
    steps = [
        ("01", "상품 확인", "링크와 정보를 다시 찾기"),
        ("02", "문안 작성", "광고 같아서 또 고치기"),
        ("03", "계정 전환", "로그인 상태 다시 확인"),
        ("04", "게시 재확인", "어디까지 올렸지?"),
    ]
    y = 500
    colors = [YELLOW, MINT, LILAC, PINK]
    for idx, (number, title, body) in enumerate(steps):
        card_im = Image.new("RGBA", (900, 142), hex_rgba(WHITE))
        cd = ImageDraw.Draw(card_im)
        cd.rounded_rectangle((0, 0, 900, 142), radius=28, fill=WHITE, outline=INK, width=3)
        cd.ellipse((22, 22, 120, 120), fill=colors[idx], outline=INK, width=3)
        cd.text((48, 39), number, font=font("bold", 27), fill=INK)
        cd.text((150, 23), title, font=font("bold", 34), fill=INK)
        cd.text((150, 76), body, font=font("body", 23), fill=MUTED)
        paste_shadow(im, card_im, (68 + (idx % 2) * 18, y), radius=28, offset=(9, 10), shadow=INK)
        y += 175
    multiline(im, (65, 1232), "한 번이 아니라 매일 반복된다는 게 문제였습니다", font("bold", 26), ROSE, 930)
    outputs.append(save(im, "instagram", "ig-carousel-02-pain.png"))

    # 3 — bold poll split
    im = canvas((w, h), "#F8E9EA")
    brand(im)
    page_no(im, 3)
    multiline(im, (55, 145), "당신이라면\n어느 글을 누르나요?", font("bold", 68), INK, 900, spacing=3)
    a = Image.new("RGBA", (855, 250), hex_rgba(WHITE))
    ad = ImageDraw.Draw(a)
    ad.rounded_rectangle((0, 0, 855, 250), radius=36, fill=WHITE, outline=INK, width=4)
    ad.text((30, 28), "A", font=font("bold", 54), fill=BLUE)
    ad.text((120, 42), "가볍고 편리한\n휴대용 선풍기입니다", font=font("bold", 36), fill=INK, spacing=8)
    paste_shadow(im, a, (105, 430), radius=36, offset=(12, 14), shadow=BLUE)
    badge(im, (450, 690), "VS", bg=YELLOW, size=35, rotate=-7)
    b = Image.new("RGBA", (855, 310), hex_rgba(ROSE))
    bd = ImageDraw.Draw(b)
    bd.rounded_rectangle((0, 0, 855, 310), radius=36, fill=ROSE, outline=INK, width=4)
    bd.text((30, 28), "B", font=font("bold", 54), fill=YELLOW)
    bd.text((120, 38), "선풍기 꺼낸 친구를\n비웃었는데 5분 뒤\n내가 빌려달라고 했다", font=font("bold", 35), fill=WHITE, spacing=8)
    paste_shadow(im, b, (105, 790), radius=36, offset=(12, 14), shadow=INK)
    multiline(im, (80, 1190), "정답은 다음 장 →", font("bold", 30), BLUE, 920, align="right")
    outputs.append(save(im, "instagram", "ig-carousel-03-quiz.png"))

    # 4 — playful bento angles
    im = canvas((w, h), PAPER)
    brand(im)
    page_no(im, 4)
    multiline(im, (55, 145), "같은 상품도\n출발점은 4개", font("bold", 71), INK, 850, spacing=2)
    cards = [
        ("01", "타깃 직격", "지금 누가\n필요한가", ROSE, WHITE),
        ("02", "편의 대비", "쓰기 전과 후가\n어떻게 다른가", BLUE, WHITE),
        ("03", "재미 반전", "예상 밖 순간은\n무엇인가", YELLOW, INK),
        ("04", "사용 장면", "어디에서\n빛나는가", MINT, INK),
    ]
    positions = [(55, 430, -2), (555, 470, 2), (72, 800, 2), (545, 830, -2)]
    for (num, title, body, bg, fg), (x, y, rot) in zip(cards, positions):
        item = Image.new("RGBA", (455, 300), (0, 0, 0, 0))
        d = ImageDraw.Draw(item)
        d.rounded_rectangle((0, 0, 455, 300), radius=38, fill=bg, outline=INK, width=4)
        d.text((28, 22), num, font=font("bold", 24), fill=fg)
        d.text((28, 78), title, font=font("bold", 39), fill=fg)
        d.text((28, 159), body, font=font("body", 27), fill=fg, spacing=7)
        item = item.rotate(rot, expand=True, resample=Image.Resampling.BICUBIC)
        paste_shadow(im, item, (x, y), radius=38, offset=(11, 13), shadow=INK)
    multiline(im, (55, 1240), "말투만 바꾼 네 개가 아닙니다", font("bold", 30), ROSE, 900)
    outputs.append(save(im, "instagram", "ig-carousel-04-angles.png"))

    # 5 — real product proof
    im = canvas((w, h), "#12111A", texture=False)
    brand(im, inverse=True)
    page_no(im, 5, inverse=True)
    badge(im, (55, 140), "REAL SCREEN", bg=YELLOW, rotate=-2)
    multiline(im, (55, 225), "말보다\n실제 작동 화면", font("bold", 72), WHITE, 850, spacing=2)
    app_card(im, sources["app"], (50, 500, 980, 610), rotate=-1.2)
    badge(im, (75, 1140), "링크 입력", bg=PINK, fg=INK, rotate=-2)
    badge(im, (318, 1165), "문안 생성", bg=MINT, fg=INK, rotate=2)
    badge(im, (565, 1138), "계정별 대기열", bg=LILAC, fg=INK, rotate=-2)
    multiline(im, (58, 1270), "영상에서는 게시 흐름까지 공개합니다", font("semibold", 24), WHITE, 900)
    outputs.append(save(im, "instagram", "ig-carousel-05-proof.png"))

    # 6 — warm human CTA
    im = cover(sources["relief"], (w, h), 0.98)
    im.alpha_composite(gradient_overlay((w, h), 0, 215, "#3B1020"))
    brand(im, inverse=True)
    page_no(im, 6, inverse=True)
    badge(im, (55, 660), "NO COURSE · REAL TOOL", bg=YELLOW, rotate=-2)
    multiline(im, (55, 770), "강의 말고\n직접 써보고\n판단하세요", font("bold", 77), WHITE, 900, spacing=0)
    cta = Image.new("RGBA", (910, 112), hex_rgba(ROSE))
    cd = ImageDraw.Draw(cta)
    cd.rounded_rectangle((0, 0, 910, 112), radius=56, fill=ROSE, outline=WHITE, width=3)
    cd.text((220, 25), "매월 5회 무료 체험", font=font("bold", 38), fill=WHITE)
    paste_shadow(im, cta, (55, 1165), radius=56, offset=(10, 11), shadow=INK)
    disclosure(im, inverse=True)
    outputs.append(save(im, "instagram", "ig-carousel-06-cta.png"))
    return outputs


def stories(sources: dict[str, Path]) -> list[Path]:
    outputs: list[Path] = []
    w, h = 1080, 1920

    im = cover(sources["multi"], (w, h), 0.96)
    im.alpha_composite(gradient_overlay((w, h), 30, 205, INK))
    brand(im, inverse=True)
    badge(im, (60, 250), "솔직히", bg=YELLOW, rotate=-5, size=30)
    multiline(im, (60, 355), "계정 3개부터\n기억력 테스트가\n시작됐습니다", font("bold", 79), WHITE, 930, spacing=1)
    poll = Image.new("RGBA", (930, 265), hex_rgba(PAPER))
    pd = ImageDraw.Draw(poll)
    pd.rounded_rectangle((0, 0, 930, 265), radius=44, fill=PAPER, outline=INK, width=4)
    pd.text((43, 28), "어디까지 올렸는지 기억나요?", font=font("bold", 31), fill=INK)
    pd.rounded_rectangle((40, 105, 445, 220), radius=55, fill=WHITE, outline=INK, width=3)
    pd.rounded_rectangle((485, 105, 890, 220), radius=55, fill=ROSE, outline=INK, width=3)
    pd.text((126, 140), "항상 기억", font=font("bold", 29), fill=INK)
    pd.text((560, 140), "매번 헷갈림", font=font("bold", 29), fill=WHITE)
    paste_shadow(im, poll, (75, 1505), radius=44, offset=(14, 15), shadow=BLUE)
    disclosure(im, inverse=True)
    outputs.append(save(im, "stories", "story-01-poll.png"))

    im = canvas((w, h), PAPER)
    brand(im)
    badge(im, (62, 250), "DAILY LOOP", bg=LILAC, rotate=-4, size=28)
    multiline(im, (62, 355), "게시 하나에\n숨어 있던\n반복 작업", font("bold", 82), INK, 900, spacing=0)
    d = ImageDraw.Draw(im)
    d.text((680, 285), "4×", font=font("bold", 145), fill=ROSE)
    labels = [("상품 확인", YELLOW, -3), ("문안 작성", MINT, 2), ("계정 전환", PINK, -2), ("상태 재확인", LILAC, 3)]
    y = 840
    for index, (label, bg, rot) in enumerate(labels, start=1):
        card_im = Image.new("RGBA", (800, 170), (0, 0, 0, 0))
        cd = ImageDraw.Draw(card_im)
        cd.rounded_rectangle((0, 0, 800, 170), radius=36, fill=bg, outline=INK, width=4)
        cd.text((32, 42), f"0{index}", font=font("bold", 32), fill=INK)
        cd.text((145, 34), label, font=font("bold", 52), fill=INK)
        card_im = card_im.rotate(rot, expand=True, resample=Image.Resampling.BICUBIC)
        paste_shadow(im, card_im, (130, y), radius=36, offset=(12, 14), shadow=INK)
        y += 225
    multiline(im, (65, 1770), "제일 귀찮은 단계를 답장으로 알려주세요", font("bold", 28), BLUE, 940)
    outputs.append(save(im, "stories", "story-02-pain.png"))

    im = canvas((w, h), "#11131F", texture=False)
    brand(im, inverse=True)
    badge(im, (62, 260), "NO MOCKUP", bg=YELLOW, rotate=-3, size=27)
    multiline(im, (62, 360), "홍보용 그림 말고\n실제 화면입니다", font("bold", 75), WHITE, 930, spacing=0)
    app_card(im, sources["app"], (45, 735, 990, 720), rotate=-1.4)
    line_scribble(im, [(80, 1480), (265, 1510), (478, 1480), (705, 1510), (930, 1480)], PINK, 8)
    badge(im, (105, 1570), "상품 링크", bg=PINK, rotate=-2)
    badge(im, (410, 1600), "문안 4종", bg=MINT, rotate=2)
    badge(im, (700, 1560), "대기열", bg=LILAC, rotate=-2)
    multiline(im, (60, 1770), "영상에서 게시 흐름까지 확인 →", font("bold", 30), WHITE, 950, align="right")
    outputs.append(save(im, "stories", "story-03-proof.png"))

    im = canvas((w, h), "#F8E9EA")
    brand(im)
    badge(im, (62, 250), "1초 선택", bg=YELLOW, rotate=-5)
    multiline(im, (62, 360), "어느 쪽이\n더 궁금하세요?", font("bold", 84), INK, 900, spacing=0)
    choices = [
        ("A", "가볍고 편리한\n휴대용 선풍기", WHITE, BLUE, 730, -2),
        ("B", "비웃던 친구가\n5분 뒤 빌려달라고 했다", ROSE, YELLOW, 1100, 2),
    ]
    for label, copy, bg, accent, y, rot in choices:
        item = Image.new("RGBA", (880, 300), (0, 0, 0, 0))
        idraw = ImageDraw.Draw(item)
        idraw.rounded_rectangle((0, 0, 880, 300), radius=44, fill=bg, outline=INK, width=4)
        idraw.text((35, 27), label, font=font("bold", 66), fill=accent)
        idraw.text((145, 45), copy, font=font("bold", 40), fill=WHITE if bg == ROSE else INK, spacing=10)
        item = item.rotate(rot, expand=True, resample=Image.Resampling.BICUBIC)
        paste_shadow(im, item, (90, y), radius=44, offset=(14, 15), shadow=INK)
    badge(im, (365, 1550), "A / B 투표", bg=BLUE, fg=WHITE, size=34)
    outputs.append(save(im, "stories", "story-04-quiz.png"))

    im = cover(sources["relief"], (w, h), 1.0)
    im.alpha_composite(gradient_overlay((w, h), 0, 220, "#33101F"))
    brand(im, inverse=True)
    badge(im, (62, 800), "직접 만든 도구", bg=YELLOW, rotate=-3)
    multiline(im, (62, 905), "강의 안 팝니다.\n기능부터\n확인하세요", font("bold", 82), WHITE, 910, spacing=0)
    cta = Image.new("RGBA", (900, 150), hex_rgba(ROSE))
    cd = ImageDraw.Draw(cta)
    cd.rounded_rectangle((0, 0, 900, 150), radius=75, fill=ROSE, outline=WHITE, width=4)
    cd.text((184, 42), "매월 5회 무료", font=font("bold", 49), fill=WHITE)
    paste_shadow(im, cta, (90, 1580), radius=75, offset=(13, 15), shadow=INK)
    multiline(im, (90, 1760), "링크 스티커를 눌러 실제 화면 보기", font("semibold", 27), WHITE, 900, align="center")
    disclosure(im, inverse=True)
    outputs.append(save(im, "stories", "story-05-cta.png"))
    return outputs


def threads_cards(sources: dict[str, Path]) -> list[Path]:
    outputs: list[Path] = []
    w = h = 1200

    im = canvas((w, h), "#F8E9EA")
    brand(im)
    badge(im, (62, 160), "댓글로 A 또는 B", bg=YELLOW, rotate=-3)
    multiline(im, (62, 250), "어느 첫 문장에\n손가락이 멈출까요?", font("bold", 70), INK, 1060, spacing=1)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((64, 500, 1135, 700), radius=34, fill=WHITE, outline=INK, width=4)
    d.text((96, 545), "A", font=font("bold", 50), fill=BLUE)
    d.text((190, 558), "가볍고 편리한 휴대용 선풍기", font=font("bold", 35), fill=INK)
    d.rounded_rectangle((64, 755, 1135, 1035), radius=34, fill=ROSE, outline=INK, width=4)
    d.text((96, 805), "B", font=font("bold", 50), fill=YELLOW)
    d.text((190, 805), "선풍기 꺼낸 친구를 비웃었는데\n5분 뒤 내가 빌려달라고 했다", font=font("bold", 35), fill=WHITE, spacing=12)
    outputs.append(save(im, "threads", "threads-01-quiz.png"))

    im = canvas((w, h), PAPER)
    brand(im)
    multiline(im, (62, 160), "같은 상품,\n서로 다른 4개의 시작점", font("bold", 69), INK, 1050, spacing=0)
    cards = [
        ("01", "타깃 직격", ROSE, WHITE),
        ("02", "편의 대비", BLUE, WHITE),
        ("03", "재미 반전", YELLOW, INK),
        ("04", "사용 장면", MINT, INK),
    ]
    for i, (num, title, bg, fg) in enumerate(cards):
        x = 62 + (i % 2) * 550
        y = 505 + (i // 2) * 300
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((x, y, x + 510, y + 235), radius=36, fill=bg, outline=INK, width=4)
        d.text((x + 28, y + 26), num, font=font("bold", 29), fill=fg)
        d.text((x + 28, y + 93), title, font=font("bold", 45), fill=fg)
    multiline(im, (62, 1080), "말투만 바꾼 네 개가 아닙니다", font("bold", 29), ROSE, 1060)
    outputs.append(save(im, "threads", "threads-02-four-angles.png"))

    im = canvas((w, h), "#11131F", texture=False)
    brand(im, inverse=True)
    badge(im, (62, 155), "REAL SCREEN", bg=YELLOW, rotate=-3)
    multiline(im, (62, 245), "설명 대신\n실제 화면", font("bold", 74), WHITE, 900, spacing=0)
    app_card(im, sources["app"], (105, 535, 1000, 500), rotate=-1)
    badge(im, (96, 1035), "링크 → 문안 → 계정별 대기열", bg=PINK, fg=INK, size=29)
    outputs.append(save(im, "threads", "threads-03-real-screen.png"))
    return outputs


def blog_cards(sources: dict[str, Path]) -> list[Path]:
    outputs: list[Path] = []
    w, h = 1600, 900

    im = canvas((w, h), PAPER)
    brand(im, y=42)
    photo = rounded_image(sources["night"], (560, 660), 42)
    paste_shadow(im, photo, (970, 130), radius=42, offset=(15, 17), shadow=BLUE)
    badge(im, (70, 170), "실제 자동화 기록", bg=YELLOW, rotate=-3)
    multiline(im, (70, 275), "쿠팡 링크 하나,\n어디까지\n자동화될까?", font("bold", 76), INK, 850, spacing=0)
    multiline(im, (75, 665), "문안 4종부터 계정별 Threads 대기열까지", font("semibold", 28), ROSE, 820)
    disclosure(im)
    outputs.append(save(im, "blog", "blog-01-hero.png"))

    im = canvas((w, h), "#F8E9EA")
    brand(im, y=42)
    multiline(im, (70, 145), "반복 작업을 한 흐름으로", font("bold", 66), INK, 1300)
    steps = [("01", "상품 링크", YELLOW), ("02", "타깃 분석", MINT), ("03", "문안 4종", LILAC), ("04", "계정별 게시", PINK)]
    for idx, (num, title, bg) in enumerate(steps):
        x = 70 + idx * 380
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((x, 360, x + 320, 650), radius=42, fill=bg, outline=INK, width=4)
        d.text((x + 30, 390), num, font=font("bold", 32), fill=INK)
        d.text((x + 30, 505), title, font=font("bold", 38), fill=INK)
        if idx < 3:
            d.line((x + 325, 505, x + 370, 505), fill=ROSE, width=8)
            d.polygon([(x + 370, 505), (x + 348, 490), (x + 348, 520)], fill=ROSE)
    multiline(im, (70, 780), "수익 보장 도구가 아니라 반복 시간을 줄이는 도구입니다", font("bold", 27), BLUE, 1450)
    outputs.append(save(im, "blog", "blog-02-workflow.png"))

    im = canvas((w, h), "#11131F", texture=False)
    brand(im, y=42, inverse=True)
    multiline(im, (70, 145), "같은 상품을 다르게 시작하는\n네 가지 방식", font("bold", 61), WHITE, 1350, spacing=0)
    cards = [("타깃 직격", "지금 필요한 사람", ROSE), ("편의 대비", "사용 전과 후", BLUE), ("재미 반전", "예상 밖 순간", YELLOW), ("사용 장면", "쓰는 순간", MINT)]
    for idx, (title, body, bg) in enumerate(cards):
        x = 70 + idx * 380
        fg = INK if bg in (YELLOW, MINT) else WHITE
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((x, 430, x + 325, 710), radius=38, fill=bg, outline=WHITE, width=3)
        d.text((x + 28, 470), f"0{idx + 1}", font=font("bold", 26), fill=fg)
        d.text((x + 28, 545), title, font=font("bold", 36), fill=fg)
        d.text((x + 28, 625), body, font=font("semibold", 23), fill=fg)
    outputs.append(save(im, "blog", "blog-03-four-angles.png"))
    return outputs


def facebook_feed(sources: dict[str, Path]) -> Path:
    im = canvas((1080, 1350), "#F8E9EA")
    brand(im)
    badge(im, (55, 145), "실제 프로그램 화면", bg=YELLOW, rotate=-3)
    multiline(im, (55, 235), "화려한 약속 대신\n작동하는 장면", font("bold", 70), INK, 930, spacing=0)
    app_card(im, sources["app"], (45, 575, 990, 610), rotate=-1)
    multiline(im, (55, 1215), "매월 5회 무료로 직접 확인하세요", font("bold", 29), ROSE, 940, align="center")
    return save(im, "facebook", "facebook-feed-01-real-screen.png")


def make_video(name: str, segments: list[dict], directory: str) -> Path:
    target_dir = OUT / directory
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{name}.mp4"
    args = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    for segment in segments:
        if segment["kind"] == "image":
            args += ["-loop", "1", "-i", str(segment["file"])]
        else:
            args += ["-i", str(segment["file"])]
    chains = []
    labels = []
    for idx, segment in enumerate(segments):
        duration = segment["duration"]
        chains.append(
            f"[{idx}:v]scale=1080:1920:force_original_aspect_ratio=decrease,"
            f"pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=0x11131F,"
            f"setsar=1,fps=30,trim=duration={duration},setpts=PTS-STARTPTS[v{idx}]"
        )
        labels.append(f"[v{idx}]")
    chains.append(f"{''.join(labels)}concat=n={len(segments)}:v=1:a=0[out]")
    args += [
        "-filter_complex",
        ";".join(chains),
        "-map",
        "[out]",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(target),
    ]
    subprocess.run(args, check=True)
    return target


def contact_sheet(files: list[Path], name: str, columns: int, thumb: tuple[int, int]) -> Path:
    rows = math.ceil(len(files) / columns)
    sheet = Image.new("RGB", (columns * thumb[0], rows * thumb[1]), "#EDE7DE")
    for idx, path in enumerate(files):
        item = cover(path, thumb).convert("RGB")
        sheet.paste(item, ((idx % columns) * thumb[0], (idx // columns) * thumb[1]))
    target_dir = OUT / "previews"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / name
    sheet.save(target, quality=94)
    return target


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    sources = {
        "night": V1 / "sources" / "ugc-night.png",
        "multi": V1 / "sources" / "ugc-multiaccount.png",
        "relief": V1 / "sources" / "ugc-relief.png",
        "app": V1 / "sources" / "app-proof.png",
        "demo": V1 / "sources" / "app-demo.mp4",
    }
    for path in sources.values():
        if not path.exists():
            raise FileNotFoundError(path)

    instagram = ig_carousel(sources)
    story_files = stories(sources)
    thread_files = threads_cards(sources)
    blog_files = blog_cards(sources)
    facebook = facebook_feed(sources)

    video_specs = [
        ("instagram", "reel-01-real-demo", [(instagram[0], 2.5), (sources["demo"], 15), (story_files[4], 3.5)]),
        ("instagram", "reel-02-multiaccount", [(story_files[0], 3), (story_files[2], 7), (story_files[3], 5), (story_files[4], 3)]),
        ("tiktok", "tiktok-01-which-copy", [(story_files[3], 4), (story_files[2], 7), (story_files[4], 3)]),
        ("tiktok", "tiktok-02-multiaccount", [(story_files[0], 3), (story_files[2], 7), (story_files[4], 3)]),
        ("tiktok", "tiktok-03-no-course", [(story_files[4], 3), (sources["demo"], 15), (story_files[4], 3)]),
        ("youtube", "short-01-real-demo", [(story_files[1], 2.5), (sources["demo"], 15), (story_files[4], 3.5)]),
        ("youtube", "short-02-four-angles", [(story_files[3], 4), (story_files[2], 7), (story_files[4], 4)]),
        ("facebook", "facebook-reel-01-explainer", [(story_files[1], 4), (sources["demo"], 15), (story_files[3], 5), (story_files[4], 4)]),
    ]
    videos = []
    for directory, name, raw_segments in video_specs:
        segments = []
        for file_path, duration in raw_segments:
            kind = "video" if Path(file_path).suffix.lower() == ".mp4" else "image"
            segments.append({"kind": kind, "file": Path(file_path), "duration": duration})
        videos.append(make_video(name, segments, directory))

    contact_sheet(instagram, "instagram-carousel-preview.png", 3, (360, 450))
    contact_sheet(story_files, "instagram-stories-preview.png", 5, (216, 384))
    contact_sheet(thread_files, "threads-preview.png", 3, (400, 400))
    contact_sheet(blog_files, "blog-preview.png", 3, (533, 300))

    shutil.copy2(V1 / "README.md", OUT / "README.md")
    manifest = {
        "designSystem": "nextlevelbuilder/ui-ux-pro-max-skill",
        "designSystemSource": "design-system/showshortsthreadmaker/MASTER.md",
        "style": "Korean editorial collage + refined neo-brutal accents",
        "counts": {
            "instagramCarousel": len(instagram),
            "instagramStories": len(story_files),
            "threadsImages": len(thread_files),
            "blogGraphics": len(blog_files),
            "facebookFeed": 1,
            "videos": len(videos),
        },
        "files": [str(path) for path in instagram + story_files + thread_files + blog_files + [facebook] + videos],
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
