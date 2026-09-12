from __future__ import annotations

from pathlib import Path
from typing import Iterable

from reportlab.lib.colors import Color, HexColor, white
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "output" / "pdf"
TMP_DIR = ROOT / "tmp" / "pdfs"
PDF_PATH = OUT_DIR / "thread-auto-2026-08-11-10day-70m-final-live-marketing-plan-ko.pdf"

SUPPORTED_AFFILIATE_PLATFORMS = [
    "쿠팡파트너스",
    "네이버 쇼핑커넥트",
    "토스쇼핑 파트너스",
    "오늘의집 큐레이터",
    "무신사 파트너스",
    "컬리 큐레이터",
    "올리브영 큐레이터",
]

PAGE_W, PAGE_H = landscape(A4)
M = 34

INK = HexColor("#12131A")
PAPER = HexColor("#FFF8F0")
PAPER_2 = HexColor("#F5EAE6")
ROSE = HexColor("#E91E4D")
ROSE_DARK = HexColor("#B80F39")
BLUE = HexColor("#2764E8")
YELLOW = HexColor("#FFD84D")
MINT = HexColor("#A7F3D0")
LILAC = HexColor("#C4B5FD")
CORAL = HexColor("#FB7185")
GREEN = HexColor("#159A6B")
GRAY = HexColor("#6B6E78")
LIGHT_GRAY = HexColor("#E8E1DD")
SOFT_WHITE = HexColor("#FFFCF8")

FONT_REG = "Pretendard"
FONT_SEMI = "Pretendard-SemiBold"
FONT_BOLD = "Pretendard-Bold"
FONT_XB = "Pretendard-ExtraBold"


def register_fonts() -> None:
    pdfmetrics.registerFont(TTFont(FONT_REG, str(ROOT / "fonts" / "Pretendard-SemiBold.ttf")))
    pdfmetrics.registerFont(TTFont(FONT_SEMI, str(ROOT / "fonts" / "Pretendard-SemiBold.ttf")))
    pdfmetrics.registerFont(TTFont(FONT_BOLD, str(ROOT / "fonts" / "Pretendard-Bold.ttf")))
    pdfmetrics.registerFont(TTFont(FONT_XB, str(ROOT / "fonts" / "Pretendard-ExtraBold.ttf")))


def split_lines(text: str, font: str, size: float, max_width: float) -> list[str]:
    lines: list[str] = []
    for paragraph in str(text).split("\n"):
        if not paragraph:
            lines.append("")
            continue
        line = ""
        for ch in paragraph:
            candidate = line + ch
            if line and pdfmetrics.stringWidth(candidate, font, size) > max_width:
                lines.append(line.rstrip())
                line = ch.lstrip()
            else:
                line = candidate
        if line:
            lines.append(line.rstrip())
    return lines


def draw_text(
    c: canvas.Canvas,
    text: str,
    x: float,
    y: float,
    max_width: float,
    size: float = 10,
    font: str = FONT_REG,
    color: Color = INK,
    leading: float | None = None,
    max_lines: int | None = None,
) -> float:
    leading = leading or size * 1.35
    lines = split_lines(text, font, size, max_width)
    if max_lines is not None:
        lines = lines[:max_lines]
    c.setFont(font, size)
    c.setFillColor(color)
    cursor = y
    for line in lines:
        c.drawString(x, cursor, line)
        cursor -= leading
    return cursor


def draw_centered(
    c: canvas.Canvas,
    text: str,
    x: float,
    y: float,
    width: float,
    size: float,
    font: str = FONT_BOLD,
    color: Color = INK,
) -> None:
    c.setFont(font, size)
    c.setFillColor(color)
    c.drawCentredString(x + width / 2, y, text)


def draw_link(
    c: canvas.Canvas,
    label: str,
    url: str,
    x: float,
    y: float,
    max_width: float,
    size: float = 7.2,
    color: Color = BLUE,
) -> None:
    shown = label
    while shown and pdfmetrics.stringWidth(shown, FONT_SEMI, size) > max_width:
        shown = shown[:-1]
    if shown != label and len(shown) > 3:
        shown = shown[:-3] + "..."
    c.setFont(FONT_SEMI, size)
    c.setFillColor(color)
    c.drawString(x, y, shown)
    width = min(max_width, pdfmetrics.stringWidth(shown, FONT_SEMI, size))
    c.linkURL(url, (x, y - 2, x + width, y + size + 2), relative=0)


def rounded_box(
    c: canvas.Canvas,
    x: float,
    y: float,
    w: float,
    h: float,
    fill: Color = SOFT_WHITE,
    stroke: Color = INK,
    radius: float = 12,
    line_width: float = 1,
    shadow: bool = False,
) -> None:
    if shadow:
        c.setFillColor(Color(0, 0, 0, alpha=0.13))
        c.roundRect(x + 5, y - 5, w, h, radius, fill=1, stroke=0)
    c.setFillColor(fill)
    c.setStrokeColor(stroke)
    c.setLineWidth(line_width)
    c.roundRect(x, y, w, h, radius, fill=1, stroke=1)


def pill(
    c: canvas.Canvas,
    text: str,
    x: float,
    y: float,
    fill: Color,
    color: Color = INK,
    size: float = 8.5,
    pad_x: float = 10,
    height: float = 20,
) -> float:
    w = pdfmetrics.stringWidth(text, FONT_BOLD, size) + pad_x * 2
    c.setFillColor(fill)
    c.roundRect(x, y, w, height, height / 2, fill=1, stroke=0)
    draw_centered(c, text, x, y + (height - size) / 2 + 1, w, size, FONT_BOLD, color)
    return w


def page_base(c: canvas.Canvas, page_no: int, section: str, dark: bool = False) -> None:
    c.setFillColor(INK if dark else PAPER)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    c.setFillColor(ROSE)
    c.circle(M + 3, PAGE_H - 25, 3, fill=1, stroke=0)
    c.setFont(FONT_BOLD, 7.5)
    c.setFillColor(white if dark else INK)
    c.drawString(M + 11, PAGE_H - 28, "THREAD AUTO · 10-DAY FINAL-LIVE SPRINT")
    c.setFont(FONT_SEMI, 7.2)
    c.setFillColor(HexColor("#B9BBC5") if dark else GRAY)
    c.drawRightString(PAGE_W - M, PAGE_H - 28, f"{section}  ·  {page_no:02d}")
    c.setStrokeColor(HexColor("#2C2E38") if dark else LIGHT_GRAY)
    c.setLineWidth(0.7)
    c.line(M, 27, PAGE_W - M, 27)
    c.setFont(FONT_SEMI, 6.8)
    c.setFillColor(HexColor("#999CA5") if dark else GRAY)
    c.drawString(M, 15, "내부 실행안 · 2026.08.11 시작 · 판매가 700,000원 · 목표 100건")
    c.drawRightString(PAGE_W - M, 15, "수익·노출 보장 표현 금지")


def title(c: canvas.Canvas, kicker: str, heading: str, sub: str | None = None, dark: bool = False) -> None:
    color = white if dark else INK
    pill(c, kicker, M, PAGE_H - 77, YELLOW, INK, 8)
    draw_text(c, heading, M, PAGE_H - 105, PAGE_W - 2 * M, 25, FONT_XB, color, leading=29)
    if sub:
        draw_text(c, sub, M, PAGE_H - 164, PAGE_W - 2 * M, 9.2, FONT_SEMI, HexColor("#C7C9D1") if dark else GRAY, leading=13)


def draw_arrow(c: canvas.Canvas, x1: float, y: float, x2: float, color: Color = ROSE) -> None:
    c.setStrokeColor(color)
    c.setFillColor(color)
    c.setLineWidth(2)
    c.line(x1, y, x2 - 7, y)
    p = c.beginPath()
    p.moveTo(x2, y)
    p.lineTo(x2 - 8, y + 5)
    p.lineTo(x2 - 8, y - 5)
    p.close()
    c.drawPath(p, fill=1, stroke=0)


def cover(c: canvas.Canvas) -> None:
    c.setFillColor(INK)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    c.setFillColor(ROSE)
    c.rect(0, 0, 16, PAGE_H, fill=1, stroke=0)
    pill(c, "8/11~8/20 · 10일 집중 유입", 56, PAGE_H - 72, YELLOW, INK, 9)
    draw_text(c, "채널별 마케팅\n실행 플랜", 56, PAGE_H - 120, 440, 40, FONT_XB, white, leading=44)
    draw_text(
        c,
        "최종 상품: 프로그램 1년 + 개인 강의 + 원격 과외 + 사용법 PDF",
        58,
        PAGE_H - 224,
        520,
        13,
        FONT_BOLD,
        HexColor("#F4B8C7"),
    )
    pill(c, "국내 쇼핑 제휴 7개 공식 지원", 58, PAGE_H - 257, MINT, INK, 8)

    # Hero target card
    rounded_box(c, 515, 275, 272, 205, PAPER, PAPER, 22, shadow=True)
    pill(c, "NORTH STAR", 540, 445, ROSE, white, 8)
    draw_text(c, "10일 안에\n결제 100건", 540, 408, 220, 31, FONT_XB, INK, leading=34)
    draw_text(c, "700,000원 × 100명 = 총매출 70,000,000원\n일평균 결제 10건 · 최종 라이브 8/20 20:30", 540, 324, 220, 9, FONT_SEMI, GRAY, leading=13)

    # Funnel strip
    y = 116
    items = [
        ("도달", "2.7M", YELLOW),
        ("프로필", "54K", MINT),
        ("체험", "4.3K", LILAC),
        ("상담", "600", CORAL),
        ("결제", "100", ROSE),
    ]
    x = 58
    for i, (label, value, color) in enumerate(items):
        rounded_box(c, x, y, 122, 80, color, color, 14)
        draw_text(c, label, x + 13, y + 56, 95, 8, FONT_BOLD, INK)
        draw_text(c, value, x + 13, y + 31, 95, 22, FONT_XB, INK)
        if i < len(items) - 1:
            draw_arrow(c, x + 125, y + 40, x + 145, HexColor("#777A85"))
        x += 148

    c.setFont(FONT_SEMI, 7.3)
    c.setFillColor(HexColor("#9EA1AB"))
    c.drawString(58, 83, "※ 위 퍼널 수치는 초기 가설입니다. D3·D7에 실제 계정 데이터로 재산정합니다.")
    c.setFont(FONT_BOLD, 8)
    c.setFillColor(white)
    c.drawRightString(PAGE_W - 40, 34, "THREAD AUTO / 쇼츠스레드메이커")
    c.showPage()


def executive_dashboard(c: canvas.Canvas, page_no: int) -> None:
    page_base(c, page_no, "EXECUTIVE DASHBOARD")
    title(c, "한 장 요약", "10일 동안 무엇을 만들고, 어디로 보내고, 무엇을 팔 것인가")

    cards = [
        ("판매 목표", "100건", "700,000원 × 100명", ROSE),
        ("콘텐츠", "240", "8채널 × 3개 × 10일", YELLOW),
        ("목표 매출", "7,000만원", "세금·수수료·환불 전 총매출", MINT),
        ("운영", "10일", "일평균 결제 10건", LILAC),
    ]
    x = M
    for name, value, note, color in cards:
        rounded_box(c, x, 365, 180, 104, color, INK, 14, 1.2, shadow=True)
        draw_text(c, name, x + 15, 443, 150, 8, FONT_BOLD, INK)
        draw_text(c, value, x + 15, 414, 150, 25, FONT_XB, INK)
        draw_text(c, note, x + 15, 386, 150, 7.6, FONT_SEMI, INK)
        x += 196

    rounded_box(c, M, 190, 480, 145, SOFT_WHITE, INK, 16, 1.2)
    draw_text(c, "전환 구조", M + 18, 309, 120, 13, FONT_XB, INK)
    flow = [
        ("문제 공감", "링크·글쓰기·다계정 피로"),
        ("실제 증명", "무편집 화면·과정 공개"),
        ("무료 체험", "기능 적합성 확인"),
        ("1:1 세팅", "본인 PC 첫 게시 완료"),
        ("70만원 패키지", "1년 + 강의 + 지원 + PDF"),
    ]
    fx = M + 18
    for i, (a, b) in enumerate(flow):
        fill = [YELLOW, MINT, LILAC, CORAL, ROSE][i]
        rounded_box(c, fx, 222, 80, 64, fill, fill, 11)
        draw_text(c, a, fx + 8, 267, 64, 8, FONT_BOLD, INK)
        draw_text(c, b, fx + 8, 248, 64, 6.3, FONT_SEMI, INK, leading=8, max_lines=2)
        if i < 4:
            draw_arrow(c, fx + 82, 254, fx + 96, ROSE)
        fx += 94

    rounded_box(c, 540, 190, 267, 145, INK, INK, 16)
    draw_text(c, "절대 흔들지 않을 원칙", 558, 309, 230, 13, FONT_XB, white)
    rules = [
        "첫 문장은 기능이 아니라 실패·상황으로 시작",
        "실제 화면과 실제 운영 기록만 증거로 사용",
        "무료 체험 → 1:1 진단 → 70만원 패키지의 CTA를 하나로 통일",
        "조회수보다 세팅·게시·결제 전환을 우선 판단",
    ]
    y = 283
    for idx, rule in enumerate(rules, 1):
        c.setFillColor([YELLOW, MINT, LILAC, CORAL][idx - 1])
        c.circle(568, y + 2, 8, fill=1, stroke=0)
        draw_centered(c, str(idx), 560, y - 1.2, 16, 7, FONT_XB, INK)
        draw_text(c, rule, 583, y + 5, 200, 7.8, FONT_SEMI, white, leading=10, max_lines=2)
        y -= 27

    rounded_box(c, M, 58, PAGE_W - 2 * M, 102, PAPER_2, PAPER_2, 14)
    draw_text(c, "이번 스프린트의 핵심 판단", M + 18, 133, 190, 10, FONT_XB, ROSE)
    draw_text(
        c,
        "콘텐츠를 많이 올리는 것 자체가 목표가 아니다. 공식 지원하는 7개 쇼핑 제휴 플랫폼 링크가 실제 게시 흐름으로 연결되는 장면을 증명하고, 무료 체험 사용자를 1:1 진단으로 이동시켜 70만원 패키지 100건을 결제로 닫는 것이 목표다.",
        M + 18,
        110,
        PAGE_W - 2 * M - 36,
        10,
        FONT_BOLD,
        INK,
        leading=15,
        max_lines=3,
    )
    c.showPage()


def market_voice_page(c: canvas.Canvas, page_no: int) -> None:
    page_base(c, page_no, "MARKET VOICE")
    title(c, "실제 시장 신호", "사람들은 ‘더 많은 정보’보다 실행·전환·안전을 힘들어한다")

    signals = [
        ("01", "클릭이 구매가 되지 않음", "한 2026년 자기보고 사례는 초기 0원~소액 구간과 매일 발행 부담을 함께 보여준다.", "단일 운영자 자기보고", YELLOW, "S1"),
        ("02", "강의를 듣고도 실행이 멈춤", "경쟁 강의 후기에서 숙제 확인·Q&A·피드백이 반복 칭찬된다. 실행지원 가치 가설을 지지하는 신호다.", "판매 페이지 구매 후기", MINT, "S2"),
        ("03", "연동 계정 안전이 걱정됨", "공식 정책은 무단 자동 접근과 스팸을 제한한다. 2023년 단일 VOC는 Instagram 연동 장애 우려의 언어를 보여준다.", "공식 정책 + 단일 VOC", LILAC, "S6·S7"),
        ("04", "프롬프트보다 완성 흐름이 필요", "자동화 판매 페이지들은 글 주제·예약·다계정·상태 확인을 한 흐름으로 묶는다. 실제 수요 규모는 별도 검증이 필요하다.", "경쟁사 자기 주장", CORAL, "S3·S11"),
    ]
    positions = [(M, 306), (430, 306), (M, 116), (430, 116)]
    for (no, name, desc, evidence, color, source), (x, y) in zip(signals, positions):
        rounded_box(c, x, y, 377, 165, SOFT_WHITE, INK, 15, 1.1, shadow=True)
        c.setFillColor(color)
        c.circle(x + 30, y + 130, 17, fill=1, stroke=0)
        draw_centered(c, no, x + 13, y + 126, 34, 8, FONT_XB, INK)
        draw_text(c, name, x + 58, y + 139, 285, 13, FONT_XB, INK)
        draw_text(c, desc, x + 18, y + 91, 340, 8.6, FONT_SEMI, INK, leading=13, max_lines=4)
        c.setStrokeColor(LIGHT_GRAY)
        c.line(x + 18, y + 43, x + 359, y + 43)
        draw_text(c, evidence, x + 18, y + 25, 235, 7, FONT_BOLD, GRAY)
        pill(c, source, x + 298, y + 15, color, INK, 6.5, pad_x=7, height=18)

    c.showPage()


def competitor_benchmark_page(c: canvas.Canvas, page_no: int) -> None:
    page_base(c, page_no, "COMPETITOR BENCHMARK")
    title(c, "경쟁 비교", "강의는 방법을 팔고, 자동화 도구는 편의를 판다")

    rows = [
        ("스레드 수익화 코칭", "69·139·169만원", "전자책/VOD/1:1 Q&A/특강", "수익화 방법 + 밀착 케어", "S2", ROSE),
        ("Threads 올인원 도구", "0.5·5.9·24.9만원", "예약/AI 글쓰기/다계정", "수동 작업 제거", "S3", YELLOW),
        ("Instagram 실습 강의", "39·77·99만원", "90분 1~3회/실습/피드백", "수업 중 콘텐츠 완성", "S4", MINT),
        ("Instagram 컨설팅", "8.5·30·85만원", "진단/편집/2~4주 관리", "계정별 문제 해결", "S5", LILAC),
        ("AI 자동화 키트", "할인가 약 12.2만원", "3시간/25클립/챗봇", "템플릿·도구 학습", "S8", CORAL),
    ]
    x0, table_w = M, PAGE_W - 2 * M
    col = [150, 125, 215, 220, 63]
    y = 437
    headers = ["유형", "공개 가격", "무엇을 제공", "핵심 약속", "근거"]
    c.setFillColor(INK)
    c.roundRect(x0, y, table_w, 31, 8, fill=1, stroke=0)
    x = x0
    for h, w in zip(headers, col):
        draw_text(c, h, x + 10, y + 20, w - 18, 8, FONT_BOLD, white)
        x += w
    y -= 65
    for name, price, offer, promise, src, color in rows:
        rounded_box(c, x0, y, table_w, 55, SOFT_WHITE, SOFT_WHITE, 10)
        c.setFillColor(color)
        c.roundRect(x0, y, 8, 55, 4, fill=1, stroke=0)
        vals = [name, price, offer, promise, src]
        x = x0
        for idx, (val, w) in enumerate(zip(vals, col)):
            draw_text(c, val, x + 13, y + 36, w - 20, 8.3 if idx != 0 else 9.2, FONT_XB if idx == 0 else FONT_SEMI, INK, leading=11, max_lines=2)
            x += w
        y -= 63

    rounded_box(c, M, 62, 773, 69, INK, INK, 13)
    draw_text(c, "비어 있는 자리", M + 16, 106, 120, 9, FONT_XB, YELLOW)
    draw_text(c, "프롬프트·운영법만 가르치거나 설치만 주고 끝나지 않는다. ‘프로그램 12개월 + 개인 강의 + 사용법 원격 과외 + PDF 매뉴얼’을 70만원에 묶고, 국내 7개 쇼핑 제휴 플랫폼 링크를 한 흐름에 넣는 것이 차별화 지점이다.", M + 139, 106, 610, 8.7, FONT_BOLD, white, leading=12, max_lines=3)
    c.showPage()


def differentiation_page(c: canvas.Canvas, page_no: int) -> None:
    page_base(c, page_no, "POSITIONING", dark=True)
    title(c, "핵심 차별점", "프롬프트를 배우는 대신, 반복 실행 흐름을 사용한다", "정확한 표현은 ‘무검수 완전 자동’이 아니라 ‘사람 승인형 풀플로우’다.", dark=True)

    # Comparison cards
    rounded_box(c, M, 284, 348, 179, HexColor("#1C1E27"), HexColor("#444753"), 16)
    pill(c, "일반 강의·전자책", M + 18, 426, LILAC, INK, 8)
    draw_text(c, "배우고 → 만들고 → 반복", M + 18, 390, 300, 18, FONT_XB, white)
    manual = ["프롬프트 구조를 직접 익힘", "매일 소재·문안·계정을 직접 관리", "실행이 멈추면 정보가 있어도 성과가 없음"]
    y = 354
    for i, item in enumerate(manual):
        c.setFillColor([LILAC, CORAL, YELLOW][i])
        c.circle(M + 22, y + 2, 4, fill=1, stroke=0)
        draw_text(c, item, M + 35, y + 5, 285, 8.2, FONT_SEMI, HexColor("#D5D7DE"), max_lines=1)
        y -= 27

    rounded_box(c, 425, 284, 382, 179, PAPER, PAPER, 16, shadow=True)
    pill(c, "우리 패키지", 443, 426, ROSE, white, 8)
    draw_text(c, "설정하고 → 검수하고 → 실행", 443, 390, 335, 18, FONT_XB, INK)
    ours = ["프롬프트를 직접 만들 필요 없음", "공식 지원 7개 제휴 플랫폼을 한 Threads 흐름에 적용", "1:1 세팅에서 본인 상품의 첫 게시까지 완료"]
    y = 354
    for i, item in enumerate(ours):
        c.setFillColor([MINT, YELLOW, ROSE][i])
        c.circle(447, y + 2, 4, fill=1, stroke=0)
        draw_text(c, item, 460, y + 5, 315, 8.3, FONT_BOLD, INK, max_lines=1)
        y -= 27

    # Flow
    stages = [
        ("제휴 링크", "입력", YELLOW),
        ("상품", "분석", MINT),
        ("문안 4종", "생성", LILAC),
        ("이미지", "확인", CORAL),
        ("계정별", "대기열", BLUE),
        ("사람", "최종 검수", ROSE),
        ("Threads", "게시", YELLOW),
    ]
    x = M
    y = 203
    for i, (a, b, color) in enumerate(stages):
        rounded_box(c, x, y, 92, 61, color, color, 11)
        draw_text(c, a, x + 10, y + 42, 72, 8, FONT_XB, INK if color != BLUE and color != ROSE else white)
        draw_text(c, b, x + 10, y + 20, 72, 9, FONT_BOLD, INK if color != BLUE and color != ROSE else white)
        if i < len(stages) - 1:
            draw_arrow(c, x + 94, y + 31, x + 107, ROSE)
        x += 111

    rounded_box(c, M, 65, 773, 108, HexColor("#1C1E27"), HexColor("#444753"), 14)
    draw_text(c, "장점", M + 17, 147, 60, 9, FONT_XB, MINT)
    draw_text(c, "학습 부담↓ · 첫 결과까지 시간↓ · 공식 지원 7개 제휴 플랫폼 · 다계정 상태 확인", M + 75, 147, 670, 8.4, FONT_BOLD, white)
    draw_text(c, "단점", M + 17, 116, 60, 9, FONT_XB, CORAL)
    draw_text(c, "AI 초안 오류 · 플랫폼 변경/로그인 의존 · 제휴사별 링크/고지 규칙 차이 · 자동화가 매출을 보장하지는 않음", M + 75, 116, 670, 8.4, FONT_BOLD, white)
    draw_text(c, "대응", M + 17, 85, 60, 9, FONT_XB, YELLOW)
    draw_text(c, "사람 승인 단계 · 제휴사별 고지 템플릿 · 링크 사전 테스트 · 업데이트/오류 로그 · 중단 조건 공개", M + 75, 85, 670, 8.4, FONT_BOLD, white)
    c.showPage()


def support_platforms_page(c: canvas.Canvas, page_no: int) -> None:
    page_base(c, page_no, "7 PLATFORM SUPPORT", dark=True)
    title(
        c,
        "7개 플랫폼 공식 지원",
        "쿠팡 전용이 아니다: 국내 쇼핑 제휴 7곳을 한 흐름으로",
        "각 제휴사의 링크·고지 규칙은 게시 전 사람이 최종 확인한다",
        dark=True,
    )

    cards = [
        ("01", "쿠팡파트너스", "쿠팡 상품 제휴 링크", YELLOW),
        ("02", "네이버 쇼핑커넥트", "네이버 쇼핑 제휴 링크", MINT),
        ("03", "토스쇼핑 파트너스", "토스쇼핑 제휴 링크", LILAC),
        ("04", "오늘의집 큐레이터", "홈·리빙 상품 제휴 링크", CORAL),
        ("05", "무신사 파트너스", "패션 상품 제휴 링크", BLUE),
        ("06", "컬리 큐레이터", "식품·생활 상품 제휴 링크", ROSE),
        ("07", "올리브영 큐레이터", "뷰티·헬스 상품 제휴 링크", YELLOW),
    ]
    positions = []
    for idx in range(4):
        positions.append((M + idx * 193, 318, 181))
    for idx in range(3):
        positions.append((126 + idx * 215, 200, 199))

    for (no, name, desc, color), (x, y, width) in zip(cards, positions):
        rounded_box(c, x, y, width, 96, HexColor("#1D2029"), HexColor("#454956"), 14)
        pill(c, no, x + 13, y + 65, color, INK if color not in (ROSE, BLUE) else white, 7)
        draw_text(c, name, x + 14, y + 53, width - 28, 10.2, FONT_XB, white, leading=13, max_lines=2)
        draw_text(c, desc, x + 14, y + 19, width - 28, 7.2, FONT_SEMI, HexColor("#C9CBD3"), max_lines=1)

    rounded_box(c, M, 60, 773, 104, PAPER, PAPER, 15)
    draw_text(c, "공통 실행 흐름", M + 18, 137, 120, 10, FONT_XB, ROSE)
    flow = "제휴 링크 입력 → 상품 분석 → 문안 4종 → 이미지·고지 확인 → 계정별 대기열 → 사람 승인 → Threads 게시"
    draw_text(c, flow, M + 18, 111, 735, 11.5, FONT_XB, INK, leading=15, max_lines=2)
    draw_text(c, "대표 후킹: ‘쿠팡 하나 때문에 사는 프로그램이 아닙니다. 지금 쓰는 쇼핑 제휴 링크 7곳을 한 프로그램에서 운영합니다.’", M + 18, 78, 735, 8.2, FONT_BOLD, GRAY, max_lines=1)
    c.showPage()


def offer_page(c: canvas.Canvas, page_no: int) -> None:
    page_base(c, page_no, "OFFER DESIGN", dark=True)
    title(c, "판매 제안", "70만원에 사용권·강의·원격 과외·PDF를 한 번에 묶는다", "고객은 프롬프트 지식이 아니라 실제 사용과 문제 해결까지 포함된 1년 패키지를 산다.", dark=True)

    # Value stack
    components = [
        ("01", "프로그램 12개월", "쿠팡·네이버·토스·오늘의집·무신사·컬리·올리브영 제휴 링크를 반복 게시 흐름에 적용", YELLOW),
        ("02", "1:1 개인 강의", "권장 90분: 설치·로그인·제휴 링크·문안·대기열·고지·첫 게시까지 실제 화면으로 완료", MINT),
        ("03", "사용법 원격 과외", "사용 중 막히는 구간을 화면 공유로 해결. 예약 방식·횟수·응답 시간은 판매 전에 명확히 공개", LILAC),
        ("04", "사용법 전자책 PDF", "설치·첫 실행·링크 입력·검수·오류 대처·제휴 고지·FAQ를 스스로 다시 확인", CORAL),
    ]
    y = 378
    for no, name, desc, color in components:
        rounded_box(c, M, y, 474, 48, HexColor("#1C1E27"), HexColor("#444753"), 11)
        c.setFillColor(color)
        c.circle(M + 25, y + 24, 12, fill=1, stroke=0)
        draw_centered(c, no, M + 13, y + 21, 24, 7, FONT_XB, INK)
        draw_text(c, name, M + 47, y + 36, 175, 9.8, FONT_XB, white)
        draw_text(c, desc, M + 47, y + 18, 403, 6.9, FONT_SEMI, HexColor("#C9CBD3"), leading=8.4, max_lines=2)
        y -= 56

    # Pricing card
    rounded_box(c, 540, 250, 267, 180, PAPER, PAPER, 18, shadow=True)
    pill(c, "확정 판매가", 559, 395, ROSE, white, 7.5)
    draw_text(c, "4가지 구성 전체 포함", 559, 363, 180, 8, FONT_BOLD, GRAY)
    draw_text(c, "700,000원", 559, 332, 220, 24, FONT_XB, INK)
    draw_text(c, "1년 사용권 · 개인 강의 · 원격 과외 · PDF", 559, 305, 220, 7.8, FONT_SEMI, GRAY)
    c.setStrokeColor(LIGHT_GRAY)
    c.line(559, 290, 788, 290)
    draw_text(c, "목표", 559, 272, 60, 8, FONT_BOLD, ROSE)
    draw_text(c, "100명 × 70만원 = 7,000만원", 612, 272, 176, 10.5, FONT_XB, INK)

    rounded_box(c, M, 75, 773, 130, HexColor("#1C1E27"), HexColor("#444753"), 16)
    draw_text(c, "공개 문구 구조", M + 20, 180, 140, 12, FONT_XB, white)
    quote = "프롬프트를 배우고 매일 직접 조립하는 강의가 아닙니다. 공식 지원 7개 쇼핑 제휴 링크를 넣어 쓰는 프로그램 1년과 개인 강의·원격 과외·PDF를 전부 포함합니다."
    draw_text(c, quote, M + 20, 151, 470, 12, FONT_BOLD, HexColor("#F8CAD5"), leading=18, max_lines=4)
    rounded_box(c, 548, 94, 239, 91, ROSE, ROSE, 13)
    draw_text(c, "단일 CTA", 566, 161, 100, 8, FONT_BOLD, white)
    draw_text(c, "무료 체험 후\n첫 게시 진단 신청", 566, 137, 190, 18, FONT_XB, white, leading=22)
    c.showPage()


def funnel_page(c: canvas.Canvas, page_no: int) -> None:
    page_base(c, page_no, "FUNNEL & KPI")
    title(c, "숫자 설계", "70만원 패키지 100건을 만들기 위한 역산 퍼널")

    stages = [
        ("도달/재생", 2700000, "콘텐츠·공동 노출", YELLOW),
        ("프로필 방문", 54000, "2.0%", MINT),
        ("랜딩 방문", 21600, "40%", LILAC),
        ("무료 체험", 4320, "20%", CORAL),
        ("유효 상담", 600, "13.9%", BLUE),
        ("결제", 100, "16.7%", ROSE),
    ]
    max_w = 690
    y = 430
    for i, (name, val, rate, color) in enumerate(stages):
        w = max(108, max_w * (0.79 ** i))
        x = M + (max_w - w) / 2
        rounded_box(c, x, y, w, 48, color, color, 10)
        draw_text(c, name, x + 14, y + 31, 135, 8, FONT_BOLD, INK if color != BLUE and color != ROSE else white)
        draw_text(c, f"{val:,}", x + w - 115, y + 31, 100, 13, FONT_XB, INK if color != BLUE and color != ROSE else white)
        draw_text(c, rate, x + w - 115, y + 13, 100, 7, FONT_SEMI, INK if color != BLUE and color != ROSE else white)
        y -= 57

    rounded_box(c, 607, 95, 200, 150, INK, INK, 16)
    draw_text(c, "리드 자격 조건", 625, 221, 160, 12, FONT_XB, white)
    quals = [
        "지원 7개 제휴 플랫폼 중 하나 이상을 운영 중",
        "Windows 환경에서 프로그램 사용 가능",
        "반복 작업 또는 다계정 문제를 실제로 느낌",
        "70만원 예산과 1년 운영 의사가 있음",
    ]
    qy = 194
    for q in quals:
        c.setFillColor(MINT)
        c.circle(628, qy + 2, 3, fill=1, stroke=0)
        draw_text(c, q, 638, qy + 5, 145, 7.1, FONT_SEMI, white, leading=9, max_lines=2)
        qy -= 27

    rounded_box(c, M, 58, 540, 85, PAPER_2, PAPER_2, 13)
    draw_text(c, "D3 · D7 · D10 판단 규칙", M + 15, 119, 190, 9.5, FONT_XB, ROSE)
    draw_text(c, "100건은 기존 3건 모델의 약 33배다. 자연 유입 콘텐츠만으로 부족하면 추천 파트너·커뮤니티 데모를 확대한다. DAY 3에 일 10건 속도를 점검하고, 마지막 DAY 10 라이브에 상담과 결제를 집중한다.", M + 15, 96, 505, 8.4, FONT_SEMI, INK, leading=12, max_lines=3)
    c.showPage()


def channel_matrix(c: canvas.Canvas, page_no: int) -> None:
    page_base(c, page_no, "CHANNEL STRATEGY")
    title(c, "채널 역할", "모든 채널에 같은 글을 복사하지 않는다")

    rows = [
        ("Threads", "대화·댓글", "3개/일", "공감 → A/B → 실제 화면/CTA", "댓글·프로필 방문", ROSE),
        ("Instagram", "브랜드·증명", "3개/일", "Reel → Carousel → Story", "저장·링크 클릭", YELLOW),
        ("TikTok", "신규 도달", "3개/일", "원테이크 → 분할 비교 → 실제 화면", "완료율·프로필", MINT),
        ("YouTube", "검색 누적", "3개/일", "Short 2개 + Community 1개", "평균 시청·검색 유입", LILAC),
        ("Naver Blog", "검토·신뢰", "3개/일", "핵심 장문 → 비교 → FAQ", "검색·체험 클릭", CORAL),
        ("Facebook", "상세 설명", "3개/일", "Reel → 이미지 경험담 → 장문", "링크 클릭·문의", BLUE),
    ]

    x0, table_w = M, PAGE_W - 2 * M
    col = [105, 118, 90, 250, 137]
    y = 445
    headers = ["채널", "주 역할", "강도", "콘텐츠 방식", "판단 지표"]
    c.setFillColor(INK)
    c.roundRect(x0, y, table_w, 30, 8, fill=1, stroke=0)
    x = x0
    for h, w in zip(headers, col):
        draw_text(c, h, x + 10, y + 19, w - 18, 8, FONT_BOLD, white)
        x += w
    y -= 56
    for channel, role, volume, method, metric, color in rows:
        c.setFillColor(SOFT_WHITE)
        c.roundRect(x0, y, table_w, 47, 9, fill=1, stroke=0)
        c.setFillColor(color)
        c.roundRect(x0, y, 8, 47, 4, fill=1, stroke=0)
        vals = [channel, role, volume, method, metric]
        x = x0
        for idx, (val, w) in enumerate(zip(vals, col)):
            draw_text(c, val, x + 12, y + 31, w - 18, 8 if idx != 0 else 9, FONT_XB if idx == 0 else FONT_SEMI, INK, leading=10, max_lines=2)
            x += w
        y -= 55

    rounded_box(c, M, 57, table_w, 47, PAPER_2, PAPER_2, 12)
    draw_text(c, "우선순위", M + 15, 86, 80, 8, FONT_XB, ROSE)
    draw_text(c, "Threads·Instagram에 운영 시간 55% → TikTok·YouTube 25% → Naver Blog 15% → Facebook 5%", M + 93, 86, 650, 9, FONT_BOLD, INK)
    c.showPage()


def extended_channels_page(c: canvas.Canvas, page_no: int) -> None:
    page_base(c, page_no, "WEB · CLASS · COMMUNITY")
    title(c, "전환 채널", "강의·웹·커뮤니티는 ‘설명’이 아니라 불안을 제거한다")

    cards = [
        ("YouTube Long-form", "주 2편", "5~8분 무편집 시연", "링크 입력부터 게시·오류·검수까지 보여준다. 제목은 ‘프롬프트 없이 실제 게시까지’.", YELLOW),
        ("단 한 번 라이브", "D10 · 20:30", "60분 무료 실전 강의", "교육·무편집 시연 40분 → Q&A 10분 → 가격·지원·환불을 공개하는 오퍼·행동 10분.", MINT),
        ("웹 / 랜딩", "항상", "비교·FAQ·신청", "강의형 vs 프로그램형 비교, 지원 SLA, Windows 조건, 환불·해지, 추가 비용을 결제 전에 공개.", LILAC),
        ("커뮤니티", "주 3회", "체크리스트·실패 로그", "링크부터 뿌리지 않고 질문에 답한다. 타 카페 자동 댓글·방문·도배는 운영안에서 제외.", CORAL),
        ("강의 마켓", "1개 상품", "패키지 검증", "‘강의 90분’ 대신 ‘첫 게시 세팅 완료’ 산출물을 판매. 판매 페이지 후기는 독립 성과가 아님을 인지.", ROSE),
        ("이메일 / 카카오", "체험 후", "D0·D1·D3·D9·D10", "설치 → 첫 작업 → 오류 → 라이브 예고 → 마지막 라이브의 순서로만 메시지 전송.", BLUE),
    ]
    positions = [(M, 290), (302, 290), (570, 290), (M, 100), (302, 100), (570, 100)]
    for (name, volume, mode, desc, color), (x, y) in zip(cards, positions):
        rounded_box(c, x, y, 237, 160, SOFT_WHITE, INK, 14, 1, shadow=True)
        c.setFillColor(color)
        c.roundRect(x, y + 118, 237, 42, 14, fill=1, stroke=0)
        c.rect(x, y + 118, 237, 18, fill=1, stroke=0)
        draw_text(c, name, x + 13, y + 140, 155, 10.5, FONT_XB, INK if color not in (ROSE, BLUE) else white)
        draw_text(c, volume, x + 169, y + 140, 55, 7, FONT_BOLD, INK if color not in (ROSE, BLUE) else white)
        draw_text(c, mode, x + 13, y + 96, 205, 8.5, FONT_XB, ROSE)
        draw_text(c, desc, x + 13, y + 72, 207, 7.8, FONT_SEMI, INK, leading=11, max_lines=5)

    c.showPage()


def free_class_benchmark_page(c: canvas.Canvas, page_no: int) -> None:
    page_base(c, page_no, "FREE CLASS RESEARCH")
    title(c, "무료 첫 강의 벤치마크", "등록을 모으는 강의는 정보보다 작은 성공 경험을 먼저 준다")
    rows = [
        ("등록", "문제·대상·얻을 결과·시간·녹화 여부·CTA 1개", "‘링크 1개를 실제 게시까지 보내며 내 작업에 맞는지 판단’", YELLOW),
        ("도입", "긴 소개 대신 오늘 산출물과 질문 방식부터 공지", "3분 안에 수익 비보장·무편집 데모·오류 공개 선언", MINT),
        ("교육", "핵심 원리 1개와 퀵윈 1개를 무료 수업 안에서 완결", "수작업 5단계와 프롬프트 강의 vs 프로그램의 차이", LILAC),
        ("시연", "실제 화면·실시간 질문·실패 케이스로 불확실성 감소", "링크→문안 4종→고지→Threads 공개 게시와 오류 로그", CORAL),
        ("오퍼", "대상·제공물·가격·지원·환불을 숨기지 않고 공개", "1년·90분·원격 과외·PDF·70만원·100명 운영 한도", ROSE),
    ]
    y = 397
    for phase, common, ours, color in rows:
        rounded_box(c, M, y, 773, 58, SOFT_WHITE, INK, 11, 1, shadow=True)
        pill(c, phase, M + 14, y + 31, color, INK if color != ROSE else white, 7.2)
        draw_text(c, "공개 가이드", M + 93, y + 42, 78, 6.8, FONT_XB, GRAY)
        draw_text(c, common, M + 176, y + 42, 575, 7.9, FONT_BOLD, INK, max_lines=1)
        draw_text(c, "우리 설계", M + 93, y + 20, 78, 6.8, FONT_XB, ROSE)
        draw_text(c, ours, M + 176, y + 20, 575, 7.9, FONT_SEMI, INK, max_lines=1)
        y -= 64
    rounded_box(c, M, 50, 773, 67, INK, INK, 12)
    draw_text(c, "근거 한계", M + 14, 94, 72, 8, FONT_XB, YELLOW)
    draw_text(c, "‘교육 70%·판매 30%’ 같은 공식 표준은 확인되지 않았다. 60분 구성을 파일럿으로 운영하고 출석·체류·클릭·결제·환불·실행률로 검증한다.", M + 92, 95, 660, 8.2, FONT_BOLD, white, leading=11, max_lines=2)
    draw_link(c, "HubSpot webinar guide", "https://blog.hubspot.com/blog/tabid/6307/bid/2391/10-best-practices-for-webinars-or-webcasts.aspx", M + 92, 61, 190, 6.2)
    draw_link(c, "Zoom webinar settings", "https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0057935", M + 295, 61, 180, 6.2)
    draw_link(c, "Thinkific lead magnet", "https://support.thinkific.com/hc/en-us/articles/24980364410263-Use-Coaching-Webinars-as-Lead-Magnets", M + 488, 61, 180, 6.2)
    draw_link(c, "Teachable free content", "https://www.teachable.com/blog/the-case-for-free-content-in-an-online-course-launch", M + 681, 61, 95, 6.2)
    c.showPage()


def korean_free_class_examples_page(c: canvas.Canvas, page_no: int) -> None:
    page_base(c, page_no, "KOREAN PUBLIC EXAMPLES")
    title(c, "한국 공개 무료 강의에서 가져올 것", "수익 숫자가 아니라 진행 순서와 무료·유료의 경계를 참고한다")
    cards = [
        ("로알남 무료 과정", "과장광고 비판 → 16분 기본 세팅 → 최적화 → 유료 수익화", "무료 안에서 기본 세팅을 끝내고, 고급 수익화는 다음 단계로 분리", "https://presslearn.co.kr/class?lectureId=9993", YELLOW),
        ("인프런 A1 라이브", "이전 버전 비교 → 구현 구조 → 다채널 기술 이슈 → Q&A", "완벽한 결과만 말하지 않고 구조·변경·확장 문제를 실제로 공개", "https://www.inflearn.com/notices/1834698", MINT),
        ("AI 콘텐츠 웨비나", "팔로워만 늘어도 돈은 안 됨 → 3대 문제 → AI 시스템 → 가이드", "수익 약속 전에 시장·제품·시간·실행의 병목을 먼저 진단", "https://luma.com/vt91dnf6", LILAC),
        ("쿠팡 무료 설명회", "부업 훅 → 시작 장벽 → 자동화 시스템 → 수익 사례 → Q&A", "순서는 참고하되 수익 사례는 외부 검증 전 마케팅 증거로 사용하지 않음", "https://point.topzone.co.kr/bluerose/channel/muhan", CORAL),
    ]
    positions = [(M, 290), (430, 290), (M, 99), (430, 99)]
    for (name, flow, take, url, color), (x, y) in zip(cards, positions):
        rounded_box(c, x, y, 377, 163, SOFT_WHITE, INK, 14, 1, shadow=True)
        c.setFillColor(color)
        c.roundRect(x, y + 121, 377, 42, 14, fill=1, stroke=0)
        c.rect(x, y + 121, 377, 18, fill=1, stroke=0)
        draw_text(c, name, x + 15, y + 144, 245, 11, FONT_XB, INK)
        draw_text(c, "확인된 순서", x + 15, y + 101, 80, 7, FONT_XB, ROSE)
        draw_text(c, flow, x + 97, y + 102, 260, 7.8, FONT_SEMI, INK, leading=10.5, max_lines=2)
        draw_text(c, "우리 적용", x + 15, y + 62, 80, 7, FONT_XB, ROSE)
        draw_text(c, take, x + 97, y + 63, 260, 7.8, FONT_BOLD, INK, leading=10.5, max_lines=3)
        draw_link(c, url.replace("https://", ""), url, x + 15, y + 19, 340, 6.3)
    rounded_box(c, M, 50, 773, 37, INK, INK, 10)
    draw_text(c, "해석", M + 14, 74, 42, 8, FONT_XB, YELLOW)
    draw_text(c, "공개 커리큘럼·행사 공지로 순서를 확인했을 뿐, 강사·주최자의 수익·조회·참석 성과는 독립 검증 자료가 아니다.", M + 62, 75, 690, 8.1, FONT_BOLD, white)
    c.showPage()


def live_conversion_blueprint_page(c: canvas.Canvas, page_no: int) -> None:
    page_base(c, page_no, "FINAL LIVE BLUEPRINT", dark=True)
    title(c, "DAY 10 · 20:30~21:30", "한 번의 무료 실전 강의에서 교육·증명·질문·전환을 닫는다", dark=True)
    rows = [
        ("00~03", "약속", "수익이 아니라 링크→실제 게시를 검증", YELLOW),
        ("03~08", "폴", "문구·이미지·업로드·다계정 중 병목 선택", MINT),
        ("08~15", "교육", "수작업 5단계·시간값·프롬프트 강의와 차이", LILAC),
        ("15~30", "데모", "권리 확인 링크→문안 4종→고지→공개 게시", CORAL),
        ("30~35", "실패", "로그인 만료·이미지 없음·중복 링크", BLUE),
        ("35~40", "예고", "기능 경계·적합/부적합·70만원 첫 공개", MINT),
        ("40~50", "Q&A", "업보트 상위 질문·가격·계정·지원 반론", LILAC),
        ("50~58", "오퍼", "제공물·공급·지원·환불·수익 비보장", ROSE),
        ("58~60", "행동", "내 작업 적합성 확인 CTA 1개", YELLOW),
    ]
    y = 426
    for time, part, desc, color in rows:
        rounded_box(c, M, y, 773, 32, HexColor("#1D2029"), HexColor("#454956"), 8)
        pill(c, time, M + 12, y + 7, color, INK if color not in (ROSE, BLUE) else white, 6.5, height=18)
        draw_text(c, part, M + 91, y + 22, 65, 7.8, FONT_XB, white)
        draw_text(c, desc, M + 160, y + 22, 595, 7.3, FONT_SEMI, HexColor("#D7D9E0"), max_lines=1)
        y -= 37
    rounded_box(c, M, 50, 773, 49, PAPER, PAPER, 11)
    draw_text(c, "왜 60분인가", M + 14, 80, 85, 8, FONT_XB, ROSE)
    draw_text(c, "70만원 상품을 단 한 번의 라이브로 판단하려면 실제 데모와 질문 시간이 모두 필요하다. 최적 길이라는 뜻은 아니며 40분·60분 코호트로 비교한다.", M + 105, 81, 645, 8.1, FONT_BOLD, INK, leading=11, max_lines=2)
    c.showPage()


def live_measurement_page(c: canvas.Canvas, page_no: int) -> None:
    page_base(c, page_no, "LIVE OPERATIONS & METRICS")
    title(c, "리마인드·후속·측정", "결제만 보지 말고 참석·체류·환불·실행까지 연결한다")
    flow = [
        ("등록 즉시", "캘린더·접속 링크·산출물·사전 질문", YELLOW),
        ("24시간 전", "준비물 1개·무편집 데모·참석 이유", MINT),
        ("1시간 전", "짧은 접속 링크·20:30 정시·질문 안내", LILAC),
        ("종료 1~24h", "참석/불참 분리·자료·타임스탬프·리플레이", CORAL),
    ]
    x = M
    for when, action, color in flow:
        rounded_box(c, x, 355, 180, 111, color, INK, 14, 1, shadow=True)
        draw_text(c, when, x + 14, 442, 150, 9, FONT_XB, INK)
        draw_text(c, action, x + 14, 409, 150, 8, FONT_SEMI, INK, leading=11, max_lines=3)
        x += 196

    rounded_box(c, M, 138, 480, 177, SOFT_WHITE, INK, 15)
    draw_text(c, "라이브 퍼널 기록", M + 17, 289, 180, 12, FONT_XB, INK)
    metrics = [
        "등록 → 실제 출석 → 25% / 50% / 75% 체류",
        "폴 응답 → 질문 제출 → 데모 완료 시청",
        "적합성 CTA 클릭 → 체험 시작 → 상담 → 결제",
        "7일 취소·환불 → 14일 실제 발행 지속률",
    ]
    y = 255
    for idx, metric in enumerate(metrics, 1):
        c.setFillColor([YELLOW, MINT, LILAC, CORAL][idx - 1])
        c.circle(M + 27, y + 2, 8, fill=1, stroke=0)
        draw_centered(c, str(idx), M + 19, y - 1, 16, 6.5, FONT_XB, INK)
        draw_text(c, metric, M + 44, y + 6, 405, 8.2, FONT_BOLD, INK)
        y -= 32

    rounded_box(c, 540, 138, 267, 177, INK, INK, 15)
    draw_text(c, "결제 전 공개", 558, 289, 150, 12, FONT_XB, white)
    disclosures = [
        "700,000원·세금/결제 조건",
        "1년 사용의 정확한 권한·공급 시기",
        "90분 강의·원격 과외 횟수/SLA",
        "환불·해지·지원 제외·분쟁 처리",
        "수익·조회·계정 안전 비보장",
    ]
    y = 255
    for i, item in enumerate(disclosures):
        c.setFillColor([YELLOW, MINT, LILAC, CORAL, ROSE][i])
        c.circle(562, y + 2, 3.5, fill=1, stroke=0)
        draw_text(c, item, 575, y + 6, 205, 7.8, FONT_SEMI, white, max_lines=1)
        y -= 26

    rounded_box(c, M, 51, 773, 57, PAPER_2, PAPER_2, 11)
    draw_text(c, "법·근거", M + 14, 87, 58, 8, FONT_XB, ROSE)
    draw_link(c, "전자상거래법 제13조", "https://www.law.go.kr/LSW/lsLinkCommonInfo.do?chrClsCd=010202&lsJoLnkSeq=1027062829", M + 78, 87, 150, 6.5)
    draw_link(c, "Zoom email settings", "https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0065074", M + 243, 87, 150, 6.5)
    draw_link(c, "Goldcast 2026 benchmark", "https://www.goldcast.io/reports/b2b-webinar-benchmark-report-2026", M + 408, 87, 165, 6.5)
    draw_text(c, "리마인드 타이밍과 60분 구성은 표준 기능·관측자료를 바탕으로 한 실험안이며 국내 전환 최적값이 아니다.", M + 78, 68, 680, 7, FONT_SEMI, GRAY)
    c.showPage()


def calendar_page(c: canvas.Canvas, page_no: int) -> None:
    page_base(c, page_no, "10-DAY CALENDAR")
    title(c, "실행 캘린더", "10일 동안 궁금증을 쌓고 마지막 라이브로 닫는다")

    days = [
        (1, "첫 문장\n40분", "문제 공감", "COLD"),
        (2, "프롬프트\n피로", "시간 절감", "COLD"),
        (3, "7개 제휴처\n한 번에", "지원 범위", "COLD"),
        (4, "링크부터\n대기열", "실제 흐름", "WARM"),
        (5, "70만원 vs\n41일", "시간 가치", "HOT"),
        (6, "승인형\n풀플로우", "자동/사람 경계", "WARM"),
        (7, "초보 PC\n첫 게시", "1:1 세팅", "WARM"),
        (8, "전자책·\n오류 해결", "자립 증명", "WARM"),
        (9, "100명 정원·\n라이브 예고", "기대 집중", "HOT"),
        (10, "마지막\n라이브", "공개·결제", "HOT"),
    ]
    card_w, card_h, gap = 102, 142, 8
    start_x, top_y = M, 325
    for idx, (day, topic, action, stage) in enumerate(days):
        row, col_idx = divmod(idx, 7)
        x = start_x + col_idx * (card_w + gap)
        y = top_y - row * (card_h + 15)
        stage_color = {"COLD": YELLOW, "WARM": MINT, "HOT": ROSE}[stage]
        rounded_box(c, x, y, card_w, card_h, SOFT_WHITE, INK, 12, 1, shadow=True)
        c.setFillColor(stage_color)
        c.roundRect(x, y + card_h - 27, card_w, 27, 12, fill=1, stroke=0)
        c.rect(x, y + card_h - 27, card_w, 12, fill=1, stroke=0)
        draw_text(c, f"DAY {day:02d}", x + 10, y + card_h - 17, 55, 7.5, FONT_XB, INK if stage != "HOT" else white)
        draw_text(c, stage, x + 67, y + card_h - 17, 28, 6.4, FONT_BOLD, INK if stage != "HOT" else white)
        draw_text(c, topic, x + 11, y + 86, 80, 13, FONT_XB, INK, leading=16, max_lines=2)
        draw_text(c, action, x + 11, y + 44, 80, 7.5, FONT_SEMI, GRAY, leading=10, max_lines=2)
        c.setStrokeColor(LIGHT_GRAY)
        c.line(x + 10, y + 31, x + card_w - 10, y + 31)
        draw_text(c, "핵심 CTA " + ("댓글" if stage == "COLD" else "저장/프로필" if stage == "WARM" else "체험/상담"), x + 10, y + 17, 82, 6.4, FONT_BOLD, ROSE)

    c.showPage()


def upload_schedule_page(c: canvas.Canvas, page_no: int) -> None:
    page_base(c, page_no, "DATE & UPLOAD TIME")
    title(c, "8/11~8/20 업로드 시간표", "한국시간 KST · 채널마다 20분 간격으로 세 번 배포한다")
    rows = [
        ("Threads", "08:30", "13:30", "19:30", "21:30 결과 글", ROSE),
        ("Instagram", "08:50", "13:50", "19:50", "21:40 Clip/Story", YELLOW),
        ("TikTok", "09:10", "14:10", "20:10", "21:50 Clip", LILAC),
        ("YouTube", "09:30", "14:30", "20:30", "20:30~21:30 LIVE", MINT),
        ("Naver Blog", "09:50", "14:50", "20:50", "22:20 요약/FAQ", CORAL),
        ("Facebook", "10:10", "15:10", "21:10", "22:00 Highlight", BLUE),
        ("커뮤니티", "10:30", "15:30", "21:30", "22:10 질문 회수", ROSE),
        ("강의 웹", "10:50", "15:50", "21:50", "21:35 구성/CTA", MINT),
    ]
    x0, y = M, 405
    widths = [135, 92, 92, 92, 362]
    headers = ["채널", "P1", "P2", "P3", "8/20 P3 예외"]
    c.setFillColor(INK)
    c.roundRect(x0, 442, 773, 31, 8, fill=1, stroke=0)
    x = x0
    for head, width in zip(headers, widths):
        draw_text(c, head, x + 10, 462, width - 16, 7.8, FONT_XB, white)
        x += width
    for channel, p1, p2, p3, final, color in rows:
        rounded_box(c, x0, y, 773, 35, SOFT_WHITE, INK, 8)
        c.setFillColor(color)
        c.roundRect(x0, y, 7, 35, 3, fill=1, stroke=0)
        vals = [channel, p1, p2, p3, final]
        x = x0
        for idx, (val, width) in enumerate(zip(vals, widths)):
            draw_text(c, val, x + 11, y + 23, width - 17, 7.6 if idx != 4 else 7.4, FONT_XB if idx == 0 else FONT_SEMI, INK, max_lines=1)
            x += width
        y -= 40

    dates = [
        ("D1", "8/11 화"), ("D2", "8/12 수"), ("D3", "8/13 목"), ("D4", "8/14 금"), ("D5", "8/15 토"),
        ("D6", "8/16 일"), ("D7", "8/17 월"), ("D8", "8/18 화"), ("D9", "8/19 수"), ("D10", "8/20 목"),
    ]
    x = M
    for idx, (day, dt) in enumerate(dates):
        if idx == 5:
            x = M
        row_y = 91 if idx < 5 else 51
        color = ROSE if day == "D10" else [YELLOW, MINT, LILAC, CORAL, BLUE][idx % 5]
        rounded_box(c, x, row_y, 145, 31, color, color, 8)
        draw_text(c, day, x + 10, row_y + 20, 30, 7.2, FONT_XB, INK if day != "D10" else white)
        draw_text(c, dt, x + 45, row_y + 20, 88, 7.5, FONT_BOLD, INK if day != "D10" else white)
        x += 157
    c.showPage()


def daily_engine_page(c: canvas.Canvas, page_no: int) -> None:
    page_base(c, page_no, "DAILY ENGINE")
    title(c, "운영 엔진", "하루 원본 3개를 8개 채널의 24회 배포로 확장한다")

    # Timeline
    events = [
        ("08:00", "원본 3개", "얼굴·비교·화면", ROSE),
        ("08:30", "P1 파동", "공감·문제", YELLOW),
        ("13:30", "P2 파동", "참여·비교", MINT),
        ("19:30", "P3 파동", "증명·전환", LILAC),
        ("22:10", "반응 회수", "댓글·FAQ", CORAL),
        ("22:30", "다음 대기열", "승자 훅 재사용", BLUE),
    ]
    x = M + 10
    y = 392
    for i, (tm, name, detail, color) in enumerate(events):
        rounded_box(c, x, y, 111, 76, color, color, 12)
        draw_text(c, tm, x + 11, y + 56, 85, 8, FONT_BOLD, INK if color != BLUE else white)
        draw_text(c, name, x + 11, y + 34, 88, 11, FONT_XB, INK if color != BLUE else white)
        draw_text(c, detail, x + 11, y + 15, 88, 7, FONT_SEMI, INK if color != BLUE else white)
        if i < len(events) - 1:
            draw_arrow(c, x + 113, y + 38, x + 130, ROSE)
        x += 130

    rounded_box(c, M, 180, 375, 171, SOFT_WHITE, INK, 15)
    draw_text(c, "하루 게시량", M + 17, 326, 150, 13, FONT_XB, INK)
    volumes = [
        ("Threads", 3, ROSE),
        ("Instagram", 3, YELLOW),
        ("YouTube", 3, MINT),
        ("TikTok", 3, LILAC),
        ("Naver Blog", 3, CORAL),
        ("Facebook", 3, BLUE),
        ("커뮤니티", 3, ROSE),
        ("강의 웹", 3, MINT),
    ]
    yy = 298
    for name, count, color in volumes:
        draw_text(c, name, M + 17, yy, 125, 7.3, FONT_BOLD, INK)
        c.setFillColor(LIGHT_GRAY)
        c.roundRect(M + 150, yy - 2, 150, 8, 4, fill=1, stroke=0)
        c.setFillColor(color)
        c.roundRect(M + 150, yy - 2, count / 5 * 150, 8, 4, fill=1, stroke=0)
        draw_text(c, str(count), M + 320, yy, 25, 8, FONT_XB, INK)
        yy -= 15.5

    rounded_box(c, 432, 180, 375, 171, INK, INK, 15)
    draw_text(c, "제작을 버티게 하는 재사용 규칙", 450, 326, 330, 13, FONT_XB, white)
    rules = [
        "P1은 얼굴·공감, P2는 A/B·체크리스트, P3는 실제 화면·CTA",
        "같은 원본도 Threads는 대화, Instagram은 저장, YouTube는 검색으로 변환",
        "커뮤니티에는 복사문과 첫 글 링크를 금지하고 답변형으로 다시 작성",
        "라이브는 마지막 DAY 10 한 번만 하고 9개 하이라이트로 재사용",
    ]
    yy = 295
    for i, rule in enumerate(rules):
        c.setFillColor([YELLOW, MINT, LILAC, CORAL][i])
        c.circle(458, yy + 1, 5, fill=1, stroke=0)
        draw_text(c, rule, 471, yy + 4, 300, 8.2, FONT_SEMI, white, leading=11, max_lines=2)
        yy -= 28

    rounded_box(c, M, 62, 773, 99, PAPER_2, PAPER_2, 14)
    draw_text(c, "10일 총량", M + 17, 135, 90, 10, FONT_XB, ROSE)
    totals = "Threads · Instagram · YouTube · TikTok · Blog · Facebook · Community · 강의 웹: 각 30개 = 총 240회"
    draw_text(c, totals, M + 17, 111, 735, 11, FONT_XB, INK)
    draw_text(c, "원본 기준: DAY별 강한 소재 3개, 총 30개. 채널별 문장·형식·표지를 바꿔 하루 24회 순차 배포한다.", M + 17, 86, 735, 8.3, FONT_SEMI, GRAY)
    c.showPage()


def playbooks_page(c: canvas.Canvas, page_no: int) -> None:
    page_base(c, page_no, "CORE PLAYBOOKS")
    title(c, "핵심 채널", "Threads는 대화, Instagram은 증명으로 설계한다")

    # Threads
    rounded_box(c, M, 78, 367, 376, INK, INK, 18)
    pill(c, "THREADS · 하루 3개", M + 18, 418, ROSE, white, 8)
    draw_text(c, "공감 → 참여 → 증거/CTA", M + 18, 389, 325, 18, FONT_XB, white)
    thread_posts = [
        ("09:00", "실패담", "링크 없이 ‘나도 그랬다’ 댓글 유도"),
        ("14:00", "A/B 질문", "설명형 vs 상황형 선택"),
        ("21:00", "실제 화면/CTA", "무료 체험 또는 진단 신청 하나만"),
    ]
    y = 345
    for i, (tm, typ, desc) in enumerate(thread_posts):
        c.setFillColor([YELLOW, MINT, LILAC, CORAL][i])
        c.roundRect(M + 18, y - 7, 53, 23, 11, fill=1, stroke=0)
        draw_centered(c, tm, M + 18, y, 53, 7, FONT_XB, INK)
        draw_text(c, typ, M + 83, y + 7, 90, 9, FONT_XB, white)
        draw_text(c, desc, M + 83, y - 10, 245, 7.3, FONT_SEMI, HexColor("#C9CBD3"), max_lines=1)
        y -= 58
    draw_text(c, "고정 훅 예시", M + 18, 121, 100, 8, FONT_XB, ROSE)
    draw_text(c, "“상품은 10분 만에 골랐는데 첫 문장에서 40분 멈췄다.”", M + 18, 101, 325, 10, FONT_BOLD, white, leading=13, max_lines=2)

    # Instagram
    rounded_box(c, 440, 78, 367, 376, SOFT_WHITE, INK, 18)
    pill(c, "INSTAGRAM · 하루 3개", 458, 418, YELLOW, INK, 8)
    draw_text(c, "Reel → Carousel → Story", 458, 389, 325, 18, FONT_XB, INK)
    blocks = [
        ("REEL", "09시", "얼굴·문제·반전", ROSE),
        ("CAROUSEL", "14시", "A/B·체크리스트", MINT),
        ("STORY", "21시", "결과·증거·링크", LILAC),
    ]
    y = 346
    for label, timing, desc, color in blocks:
        c.setFillColor(color)
        c.roundRect(458, y - 10, 59, 29, 8, fill=1, stroke=0)
        draw_centered(c, label, 458, y, 59, 7.2, FONT_XB, INK)
        draw_text(c, timing, 530, y + 7, 75, 8.5, FONT_XB, INK)
        draw_text(c, desc, 612, y + 7, 155, 8.2, FONT_SEMI, GRAY)
        y -= 46
    rounded_box(c, 458, 95, 331, 64, PAPER_2, PAPER_2, 11)
    draw_text(c, "표지 규칙", 472, 139, 75, 8, FONT_XB, ROSE)
    draw_text(c, "8단어 이내 · 첫 장에 기능표 금지 · 실제 화면에는 REAL SCREEN 표시", 472, 119, 295, 8, FONT_BOLD, INK, leading=11, max_lines=2)
    c.showPage()


def secondary_playbooks_page(c: canvas.Canvas, page_no: int) -> None:
    page_base(c, page_no, "SECONDARY PLAYBOOKS")
    title(c, "확장 채널", "도달·검색·검토를 각기 다른 방식으로 만든다")

    cards = [
        ("TikTok", "3개/일", "얼굴 원테이크·분할 비교·실제 화면. 각 12~20초, 첫 1초 질문 또는 반전.", "완료율 · 프로필 방문", MINT),
        ("YouTube", "3개/일", "Short 2개 + Community 1개. 검색어 제목과 실제 화면, 댓글 질문을 연결.", "평균 시청률 · 검색 유입", LILAC),
        ("Naver Blog", "3개/일", "핵심 장문 1개 + 비교 1개 + FAQ 1개. 동일 문장 복사를 피하고 검색 의도를 분리.", "검색 클릭 · 체험 전환", YELLOW),
        ("Facebook", "3개/일", "Reel 1개 + 이미지 경험담 1개 + 실제 화면 장문 1개. 가격·제한을 명확히 공개.", "링크 클릭 · 상담 문의", CORAL),
    ]
    positions = [(M, 285), (430, 285), (M, 91), (430, 91)]
    for (name, volume, desc, metric, color), (x, y) in zip(cards, positions):
        rounded_box(c, x, y, 377, 165, SOFT_WHITE, INK, 16, 1.2, shadow=True)
        c.setFillColor(color)
        c.roundRect(x, y + 121, 377, 44, 16, fill=1, stroke=0)
        c.rect(x, y + 121, 377, 20, fill=1, stroke=0)
        draw_text(c, name, x + 16, y + 144, 160, 15, FONT_XB, INK)
        draw_text(c, volume, x + 270, y + 144, 90, 8, FONT_BOLD, INK)
        draw_text(c, desc, x + 16, y + 96, 342, 8.7, FONT_SEMI, INK, leading=13, max_lines=4)
        c.setStrokeColor(LIGHT_GRAY)
        c.line(x + 16, y + 45, x + 360, y + 45)
        draw_text(c, "판단", x + 16, y + 27, 40, 7, FONT_XB, ROSE)
        draw_text(c, metric, x + 61, y + 27, 290, 7.5, FONT_BOLD, GRAY)
    c.showPage()


def content_system_page(c: canvas.Canvas, page_no: int) -> None:
    page_base(c, page_no, "CONTENT SYSTEM")
    title(c, "메시지 시스템", "3단계 인지도와 5개 콘텐츠 기둥")

    # Awareness ratios
    phases = [
        ("D1~D3", "발견", [70, 25, 5]),
        ("D4~D7", "증명", [50, 35, 15]),
        ("D8~D10", "전환", [25, 35, 40]),
    ]
    x = M
    for day, name, ratios in phases:
        rounded_box(c, x, 350, 240, 116, SOFT_WHITE, INK, 14)
        draw_text(c, day, x + 15, 443, 65, 8, FONT_BOLD, ROSE)
        draw_text(c, name, x + 15, 420, 120, 14, FONT_XB, INK)
        bx, by, bw = x + 15, 383, 210
        total = 0
        for ratio, color in zip(ratios, [YELLOW, MINT, ROSE]):
            seg = bw * ratio / 100
            c.setFillColor(color)
            c.rect(bx + total, by, seg, 13, fill=1, stroke=0)
            total += seg
        draw_text(c, f"Cold {ratios[0]}%  ·  Warm {ratios[1]}%  ·  Hot {ratios[2]}%", x + 15, 370, 210, 7.2, FONT_BOLD, GRAY)
        x += 258

    pillars = [
        ("문제 공감", "프롬프트·반복·계정 전환", YELLOW),
        ("교육", "승인형 흐름·검수·고지", MINT),
        ("증명", "수동 대비·무편집 시연", LILAC),
        ("신뢰", "한계·정책·오류 기록", CORAL),
        ("오퍼", "연간권·첫 게시 세팅", ROSE),
    ]
    x = M
    for name, desc, color in pillars:
        rounded_box(c, x, 198, 145, 112, color, INK, 13, 1, shadow=True)
        draw_text(c, name, x + 13, 280, 115, 11, FONT_XB, INK)
        draw_text(c, desc, x + 13, 250, 117, 8, FONT_SEMI, INK, leading=11, max_lines=3)
        x += 157

    rounded_box(c, M, 61, 773, 102, INK, INK, 14)
    draw_text(c, "훅 공식", M + 18, 136, 95, 10, FONT_XB, YELLOW)
    hooks = [
        "차별형: 프롬프트를 배우는 대신 링크 하나로 시작",
        "실수형: 계정 3개부터 같은 링크를 두 번 올리기 시작했다",
        "대조형: 강의 3시간 뒤 빈 화면 vs 세팅 90분 뒤 첫 게시",
        "반론형: 자동수익이 아니라 사람 승인형 풀플로우",
    ]
    hx = M + 18
    hy = 111
    for i, hook in enumerate(hooks):
        xcol = hx + (i % 2) * 376
        yrow = hy - (i // 2) * 27
        c.setFillColor([ROSE, MINT, LILAC, CORAL][i])
        c.circle(xcol + 4, yrow + 2, 4, fill=1, stroke=0)
        draw_text(c, hook, xcol + 14, yrow + 5, 345, 7.8, FONT_SEMI, white, max_lines=1)
    c.showPage()


def conversion_page(c: canvas.Canvas, page_no: int) -> None:
    page_base(c, page_no, "CONVERSION")
    title(c, "전환 운영", "댓글부터 결제까지 한 문장씩 다음 행동만 제시한다")

    steps = [
        ("댓글", "‘프로필에 실제 화면과 무료 체험을 올려뒀어요.’", YELLOW),
        ("DM", "‘지금 몇 개 계정·몇 개 상품을 운영하는지 알려주시면 맞는 흐름인지 먼저 말씀드릴게요.’", MINT),
        ("체험 후", "‘막힌 지점이 설치·문안·계정 운영 중 어디였나요?’", LILAC),
        ("진단", "현재 흐름 → 반복 비용 → 프로그램 적합성 → 첫 게시 세팅 범위 확인", CORAL),
        ("제안", "‘프롬프트 강의가 아니라 1년 이용권과 첫 게시 세팅을 묶은 패키지입니다. 조건을 확인하고 결정하세요.’", ROSE),
    ]
    y = 410
    for i, (name, copy, color) in enumerate(steps, 1):
        rounded_box(c, M + 30, y, 650, 55, SOFT_WHITE, INK, 12)
        c.setFillColor(color)
        c.circle(M + 7, y + 27, 21, fill=1, stroke=0)
        draw_centered(c, str(i), M - 14, y + 20, 42, 12, FONT_XB, INK if i < 5 else white)
        draw_text(c, name, M + 48, y + 35, 80, 9, FONT_XB, ROSE)
        draw_text(c, copy, M + 134, y + 36, 525, 8.2, FONT_SEMI, INK, leading=11, max_lines=2)
        if i < len(steps):
            c.setStrokeColor(ROSE)
            c.setLineWidth(2)
            c.line(M + 7, y - 1, M + 7, y - 15)
        y -= 63

    rounded_box(c, 725, 190, 82, 275, INK, INK, 13)
    draw_text(c, "상담\n종료\n조건", 742, 431, 50, 15, FONT_XB, white, leading=18)
    draw_text(c, "적합\n가격\n정원\n시작일\n환불·해지", 742, 340, 50, 8, FONT_BOLD, HexColor("#CFD1D8"), leading=24)
    pill(c, "한 번에", 736, 210, YELLOW, INK, 6.5, pad_x=7, height=18)

    rounded_box(c, M, 56, 773, 68, PAPER_2, PAPER_2, 12)
    draw_text(c, "금지", M + 15, 99, 42, 8, FONT_XB, ROSE)
    draw_text(c, "‘오늘만’, ‘몇 자리 안 남음’, ‘수익 보장’처럼 사실 확인이 안 되는 압박 문구. 정원은 실제 강의 가능 인원만 공개한다.", M + 61, 99, 690, 8.4, FONT_BOLD, INK, leading=12, max_lines=2)
    c.showPage()


def asset_audit_page(c: canvas.Canvas, page_no: int) -> None:
    page_base(c, page_no, "ASSET AUDIT")
    title(c, "기존 자산 판단", "잘 만든 소재도 새 오퍼와 충돌하면 수정한다")

    previews = [
        ROOT / "output" / "organic-launch-pack-v2" / "previews" / "instagram-carousel-preview.png",
        ROOT / "output" / "organic-launch-pack-v2" / "previews" / "threads-preview.png",
        ROOT / "output" / "organic-launch-pack-v2" / "previews" / "videos-preview.png",
    ]
    y_positions = [342, 215, 88]
    labels = [
        ("수정 후 사용", "캐러셀 6장: 마지막 장 ‘강의 말고’ 문구를 ‘무료 체험 후 1:1 진단’으로 교체", YELLOW),
        ("즉시 사용", "A/B·4관점·실제 화면 카드. 단, 프로필 CTA와 브랜드명을 현재 버전으로 통일", MINT),
        ("선별 사용", "문제 공감·실제 화면은 사용. ‘강의 안 팝니다’ 영상/스토리는 이번 캠페인에서 제외", CORAL),
    ]
    for path, y, (status, note, color) in zip(previews, y_positions, labels):
        rounded_box(c, M, y, 300, 105, white, INK, 12)
        if path.exists():
            img = ImageReader(str(path))
            iw, ih = img.getSize()
            scale = min(280 / iw, 87 / ih)
            w, h = iw * scale, ih * scale
            c.drawImage(img, M + 10, y + (105 - h) / 2, w, h, preserveAspectRatio=True, mask="auto")
        rounded_box(c, 355, y, 452, 105, SOFT_WHITE, INK, 12)
        pill(c, status, 373, y + 69, color, INK, 7.5)
        draw_text(c, note, 373, y + 48, 410, 8.8, FONT_BOLD, INK, leading=13, max_lines=3)

    c.showPage()


def measurement_page(c: canvas.Canvas, page_no: int) -> None:
    page_base(c, page_no, "MEASUREMENT")
    title(c, "성과판", "매일 30분, 같은 숫자만 기록한다")

    metrics = [
        ("도달", "조회/재생", "채널별", YELLOW),
        ("관심", "댓글·저장", "콘텐츠별", MINT),
        ("의도", "프로필 방문", "훅별", LILAC),
        ("행동", "체험 시작", "UTM별", CORAL),
        ("리드", "유효 상담", "상담 사유", BLUE),
        ("매출", "결제 건수", "패키지", ROSE),
    ]
    x = M
    for name, metric, cut, color in metrics:
        rounded_box(c, x, 370, 119, 96, color, INK, 13, 1)
        draw_text(c, name, x + 12, 443, 90, 8, FONT_XB, INK if color not in (BLUE, ROSE) else white)
        draw_text(c, metric, x + 12, 415, 95, 11, FONT_XB, INK if color not in (BLUE, ROSE) else white, leading=13, max_lines=2)
        draw_text(c, cut, x + 12, 386, 95, 7, FONT_SEMI, INK if color not in (BLUE, ROSE) else white)
        x += 130

    rounded_box(c, M, 146, 492, 186, SOFT_WHITE, INK, 15)
    draw_text(c, "중단 / 수정 / 확대 규칙", M + 18, 306, 210, 13, FONT_XB, INK)
    rules = [
        ("노출만 높고 반응 없음", "첫 2초 훅과 질문 교체", ROSE),
        ("댓글·저장 높고 프로필 낮음", "실제 화면 또는 다음 행동 추가", YELLOW),
        ("프로필 높고 체험 낮음", "랜딩 첫 화면·가격·설치 신뢰 보강", MINT),
        ("체험 높고 상담 낮음", "체험 종료 시 진단 CTA 노출", LILAC),
        ("상담 높고 결제 낮음", "오퍼 적합성·가격·반론 기록 점검", CORAL),
    ]
    y = 278
    for issue, action, color in rules:
        c.setFillColor(color)
        c.roundRect(M + 18, y - 6, 10, 20, 5, fill=1, stroke=0)
        draw_text(c, issue, M + 39, y + 8, 176, 7.5, FONT_BOLD, INK)
        draw_text(c, action, M + 223, y + 8, 240, 7.5, FONT_SEMI, GRAY)
        y -= 28

    rounded_box(c, 548, 146, 259, 186, INK, INK, 15)
    draw_text(c, "30분 루틴", 566, 306, 150, 13, FONT_XB, white)
    routine = [
        "09:00 전일 채널 지표 기록",
        "12:00 댓글·DM을 가격/기능/설치/신뢰로 분류",
        "18:00 승자 훅 1개·패자 훅 1개 선택",
        "22:30 체험·상담·결제와 콘텐츠를 연결",
    ]
    y = 278
    for idx, line in enumerate(routine, 1):
        c.setFillColor([YELLOW, MINT, LILAC, CORAL][idx - 1])
        c.circle(573, y + 1, 7, fill=1, stroke=0)
        draw_centered(c, str(idx), 566, y - 2, 14, 6.5, FONT_XB, INK)
        draw_text(c, line, 588, y + 4, 190, 7.7, FONT_SEMI, white, leading=10, max_lines=2)
        y -= 31

    rounded_box(c, M, 57, 773, 75, PAPER_2, PAPER_2, 12)
    draw_text(c, "핵심", M + 15, 104, 45, 8, FONT_XB, ROSE)
    draw_text(c, "목표 기준은 유효 상담 600명과 결제 100건이다. 제휴사·유입 채널·콘텐츠별 상담과 결제를 연결해 일 10건 속도를 매일 확인한다.", M + 65, 104, 685, 9, FONT_BOLD, INK, leading=13, max_lines=2)
    c.showPage()


def fulfillment_capacity_page(c: canvas.Canvas, page_no: int) -> None:
    page_base(c, page_no, "DELIVERY CAPACITY")
    title(c, "제공 역량", "100명을 팔기 전에 100명을 지원할 구조부터 만든다")

    stats = [
        ("결제 목표", "100명", "10일 · 일평균 10명", ROSE),
        ("1:1 강의", "150시간", "1인 90분 기준", YELLOW),
        ("8주 제공", "주 12~13명", "주 18.75시간", MINT),
        ("매출", "7,000만원", "세금·수수료·환불 전", LILAC),
    ]
    x = M
    for name, value, note, color in stats:
        rounded_box(c, x, 365, 180, 104, color, INK, 14, 1.1, shadow=True)
        draw_text(c, name, x + 15, 443, 150, 8, FONT_BOLD, INK)
        draw_text(c, value, x + 15, 414, 150, 21, FONT_XB, INK)
        draw_text(c, note, x + 15, 386, 150, 7.5, FONT_SEMI, INK)
        x += 196

    rounded_box(c, M, 150, 480, 177, SOFT_WHITE, INK, 16, 1.1)
    draw_text(c, "권장 제공 흐름", M + 18, 301, 170, 13, FONT_XB, INK)
    steps = [
        ("결제 즉시", "PDF + 설치 체크리스트 + 예약 링크 자동 발송", YELLOW),
        ("강의 전", "제휴사·PC 환경·계정 수·현재 막힌 지점 사전 설문", MINT),
        ("90분 강의", "실제 제휴 링크로 첫 흐름 설정·검수·게시", LILAC),
        ("강의 후", "원격 과외 예약·오류 유형·해결 기록을 고객별 저장", CORAL),
    ]
    y = 269
    for idx, (when, action, color) in enumerate(steps, 1):
        c.setFillColor(color)
        c.circle(M + 28, y + 1, 11, fill=1, stroke=0)
        draw_centered(c, str(idx), M + 17, y - 2.5, 22, 7, FONT_XB, INK)
        draw_text(c, when, M + 52, y + 5, 80, 8.2, FONT_XB, ROSE)
        draw_text(c, action, M + 135, y + 5, 360, 8, FONT_SEMI, INK, max_lines=1)
        y -= 32

    rounded_box(c, 540, 150, 267, 177, INK, INK, 16)
    draw_text(c, "판매 전 확정할 지원 정책", 558, 301, 225, 13, FONT_XB, white)
    policies = [
        "개인 강의 90분의 일정·지각·재예약 기준",
        "원격 과외의 포함 횟수·회당 시간·응답 SLA",
        "지원 범위: 사용법·설정 / 제외: 수익 보장·계정 제재",
        "제휴사별 링크·고지 규칙은 고객이 최종 확인",
        "100명 마감 후 대기자 접수와 다음 기수 일정",
    ]
    y = 268
    for i, line in enumerate(policies):
        c.setFillColor([YELLOW, MINT, LILAC, CORAL, ROSE][i])
        c.circle(561, y + 2, 3.5, fill=1, stroke=0)
        draw_text(c, line, 573, y + 5, 210, 7.6, FONT_SEMI, white, leading=10, max_lines=2)
        y -= 29

    rounded_box(c, M, 58, 773, 63, PAPER_2, PAPER_2, 12)
    draw_text(c, "운영 경고", M + 15, 98, 65, 8.5, FONT_XB, ROSE)
    draw_text(c, "‘사용법 모르면 언제든 무제한 원격 지원’으로 판매하면 100명 달성 순간 서비스가 막힌다. 예약제·횟수·응답 시간·지원 제외를 결제 전에 공개한다.", M + 88, 99, 665, 8.6, FONT_BOLD, INK, leading=12, max_lines=2)
    c.showPage()


def launch_checklist_page(c: canvas.Canvas, page_no: int) -> None:
    page_base(c, page_no, "LAUNCH CHECKLIST", dark=True)
    title(c, "첫 24시간", "오늘 확정하고 내일부터 바로 올린다", dark=True)

    tasks = [
        ("오퍼", "700,000원·100명·1년 사용·개인 강의·원격 과외·PDF 확정", YELLOW),
        ("프로필", "모든 채널 이름·사진·소개·링크를 하나로 통일", MINT),
        ("랜딩", "무료 체험 → 1:1 진단 → 70만원 패키지 흐름과 UTM 설치", LILAC),
        ("정책", "고지·활동채널·게시빈도·실패 중단·지원 제외 공개", CORAL),
        ("촬영", "DAY 1 실패담 + 실제 화면 20초 원본 촬영", ROSE),
        ("응대", "댓글·DM·체험 후·상담 스크립트 저장", BLUE),
    ]
    y = 351
    for i, (name, desc, color) in enumerate(tasks, 1):
        col = 0 if i <= 3 else 1
        row = (i - 1) % 3
        x = M + col * 390
        yy = y - row * 101
        rounded_box(c, x, yy, 365, 78, HexColor("#1C1E27"), HexColor("#444753"), 14)
        c.setFillColor(color)
        c.circle(x + 28, yy + 39, 16, fill=1, stroke=0)
        draw_centered(c, str(i), x + 12, yy + 34, 32, 9, FONT_XB, INK if color != BLUE and color != ROSE else white)
        draw_text(c, name, x + 57, yy + 54, 110, 10, FONT_XB, white)
        draw_text(c, desc, x + 57, yy + 30, 285, 8, FONT_SEMI, HexColor("#D5D7DE"), leading=11, max_lines=2)

    rounded_box(c, M, 55, 755, 78, ROSE, ROSE, 15)
    draw_text(c, "내일 DAY 1 게시 순서", M + 18, 108, 170, 10, FONT_XB, white)
    draw_text(c, "09:00 실패담 Threads → 11:00 20초 Reel/TikTok/Shorts → 14:00 4관점 캐러셀 → 18:00 A/B 결과 → 22:00 실제 화면 + 무료 체험 CTA", M + 18, 84, 710, 9.5, FONT_BOLD, white, leading=13, max_lines=2)
    c.showPage()


def research_sources_page(c: canvas.Canvas, page_no: int) -> None:
    page_base(c, page_no, "EXTERNAL SOURCES")
    title(c, "외부 근거", "공식 정책·판매 페이지·공개 후기를 구분해 읽었다")

    sources = [
        ("S1", "2026 개인 운영 자기보고", "초기 0원~소액·구매전환 병목의 단일 사례", "https://joahyun.tistory.com/57", YELLOW),
        ("S2", "크몽 스레드 수익화 패키지", "69/139/169만원·107건 4.9·세팅/Q&A 구성", "https://kmong.com/gig/701315", MINT),
        ("S3", "크몽 Threads 올인원 도구", "0.5/5.9/24.9만원·예약/AI 글쓰기/다계정", "https://kmong.com/gig/641225", LILAC),
        ("S4", "크몽 Instagram 실습 강의", "39/77/99만원·90분 1~3회·실습/피드백", "https://kmong.com/gig/185577", CORAL),
        ("S5", "크몽 Instagram 컨설팅", "8.5/30/85만원·진단/편집/2~4주 관리", "https://kmong.com/gig/494720", ROSE),
        ("S6", "YouTube 공식 정책", "스팸·기만·인위적 참여 금지. 모든 자동화 금지는 아님", "https://support.google.com/youtube/answer/3399767?hl=en", BLUE),
        ("S7", "Instagram 약관", "명시적 허가 없는 자동 접근·수집 제한", "https://www.facebook.com/help/instagram/581066165581870", YELLOW),
        ("S8", "Fastcampus AI 마케팅 자동화 키트", "유료 가치는 템플릿·실습·지원 산출물로 구체화", "https://fastcampus.co.kr/mktg_online_itemkitaiauto", MINT),
        ("S9", "공정위·쿠팡 공식 고지 자료", "경제적 이해관계 공개·활동 채널 등록 운영요건", "https://partners.coupangcdn.com/partners-guide/partners-guide-20240716100922.pdf", LILAC),
        ("S10", "Instagram 강의 공개 수강후기", "실행 체크리스트·프로필/DM/전환 지표의 가치", "https://fastcampus.co.kr/community/102975", CORAL),
        ("S11", "경쟁 자동화 SaaS", "무료/월 구독·생성량·다계정 기능은 판매자 자기 주장", "https://chronit.kr/", ROSE),
        ("S12", "Meta Threads API 자료", "공식 API 범위 비교용. 현재 우리 제품은 브라우저 세션 기반", "https://www.postman.com/meta/threads/overview", BLUE),
    ]
    x_positions = [M, 425]
    start_y = 425
    for idx, (sid, name, desc, url, color) in enumerate(sources):
        col = 0 if idx < 6 else 1
        row = idx if idx < 6 else idx - 6
        x = x_positions[col]
        y = start_y - row * 61
        c.setFillColor(color)
        c.circle(x + 14, y + 10, 12, fill=1, stroke=0)
        draw_centered(c, sid, x + 2, y + 6, 24, 6.5, FONT_XB, INK if color not in (ROSE, BLUE) else white)
        draw_text(c, name, x + 38, y + 20, 335, 8.5, FONT_XB, INK)
        draw_text(c, desc, x + 38, y + 3, 335, 6.9, FONT_SEMI, GRAY, max_lines=1)
        draw_link(c, url.replace("https://", ""), url, x + 38, y - 13, 335, 6.2)

    rounded_box(c, M, 51, 773, 55, PAPER_2, PAPER_2, 11)
    draw_text(c, "해석 원칙", M + 14, 83, 70, 8, FONT_XB, ROSE)
    draw_text(c, "판매 페이지의 수익·조회수·후기는 독립 성과 검증이 아니다. 자료 조사 2026-08-10·실행안 갱신 2026-08-11 기준이며 공개 직전 재확인한다.", M + 88, 83, 665, 8, FONT_BOLD, INK, leading=11, max_lines=2)
    c.showPage()


def sources_page(c: canvas.Canvas, page_no: int) -> None:
    page_base(c, page_no, "SOURCES & ASSUMPTIONS")
    title(c, "근거와 가정", "이전 계획을 유지하되 판매 목적에 맞게 다시 묶었다")

    rounded_box(c, M, 277, 773, 184, SOFT_WHITE, INK, 15)
    draw_text(c, "내부 근거 자료", M + 18, 434, 170, 13, FONT_XB, INK)
    sources = [
        "output/organic-launch-pack-v2/AWARENESS_FUNNEL_PLAN.md — Cold/Warm/Hot 비율과 채널별 메시지",
        "output/organic-launch-pack-v2/WEEKLY_SCHEDULE.md — 게시 시간·채널 형식·운영 규칙",
        "output/organic-launch-pack-v2/ — 기존 이미지·영상·프리뷰 자산",
        ".omx/plans/meta-performance-campaign-v2-2026-07-18.md — 실제 화면 중심 증명, 추적·중단 기준",
        "README.md / public/index.html — 현재 기능·공개 월 요금제·무료 체험 조건",
    ]
    y = 404
    for i, src in enumerate(sources, 1):
        c.setFillColor([YELLOW, MINT, LILAC, CORAL, ROSE][i - 1])
        c.circle(M + 25, y + 2, 8, fill=1, stroke=0)
        draw_centered(c, str(i), M + 17, y - 1, 16, 6.5, FONT_XB, INK if i < 5 else white)
        draw_text(c, src, M + 43, y + 5, 718, 7.7, FONT_SEMI, INK, max_lines=1)
        y -= 27

    rounded_box(c, M, 88, 373, 151, PAPER_2, PAPER_2, 14)
    draw_text(c, "명시적 가정", M + 17, 213, 120, 12, FONT_XB, ROSE)
    assumptions = [
        "판매가 700,000원·목표 100건·총매출 70,000,000원으로 확정",
        "10일은 결제 목표 기간이며 1:1 강의는 예약 일정에 따라 순차 제공",
        "현재 확정 지원은 쿠팡파트너스·네이버 쇼핑커넥트·토스쇼핑 파트너스·오늘의집 큐레이터·무신사 파트너스·컬리 큐레이터·올리브영 큐레이터",
        "현재 제품은 브라우저 세션 기반이므로 UI·정책 변경 리스크가 존재",
    ]
    y = 183
    for a in assumptions:
        c.setFillColor(ROSE)
        c.circle(M + 21, y + 2, 3, fill=1, stroke=0)
        draw_text(c, a, M + 32, y + 5, 330, 7.7, FONT_SEMI, INK, leading=10, max_lines=2)
        y -= 25

    rounded_box(c, 434, 88, 373, 151, INK, INK, 14)
    draw_text(c, "공개 전 반드시 확정", 452, 213, 170, 12, FONT_XB, white)
    approvals = [
        "개인 강의 일정·원격 과외 횟수·응답 SLA",
        "브라우저 자동화의 약관·빈도·중단 기준",
        "제휴 고지 자동삽입·활동 채널 등록 흐름",
        "결제·환불·해지·외부 비용·지원 제외·100명 마감",
    ]
    y = 183
    for i, a in enumerate(approvals):
        c.setFillColor([YELLOW, MINT, LILAC, CORAL][i])
        c.rect(452, y - 3, 9, 9, fill=0, stroke=1)
        draw_text(c, a, 472, y + 5, 300, 7.8, FONT_SEMI, white, max_lines=1)
        y -= 25
    c.showPage()


def build() -> Path:
    register_fonts()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(PDF_PATH), pagesize=(PAGE_W, PAGE_H), pageCompression=1)
    c.setTitle("Thread Auto 10일 7,000만원 매출 목표 마지막 라이브 채널별 마케팅 실행 플랜")
    c.setAuthor("OpenAI Codex")
    c.setSubject("국내 쇼핑 제휴 7개 지원 · 70만원 패키지 100건: 프로그램 1년 + 개인 강의 + 원격 과외 + PDF + 마지막 60분 무료 라이브 판매 계획")

    cover(c)
    executive_dashboard(c, 2)
    market_voice_page(c, 3)
    competitor_benchmark_page(c, 4)
    differentiation_page(c, 5)
    support_platforms_page(c, 6)
    offer_page(c, 7)
    funnel_page(c, 8)
    channel_matrix(c, 9)
    extended_channels_page(c, 10)
    free_class_benchmark_page(c, 11)
    korean_free_class_examples_page(c, 12)
    live_conversion_blueprint_page(c, 13)
    live_measurement_page(c, 14)
    calendar_page(c, 15)
    upload_schedule_page(c, 16)
    daily_engine_page(c, 17)
    playbooks_page(c, 18)
    secondary_playbooks_page(c, 19)
    content_system_page(c, 20)
    conversion_page(c, 21)
    asset_audit_page(c, 22)
    measurement_page(c, 23)
    fulfillment_capacity_page(c, 24)
    launch_checklist_page(c, 25)
    research_sources_page(c, 26)
    sources_page(c, 27)
    c.save()
    return PDF_PATH


if __name__ == "__main__":
    print(build())
