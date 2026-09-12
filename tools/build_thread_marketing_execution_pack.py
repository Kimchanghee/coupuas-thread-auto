from __future__ import annotations

import csv
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from build_14day_high_hook_content_book import (
    CAMPAIGN_START,
    CHANNEL_UPLOAD_TIMES,
    DAY10_P3_TIMES,
    DAYS,
    WEEKDAYS_KO,
)


ROOT = Path(__file__).resolve().parents[1]
TARGET = Path(r"D:\스레드 마케팅 계획")
OPS = TARGET / "00_전체운영"
MASTER_ASSETS = OPS / "원본_자산"
REFERENCE = OPS / "참고자료"

PHOTOREAL_SOURCES = {
    day_no: ROOT / "output" / "photoreal-v2" / f"DAY{day_no:02d}_photoreal.png"
    for day_no in range(1, 11)
}

REAL_SCREEN = ROOT / "output" / "organic-launch-pack" / "sources" / "app-proof.png"
REAL_DEMO = ROOT / "output" / "organic-launch-pack" / "sources" / "app-demo.mp4"
FINAL_PDF = ROOT / "output" / "pdf" / "thread-auto-2026-08-11-complete-marketing-content-playbook-ko.pdf"
AFFILIATE_DOC = ROOT / "docs" / "AFFILIATE_MARKETPLACES.md"
PHOTOREAL_PROMPTS_DOC = ROOT / "docs" / "PHOTOREAL_V2_PROMPTS.md"

FONT_BOLD_PATH = ROOT / "fonts" / "Pretendard-ExtraBold.ttf"
FONT_SEMI_PATH = ROOT / "fonts" / "Pretendard-SemiBold.ttf"

INK = "#11131A"
ROSE = "#ED174C"
YELLOW = "#FFD84D"
MINT = "#9EEBCB"
LILAC = "#B8A7F5"
CORAL = "#F66F82"
CREAM = "#FFF8EF"
WHITE = "#FFFFFF"
GRAY = "#B8BBC5"

CHANNEL_ORDER = [
    "Threads",
    "Instagram",
    "TikTok",
    "YouTube",
    "Naver Blog",
    "Facebook",
    "커뮤니티",
    "강의 웹",
]

CHANNEL_FILENAMES = {
    "Threads": "Threads.txt",
    "Instagram": "Instagram.txt",
    "TikTok": "TikTok_스크립트.txt",
    "YouTube": "YouTube_제목_설명_스크립트.txt",
    "Naver Blog": "Naver_Blog.md",
    "Facebook": "Facebook.txt",
    "커뮤니티": "커뮤니티.txt",
    "강의 웹": "강의_웹.md",
}

PLATFORMS = [
    "쿠팡파트너스",
    "네이버 쇼핑커넥트",
    "토스쇼핑 파트너스",
    "오늘의집 큐레이터",
    "무신사 파트너스",
    "컬리 큐레이터",
    "올리브영 큐레이터",
]

PROOF_DAYS = {3, 4, 6, 7, 8, 10}


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8-sig")


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_BOLD_PATH if bold else FONT_SEMI_PATH), size)


def wrap_lines(draw: ImageDraw.ImageDraw, text: str, face: ImageFont.FreeTypeFont, width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        if not paragraph:
            lines.append("")
            continue
        current = ""
        for ch in paragraph:
            candidate = current + ch
            if current and draw.textbbox((0, 0), candidate, font=face)[2] > width:
                lines.append(current.rstrip())
                current = ch.lstrip()
            else:
                current = candidate
        if current:
            lines.append(current.rstrip())
    return lines


def draw_multiline(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    face: ImageFont.FreeTypeFont,
    fill: str,
    width: int,
    spacing: int,
    max_lines: int | None = None,
) -> int:
    x, y = xy
    lines = wrap_lines(draw, text, face, width)
    if max_lines:
        lines = lines[:max_lines]
    line_h = face.size + spacing
    for line in lines:
        draw.text((x, y), line, font=face, fill=fill)
        y += line_h
    return y


def day_date(day_no: int):
    from datetime import timedelta

    return CAMPAIGN_START + timedelta(days=day_no - 1)


def date_slug(day_no: int) -> str:
    value = day_date(day_no)
    return value.strftime("%Y-%m-%d")


def date_display(day_no: int) -> str:
    value = day_date(day_no)
    return f"{value.year}.{value.month:02d}.{value.day:02d} ({WEEKDAYS_KO[value.weekday()]})"


def safe_name(text: str) -> str:
    for ch in '<>:"/\\|?*\n\r':
        text = text.replace(ch, "_")
    return "_".join(text.split())[:42]


def slot_label(index: int) -> str:
    return {1: "P1_오전", 2: "P2_오후", 3: "P3_저녁"}[index]


def upload_time(day_no: int, post_no: int, channel: str) -> str:
    if day_no == 10 and post_no == 3:
        return DAY10_P3_TIMES[channel]
    return CHANNEL_UPLOAD_TIMES[channel][post_no - 1]


def disclosure(day_no: int) -> str:
    if day_no == 3:
        return (
            "제휴 링크 사용 시 각 플랫폼의 경제적 이해관계 고지를 게시물 안에 명확히 표시하세요. "
            "실제 제휴 링크는 본인 승인 계정에서 발급한 원본만 사용합니다."
        )
    return "수익·조회·구매 전환을 보장하지 않습니다. 실제 화면과 측정된 결과만 사용합니다."


def platform_line() -> str:
    return " · ".join(PLATFORMS)


def channel_copy(day: dict, post: dict, post_no: int, channel: str) -> str:
    day_no = day["day"]
    hook = post["hook"].replace("\n", " ")
    script = post["script"]
    cta = post["cta"]
    when = upload_time(day_no, post_no, channel)
    common_meta = (
        f"업로드: {date_display(day_no)} {when} KST\n"
        f"캠페인: DAY {day_no:02d} / {slot_label(post_no)}\n"
    )

    if channel == "Threads":
        body = (
            f"{hook}\n\n"
            f"{script}\n\n"
            f"{cta}\n\n"
            f"{disclosure(day_no)}"
        )
    elif channel == "Instagram":
        body = (
            f"{hook}\n\n"
            f"오늘 보여드릴 장면\n- {script}\n\n"
            f"저장해두고 실제 화면과 비교해보세요.\n{cta}\n\n"
            "#스레드자동화 #쇼핑제휴 #제휴마케팅 #콘텐츠자동화 #온라인마케팅\n\n"
            f"{disclosure(day_no)}"
        )
    elif channel == "TikTok":
        body = (
            f"영상 제목: {hook}\n\n"
            f"[0~2초] {hook}\n"
            f"[2~6초] {post['video']}\n"
            f"[6~8초] {script}\n"
            f"[8~9초] {cta}\n\n"
            "편집: 자막은 두 줄 이하, 첫 화면 무음 재생 대비, 끝 CTA 한 개만.\n"
            f"고정 댓글: {disclosure(day_no)}"
        )
    elif channel == "YouTube":
        body = (
            f"제목: {hook} | 스레드 쇼핑 자동화\n\n"
            f"Shorts 대본\n0~2초: {hook}\n"
            f"2~7초: {script}\n"
            f"7~9초: {cta}\n\n"
            f"설명란\n{script}\n\n{cta}\n\n{disclosure(day_no)}\n"
            "태그: 스레드자동화, 제휴마케팅, 쇼핑제휴, 콘텐츠자동화"
        )
    elif channel == "Naver Blog":
        body = (
            f"# {hook}\n\n"
            f"## 오늘 확인할 문제\n{script}\n\n"
            "## 프로그램에서 확인할 흐름\n"
            "제휴 링크 입력 → 상품 분석 → 문안 4종 → 이미지·고지 확인 → 계정별 대기열 → 사람 승인 → 게시\n\n"
            f"## 오늘의 행동\n{cta}\n\n"
            f"> {disclosure(day_no)}\n"
        )
    elif channel == "Facebook":
        body = (
            f"{hook}\n\n"
            f"저도 이 구간이 가장 오래 걸렸습니다. {script}\n\n"
            "기능을 나열하는 대신 실제 화면과 실패 장면까지 같이 보여드리겠습니다.\n"
            f"{cta}\n\n{disclosure(day_no)}"
        )
    elif channel == "커뮤니티":
        body = (
            f"제목: {hook}\n\n"
            f"홍보글보다 운영 경험을 묻고 싶습니다. {script}\n\n"
            "비슷한 작업을 하는 분들은 어느 단계에서 가장 오래 걸리나요?"
            " 첫 글에는 외부 링크를 넣지 않고 답변에서 체크리스트만 공유합니다.\n\n"
            f"{disclosure(day_no)}"
        )
    else:
        body = (
            f"# {hook}\n\n"
            f"**핵심 증명**\n{script}\n\n"
            "**제공 상품**\n프로그램 1년 + 개인 강의 + 사용법 원격 과외 + 전자책 PDF = 700,000원\n\n"
            f"**CTA**\n{cta}\n\n"
            f"**공개 조건**\n{disclosure(day_no)}"
        )
    return common_meta + "\n" + body


def image_source_for_day(day_no: int) -> Path:
    return PHOTOREAL_SOURCES[day_no]


def make_background(source: Path, size: tuple[int, int], add_real_screen: bool) -> Image.Image:
    image = Image.open(source).convert("RGB")
    canvas = ImageOps.fit(image, size, method=Image.Resampling.LANCZOS)
    canvas = ImageEnhance.Brightness(canvas).enhance(0.82).convert("RGBA")

    # 사진의 실제 질감은 유지하고, 카피가 놓이는 상단과 하단만 자연스럽게 눌러준다.
    _, h = size
    shade_strip = Image.new("RGBA", (1, h), (0, 0, 0, 0))
    shade_px = shade_strip.load()
    for y in range(h):
        top = max(0.0, 1.0 - y / (h * 0.48))
        bottom = max(0.0, (y - h * 0.74) / (h * 0.26))
        alpha = int(min(172, 32 + 132 * top + 54 * bottom))
        shade_px[0, y] = (8, 10, 14, alpha)
    shade = shade_strip.resize(size)
    canvas = Image.alpha_composite(canvas, shade)

    if add_real_screen:
        screen = Image.open(REAL_SCREEN).convert("RGB")
        max_w = int(size[0] * 0.84)
        max_h = int(size[1] * 0.28)
        screen = ImageOps.contain(screen, (max_w, max_h), Image.Resampling.LANCZOS)
        x = (size[0] - screen.width) // 2
        y = int(size[1] * 0.48)
        shadow = Image.new("RGBA", size, (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow)
        shadow_draw.rounded_rectangle(
            (x - 18, y - 18, x + screen.width + 18, y + screen.height + 18),
            radius=26,
            fill=(0, 0, 0, 150),
        )
        shadow = shadow.filter(ImageFilter.GaussianBlur(18))
        canvas = Image.alpha_composite(canvas, shadow)
        frame = Image.new("RGBA", size, (0, 0, 0, 0))
        frame_draw = ImageDraw.Draw(frame)
        frame_draw.rounded_rectangle(
            (x - 10, y - 10, x + screen.width + 10, y + screen.height + 10),
            radius=18,
            fill=(245, 245, 242, 238),
            outline=(255, 255, 255, 210),
            width=3,
        )
        frame.paste(screen, (x, y))
        canvas = Image.alpha_composite(canvas, frame)

    return canvas.convert("RGB")


def render_card(
    out: Path,
    size: tuple[int, int],
    day: dict,
    post: dict,
    post_no: int,
    kind: str,
) -> None:
    day_no = day["day"]
    source = image_source_for_day(day_no)
    add_real_screen = day_no in PROOF_DAYS and kind == "proof"
    label = "REAL SCREEN 합성" if add_real_screen else "실사 연출 사진"
    canvas = make_background(source, size, add_real_screen)
    draw = ImageDraw.Draw(canvas)
    w, h = size
    pad = int(w * 0.065)
    scale = w / 1080

    tag_text = f"D{day_no:02d} · {date_slug(day_no)[5:].replace('-', '/')} · P{post_no} {slot_label(post_no).split('_', 1)[1]}"
    tag_font = font(int(28 * scale), True)
    tag_width = draw.textbbox((0, 0), tag_text, font=tag_font)[2] + int(48 * scale)
    draw.rounded_rectangle((pad, int(58 * scale), pad + tag_width, int(118 * scale)), radius=int(25 * scale), fill=YELLOW)
    draw.text((pad + int(24 * scale), int(73 * scale)), tag_text, font=tag_font, fill=INK)
    draw.text((w - pad - int(250 * scale), int(78 * scale)), label, font=font(int(24 * scale), True), fill=WHITE)

    if kind == "cover":
        hook = post["hook"]
        longest = max(len(line) for line in hook.split("\n"))
        hook_size = 70 if longest <= 14 else 62 if longest <= 18 else 54
        draw_multiline(draw, (pad, int(h * 0.16)), hook, font(int(hook_size * scale), True), WHITE, w - pad * 2, int(12 * scale), max_lines=5)
        draw.rounded_rectangle((pad, int(h * 0.80), w - pad, int(h * 0.89)), radius=int(24 * scale), fill=(237, 23, 76, 225))
        draw_multiline(draw, (pad + int(28 * scale), int(h * 0.805)), "설명보다 실제 화면과 결과를 먼저 보여드립니다", font(int(30 * scale), True), WHITE, w - pad * 2 - int(56 * scale), int(8 * scale), max_lines=2)
    elif kind == "proof":
        draw.rounded_rectangle((pad, int(h * 0.13), w - pad, int(h * 0.40)), radius=int(28 * scale), fill=(17, 19, 26, 212))
        draw.text((pad + int(28 * scale), int(h * 0.16)), "오늘 보여줄 장면", font=font(int(34 * scale), True), fill=MINT)
        draw_multiline(draw, (pad + int(28 * scale), int(h * 0.215)), post["script"], font(int(35 * scale), True), WHITE, w - pad * 2 - int(56 * scale), int(10 * scale), max_lines=5)
        draw.rounded_rectangle((pad, int(h * 0.82), w - pad, int(h * 0.91)), radius=int(24 * scale), fill=(255, 248, 239, 232))
        draw_multiline(draw, (pad + int(28 * scale), int(h * 0.838)), post["image"], font(int(26 * scale), True), INK, w - pad * 2 - int(56 * scale), int(6 * scale), max_lines=3)
    else:
        draw.rounded_rectangle((pad, int(h * 0.25), w - pad, int(h * 0.64)), radius=int(36 * scale), fill=(255, 248, 239, 232))
        draw.text((pad + int(34 * scale), int(h * 0.28)), "NEXT ACTION", font=font(int(30 * scale), True), fill=ROSE)
        draw_multiline(draw, (pad + int(34 * scale), int(h * 0.36)), post["cta"], font(int(60 * scale), True), INK, w - pad * 2 - int(68 * scale), int(12 * scale), max_lines=5)
        draw.rounded_rectangle((pad, int(h * 0.72), w - pad, int(h * 0.79)), radius=int(28 * scale), fill=YELLOW)
        draw.text((pad + int(30 * scale), int(h * 0.738)), "링크 1개 → 문안 → 이미지·고지 → 승인 → 게시", font=font(int(27 * scale), True), fill=INK)

    draw.line((pad, h - int(78 * scale), w - pad, h - int(78 * scale)), fill="#454956", width=max(1, int(2 * scale)))
    draw.text((pad, h - int(58 * scale)), "THREAD AUTO · 쇼핑 제휴 7개 플랫폼 지원", font=font(int(23 * scale), True), fill=GRAY)
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, optimize=True)


def make_video(frames: list[Path], out: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg를 찾을 수 없습니다.")
    cmd = [ffmpeg, "-y"]
    for frame in frames:
        cmd += ["-loop", "1", "-t", "3", "-i", str(frame)]
    filter_complex = (
        "[0:v]scale=1080:1920,setsar=1[v0];"
        "[1:v]scale=1080:1920,setsar=1[v1];"
        "[2:v]scale=1080:1920,setsar=1[v2];"
        "[v0][v1][v2]concat=n=3:v=1:a=0,format=yuv420p[v]"
    )
    cmd += [
        "-filter_complex", filter_complex,
        "-map", "[v]",
        "-r", "30",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "23",
        "-movflags", "+faststart",
        str(out),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def video_script(day: dict, post: dict, post_no: int) -> str:
    return (
        f"촬영/업로드: {date_display(day['day'])} · {slot_label(post_no)}\n\n"
        f"0~3초 - 화면: 01_story_cover.png\n멘트: {post['hook'].replace(chr(10), ' ')}\n\n"
        f"3~6초 - 화면: 02_story_proof.png\n멘트: {post['script']}\n\n"
        f"6~9초 - 화면: 03_story_cta.png\n멘트: {post['cta']}\n\n"
        "편집 지시\n"
        "- 제공된 09_vertical_short.mp4는 무음 모션 포스터입니다.\n"
        "- 위 멘트를 직접 녹음하거나 TTS를 얹고, 배경음악은 저작권 확인된 음원만 사용합니다.\n"
        "- 실제 프로그램 화면이 들어간 파일은 REAL SCREEN 표기를 유지합니다.\n"
        "- 수익·조회·계정 안전 보장 표현은 사용하지 않습니다.\n"
    )


def day_readme(day: dict) -> str:
    day_no = day["day"]
    lines = [
        f"# DAY {day_no:02d} · {date_display(day_no)}",
        "",
        f"- 오늘 주제: {day['theme']}",
        f"- 오늘 목표: {day['goal']}",
        "- 모든 시간: 한국시간 KST",
        "",
        "## 업로드 순서",
        "",
        "| 채널 | P1 | P2 | P3 |",
        "|---|---:|---:|---:|",
    ]
    for channel in CHANNEL_ORDER:
        lines.append(
            f"| {channel} | {upload_time(day_no, 1, channel)} | {upload_time(day_no, 2, channel)} | {upload_time(day_no, 3, channel)} |"
        )
    lines += [
        "",
        "## 오늘 반드시 할 일",
        "",
        "- [ ] P1 업로드 전 링크·고지·계정 확인",
        "- [ ] P2 댓글과 저장 반응 30분 내 확인",
        "- [ ] P3 업로드 후 클릭·문의 기록",
        "- [ ] 같은 문장을 8개 채널에 그대로 복사하지 않았는지 확인",
        "- [ ] 실사 연출 사진과 실제 프로그램 화면 합성을 구분 표기",
    ]
    if day_no == 10:
        lines += [
            "",
            "## 라이브 당일",
            "",
            "- 19:45 링크·로그인·화면공유·마이크 테스트",
            "- 20:15 운영자 입장",
            "- 20:25 대기 화면",
            "- 20:30~21:30 라이브",
            "- 21:30~22:20 채널별 결과·요약·FAQ 순차 업로드",
        ]
    return "\n".join(lines)


def copy_asset(source: Path, dest: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(source)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)


def build_root_docs() -> None:
    OPS.mkdir(parents=True, exist_ok=True)
    MASTER_ASSETS.mkdir(parents=True, exist_ok=True)
    REFERENCE.mkdir(parents=True, exist_ok=True)

    write_text(
        TARGET / "00_README_먼저보세요.md",
        """# 스레드 마케팅 10일 실행 폴더

이 폴더는 2026-08-11부터 2026-08-20까지의 실제 업로드 제작물입니다.

## 구조

- `00_전체운영`: 전체 시간표, URL 입력, 원본 자산, 통합 PDF
- `2026-08-11_DAY01` ~ `2026-08-20_DAY10`: 날짜별 P1·P2·P3 실행 폴더
- 각 P 폴더의 `TEXT`: 8개 채널별 완성 문안
- 각 P 폴더의 `DESIGN`: 피드 3장 + 스토리 3장
- 각 P 폴더의 `VIDEO`: 9초 세로 영상 + 내레이션 대본

## 사용 순서

1. `00_전체운영/필수_URL_입력.txt`를 실제 URL로 교체합니다.
2. 날짜 폴더의 `00_오늘_실행표.md`를 엽니다.
3. P1 → P2 → P3 순서로 채널별 시간에 맞춰 업로드합니다.
4. 업로드 직전 각 문안의 사실·고지·링크·계정을 다시 확인합니다.

실사형 AI 촬영 원본은 `실사 연출 사진`, 실제 프로그램 캡처를 합성한 장면은 `REAL SCREEN 합성`으로 표시했습니다.
""",
    )

    write_text(
        OPS / "필수_URL_입력.txt",
        """[업로드 전에 아래 값을 실제 URL로 교체]

LANDING_PAGE_URL=[70만원 패키지 상담/결제 페이지]
FREE_TRIAL_URL=[무료 체험 페이지]
LIVE_URL=[2026-08-20 20:30 라이브 접속 주소]
PROFILE_URL=[통합 프로필 링크]
DEMO_AFFILIATE_LINK=[본인 승인 계정에서 발급한 제휴 링크]

중요:
- 프로그램은 제휴 링크를 새로 발급하거나 일반 상품 URL을 제휴 링크로 바꾸지 않습니다.
- 제휴 링크는 반드시 본인의 승인 계정에서 직접 발급한 원본을 사용합니다.
- 링크 발급 전에는 샘플·테스트 링크를 외부 게시물에 넣지 않습니다.
""",
    )

    platform_rows = [f"{idx}. {name}" for idx, name in enumerate(PLATFORMS, 1)]
    write_text(
        OPS / "지원_플랫폼_7개_및_발급체크.md",
        "# 공식 지원 쇼핑 제휴 플랫폼 7개\n\n"
        + "\n".join(platform_rows)
        + "\n\n## 게시 전 체크\n\n"
        "- [ ] 해당 플랫폼에서 본인 계정으로 제휴 링크를 발급했다.\n"
        "- [ ] 링크를 직접 클릭해 상품 목적지를 확인했다.\n"
        "- [ ] 경제적 이해관계 고지 문구를 확인했다.\n"
        "- [ ] 활동 채널 등록이 필요한 경우 등록했다.\n"
        "- [ ] 이미지·영상의 사용 권리를 확인했다.\n"
        "- [ ] 프로그램 입력 후 상품명과 링크가 맞는지 사람이 검수했다.\n",
    )

    for stale_name in (
        "01_AI_pain_background.png",
        "02_AI_flow_background.png",
        "03_AI_live_background.png",
        "04_REAL_app_screen.png",
        "05_REAL_app_demo.mp4",
    ):
        (MASTER_ASSETS / stale_name).unlink(missing_ok=True)
    (OPS / "AI_이미지_프롬프트_및_표기규칙.md").unlink(missing_ok=True)

    for day_no, source in PHOTOREAL_SOURCES.items():
        copy_asset(source, MASTER_ASSETS / f"DAY{day_no:02d}_photoreal_source.png")
    copy_asset(REAL_SCREEN, MASTER_ASSETS / "REAL_app_screen.png")
    copy_asset(REAL_DEMO, MASTER_ASSETS / "REAL_app_demo.mp4")
    copy_asset(PHOTOREAL_PROMPTS_DOC, OPS / "실사_v2_이미지_프롬프트_및_제작법.md")
    copy_asset(FINAL_PDF, REFERENCE / FINAL_PDF.name)
    copy_asset(AFFILIATE_DOC, REFERENCE / "AFFILIATE_MARKETPLACES.md")


def build_schedule_csv() -> None:
    path = OPS / "전체_업로드_시간표.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["날짜", "DAY", "채널", "P1", "P2", "P3", "주제"])
        for day in DAYS:
            for channel in CHANNEL_ORDER:
                writer.writerow([
                    date_slug(day["day"]),
                    day["day"],
                    channel,
                    upload_time(day["day"], 1, channel),
                    upload_time(day["day"], 2, channel),
                    upload_time(day["day"], 3, channel),
                    day["theme"],
                ])


def build_post(day: dict, post: dict, post_no: int, day_folder: Path) -> dict[str, str]:
    hook_name = safe_name(post["hook"].split("\n")[0])
    post_folder = day_folder / f"{post_no:02d}_{slot_label(post_no)}_{hook_name}"
    text_dir = post_folder / "TEXT"
    design_dir = post_folder / "DESIGN"
    video_dir = post_folder / "VIDEO"
    text_dir.mkdir(parents=True, exist_ok=True)
    design_dir.mkdir(parents=True, exist_ok=True)
    video_dir.mkdir(parents=True, exist_ok=True)

    schedule_lines = [
        f"# {slot_label(post_no)} 업로드 체크리스트",
        "",
        f"후킹: {post['hook'].replace(chr(10), ' / ')}",
        "",
        "| 완료 | 시간 | 채널 | 문안 파일 |",
        "|---|---:|---|---|",
    ]
    for channel in CHANNEL_ORDER:
        filename = CHANNEL_FILENAMES[channel]
        write_text(text_dir / filename, channel_copy(day, post, post_no, channel))
        schedule_lines.append(
            f"| [ ] | {upload_time(day['day'], post_no, channel)} | {channel} | TEXT/{filename} |"
        )
    write_text(post_folder / "00_업로드_체크리스트.md", "\n".join(schedule_lines))

    feed_frames = []
    story_frames = []
    for idx, kind in enumerate(("cover", "proof", "cta"), 1):
        feed = design_dir / f"0{idx}_feed_{kind}.png"
        story = design_dir / f"0{idx}_story_{kind}.png"
        render_card(feed, (1080, 1350), day, post, post_no, kind)
        render_card(story, (1080, 1920), day, post, post_no, kind)
        feed_frames.append(feed)
        story_frames.append(story)

    video_path = video_dir / "09_vertical_short.mp4"
    make_video(story_frames, video_path)
    write_text(video_dir / "08_내레이션_및_편집대본.txt", video_script(day, post, post_no))

    if day["day"] in PROOF_DAYS and post_no in {2, 3}:
        copy_asset(REAL_SCREEN, design_dir / "REAL_프로그램_화면.png")
        copy_asset(REAL_DEMO, video_dir / "REAL_프로그램_데모_원본.mp4")

    return {
        "date": date_slug(day["day"]),
        "day": str(day["day"]),
        "post": str(post_no),
        "hook": post["hook"].replace("\n", " / "),
        "folder": str(post_folder),
        "video": str(video_path),
    }


def build() -> Path:
    TARGET.mkdir(parents=True, exist_ok=True)
    build_root_docs()
    build_schedule_csv()

    index_rows: list[dict[str, str]] = []
    for day in DAYS:
        day_folder = TARGET / f"{date_slug(day['day'])}_DAY{day['day']:02d}"
        day_folder.mkdir(parents=True, exist_ok=True)
        write_text(day_folder / "00_오늘_실행표.md", day_readme(day))
        for post_no, post in enumerate(day["posts"], 1):
            index_rows.append(build_post(day, post, post_no, day_folder))

    index_path = OPS / "콘텐츠_인덱스.csv"
    with index_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "day", "post", "hook", "folder", "video"])
        writer.writeheader()
        writer.writerows(index_rows)

    return TARGET


if __name__ == "__main__":
    print(build())
