from __future__ import annotations

import sys
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path

from reportlab.lib.colors import HexColor, white
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

TOOLS_DIR = Path(__file__).resolve().parent
ROOT = TOOLS_DIR.parent
sys.path.insert(0, str(TOOLS_DIR))

from build_14day_channel_marketing_pdf import (  # noqa: E402
    BLUE,
    CORAL,
    FONT_BOLD,
    FONT_SEMI,
    FONT_XB,
    GRAY,
    INK,
    LIGHT_GRAY,
    LILAC,
    M,
    MINT,
    PAGE_H,
    PAGE_W,
    PAPER,
    PAPER_2,
    ROSE,
    SOFT_WHITE,
    YELLOW,
    draw_centered,
    draw_link,
    draw_text,
    page_base,
    pill,
    register_fonts,
    rounded_box,
    title,
)


OUT_DIR = ROOT / "output" / "pdf"
PDF_PATH = OUT_DIR / "thread-auto-2026-08-11-10day-240-post-final-live-content-book-ko.pdf"
CAMPAIGN_START = date(2026, 8, 11)
WEEKDAYS_KO = ["월", "화", "수", "목", "금", "토", "일"]
CHANNEL_UPLOAD_TIMES = {
    "Threads": ("08:30", "13:30", "19:30"),
    "Instagram": ("08:50", "13:50", "19:50"),
    "TikTok": ("09:10", "14:10", "20:10"),
    "YouTube": ("09:30", "14:30", "20:30"),
    "Naver Blog": ("09:50", "14:50", "20:50"),
    "Facebook": ("10:10", "15:10", "21:10"),
    "커뮤니티": ("10:30", "15:30", "21:30"),
    "강의 웹": ("10:50", "15:50", "21:50"),
}
DAY10_P3_TIMES = {
    "Threads": "21:30",
    "Instagram": "21:40",
    "TikTok": "21:50",
    "YouTube": "20:30",
    "Naver Blog": "22:20",
    "Facebook": "22:00",
    "커뮤니티": "22:10",
    "강의 웹": "21:35",
}

SUPPORTED_AFFILIATE_PLATFORMS = [
    "쿠팡파트너스",
    "네이버 쇼핑커넥트",
    "토스쇼핑 파트너스",
    "오늘의집 큐레이터",
    "무신사 파트너스",
    "컬리 큐레이터",
    "올리브영 큐레이터",
]


DAYS = [
    {
        "day": 1,
        "theme": "첫 문장에서 멈춘 40분",
        "goal": "문제 공감 → 댓글",
        "posts": [
            {
                "slot": "09:00 · 공감",
                "hook": "링크는 골랐는데\n첫 문장에서 40분 멈췄다",
                "script": "상품 찾기는 끝났는데 빈 입력창만 보고 있었다. 문제는 의지가 아니라 매번 상품 확인·문안·계정 전환을 다시 하는 과정이었다. 이 장면, 나만 겪은 건지 묻는다.",
                "video": "밤 책상 얼굴 2초 → 빈 문서와 40:00 타이머 → 손이 멈춘 클로즈업. 12~15초, 무음 구간 없이 시작.",
                "image": "어두운 책상 실사 + 타이머 40:00. 표지 문구는 ‘링크는 골랐는데 / 첫 문장에서 멈췄다’.",
                "cta": "‘나도 멈춘다’면 댓글에 40분.",
            },
            {
                "slot": "14:00 · 참여",
                "hook": "같은 링크인데\n어느 첫 문장을 누르겠어요?",
                "script": "상품은 하나, 출발점은 네 개다. 타깃 직격·편의 대비·재미 반전·사용 장면 중 실제로 손가락이 멈추는 문장을 고르게 한다.",
                "video": "A/B/C/D 문장을 0.8초씩 빠르게 교차 → 마지막 3초 정지 화면. 정답을 말하지 말고 투표를 남긴다.",
                "image": "4분할 카드. 문장 전체 대신 첫 12자만 크게. A/B/C/D 색상 고정.",
                "cta": "A·B·C·D 중 하나만 댓글.",
            },
            {
                "slot": "21:00 · 증명",
                "hook": "설명은 빼고\n링크가 게시 대기열에 들어가는 장면만",
                "script": "링크 입력 → 상품 분석 → 문안 4종 → 이미지 확인 → 계정별 대기열. 기능 목록을 읽지 않고 실제 화면을 한 번에 통과시킨다.",
                "video": "실제 앱 화면 18~22초. 마우스 원형 강조, 개인정보 블러, 배속 1.6배. 오류가 나면 잘라내지 말고 자막으로 표시.",
                "image": "실제 화면 캡처 3장을 화살표로 연결. ‘REAL SCREEN’ 배지.",
                "cta": "전체 흐름은 프로필의 무료 체험에서 직접 확인.",
            },
        ],
    },
    {
        "day": 2,
        "theme": "프롬프트 피로",
        "goal": "저장 → 무료 체험",
        "posts": [
            {
                "slot": "09:00 · 반전",
                "hook": "프롬프트 27개 저장하고\n오늘 올린 글은 0개",
                "script": "배우지 못해서가 아니라 고를 것이 너무 많아서 멈춘다. 저장한 프롬프트 폴더를 빠르게 보여주고, 결국 게시가 0개였던 화면으로 반전한다.",
                "video": "프롬프트 파일 목록 스크롤 2초 → 빈 게시 기록 → 프로그램의 단일 링크 입력창. 15초.",
                "image": "왼쪽 ‘저장 27개’, 오른쪽 ‘게시 0개’. 숫자를 화면 절반 크기로.",
                "cta": "저장보다 게시가 필요하면 ‘실행’ 댓글.",
            },
            {
                "slot": "14:00 · 실험",
                "hook": "매일 3개면 1년에 420시간\n계산 예시부터 공개합니다",
                "script": "기준 예시는 수동 30분, 프로그램 7분, 1개당 23분 절감이다. 매일 3개면 연 약 420시간이다. 게시물에는 반드시 ‘실측 전 계산 예시’라고 쓰고 10개 작업 중앙값으로 교체한다.",
                "video": "좌우 분할 타이머. 왼쪽 수동, 오른쪽 프로그램. 결과 숫자는 편집 전에 실제 측정값으로 교체.",
                "image": "30분 - 7분 = 23분 / 3개 × 365일 = 약 420시간. 하단 ‘계산 예시’ 고정.",
                "cta": "본인의 하루 게시 개수를 댓글.",
            },
            {
                "slot": "21:00 · 오퍼",
                "hook": "강의 끝나고 까먹는 첫 단계,\n이 PDF에서 바로 찾게 만들었다",
                "script": "설치·로그인·링크 입력·검수·오류 대응을 목차 검색으로 다시 찾는 장면을 보여준다. 전자책은 보너스가 아니라 혼자 재시작하는 매뉴얼이다.",
                "video": "PDF 표지 → 목차 검색 → 오류 해결 페이지 확대. 15~18초.",
                "image": "노트북과 PDF 표지 목업. 표지 문구 ‘막히면 여기서 다시 시작’.",
                "cta": "목차가 궁금하면 ‘PDF’ 댓글.",
            },
        ],
    },
    {
        "day": 3,
        "theme": "7개 제휴 플랫폼을 한 프로그램으로",
        "goal": "지원 범위 증명 → 프로필",
        "posts": [
            {
                "slot": "09:00 · 오해 깨기",
                "hook": "쿠팡만 된다고요?\n국내 쇼핑 제휴 7곳을 지원합니다",
                "script": "쿠팡파트너스부터 올리브영 큐레이터까지 공식 지원 7개 플랫폼명을 한 화면에 띄우고, 서로 다른 링크가 같은 입력 흐름으로 들어가는 장면을 보여준다.",
                "video": "7개 플랫폼명 카드 2초 → 실제 링크 유형 7개 빠른 전환 → 같은 입력창 → 성공 이력. 개인정보와 제휴 ID는 블러.",
                "image": "‘쿠팡만?’을 취소선 처리하고 ‘공식 지원 7개’와 일곱 플랫폼명을 4+3 카드 배열로 배치.",
                "cta": "지금 쓰는 제휴 플랫폼 번호를 댓글로 남겨주세요.",
            },
            {
                "slot": "14:00 · 검증",
                "hook": "쇼핑 제휴 링크 7개를\n같은 입력창에 넣어봤습니다",
                "script": "일곱 플랫폼 링크가 상품 정보로 변환되는 과정을 빠르게 비교한다. 각 플랫폼별 성공 캡처와 링크 형식·고지 확인 지점을 함께 보여준다.",
                "video": "7분할 세로 스택: 플랫폼명 → 링크 입력 → 성공 상태를 각 2초. 마지막에 7개 체크가 한 번에 켜지는 장면. 20~25초.",
                "image": "7개 호환 체크표. 플랫폼명·링크 인식·고지 확인을 한 줄씩 표시하고 실제 테스트 화면을 근거로 사용.",
                "cta": "7개 전체 지원표는 프로필에서 확인.",
            },
            {
                "slot": "21:00 · 신뢰",
                "hook": "7개는 확실히,\n그 밖은 테스트 후 말하겠습니다",
                "script": "공식 지원 7개를 정확히 밝히고, 그 밖의 제휴사는 링크 형식·로그인·고지 규칙을 실제 확인한 뒤 안내한다고 말한다. ‘모든 쇼핑몰 지원’ 같은 과장 표현은 쓰지 않는다.",
                "video": "체크리스트에 직접 체크: 단축 URL·리디렉션·로그인 필요·고지 문구. 15초.",
                "image": "검정 배경 체크리스트. 제목 ‘지원 / 조건부 / 확인 필요’.",
                "cta": "본인 링크 1개로 무료 진단 신청.",
            },
        ],
    },
    {
        "day": 4,
        "theme": "한 번도 끊기지 않는 흐름",
        "goal": "기능 이해 → 체험",
        "posts": [
            {
                "slot": "09:00 · 호기심",
                "hook": "링크 하나 넣었는데\n첫 문장이 4개로 갈라졌다",
                "script": "말투만 바꾼 네 문장이 아니라 타깃·편의·반전·사용 장면으로 출발점이 달라지는 것을 비교한다.",
                "video": "입력 링크 1개 → 네 카드가 동시에 펼쳐지는 모션 → 각 카드 첫 줄 1초씩.",
                "image": "중앙 링크 1개, 주변 문안 4개. 문장 길이는 2줄 이내.",
                "cta": "네 가지 중 다음에 공개할 관점을 선택.",
            },
            {
                "slot": "14:00 · 과정",
                "hook": "자동화의 핵심은 글 생성이 아니라\n게시 전까지 안 끊기는 것입니다",
                "script": "생성만 하고 복사·이미지·계정 이동을 다시 하면 반쪽 자동화다. 링크에서 대기열까지 끊기지 않는 구간을 손가락으로 짚는다.",
                "video": "화면 녹화 위에 1~5 단계 번호. 각 전환마다 딱 소리 효과, 총 20초.",
                "image": "5단계 파이프라인. 끊기는 지점을 빨간 X로 표시.",
                "cta": "지금 가장 끊기는 단계를 댓글.",
            },
            {
                "slot": "21:00 · 안전",
                "hook": "자동으로 올리기 직전\n제가 딱 한 번 멈추는 이유",
                "script": "링크·고지·계정·첫 문장을 사람이 마지막으로 본다. 완전 자동을 말하되 최종 승인이 안전장치라는 점을 실제 승인 버튼으로 설명한다.",
                "video": "게시 버튼 직전 정지 → 4개 체크 → 승인 클릭. 15초.",
                "image": "큰 승인 버튼과 ‘마지막 10초가 계정을 지킨다’ 문구.",
                "cta": "승인형 자동화가 필요한 이유를 저장.",
            },
        ],
    },
    {
        "day": 5,
        "theme": "70만원 가격 공개",
        "goal": "가격 반론 → 상담",
        "posts": [
            {
                "slot": "09:00 · 가격 훅",
                "hook": "70만원?\n프로그램만 받는 가격이면 저도 안 삽니다",
                "script": "가격을 숨기지 않고 첫 화면에 띄운다. 1년 사용권·개인 강의·원격 과외·전자책 PDF 네 가지를 한 장씩 쌓는다.",
                "video": "70만원 숫자 1초 → 구성 4개가 0.7초 간격으로 등장 → 마지막 전체 패키지.",
                "image": "700,000원을 중앙에 크게, 아래 4개 구성 아이콘. 할인율·가짜 정상가 금지.",
                "cta": "프로그램보다 필요한 구성을 하나 댓글.",
            },
            {
                "slot": "14:00 · 비교",
                "hook": "70만원이 비싼지\n41일이 비싼지 계산해봤습니다",
                "script": "수동 30분·프로그램 7분·하루 3개·시급 15,000원이라는 기준 예시에서는 하루 노동가치 17,250원을 아끼고 약 41일에 70만원과 같아진다. 실제 측정 전에는 예시임을 크게 표시한다.",
                "video": "70만원 → 하루 69분 절감 → 시급 15,000원 → 41일 손익분기. 계산식이 한 단계씩 등장.",
                "image": "700,000 ÷ 17,250원/일 = 약 41일. ‘기준 예시·수익 보장 아님’ 하단 고정.",
                "cta": "본인 시급과 하루 게시량으로 계산 요청.",
            },
            {
                "slot": "21:00 · 전환",
                "hook": "1년 동안 쓰다가 막히면\n화면을 같이 보는 지원까지 포함했습니다",
                "script": "‘언제든 무제한’이 아니라 예약 방식·포함 횟수·응답 시간을 화면에 정확히 공개한다. 명확한 범위가 오히려 신뢰를 만든다.",
                "video": "예약 캘린더 → 화면 공유 장면 → 해결 체크. 실제 고객이 없으면 ‘지원 상황 연출’ 표기.",
                "image": "지원 범위 카드: 강의 / 원격 과외 / PDF / 1년 사용.",
                "cta": "내 환경에서 가능한지 1:1 진단 신청.",
            },
        ],
    },
    {
        "day": 6,
        "theme": "사람 승인형 풀플로우",
        "goal": "안전 반론 → 저장",
        "posts": [
            {
                "slot": "09:00 · 질문",
                "hook": "완전 자동인데\n왜 마지막에 사람이 누르냐고요?",
                "script": "자동화는 반복을 없애고 사람은 링크·고지·맥락을 판단한다. 승인 버튼이 자동화를 덜 만든 것이 아니라 사고를 줄이는 마지막 장치다.",
                "video": "자동 진행 바 90% → 사람 눈·승인 클릭 → 게시 성공. 15초.",
                "image": "‘자동 90% + 사람 10%’ 원형 그래프.",
                "cta": "무검수와 승인형 중 더 믿는 쪽을 댓글.",
            },
            {
                "slot": "14:00 · 경고",
                "hook": "자동화가 제일 위험한 순간은\n너무 잘 돌아갈 때입니다",
                "script": "틀린 링크나 고지 누락도 빠르게 반복될 수 있다. 그래서 실패 로그·게시 빈도·중단 기준을 실제 설정 화면으로 보여준다.",
                "video": "성공 게시 연속 → 빨간 오류 1건 → 자동 중단 토글. 공포 연출보다 실제 로그 중심.",
                "image": "초록 8개 사이 빨간 1개. 문구 ‘1개 틀리면 멈춤’.",
                "cta": "자동화 전 체크리스트를 저장.",
            },
            {
                "slot": "21:00 · 체크리스트",
                "hook": "게시 전에 보는 건\n딱 4개뿐입니다",
                "script": "1 링크 목적지, 2 경제적 이해관계 고지, 3 게시 계정, 4 첫 문장. 10초 검수 루틴을 화면에 고정한다.",
                "video": "손가락 네 개 → 각 항목 실제 화면 2초씩 → 승인.",
                "image": "4칸 체크 카드. 링크·고지·계정·첫 문장.",
                "cta": "필요하면 ‘체크’ 댓글로 PDF 목차 요청.",
            },
        ],
    },
    {
        "day": 7,
        "theme": "캠페인 단 한 번의 라이브",
        "goal": "집중 이벤트 → 상담",
        "posts": [
            {
                "slot": "09:00 · 초대",
                "hook": "오늘 저녁 링크 하나만 주세요\n처음부터 끝까지 화면을 안 끄겠습니다",
                "script": "20:30 한 번만 라이브한다. 링크 입력부터 문안·이미지·대기열·승인까지 보여주고, 중간 오류도 숨기지 않는다고 약속한다.",
                "video": "얼굴 정면 6초 + 라이브 시간 카드 + 실제 앱 3초. 과한 오프닝 음악 금지.",
                "image": "오늘 20:30 / 링크 1개 / 무편집 데모. 세 문구만.",
                "cta": "라이브에서 볼 제휴 링크 유형을 댓글.",
            },
            {
                "slot": "14:00 · 예고",
                "hook": "라이브에서 이 화면은\n오류가 나도 끄지 않겠습니다",
                "script": "보여줄 5단계와 숨기지 않을 3가지: 로딩, 실패 로그, 사람 승인. 예상 질문을 투표로 받는다.",
                "video": "앱 화면 위 ‘NO CUT’ 스탬프 → 5단계 체크 → 질문 스티커.",
                "image": "라이브 목차 5개 + 질문 QR/링크. 댓글 질문 3개 캡처.",
                "cta": "가장 보고 싶은 단계 번호를 댓글.",
            },
            {
                "slot": "21:30 · 결과",
                "hook": "방금 60분 라이브에서\n사람들이 멈춘 장면은 이 18초였습니다",
                "script": "라이브 종료 직후 반응이 컸던 실제 구간 하나를 잘라 올린다. 조회수보다 질문 수와 체험 클릭을 함께 공개한다.",
                "video": "실제 라이브 클립 18초 + 댓글 2개 + 다음 행동. 라이브가 끝난 뒤에만 제작.",
                "image": "라이브 캡처 + 실제 질문 2개. 닉네임은 동의 없으면 블러.",
                "cta": "놓쳤다면 60초 요약과 무료 체험은 프로필.",
            },
        ],
    },
    {
        "day": 8,
        "theme": "다계정 기억력 문제",
        "goal": "운영 공감 → 체험",
        "posts": [
            {
                "slot": "09:00 · 공감",
                "hook": "계정 3개부터\n기억력이 마케팅을 망치기 시작했다",
                "script": "글솜씨보다 ‘어디에 무엇을 올렸지?’를 다시 찾는 시간이 늘어난다. 메모·브라우저 탭·계정 전환이 엉킨 실제 책상을 보여준다.",
                "video": "열린 탭 12개 → 메모 3개 → 계정별 대기열 한 화면. 15초.",
                "image": "왼쪽 혼란스러운 탭, 오른쪽 계정 3개 대기열. BEFORE/AFTER.",
                "cta": "현재 운영 계정 수를 숫자로 댓글.",
            },
            {
                "slot": "14:00 · 화면 증명",
                "hook": "어느 계정에 뭘 올렸지?\n이 질문이 사라지는 화면",
                "script": "계정별 예정·성공·실패 상태를 필터링하는 장면을 보여준다. ‘다계정 무조건 확대’가 아니라 기존 운영의 확인 비용을 줄이는 기능이라고 말한다.",
                "video": "계정 A/B/C 탭 클릭 → 상태 필터 → 실패 1건 확인. 18초.",
                "image": "대기열 실화면을 크게, 계정명은 테스트 계정으로 교체.",
                "cta": "실제 화면을 확대해서 보고 싶으면 저장.",
            },
            {
                "slot": "21:00 · 반전",
                "hook": "다계정이 장점이 아닙니다\n관리 실수가 줄어드는 게 장점입니다",
                "script": "계정을 늘리라는 메시지를 버리고, 링크 중복·잘못된 계정·실패 재확인을 줄이는 세 가지 장면을 보여준다.",
                "video": "실수 3개 빨간 X → 프로그램 확인 화면 3개 초록 체크. 15초.",
                "image": "‘계정 수 ↑’ 취소선, ‘실수 ↓’ 강조.",
                "cta": "가장 자주 하는 실수 하나를 댓글.",
            },
        ],
    },
    {
        "day": 9,
        "theme": "초보의 첫 설치",
        "goal": "설치 불안 → 1:1 진단",
        "posts": [
            {
                "slot": "09:00 · 직격",
                "hook": "설치 화면에서 막히면\n좋은 프로그램도 0원짜리입니다",
                "script": "구매 후 혼자 설치하다 닫아버리는 순간을 연출하고, 패키지가 첫 게시 완료를 기준으로 설계됐다고 설명한다.",
                "video": "설치 경고창 앞 멈춤 → 화면 공유 연결 → 첫 게시 체크. 연출이면 자막 표기.",
                "image": "설치 37% 화면 + ‘여기서 닫았다면?’ 문구.",
                "cta": "설치에서 걱정되는 지점을 질문으로 남기기.",
            },
            {
                "slot": "14:00 · 결과",
                "hook": "90분 강의가 끝날 때\n남아 있어야 하는 건 노트가 아닙니다",
                "script": "설치 완료·제휴 링크 입력·문안 생성·검수·첫 게시까지 다섯 개 체크가 남아야 한다. 슬라이드가 아니라 결과물을 판매한다.",
                "video": "빈 체크리스트 → 실제 화면에서 하나씩 완료 → 게시 URL. 20초.",
                "image": "‘수강 완료’ 취소선, ‘첫 게시 완료’ 체크.",
                "cta": "첫 게시까지 같이 끝내고 싶으면 진단 신청.",
            },
            {
                "slot": "21:00 · 진단",
                "hook": "원격 과외를 시작하면\n가장 먼저 보는 세 곳",
                "script": "PC 환경, 로그인 상태, 제휴 링크 형식부터 본다. 글쓰기 팁보다 실행을 막는 기술 조건을 먼저 없앤다.",
                "video": "시스템 정보 → 로그인 테스트 → 링크 검사. 개인정보·키는 모두 블러.",
                "image": "PC / 로그인 / 링크 3칸 진단 카드.",
                "cta": "내 환경 진단 체크리스트 요청.",
            },
        ],
    },
    {
        "day": 10,
        "theme": "원격 과외의 실제 가치",
        "goal": "지원 신뢰 → 상담",
        "posts": [
            {
                "slot": "09:00 · 상황",
                "hook": "설명서 40페이지보다\n화면 공유 10분이 빠른 순간",
                "script": "버튼 위치·로그인·링크 형식처럼 말로 설명할수록 길어지는 문제를 화면 공유로 함께 찾는 장면을 보여준다. 시간 숫자는 실제 세션에서 측정 후 사용한다.",
                "video": "채팅 왕복 화면 → 화면 공유 → 해결 체크. 실제 고객 화면은 사전 동의와 블러 필수.",
                "image": "‘채팅 18번’ vs ‘화면 공유 1번’은 실제 기록이 있을 때만 사용.",
                "cta": "혼자 해결하기 힘든 오류를 댓글.",
            },
            {
                "slot": "14:00 · 재현",
                "hook": "클릭이 안 되는 게 아니라\n로그인이 다른 계정에 되어 있었습니다",
                "script": "자주 생기는 지원 상황을 15초 재현한다. 실제 사례가 아니면 ‘지원 상황 재현’이라고 크게 표시하고 해결 순서를 보여준다.",
                "video": "잘못된 계정 → 계정 확인 → 재로그인 → 정상. 4컷.",
                "image": "‘버그?’를 취소선, ‘계정 확인’에 화살표.",
                "cta": "이 오류를 겪었다면 저장.",
            },
            {
                "slot": "21:00 · 신뢰 반전",
                "hook": "‘언제든 도와드립니다’가\n가장 위험한 약속인 이유",
                "script": "100명에게 무제한 지원을 약속하면 결국 아무도 빨리 못 돕는다. 포함 횟수·회당 시간·응답 SLA·지원 제외를 공개한다.",
                "video": "무제한 문구 빨간 X → 예약 캘린더·SLA 카드·지원 범위. 18초.",
                "image": "지원 정책 4칸: 횟수 / 시간 / 응답 / 제외.",
                "cta": "지원 범위를 보고 상담 여부를 판단.",
            },
        ],
    },
    {
        "day": 11,
        "theme": "전자책은 재시작 버튼",
        "goal": "구성 가치 → 저장",
        "posts": [
            {
                "slot": "09:00 · 기억",
                "hook": "강의 다음 날\n제일 먼저 까먹는 건 첫 단계입니다",
                "script": "수업 때는 다 알 것 같지만 혼자 켜면 설치 경로부터 다시 찾는다. PDF 첫 장에서 시작 버튼까지 20초 안에 찾는 장면을 보여준다.",
                "video": "다음 날 멍한 얼굴 → PDF 검색 ‘설치’ → 해당 페이지 → 실행. 15초.",
                "image": "‘어디서 시작하지?’ 검색창 + PDF 목차.",
                "cta": "전자책에서 꼭 필요한 목차를 댓글.",
            },
            {
                "slot": "14:00 · 내부 공개",
                "hook": "70만원 패키지 PDF에\n실제로 들어가는 페이지를 공개합니다",
                "script": "표지보다 설치·첫 링크·승인·오류 로그·제휴 고지 페이지를 빠르게 넘긴다. 아직 완성 전이면 ‘제작 중 미리보기’로 표시한다.",
                "video": "PDF 6페이지 플립 1초씩 → 가장 중요한 오류 페이지 4초 정지.",
                "image": "6페이지 썸네일 그리드. 작은 본문 대신 섹션명만 읽히게.",
                "cta": "가장 먼저 받고 싶은 페이지 번호 선택.",
            },
            {
                "slot": "21:00 · 문제 해결",
                "hook": "검색하지 않아도 되는\n초보 오류 7개",
                "script": "로그인·링크 형식·이미지·계정·고지·대기열·게시 실패를 한 줄 해결표로 보여준다. 상세 답은 PDF에 연결한다.",
                "video": "오류 메시지 7개를 0.7초씩 → 해결표 5초 정지. 총 14초.",
                "image": "오류 7개 체크리스트. 해결 문장은 12자 이내.",
                "cta": "현재 오류 번호를 댓글로 남기기.",
            },
        ],
    },
    {
        "day": 12,
        "theme": "과장 대신 한계 공개",
        "goal": "불신 해소 → 체험",
        "posts": [
            {
                "slot": "09:00 · 금지 선언",
                "hook": "이 프로그램이\n절대 해주지 못하는 것 3개",
                "script": "수익 보장, 좋은 상품 선택, 플랫폼 정책 책임을 대신하지 못한다. 먼저 한계를 공개한 뒤 반복 작업을 어디까지 줄이는지 보여준다.",
                "video": "수익 보장 X / 상품 안목 X / 정책 면책 X → 반복 흐름 자동화 O. 15초.",
                "image": "3개의 큰 X와 마지막 1개의 O.",
                "cta": "자동화에 기대했던 것을 솔직히 댓글.",
            },
            {
                "slot": "14:00 · 가치",
                "hook": "대신 매일 다시 하던\n이 네 번은 줄입니다",
                "script": "상품 확인·문안 작성·계정 전환·상태 재확인을 실제 흐름에서 보여준다. ‘없앤다’보다 ‘줄인다’로 정확히 표현한다.",
                "video": "네 반복 장면 각 2초 → 하나의 대기열 화면 5초. 총 15초.",
                "image": "반복 4개를 겹쳐 놓고 중앙에 대기열.",
                "cta": "가장 줄이고 싶은 반복 번호 선택.",
            },
            {
                "slot": "21:00 · 숫자",
                "hook": "수익 인증 대신\n제가 매일 공개할 숫자",
                "script": "세팅 완료율·승인 게시 성공률·오류율·7일 지속률을 공개한다. 시간 절감 수치는 동일 조건으로 실제 측정한 경우에만 사용한다.",
                "video": "대시보드 숫자 4개 → 측정 기준 하단 자막 → 날짜 스탬프.",
                "image": "운영 지표 4개 카드. 매출 그래프처럼 오해시키지 않는다.",
                "cta": "성과보다 과정 지표가 궁금하면 저장.",
            },
        ],
    },
    {
        "day": 13,
        "theme": "100명 정원의 이유",
        "goal": "사실 기반 마감 → 결제",
        "posts": [
            {
                "slot": "09:00 · 희소성 해명",
                "hook": "100명만 받는 이유는\n희소성 연출이 아닙니다",
                "script": "100명 × 90분은 개인 강의 150시간이다. 8주 일정표를 보여주며 실제 제공 가능한 선에서 정원을 닫는다고 설명한다.",
                "video": "100명 숫자 → 150시간 계산 → 8주 캘린더. 18초.",
                "image": "100 × 90분 = 150시간. 계산식을 크게.",
                "cta": "가능한 강의 시간대를 진단 폼에 선택.",
            },
            {
                "slot": "14:00 · 운영 공개",
                "hook": "결제 100건보다 먼저 만든 것\n바로 이 예약표입니다",
                "script": "결제 즉시 PDF·체크리스트·예약 링크가 가고, 강의 전 설문과 강의 후 지원 기록이 이어지는 제공 흐름을 보여준다.",
                "video": "결제 완료 → 자동 메일 → 예약 → 설문 → 고객 카드. 개인정보는 테스트 데이터.",
                "image": "고객 제공 여정 5단계.",
                "cta": "결제 전 제공 일정을 반드시 확인.",
            },
            {
                "slot": "21:00 · 실제 좌석",
                "hook": "남은 자리는 숫자로 장난치지 않고\n결제 기준으로만 바꿉니다",
                "script": "오늘 실제 결제 건수와 남은 정원을 같은 시각에 업데이트한다. 결제가 없으면 100/100 그대로 공개하고, 가짜 카운트다운은 쓰지 않는다.",
                "video": "결제 관리자 숫자 → 좌석 카드 수정 → 타임스탬프. 민감 정보 블러.",
                "image": "‘결제 완료 N / 남은 자리 100-N’ 실제 숫자만.",
                "cta": "남은 자리와 일정 확인 후 결제.",
            },
        ],
    },
    {
        "day": 14,
        "theme": "마지막 선택",
        "goal": "결정 → 결제",
        "posts": [
            {
                "slot": "09:00 · 선택",
                "hook": "내일도 링크 복사부터\n다시 시작할 건가요?",
                "script": "10일 동안 반복해서 보여준 문제와 실제 화면을 1초씩 회수한다. 마지막에는 ‘지금 필요한 건 정보인가, 실행 흐름인가’만 묻는다.",
                "video": "40분 타이머 → 문안 4종 → 대기열 → 원격 지원 → PDF. 각 1.2초.",
                "image": "왼쪽 ‘다시 반복’, 오른쪽 ‘설정 후 실행’ 두 갈래.",
                "cta": "오늘 본인에게 필요한 경로를 선택.",
            },
            {
                "slot": "14:00 · 패키지 요약",
                "hook": "70만원에 포함되는 걸\n15초 안에 전부 보여드리겠습니다",
                "script": "프로그램 1년·개인 강의·원격 과외·전자책 PDF·공식 지원하는 7개 쇼핑 제휴 플랫폼을 실제 화면과 함께 한 번에 정리한다.",
                "video": "구성 5개를 2초씩 → 가격 70만원 → 남은 실제 좌석. 15초.",
                "image": "구성 5개 + 가격 1개. 불필요한 가치합계·할인율 없음.",
                "cta": "구성·지원 범위 확인 후 결제.",
            },
            {
                "slot": "21:00 · 마감",
                "hook": "오늘 닫는 건 할인창이 아니라\n이번 1:1 강의 예약표입니다",
                "script": "실제 마감 시각·남은 좌석·다음 모집 예정일을 공개한다. 마감이 연장될 가능성이 있으면 ‘연장 없음’이라고 쓰지 않는다.",
                "video": "현재 시각 → 실제 예약표 → 남은 좌석 → 결제 버튼. 18초.",
                "image": "마감 시각과 다음 모집 예정. 사실로 확정된 정보만.",
                "cta": "마지막 결제 또는 다음 기수 대기 신청.",
            },
        ],
    },
]

# 14일 초안에서 전환력이 높은 주제만 남긴 10일 압축 스프린트.
# 마지막 날에 유일한 라이브를 배치해 예열과 공개를 한 번에 닫는다.
ALL_DAYS = DAYS
DAY_SEQUENCE = [0, 1, 2, 3, 4, 5, 8, 10, 12, 6]
DAYS = []
for new_day_number, source_index in enumerate(DAY_SEQUENCE, 1):
    selected = deepcopy(ALL_DAYS[source_index])
    selected["day"] = new_day_number
    DAYS.append(selected)

DAYS[8]["posts"][2] = deepcopy(ALL_DAYS[6]["posts"][0])
DAYS[8]["posts"][2]["slot"] = "21:00 · 라이브 예고"
DAYS[8]["posts"][2]["hook"] = "내일 저녁 링크 하나만 주세요\n처음부터 끝까지 화면을 안 끄겠습니다"
DAYS[8]["posts"][2]["script"] = "다음 날 20:30 마지막 라이브를 예고한다. 링크 입력부터 문안·이미지·대기열·승인까지 보여주고, 오류도 숨기지 않는다고 약속한다."
DAYS[8]["posts"][2]["cta"] = "라이브에서 볼 제휴 링크 유형을 댓글."


def cover(c: canvas.Canvas) -> None:
    c.setFillColor(INK)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    c.setFillColor(ROSE)
    c.rect(0, 0, 16, PAGE_H, fill=1, stroke=0)
    pill(c, "10 DAYS · 240 DISTRIBUTIONS", 56, PAGE_H - 72, YELLOW, INK, 8.5)
    draw_text(c, "매일 3개씩\n전 채널 후킹\n콘텐츠 북", 56, PAGE_H - 120, 430, 37, FONT_XB, white, leading=41)
    draw_text(c, "30개 원본 소재를 8개 채널에 맞춰 바꾸고 마지막 날 라이브로 닫는 실행안", 58, PAGE_H - 272, 510, 12, FONT_BOLD, HexColor("#F5B4C5"))
    pill(c, "국내 쇼핑 제휴 7개 공식 지원", 58, PAGE_H - 311, MINT, INK, 8)

    rounded_box(c, 526, 274, 260, 214, PAPER, PAPER, 22, shadow=True)
    pill(c, "OPERATING NUMBER", 548, 451, ROSE, white, 7.5)
    draw_text(c, "3 원본/일", 548, 416, 210, 25, FONT_XB, INK)
    draw_text(c, "× 8개 채널 × 10일", 548, 377, 210, 17, FONT_XB, INK)
    c.setStrokeColor(LIGHT_GRAY)
    c.line(548, 351, 764, 351)
    draw_text(c, "총 240회 배포", 548, 329, 210, 21, FONT_XB, ROSE)
    draw_text(c, "라이브는 8/20 (목) · 20:30 단 한 번", 548, 296, 210, 8.5, FONT_BOLD, GRAY)

    rounded_box(c, 56, 82, 730, 121, HexColor("#1D2029"), HexColor("#454956"), 16)
    draw_text(c, "후킹의 기준", 76, 177, 120, 10, FONT_XB, YELLOW)
    rules = [
        "첫 1초에 문제·숫자·반전 중 하나",
        "설명 대신 실제 화면·타이머·오류·예약표",
        "한 콘텐츠에는 궁금증 하나, CTA 하나",
        "가짜 수익·가짜 후기·가짜 마감은 사용 금지",
    ]
    x, y = 76, 143
    for i, rule in enumerate(rules):
        color = [ROSE, MINT, LILAC, CORAL][i]
        c.setFillColor(color)
        c.circle(x + (i % 2) * 350, y - (i // 2) * 34 + 2, 4, fill=1, stroke=0)
        draw_text(c, rule, x + 13 + (i % 2) * 350, y - (i // 2) * 34 + 5, 315, 8.5, FONT_BOLD, white)
    c.setFont(FONT_BOLD, 7.5)
    c.setFillColor(HexColor("#A7AAB4"))
    c.drawString(58, 36, "실전 제작본 · 2026.08.11 시작 · 70만원 패키지 100건 목표")
    c.drawRightString(PAGE_W - 42, 36, "THREAD AUTO")
    c.showPage()


def math_page(c: canvas.Canvas, page_no: int) -> None:
    page_base(c, page_no, "PUBLISHING SYSTEM")
    title(c, "운영 수치", "매일 새로 만드는 건 24개가 아니라 강한 원본 3개다")
    stats = [
        ("원본", "30개", "3개 × 10일", ROSE),
        ("채널", "8개", "공개 피드 기준", YELLOW),
        ("배포", "240회", "24회 × 10일", MINT),
        ("라이브", "1회", "마지막 DAY 10", LILAC),
    ]
    x = M
    for name, value, note, color in stats:
        rounded_box(c, x, 372, 180, 101, color, INK, 14, shadow=True)
        draw_text(c, name, x + 15, 447, 145, 8, FONT_BOLD, INK)
        draw_text(c, value, x + 15, 419, 145, 23, FONT_XB, INK)
        draw_text(c, note, x + 15, 391, 145, 7.5, FONT_SEMI, INK)
        x += 196

    rounded_box(c, M, 161, 773, 170, SOFT_WHITE, INK, 15)
    draw_text(c, "하루 배포 파동", M + 18, 305, 150, 13, FONT_XB, INK)
    waves = [
        ("P1 · 09시 파동", "공감·문제", "얼굴/상황 → ‘이게 내 얘기’", YELLOW),
        ("P2 · 14시 파동", "참여·비교", "A/B·숫자·체크리스트 → 댓글/저장", MINT),
        ("P3 · 21시 파동", "증명·전환", "실제 화면·지원·가격 → 체험/진단", ROSE),
    ]
    x = M + 18
    for name, role, desc, color in waves:
        rounded_box(c, x, 190, 231, 85, color, color, 13)
        draw_text(c, name, x + 13, 253, 200, 9.5, FONT_XB, INK)
        draw_text(c, role, x + 13, 230, 200, 8.5, FONT_BOLD, INK)
        draw_text(c, desc, x + 13, 207, 200, 7.3, FONT_SEMI, INK, max_lines=2)
        x += 250

    rounded_box(c, M, 62, 773, 70, INK, INK, 12)
    draw_text(c, "중요", M + 17, 107, 55, 8.5, FONT_XB, YELLOW)
    draw_text(c, "이메일·카카오는 공개 콘텐츠 채널에서 제외한다. 동의한 리드에게 하루 3회 보내면 스팸이 되므로 D1·D3·D9·D10의 행동 알림만 보낸다.", M + 78, 108, 690, 8.6, FONT_BOLD, white, leading=12, max_lines=2)
    c.showPage()


def labor_model_page(c: canvas.Canvas, page_no: int) -> None:
    page_base(c, page_no, "LABOR VALUE MODEL")
    title(c, "시간 가치", "노가다 방식 30분과 프로그램 7분을 같은 작업으로 비교한다")

    manual = [
        ("상품·링크 확인", 4),
        ("문안 4종 작성", 12),
        ("이미지·고지", 5),
        ("계정 전환·게시", 6),
        ("기록·상태 확인", 3),
    ]
    automated = [
        ("링크 입력·분석", 1.5),
        ("문안·이미지 검수", 3),
        ("계정·대기열 확인", 1.5),
        ("최종 승인·로그", 1),
    ]

    for x, heading, total, rows, color in [
        (M, "수동 작업 · 기준 예시", 30, manual, CORAL),
        (430, "프로그램 사용 · 기준 예시", 7, automated, MINT),
    ]:
        rounded_box(c, x, 152, 377, 309, SOFT_WHITE, INK, 16, 1.1, shadow=True)
        c.setFillColor(color)
        c.roundRect(x, 398, 377, 63, 16, fill=1, stroke=0)
        c.rect(x, 398, 377, 24, fill=1, stroke=0)
        draw_text(c, heading, x + 18, 438, 235, 12, FONT_XB, INK)
        draw_text(c, f"{total}분", x + 283, 438, 72, 18, FONT_XB, INK)
        y = 366
        max_minutes = max(v for _, v in rows)
        for name, minutes in rows:
            draw_text(c, name, x + 18, y + 5, 145, 8, FONT_BOLD, INK)
            c.setFillColor(LIGHT_GRAY)
            c.roundRect(x + 163, y - 1, 145, 9, 4, fill=1, stroke=0)
            c.setFillColor(color)
            c.roundRect(x + 163, y - 1, minutes / max_minutes * 145, 9, 4, fill=1, stroke=0)
            draw_text(c, f"{minutes:g}분", x + 320, y + 5, 42, 8, FONT_XB, INK)
            y -= 43

    rounded_box(c, M, 62, 773, 65, INK, INK, 12)
    draw_text(c, "계산 결과", M + 16, 104, 75, 9, FONT_XB, YELLOW)
    draw_text(c, "1개당 23분 절감 · 76.7% 감소. 단, 현재 숫자는 마케팅용 기준 예시다. 실제 주장은 동일한 링크 10개를 수동·프로그램으로 처리한 중앙값으로 교체한다.", M + 97, 105, 660, 8.5, FONT_BOLD, white, leading=12, max_lines=2)
    c.showPage()


def savings_table_page(c: canvas.Canvas, page_no: int) -> None:
    page_base(c, page_no, "VISIBLE SAVINGS")
    title(c, "눈에 보이는 절감", "매일 올릴수록 70만원은 사용료가 아니라 절약 시간과 비교된다")

    hourly = 15000
    saved_per_post = 23
    rows = []
    for posts in [1, 3, 5, 10]:
        daily_minutes = saved_per_post * posts
        annual_hours = daily_minutes * 365 / 60
        annual_value = annual_hours * hourly
        break_even = 700000 / (daily_minutes / 60 * hourly)
        net_value = annual_value - 700000
        rows.append((posts, daily_minutes, annual_hours, annual_value, break_even, net_value))

    headers = ["하루 게시", "하루 절감", "연간 절감", "연간 노동가치", "70만원 회수", "가격 차감 후"]
    widths = [95, 120, 120, 150, 130, 158]
    x0, y = M, 420
    c.setFillColor(INK)
    c.roundRect(x0, y, sum(widths), 39, 10, fill=1, stroke=0)
    x = x0
    for h, w in zip(headers, widths):
        draw_centered(c, h, x + 3, y + 14, w - 6, 7.5, FONT_BOLD, white)
        x += w
    y -= 66
    colors = [YELLOW, MINT, LILAC, ROSE]
    for row, color in zip(rows, colors):
        posts, daily_minutes, annual_hours, annual_value, break_even, net_value = row
        values = [
            f"{posts}개",
            f"{daily_minutes}분",
            f"{annual_hours:,.0f}시간",
            f"{annual_value/10000:,.0f}만원",
            f"약 {break_even:.1f}일",
            f"{net_value/10000:,.0f}만원",
        ]
        rounded_box(c, x0, y, sum(widths), 51, color, color, 10)
        x = x0
        for value, w in zip(values, widths):
            draw_centered(c, value, x + 3, y + 20, w - 6, 10 if posts == 3 else 9, FONT_XB, INK if color != ROSE else white)
            x += w
        y -= 67

    rounded_box(c, M, 78, 773, 75, PAPER_2, PAPER_2, 12)
    draw_text(c, "기준 예시", M + 16, 127, 70, 8.5, FONT_XB, ROSE)
    draw_text(c, "수동 30분 → 프로그램 7분 · 1개당 23분 절감 · 시급 15,000원 · 365일 사용. 실제 시간·PC·상품·검수량에 따라 달라지며 수익이나 매출을 의미하지 않는다.", M + 94, 128, 665, 8.3, FONT_BOLD, INK, leading=11, max_lines=2)
    c.showPage()


def savings_content_page(c: canvas.Canvas, page_no: int) -> None:
    page_base(c, page_no, "TIME-SAVING CONTENT")
    title(c, "마케팅 문구", "시간 절약을 클릭하게 만드는 콘텐츠 3개를 그대로 사용한다")
    cards = [
        (
            "01 · 연간 시간",
            "매일 3개면\n1년에 약 420시간",
            "수동 30분 - 프로그램 7분 = 23분. 23분 × 3개 × 365일 = 419.75시간.",
            "420시간 숫자 → 달력 365장 → 수동/프로그램 타이머. 하단 ‘계산 예시’.",
            "내 하루 게시량으로 계산해보기",
            YELLOW,
        ),
        (
            "02 · 손익분기",
            "70만원이 비싼지\n41일이 비싼지",
            "하루 3개·시급 15,000원이면 하루 절감 노동가치 17,250원. 70만원과 같아지는 시점은 약 40.6일.",
            "700,000원 ÷ 17,250원/일 계산식이 한 줄씩 완성되는 15초 영상.",
            "시급과 게시량으로 계산 요청",
            MINT,
        ),
        (
            "03 · 실측 예고",
            "광고 문구 말고\n링크 10개로 직접 재겠습니다",
            "같은 링크·같은 문안 수·같은 계정 조건으로 수동과 프로그램을 각각 10번 측정하고 가장 빠른 값이 아닌 중앙값을 공개.",
            "좌우 타이머 + 측정 조건 카드 + 10개 결과표. 실패 작업도 포함.",
            "실측 결과 공개 알림 받기",
            ROSE,
        ),
    ]
    x_positions = [M, 298, 562]
    for (label, hook, body, visual, cta, color), x in zip(cards, x_positions):
        rounded_box(c, x, 75, 245, 385, SOFT_WHITE, INK, 15, 1, shadow=True)
        c.setFillColor(color)
        c.roundRect(x, 398, 245, 62, 15, fill=1, stroke=0)
        c.rect(x, 398, 245, 23, fill=1, stroke=0)
        draw_text(c, label, x + 14, 438, 210, 8.5, FONT_XB, INK if color != ROSE else white)
        draw_text(c, hook, x + 14, 378, 215, 15, FONT_XB, INK, leading=19, max_lines=3)
        c.setStrokeColor(LIGHT_GRAY)
        c.line(x + 14, 318, x + 231, 318)
        draw_text(c, "본문", x + 14, 300, 45, 7.5, FONT_XB, ROSE)
        draw_text(c, body, x + 14, 280, 216, 7.6, FONT_SEMI, INK, leading=10.5, max_lines=6)
        draw_text(c, "필요 영상/이미지", x + 14, 195, 92, 7.5, FONT_XB, BLUE)
        draw_text(c, visual, x + 14, 176, 216, 7.4, FONT_SEMI, INK, leading=10.2, max_lines=5)
        rounded_box(c, x + 12, 91, 221, 49, PAPER_2, PAPER_2, 10)
        draw_text(c, "CTA", x + 22, 122, 30, 7.2, FONT_XB, ROSE)
        draw_text(c, cta, x + 54, 122, 164, 7.5, FONT_BOLD, INK, leading=9.5, max_lines=2)
    c.showPage()


def channel_map_page(c: canvas.Canvas, page_no: int) -> None:
    page_base(c, page_no, "CHANNEL MAP")
    title(c, "채널별 3개", "같은 원본도 채널의 습관에 맞춰 완전히 다르게 보이게 한다")
    channels = [
        ("Threads", "P1 텍스트 경험담", "P2 A/B 이미지", "P3 화면+답글 CTA", ROSE),
        ("Instagram", "P1 Reel", "P2 5장 Carousel", "P3 Story 3장", YELLOW),
        ("YouTube", "P1 Short", "P2 Short", "P3 Community", MINT),
        ("TikTok", "P1 얼굴 원테이크", "P2 분할 비교", "P3 실제 화면 컷", LILAC),
        ("Naver Blog", "P1 핵심 장문", "P2 비교 포스트", "P3 FAQ 포스트", CORAL),
        ("Facebook", "P1 Reel", "P2 이미지 경험담", "P3 장문 증명", BLUE),
        ("커뮤니티", "P1 경험 공유", "P2 질문/투표", "P3 답변형 사례", ROSE),
        ("강의 웹", "P1 첫 화면 훅", "P2 데모/FAQ", "P3 지원·좌석 업데이트", MINT),
    ]
    positions = [(M, 350), (430, 350), (M, 254), (430, 254), (M, 158), (430, 158), (M, 62), (430, 62)]
    for (name, p1, p2, p3, color), (x, y) in zip(channels, positions):
        rounded_box(c, x, y, 377, 80, SOFT_WHITE, INK, 13, 1, shadow=True)
        c.setFillColor(color)
        c.roundRect(x, y, 10, 80, 5, fill=1, stroke=0)
        draw_text(c, name, x + 22, y + 61, 95, 10.5, FONT_XB, INK)
        draw_text(c, p1, x + 120, y + 62, 225, 7.6, FONT_BOLD, ROSE)
        draw_text(c, p2, x + 120, y + 40, 225, 7.6, FONT_SEMI, INK)
        draw_text(c, p3, x + 120, y + 18, 225, 7.6, FONT_SEMI, GRAY)
    c.showPage()


def timing_page(c: canvas.Canvas, page_no: int) -> None:
    page_base(c, page_no, "DAILY TIMING")
    title(c, "업로드 시간", "동시에 복사해 올리지 말고 20분 간격으로 파동을 만든다")
    rows = [
        ("P1", "08:30", "08:50", "09:10", "09:30", "09:50", "10:10", "10:30", "10:50", YELLOW),
        ("P2", "13:30", "13:50", "14:10", "14:30", "14:50", "15:10", "15:30", "15:50", MINT),
        ("P3", "19:30", "19:50", "20:10", "20:30", "20:50", "21:10", "21:30", "21:50", ROSE),
    ]
    headers = ["파동", "Threads", "Instagram", "TikTok", "YouTube", "Blog", "Facebook", "Community", "강의 웹"]
    widths = [60] + [88] * 8
    x0, y = M, 406
    c.setFillColor(INK)
    c.roundRect(x0, y, sum(widths), 38, 10, fill=1, stroke=0)
    x = x0
    for h, w in zip(headers, widths):
        draw_centered(c, h, x + 3, y + 13, w - 6, 7.2, FONT_BOLD, white)
        x += w
    y -= 78
    for vals in rows:
        *cells, color = vals
        rounded_box(c, x0, y, sum(widths), 60, color, color, 11)
        x = x0
        for idx, (cell, w) in enumerate(zip(cells, widths)):
            draw_centered(c, cell, x + 3, y + 24, w - 6, 8.5 if idx else 11, FONT_XB, INK)
            x += w
        y -= 81

    rounded_box(c, M, 69, 773, 92, PAPER_2, PAPER_2, 13)
    draw_text(c, "DAY 10 예외", M + 16, 135, 90, 9.5, FONT_XB, ROSE)
    draw_text(c, "8/20 YouTube는 20:30~21:30 라이브. 종료 후 강의 웹 21:35 → Instagram 21:40 → TikTok 21:50 → Facebook 22:00 → 커뮤니티 22:10 → Blog 22:20. Threads는 21:30 결과 글을 올린다.", M + 108, 136, 645, 8.7, FONT_BOLD, INK, leading=12, max_lines=3)
    c.showPage()


def visual_rules_page(c: canvas.Canvas, page_no: int) -> None:
    page_base(c, page_no, "HOOK & VISUAL RULES", dark=True)
    title(c, "후킹 규칙", "첫 1초에 설명하지 말고 빈칸을 만든다", dark=True)
    cards = [
        ("숫자", "40분·4개·150시간", "숫자의 이유는 다음 장면에서 공개", YELLOW),
        ("반전", "프로그램만이면 나도 안 산다", "예상과 반대되는 문장을 먼저", MINT),
        ("비교", "수동 vs 프로그램", "좌우 화면으로 선택하게 만들기", LILAC),
        ("공개", "오류도 화면을 끄지 않는다", "숨길 것 같은 장면을 먼저 약속", CORAL),
        ("경고", "잘 돌아갈 때가 더 위험하다", "불안 뒤에 실제 안전장치 제시", ROSE),
    ]
    x = M
    for name, hook, desc, color in cards:
        rounded_box(c, x, 310, 142, 143, HexColor("#1D2029"), HexColor("#454956"), 14)
        pill(c, name, x + 13, 421, color, INK if color not in (ROSE,) else white, 7)
        draw_text(c, hook, x + 13, 389, 116, 10.5, FONT_XB, white, leading=14, max_lines=3)
        draw_text(c, desc, x + 13, 337, 116, 7.3, FONT_SEMI, HexColor("#C9CBD3"), leading=10, max_lines=3)
        x += 157

    rounded_box(c, M, 142, 773, 125, PAPER, PAPER, 15)
    draw_text(c, "영상 0~20초 공식", M + 18, 240, 160, 12, FONT_XB, INK)
    stages = [
        ("0~1초", "훅 문장", ROSE),
        ("1~4초", "문제 장면", YELLOW),
        ("4~13초", "실제 화면/비교", MINT),
        ("13~17초", "결과·한계", LILAC),
        ("17~20초", "행동 하나", CORAL),
    ]
    x = M + 18
    for time, label, color in stages:
        rounded_box(c, x, 170, 137, 48, color, color, 10)
        draw_text(c, time, x + 10, 204, 52, 7.2, FONT_BOLD, INK)
        draw_text(c, label, x + 10, 186, 115, 8.5, FONT_XB, INK)
        x += 148

    draw_text(c, "금지", M, 106, 50, 9, FONT_XB, CORAL)
    draw_text(c, "로고 인트로 · ‘안녕하세요’ · 기능 목록 낭독 · 8단어 넘는 표지 · 가짜 후기 · 가짜 남은 자리 · 미측정 시간 절감", M + 58, 107, 710, 8.5, FONT_BOLD, white)
    draw_text(c, "필수", M, 77, 50, 9, FONT_XB, MINT)
    draw_text(c, "첫 문장 0.3초 안에 시작 · 실제 화면 표기 · 개인정보 블러 · 자막 2줄 이하 · CTA 1개 · 제휴 고지 규칙 확인", M + 58, 78, 710, 8.5, FONT_BOLD, white)
    c.showPage()


def asset_page(c: canvas.Canvas, page_no: int) -> None:
    page_base(c, page_no, "ASSET PRODUCTION")
    title(c, "촬영 목록", "이 파일만 준비하면 30개 원본과 마지막 라이브를 만들 수 있다")
    assets = [
        ("A-ROLL 10개", "DAY별 훅을 얼굴 정면으로 8~12초씩. 9:16, 눈높이, 첫 문장부터 촬영.", ROSE),
        ("SCREEN 10개", "링크 입력·문안 4종·이미지·대기열·승인·실패 로그·다계정·PDF·예약·원격지원.", MINT),
        ("STILL 12개", "40분 타이머·70만원 구성·호환표·4개 검수·150시간·실제 좌석·지원 SLA.", LILAC),
        ("LIVE 1세트", "웹캠 1080p·화면 녹화·마이크 백업·테스트 링크·질문 보드·결제/체험 QR.", YELLOW),
    ]
    y = 386
    for name, desc, color in assets:
        rounded_box(c, M, y, 390, 72, SOFT_WHITE, INK, 12, 1, shadow=True)
        c.setFillColor(color)
        c.roundRect(M, y, 9, 72, 5, fill=1, stroke=0)
        draw_text(c, name, M + 22, y + 51, 130, 10, FONT_XB, INK)
        draw_text(c, desc, M + 150, y + 53, 252, 7.5, FONT_SEMI, INK, leading=10, max_lines=3)
        y -= 83

    preview = ROOT / "output" / "organic-launch-pack-v2" / "previews" / "instagram-carousel-preview.png"
    if preview.exists():
        rounded_box(c, 455, 221, 352, 237, PAPER_2, INK, 14, 1, shadow=True)
        c.drawImage(ImageReader(str(preview)), 468, 236, width=326, height=197, preserveAspectRatio=True, anchor="c", mask="auto")
        pill(c, "기존 재사용 가능", 472, 409, YELLOW, INK, 7)

    rounded_box(c, 455, 62, 352, 137, INK, INK, 14)
    draw_text(c, "파일 이름 규칙", 472, 173, 150, 11, FONT_XB, white)
    names = [
        "D01_P1_FACE_hook.mp4",
        "D01_P2_AB_card.png",
        "D01_P3_APP_flow.mp4",
        "D10_LIVE_full.mp4 / D10_LIVE_clip01.mp4",
    ]
    yy = 143
    for name in names:
        draw_text(c, name, 472, yy, 305, 7.8, FONT_SEMI, HexColor("#D6D8DF"))
        yy -= 22
    c.showPage()


def support_platform_content_page(c: canvas.Canvas, page_no: int) -> None:
    page_base(c, page_no, "7 PLATFORM CONTENT", dark=True)
    title(
        c,
        "이 일곱 이름을 작게 숨기지 말고 전면에 보여준다",
        "‘다양한 쇼핑몰’보다 정확한 플랫폼명이 훨씬 강한 증거가 된다",
        dark=True,
    )

    names = [
        ("01", "쿠팡파트너스", YELLOW),
        ("02", "네이버 쇼핑커넥트", MINT),
        ("03", "토스쇼핑 파트너스", LILAC),
        ("04", "오늘의집 큐레이터", CORAL),
        ("05", "무신사 파트너스", BLUE),
        ("06", "컬리 큐레이터", ROSE),
        ("07", "올리브영 큐레이터", YELLOW),
    ]
    for idx, (no, name, color) in enumerate(names):
        row, col = divmod(idx, 4)
        card_w = 181 if row == 0 else 199
        start_x = M if row == 0 else 126
        gap = 12 if row == 0 else 16
        x = start_x + col * (card_w + gap)
        y = 346 if row == 0 else 263
        rounded_box(c, x, y, card_w, 66, HexColor("#1D2029"), HexColor("#454956"), 12)
        pill(c, no, x + 10, y + 38, color, INK if color not in (ROSE, BLUE) else white, 6.5)
        draw_text(c, name, x + 10, y + 27, card_w - 20, 9, FONT_XB, white, max_lines=1)

    rounded_box(c, M, 67, 374, 164, PAPER, PAPER, 14)
    draw_text(c, "필수 이미지·영상", M + 17, 204, 150, 11, FONT_XB, ROSE)
    shots = [
        "이미지: 7개 플랫폼명 4+3 카드 + ‘공식 지원 7곳’",
        "영상: 7개 링크 유형 → 같은 입력창 → 성공 이력",
        "화면: 링크 인식·문안 생성·고지·대기열·게시 결과",
        "주의: 제휴 ID·고객정보 블러, 실제 성공 화면만 사용",
    ]
    yy = 176
    for shot in shots:
        c.setFillColor(ROSE)
        c.circle(M + 22, yy + 2, 3.3, fill=1, stroke=0)
        draw_text(c, shot, M + 34, yy + 6, 325, 7.7, FONT_SEMI, INK, leading=10, max_lines=2)
        yy -= 30

    rounded_box(c, 425, 67, 382, 164, HexColor("#1D2029"), HexColor("#454956"), 14)
    draw_text(c, "바로 쓰는 후킹 3개", 443, 204, 170, 11, FONT_XB, YELLOW)
    hooks = [
        "“쿠팡만 된다고요? 국내 쇼핑 제휴 7곳을 지원합니다.”",
        "“링크 7개, 입력창은 하나였습니다.”",
        "“프롬프트 7세트가 아니라 프로그램 하나로 돌립니다.”",
    ]
    yy = 171
    for idx, hook in enumerate(hooks, 1):
        c.setFillColor([YELLOW, MINT, LILAC][idx - 1])
        c.circle(445, yy + 3, 9, fill=1, stroke=0)
        draw_centered(c, str(idx), 436, yy, 18, 6.5, FONT_XB, INK)
        draw_text(c, hook, 462, yy + 7, 320, 8.2, FONT_BOLD, white, leading=11, max_lines=2)
        yy -= 39
    c.showPage()


def campaign_date(day_number: int) -> date:
    return CAMPAIGN_START + timedelta(days=day_number - 1)


def date_label(day_number: int) -> str:
    current = campaign_date(day_number)
    return f"{current.month}/{current.day} ({WEEKDAYS_KO[current.weekday()]})"


def day_page(c: canvas.Canvas, page_no: int, day: dict) -> None:
    page_base(c, page_no, f"DAY {day['day']:02d} · {day['goal']}")
    title(c, f"DAY {day['day']:02d} · {date_label(day['day'])}", day["theme"])
    colors = [YELLOW, MINT, ROSE]
    x_positions = [M, 298, 562]
    master_slots = ["원본 P1 · 오전", "원본 P2 · 오후", "원본 P3 · 저녁"]
    if day["day"] == 10:
        master_slots[2] = "P3 · 20:30 라이브/후속"
    for post, color, x, master_slot in zip(day["posts"], colors, x_positions, master_slots):
        rounded_box(c, x, 67, 245, 390, SOFT_WHITE, INK, 15, 1, shadow=True)
        c.setFillColor(color)
        c.roundRect(x, 399, 245, 58, 15, fill=1, stroke=0)
        c.rect(x, 399, 245, 23, fill=1, stroke=0)
        draw_text(c, master_slot, x + 14, 437, 210, 8.5, FONT_XB, INK if color != ROSE else white)
        draw_text(c, post["hook"], x + 14, 384, 216, 13.2, FONT_XB, INK, leading=17, max_lines=3)
        c.setStrokeColor(LIGHT_GRAY)
        c.line(x + 14, 333, x + 231, 333)

        draw_text(c, "말할 내용", x + 14, 316, 72, 7.3, FONT_XB, ROSE)
        draw_text(c, post["script"], x + 14, 297, 216, 7.25, FONT_SEMI, INK, leading=10.2, max_lines=6)

        draw_text(c, "영상", x + 14, 224, 40, 7.3, FONT_XB, BLUE)
        draw_text(c, post["video"], x + 14, 206, 216, 7.0, FONT_SEMI, INK, leading=9.6, max_lines=4)

        draw_text(c, "이미지", x + 14, 158, 44, 7.3, FONT_XB, HexColor("#8B5CF6"))
        draw_text(c, post["image"], x + 14, 140, 216, 7.0, FONT_SEMI, INK, leading=9.6, max_lines=3)

        rounded_box(c, x + 12, 81, 221, 42, PAPER_2, PAPER_2, 9)
        draw_text(c, "CTA", x + 23, 108, 28, 7, FONT_XB, ROSE)
        draw_text(c, post["cta"], x + 52, 108, 167, 7.2, FONT_BOLD, INK, leading=9, max_lines=3)
    c.showPage()


def short_hook(text_value: str, limit: int = 35) -> str:
    value = " ".join(text_value.split())
    return value if len(value) <= limit else value[: limit - 1] + "…"


def channel_schedule_page(c: canvas.Canvas, page_no: int, day: dict) -> None:
    page_base(c, page_no, f"DATE × CHANNEL · DAY {day['day']:02d}")
    title(c, f"{date_label(day['day'])} · DAY {day['day']:02d}", f"8개 채널에 올릴 3개 콘텐츠 - {day['theme']}")
    hooks = [short_hook(post["hook"]) for post in day["posts"]]
    formats = {
        "Threads": ("경험담", "질문", "화면+CTA"),
        "Instagram": ("Reel", "Carousel", "Story/Clip"),
        "YouTube": ("Short 1", "Short 2", "Community"),
        "TikTok": ("원테이크", "분할 비교", "실제 화면"),
        "Naver Blog": ("핵심 장문", "비교 글", "FAQ/요약"),
        "Facebook": ("Reel", "이미지담", "장문/Clip"),
        "커뮤니티": ("경험 질문", "투표", "답변 사례"),
        "강의 웹": ("첫 화면", "데모/FAQ", "증거/CTA"),
    }
    colors = {
        "Threads": ROSE,
        "Instagram": YELLOW,
        "YouTube": MINT,
        "TikTok": LILAC,
        "Naver Blog": CORAL,
        "Facebook": BLUE,
        "커뮤니티": ROSE,
        "강의 웹": MINT,
    }
    channel_order = ["Threads", "Instagram", "YouTube", "TikTok", "Naver Blog", "Facebook", "커뮤니티", "강의 웹"]
    channels = []
    for channel in channel_order:
        p1, p2, p3 = CHANNEL_UPLOAD_TIMES[channel]
        if day["day"] == 10:
            p3 = DAY10_P3_TIMES[channel]
        f1, f2, f3 = formats[channel]
        if day["day"] == 10 and channel == "YouTube":
            f3 = "LIVE"
        elif day["day"] == 10:
            f3 = "라이브 후속"
        entries = [(f"{p1} {f1}", hooks[0]), (f"{p2} {f2}", hooks[1]), (f"{p3} {f3}", hooks[2])]
        channels.append((channel, entries, colors[channel]))
    positions = [(M, 350), (430, 350), (M, 254), (430, 254), (M, 158), (430, 158), (M, 62), (430, 62)]
    for (channel, entries, color), (x, y) in zip(channels, positions):
        rounded_box(c, x, y, 377, 82, SOFT_WHITE, INK, 12, 1, shadow=True)
        c.setFillColor(color)
        c.roundRect(x, y, 9, 82, 5, fill=1, stroke=0)
        draw_text(c, channel, x + 20, y + 63, 92, 9.5, FONT_XB, INK)
        yy = y + 64
        for label, hook in entries:
            draw_text(c, label, x + 112, yy, 88, 6.8, FONT_XB, ROSE if color != ROSE else BLUE)
            draw_text(c, hook, x + 201, yy, 158, 6.7, FONT_SEMI, INK, max_lines=1)
            yy -= 21
    c.showPage()


def live_page(c: canvas.Canvas, page_no: int) -> None:
    page_base(c, page_no, "ONE LIVE ONLY", dark=True)
    title(c, "DAY 10 · 20:30", "마지막 날 한 번의 라이브로 궁금증과 결제를 닫는다", dark=True)
    segments = [
        ("00~03", "약속", "돈이 아니라 ‘링크 1개가 실제 게시까지 가는지’를 검증한다고 선언", YELLOW),
        ("03~08", "진단", "가장 오래 걸리는 단계 투표 → 오늘 보여줄 순서를 즉석 조정", MINT),
        ("08~15", "교육", "수작업 5단계·시간값·프롬프트 강의와 프로그램 사용의 차이", LILAC),
        ("15~30", "실전", "권리 확인된 링크 입력 → 분석 → 문안 4종 → 이미지·고지 → 업로드", CORAL),
        ("30~35", "실패", "로그인 만료·이미지 없음·중복 링크를 숨기지 않고 중단/복구", BLUE),
        ("35~40", "예고", "공식 지원 7개 제휴 플랫폼·사람 검수·70만원 구성의 첫 공개", MINT),
        ("40~50", "Q&A", "업보트 상위 질문부터 답하고, 계정·지원·비용 반론을 회수", LILAC),
        ("50~58", "오퍼", "70만원 제공물·지원 범위·공급·환불 조건을 한 화면에 공개", ROSE),
        ("58~60", "행동", "‘내 작업 적합성 확인’ 단일 CTA를 한 번 더 안내", YELLOW),
    ]
    y = 429
    for time, name, desc, color in segments:
        rounded_box(c, M, y, 773, 31, HexColor("#1D2029"), HexColor("#454956"), 8)
        pill(c, time, M + 12, y + 7, color, INK if color not in (ROSE, BLUE) else white, 6.5, height=17)
        draw_text(c, name, M + 92, y + 21, 62, 7.6, FONT_XB, white)
        draw_text(c, desc, M + 157, y + 21, 625, 7.0, FONT_SEMI, HexColor("#D7D9E0"), max_lines=1)
        y -= 37

    rounded_box(c, M, 53, 773, 76, PAPER, PAPER, 13)
    draw_text(c, "라이브 직후 산출물", M + 16, 104, 130, 9, FONT_XB, ROSE)
    draw_text(c, "18초 하이라이트 3개 · 질문 답변 3개 · 60초 요약 1개 · 실제 오류/해결 1개 · 다음 날 블로그 정리 1개. 같은 라이브를 잘라 후속 주간의 증거로 재사용한다.", M + 151, 105, 635, 8.3, FONT_BOLD, INK, leading=12, max_lines=2)
    c.showPage()


def free_class_pattern_page(c: canvas.Canvas, page_no: int) -> None:
    page_base(c, page_no, "FREE CLASS BENCHMARK")
    title(c, "보통 무료 첫 강의는 무엇을 하는가", "정보를 많이 주는 것이 아니라 작은 결과를 먼저 완성시킨다")
    rows = [
        ("1 · 등록", "문제와 얻을 결과를 한 문장으로 약속", "‘링크 1개가 실제 Threads 게시까지 가는 흐름을 판단’", YELLOW),
        ("2 · 참여", "초반 폴·질문으로 현재 막힌 지점을 분류", "문구 / 이미지 / 업로드 / 다계정 중 하나를 선택", MINT),
        ("3 · 퀵윈", "무료 수업 안에서 작지만 완결된 결과 제공", "권리 확인된 링크 1개로 문안 4종과 실제 게시 1개 완성", LILAC),
        ("4 · 신뢰", "성공만이 아니라 실패·비용·수동 지점 공개", "로그인 만료·이미지 없음·중복 링크의 중단/복구 시연", CORAL),
        ("5 · 전환", "마지막에 대상·제공물·가격·조건을 투명하게 공개", "1년 사용·90분 강의·원격 과외·PDF·70만원을 5분에 설명", ROSE),
    ]
    y = 397
    for label, common, ours, color in rows:
        rounded_box(c, M, y, 773, 58, SOFT_WHITE, INK, 11, 1, shadow=True)
        pill(c, label, M + 13, y + 31, color, INK if color != ROSE else white, 7.0)
        draw_text(c, "일반 구조", M + 125, y + 42, 65, 6.8, FONT_XB, GRAY)
        draw_text(c, common, M + 193, y + 42, 555, 7.9, FONT_BOLD, INK, max_lines=1)
        draw_text(c, "우리 적용", M + 125, y + 20, 65, 6.8, FONT_XB, ROSE)
        draw_text(c, ours, M + 193, y + 20, 555, 7.9, FONT_SEMI, INK, max_lines=1)
        y -= 64

    rounded_box(c, M, 50, 773, 65, INK, INK, 12)
    draw_text(c, "근거 기반 시작값", M + 15, 91, 105, 8.5, FONT_XB, YELLOW)
    draw_text(c, "공식 자료에서 교육:판매의 보편적 비율은 확인되지 않았다. 60분 중 교육·데모 40분 + Q&A 10분 + 오퍼·행동 10분을 파일럿으로 측정한다.", M + 125, 92, 640, 8.2, FONT_BOLD, white, leading=11, max_lines=2)
    draw_link(c, "HubSpot Webinar Best Practices", "https://blog.hubspot.com/blog/tabid/6307/bid/2391/10-best-practices-for-webinars-or-webcasts.aspx", M + 125, 61, 205, 6.2)
    draw_link(c, "Zoom Webinar Settings", "https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0057935", M + 342, 61, 175, 6.2)
    draw_link(c, "Thinkific Lead Magnets", "https://support.thinkific.com/hc/en-us/articles/24980364410263-Use-Coaching-Webinars-as-Lead-Magnets", M + 529, 61, 205, 6.2)
    c.showPage()


def live_promise_page(c: canvas.Canvas, page_no: int) -> None:
    page_base(c, page_no, "LIVE PROMISE", dark=True)
    title(c, "오늘 방송의 한 문장", "‘돈 버는 법’이 아니라 내 반복 작업을 줄일 수 있는지 직접 판정한다", dark=True)
    rounded_box(c, M, 340, 773, 111, PAPER, PAPER, 18)
    draw_text(c, "시청자가 60분 뒤 가져갈 것", M + 18, 423, 230, 12, FONT_XB, ROSE)
    wins = [
        "수작업 5단계와 내 시간값을 적는 1장 체크표",
        "자동으로 되는 일 / 사람이 확인할 일 / 멈춰야 할 일의 경계",
        "무료 월 5회로 내 링크 1개를 시험하는 정확한 시작 순서",
    ]
    yy = 393
    for idx, win in enumerate(wins, 1):
        c.setFillColor([YELLOW, MINT, LILAC][idx - 1])
        c.circle(M + 27, yy + 2, 8, fill=1, stroke=0)
        draw_centered(c, str(idx), M + 19, yy - 1, 16, 6.5, FONT_XB, INK)
        draw_text(c, win, M + 44, yy + 6, 710, 8.7, FONT_BOLD, INK)
        yy -= 27

    cards = [
        ("현재 확인된 사실", ["Windows 앱", "국내 쇼핑 제휴 7개 플랫폼", "Threads 브라우저 세션 업로드", "문안 4종·고지·이력·다계정"], MINT),
        ("방송에서 보장하지 않는 것", ["수익·조회·구매전환", "계정 안전·정책 불변", "모든 제휴 링크 호환", "이미지 권리·상품 정확성의 자동 책임"], CORAL),
    ]
    for i, (name, items, color) in enumerate(cards):
        x = M + i * 395
        rounded_box(c, x, 132, 378, 175, HexColor("#1D2029"), HexColor("#454956"), 15)
        pill(c, name, x + 15, 268, color, INK, 8)
        y = 238
        for item in items:
            c.setFillColor(color)
            c.circle(x + 23, y + 2, 3.5, fill=1, stroke=0)
            draw_text(c, item, x + 36, y + 6, 315, 8.2, FONT_SEMI, white)
            y -= 29

    rounded_box(c, M, 53, 773, 52, ROSE, ROSE, 12)
    draw_text(c, "진행자 첫 문장", M + 16, 85, 92, 8, FONT_XB, white)
    draw_text(c, "오늘은 수익을 약속하지 않습니다. 링크 1개가 실제 게시까지 가는 전 과정을 보고, 이 흐름이 내 반복 작업을 줄이는지 직접 판단하는 방송입니다.", M + 115, 86, 640, 8.5, FONT_BOLD, white, leading=11, max_lines=2)
    c.showPage()


def live_run_of_show_page(c: canvas.Canvas, page_no: int) -> None:
    page_base(c, page_no, "60-MIN RUN OF SHOW")
    title(c, "60분 큐시트", "교육·데모 40분 · 질문 10분 · 오퍼·행동 10분")
    rows = [
        ("00~03", "약속", "카메라", "오늘 결과물·질문 방식·녹화 여부", "이탈 방지", YELLOW),
        ("03~08", "진단", "폴 화면", "가장 오래 걸리는 단계 4지선다", "개인화", MINT),
        ("08~15", "교육", "수작업 지도", "5단계·시간값·프롬프트 강의와 차이", "문제 재정의", LILAC),
        ("15~30", "실전", "앱+Threads", "링크→분석→문안→이미지/고지→게시", "작동 증거", CORAL),
        ("30~35", "실패", "오류 로그", "로그인 만료·이미지 없음·중복 링크", "불신 해소", BLUE),
        ("35~40", "예고", "적합성 표", "지원 7곳·사람 검수·70만원 첫 공개", "조기 CTA", MINT),
        ("40~50", "Q&A", "질문 업보트", "상위 질문→가격·초보·계정·지원", "반론 회수", LILAC),
        ("50~58", "오퍼", "구성/조건", "70만원·지원·공급·환불 조건", "전환", ROSE),
        ("58~60", "행동", "CTA 화면", "내 작업 적합성 확인 1개", "다음 행동", YELLOW),
    ]
    x0, y = M, 419
    widths = [68, 72, 105, 352, 105]
    headers = ["시간", "파트", "화면", "말할 핵심", "목적"]
    c.setFillColor(INK)
    c.roundRect(x0, 453, 773, 27, 8, fill=1, stroke=0)
    x = x0
    for head, width in zip(headers, widths):
        draw_text(c, head, x + 8, 470, width - 12, 7.5, FONT_XB, white)
        x += width
    for time, part, screen, line, goal, color in rows:
        rounded_box(c, x0, y, 773, 34, SOFT_WHITE, INK, 7)
        c.setFillColor(color)
        c.roundRect(x0, y, 7, 34, 3, fill=1, stroke=0)
        vals = [time, part, screen, line, goal]
        x = x0
        for idx, (val, width) in enumerate(zip(vals, widths)):
            draw_text(c, val, x + 10, y + 22, width - 16, 7.2 if idx != 3 else 7.5, FONT_XB if idx < 2 else FONT_SEMI, INK, max_lines=1)
            x += width
        y -= 40
    rounded_box(c, M, 51, 773, 44, PAPER_2, PAPER_2, 11)
    draw_text(c, "운영 기준", M + 14, 79, 67, 8, FONT_XB, ROSE)
    draw_text(c, "20:28에 시작하지 않는다. 20:30 정시 오프닝, 21:15 본 강의 종료, 21:30 방송 종료를 화면 타이머로 지킨다.", M + 88, 80, 660, 8.3, FONT_BOLD, INK)
    c.showPage()


def live_opening_script_page(c: canvas.Canvas, page_no: int) -> None:
    page_base(c, page_no, "EXACT SCRIPT · 00~15")
    title(c, "오프닝·진단·교육 대본", "길게 소개하지 말고 3분 안에 시청 이유를 만든다")
    blocks = [
        ("00~03 · 약속", "화면: 얼굴 + ‘링크 1개 → 실제 게시’", "“오늘은 수익을 약속하는 방송이 아닙니다. 상품 링크 1개가 문안·이미지·고지를 거쳐 실제 Threads 게시까지 가는 장면을 그대로 보여드리겠습니다. 중간에 오류가 나도 화면을 끄지 않겠습니다.”", YELLOW),
        ("03~08 · 진단", "화면: 4지선다 폴", "“지금 가장 오래 걸리는 곳을 골라주세요. 1 문구, 2 이미지, 3 업로드, 4 여러 계정 관리. 가장 많은 답부터 실제 화면에서 확인하겠습니다. 질문은 지금부터 남기되 40분부터 업보트 순으로 답합니다.”", MINT),
        ("08~12 · 문제", "화면: 수작업 5단계 지도", "“보통은 상품 고르기, 문구 만들기, 이미지 찾기, 고지 붙이기, 계정마다 올리기를 따로 합니다. 무료 프롬프트는 문구 한 번을 줄여주지만 다음 상품에서도 사람이 다시 조립합니다.”", LILAC),
        ("12~15 · 차이", "화면: 프롬프트 강의 vs 프로그램", "“이 프로그램의 장점은 프롬프트를 더 잘 쓰는 법을 가르치는 데 있지 않습니다. 링크를 넣으면 반복 흐름이 이어집니다. 대신 상품 선택, 이미지 권리, 고지 정확성, 로그인과 최종 결과는 사람이 확인해야 합니다.”", CORAL),
    ]
    y = 374
    for label, screen, script, color in blocks:
        rounded_box(c, M, y, 773, 84, SOFT_WHITE, INK, 12, 1, shadow=True)
        pill(c, label, M + 15, y + 53, color, INK, 7.6)
        draw_text(c, screen, M + 184, y + 63, 555, 7.2, FONT_XB, ROSE)
        draw_text(c, script, M + 16, y + 36, 735, 8.1, FONT_SEMI, INK, leading=11, max_lines=3)
        y -= 91
    rounded_box(c, M, 51, 773, 42, INK, INK, 10)
    draw_text(c, "금지", M + 15, 78, 40, 8, FONT_XB, YELLOW)
    draw_text(c, "경력 소개 3분 · 확인 안 된 수익 인증 · ‘누구나’ · ‘완전 자동’ · ‘계정 안전’ · 다음 파트 예고만 반복하기", M + 62, 79, 690, 8.2, FONT_BOLD, white)
    c.showPage()


def live_demo_script_page(c: canvas.Canvas, page_no: int) -> None:
    page_base(c, page_no, "EXACT SCRIPT · 15~35", dark=True)
    title(c, "무편집 데모·실패 대본", "말보다 커서를 천천히 움직이고 매 화면을 2~5초 멈춘다", dark=True)
    steps = [
        ("15~17", "입력", "공식 지원 7개 플랫폼 중 시청자 수요가 높은 실제 링크 1개를 붙인다.", "“현재 지원하는 일곱 플랫폼을 먼저 보여드렸고, 오늘은 그중 이 링크 하나를 처음부터 끝까지 깊게 시연하겠습니다.”", YELLOW),
        ("17~20", "분석", "쇼핑몰·상품명·공개 특징 인식 화면을 멈춘다.", "“틀린 상품명이나 과장된 특징이 보이면 여기서 중단합니다. 자동 생성보다 잘못된 게시를 막는 게 먼저입니다.”", MINT),
        ("20~24", "문안", "타깃·편의·반전·사용 장면 4종을 만들고 1개만 읽는다.", "“프롬프트를 복사해 네 번 묻는 대신 앱이 네 관점을 만듭니다. 저는 첫 문장과 사실만 고릅니다.”", LILAC),
        ("24~27", "이미지/고지", "이미지 출처·사용 권리와 제휴 고지 문구를 확대한다.", "“이미지가 검색됐다는 사실은 사용 권리 보장이 아닙니다. 권리가 불명확하면 이미지 없이 가거나 내 자산으로 교체합니다.”", CORAL),
        ("27~30", "게시", "계정 선택→브라우저 세션→Threads 공개 게시→이력 확인.", "“공식 API 방식이 아니라 저장된 브라우저 세션을 사용합니다. 로그인 만료·2FA·CAPTCHA가 나오면 우회하지 않고 멈춥니다.”", BLUE),
        ("30~35", "실패", "로그인 만료·이미지 없음·중복 링크 중 1개를 재현한다.", "“자동화가 멈춰야 하는 장면입니다. 오류를 성공으로 보이게 하지 않고 로그를 남긴 뒤 사람이 해결합니다.”", ROSE),
    ]
    y = 416
    for time, part, action, script, color in steps:
        rounded_box(c, M, y, 773, 55, HexColor("#1D2029"), HexColor("#454956"), 10)
        pill(c, time, M + 13, y + 29, color, INK if color not in (ROSE, BLUE) else white, 6.8)
        draw_text(c, part, M + 90, y + 40, 55, 7.8, FONT_XB, white)
        draw_text(c, action, M + 150, y + 40, 610, 7.5, FONT_BOLD, HexColor("#D7D9E0"), max_lines=1)
        draw_text(c, script, M + 90, y + 19, 665, 7.2, FONT_SEMI, white, leading=9.5, max_lines=2)
        y -= 58
    rounded_box(c, M, 51, 773, 43, PAPER, PAPER, 11)
    draw_text(c, "데모 성공 기준", M + 14, 79, 85, 8, FONT_XB, ROSE)
    draw_text(c, "생성 화면이 아니라 공개된 Threads 게시물·고지·올바른 링크·업로드 이력까지 확인해야 성공이다.", M + 105, 80, 645, 8.3, FONT_BOLD, INK)
    c.showPage()


def live_boundary_script_page(c: canvas.Canvas, page_no: int) -> None:
    page_base(c, page_no, "EXACT SCRIPT · 35~40")
    title(c, "‘풀 자동’의 장단점을 이렇게 말한다", "강점을 세게 말하되 책임까지 자동이라고 오해시키지 않는다")
    columns = [
        ("프롬프트 강의", ["사용자가 매번 질문 조립", "도구 사이 복사·붙여넣기", "계정별 업로드 반복", "대신 범용 응용력은 큼"], YELLOW),
        ("우리 프로그램", ["링크 분석→문안 4종→업로드 연결", "별도 AI 키 없이 시작", "7개 제휴 플랫폼·다계정·이력", "대신 Threads와 현재 기능 범위에 특화"], MINT),
        ("사람이 끝까지 할 일", ["상품·제휴 조건 판단", "이미지 권리·사실·고지 검수", "로그인/2FA/CAPTCHA 해결", "성과 분석·댓글·관계 형성"], CORAL),
    ]
    for idx, (name, items, color) in enumerate(columns):
        x = M + idx * 260
        rounded_box(c, x, 240, 245, 216, SOFT_WHITE, INK, 15, 1, shadow=True)
        c.setFillColor(color)
        c.roundRect(x, 408, 245, 48, 14, fill=1, stroke=0)
        c.rect(x, 408, 245, 20, fill=1, stroke=0)
        draw_text(c, name, x + 15, 438, 210, 12, FONT_XB, INK)
        y = 377
        for item in items:
            c.setFillColor(color)
            c.circle(x + 20, y + 2, 4, fill=1, stroke=0)
            draw_text(c, item, x + 33, y + 6, 190, 8.1, FONT_SEMI, INK, leading=11, max_lines=2)
            y -= 36

    rounded_box(c, M, 123, 773, 83, INK, INK, 14)
    draw_text(c, "정확한 발화", M + 16, 180, 80, 8.5, FONT_XB, YELLOW)
    draw_text(c, "“풀 자동이라는 말은 링크 입력 뒤 반복 클릭을 줄인다는 뜻입니다. 수익과 계정 책임까지 프로그램이 대신한다는 뜻은 아닙니다. 지금 공식 지원하는 범위는 국내 쇼핑 제휴 7개 플랫폼과 Threads 게시 흐름입니다.”", M + 102, 181, 650, 9, FONT_BOLD, white, leading=13, max_lines=3)
    rounded_box(c, M, 53, 773, 45, PAPER_2, PAPER_2, 11)
    draw_text(c, "라이브 전 확인", M + 14, 81, 86, 8, FONT_XB, ROSE)
    draw_text(c, "다른 제휴 링크를 시연하려면 실제 테스트 성공·고지 형식·이미지 권리를 먼저 확인한다. 확인 전에는 ‘다 된다’고 말하지 않는다.", M + 106, 82, 645, 8.2, FONT_BOLD, INK)
    c.showPage()


def live_offer_script_page(c: canvas.Canvas, page_no: int) -> None:
    page_base(c, page_no, "EXACT SCRIPT · 40~60", dark=True)
    title(c, "Q&A·70만원 오퍼 대본", "질문 10분을 먼저 주고 마지막 10분에 조건과 행동을 공개한다", dark=True)
    qas = [
        ("수익이 나나요?", "수익은 보장하지 않습니다. 반복 작업과 게시 흐름을 줄이는 도구이며 클릭·구매는 따로 측정합니다."),
        ("초보도 되나요?", "Windows 설치와 Threads 로그인이 가능하면 90분 1:1에서 본인 링크로 첫 게시까지 진행합니다."),
        ("모든 링크가 되나요?", "공식 지원하는 7개 플랫폼은 확정입니다. 그 밖의 제휴사는 결제 전 실제 링크로 호환성부터 확인합니다."),
        ("계정이 안전한가요?", "안전을 보장하지 않습니다. 브라우저 세션 방식·빈도·중단 기준을 공개하고 2FA/CAPTCHA는 우회하지 않습니다."),
    ]
    y = 374
    for idx, (q, a) in enumerate(qas, 1):
        rounded_box(c, M, y, 773, 54, HexColor("#1D2029"), HexColor("#454956"), 10)
        c.setFillColor([YELLOW, MINT, LILAC, CORAL][idx - 1])
        c.circle(M + 25, y + 27, 10, fill=1, stroke=0)
        draw_centered(c, str(idx), M + 15, y + 24, 20, 6.8, FONT_XB, INK)
        draw_text(c, q, M + 48, y + 37, 140, 8.2, FONT_XB, white)
        draw_text(c, a, M + 194, y + 38, 560, 7.4, FONT_SEMI, HexColor("#D7D9E0"), leading=10, max_lines=2)
        y -= 61

    rounded_box(c, M, 58, 773, 110, PAPER, PAPER, 14)
    pill(c, "50~60 · 오퍼/행동", M + 16, 135, ROSE, white, 7.6)
    draw_text(c, "“오늘 안내하는 패키지는 70만원입니다. 프로그램 1년, 90분 개인 강의, 예약형 원격 과외, 사용법 PDF가 포함됩니다. 지원 횟수·응답 시간·환불 조건은 결제 화면에서 먼저 확인합니다.”", M + 16, 118, 735, 8.3, FONT_BOLD, INK, leading=11.5, max_lines=3)
    draw_text(c, "“지금 화면의 ‘내 작업 적합성 확인’ 버튼 하나만 누르세요. 세 문항 뒤 무료 5회 체험 또는 결제 중 맞는 경로만 보여드리겠습니다.”", M + 16, 82, 735, 8.1, FONT_XB, ROSE, leading=11, max_lines=2)
    draw_text(c, "권장 운영안: 90분 1회 + 30분 원격 2회(30일 내) + 영업일 24시간 내 질문 응답. 라이브 전에 실제 제공 조건으로 확정·고지.", M + 16, 65, 735, 6.5, FONT_SEMI, GRAY)
    c.showPage()


def live_ops_page(c: canvas.Canvas, page_no: int) -> None:
    page_base(c, page_no, "BROADCAST OPERATIONS")
    title(c, "방송 운영 체크리스트", "진행자는 말하고 운영자는 질문·링크·오류를 맡는다")
    sections = [
        ("필수 화면 6개", ["20:30 카운트다운", "수작업 5단계/시간표", "앱 링크 입력", "문안 4종·고지", "Threads 공개 결과", "70만원 구성/조건"], YELLOW),
        ("진행자", ["15분 전 입장", "알림·메일·개인정보 닫기", "화면 전환 때 2~5초 정지", "오류를 숨기지 않기", "21:15 교육 종료", "21:30 방송 종료"], MINT),
        ("운영자", ["질문 업보트 관리", "CTA 링크 1개 고정", "개인정보 노출 감시", "타임 큐 전달", "답 못한 질문 저장", "참석/클릭 로그 기록"], LILAC),
    ]
    for idx, (name, items, color) in enumerate(sections):
        x = M + idx * 260
        rounded_box(c, x, 230, 245, 226, SOFT_WHITE, INK, 15, 1, shadow=True)
        pill(c, name, x + 14, 416, color, INK, 8)
        y = 381
        for item in items:
            c.setFillColor(color)
            c.circle(x + 20, y + 2, 4, fill=1, stroke=0)
            draw_text(c, item, x + 33, y + 6, 190, 8.2, FONT_SEMI, INK)
            y -= 29
    rounded_box(c, M, 119, 773, 80, INK, INK, 14)
    draw_text(c, "실패 시 대체", M + 16, 174, 80, 8.5, FONT_XB, YELLOW)
    draw_text(c, "실시간 오류를 먼저 보여주고 로그를 저장한다. 그 다음에만 ‘사전 녹화’ 라벨을 붙인 정상 흐름 60초를 재생한다. 녹화로 성공한 척 연결하지 않는다.", M + 103, 175, 650, 8.5, FONT_BOLD, white, leading=12, max_lines=2)
    rounded_box(c, M, 53, 773, 42, PAPER_2, PAPER_2, 10)
    draw_text(c, "리허설", M + 14, 79, 48, 8, FONT_XB, ROSE)
    draw_text(c, "D9 20:30 전체 1회 · D10 19:45 링크/로그인/화면공유/마이크 · 20:15 운영자 입장 · 20:25 대기 화면", M + 68, 80, 680, 8.2, FONT_BOLD, INK)
    c.showPage()


def live_followup_page(c: canvas.Canvas, page_no: int) -> None:
    page_base(c, page_no, "REMINDER & REPLAY")
    title(c, "등록부터 리플레이까지 보낼 문장", "24시간 전·1시간 전·종료 후를 각각 다른 목적으로 쓴다")
    messages = [
        ("등록 즉시", "신청 완료", "8/20 20:30, 60분입니다. Windows PC와 테스트할 쇼핑 링크 1개만 준비하세요. 캘린더와 접속 링크는 여기입니다.", YELLOW),
        ("24시간 전", "내일 얻을 것", "문구 강의가 아니라 링크→실제 게시 전체를 봅니다. 오류가 나도 끄지 않습니다. 가장 막힌 단계를 이 메시지에 답해주세요.", MINT),
        ("1시간 전", "준비물", "19:30입니다. 창을 미리 열고 링크 1개를 준비하세요. 20:30 정시 시작, 질문은 시작부터 받을게요.", LILAC),
        ("종료 30분", "참석자", "오늘 자료·타임스탬프·무료 5회 경로입니다. 70만원 구성보다 먼저 내 링크 1개가 맞는지 확인하세요.", CORAL),
        ("다음 날", "불참자", "놓친 60분을 그대로 드립니다. 18:00 데모, 35:00 실패, 55:00 구성 공개부터 골라 볼 수 있습니다.", BLUE),
        ("3일 후", "후속", "방송 뒤 가장 많았던 질문은 ‘완전 자동인가’였습니다. 자동/사람 경계표와 답하지 못한 FAQ를 보냅니다.", ROSE),
    ]
    y = 412
    for when, purpose, msg, color in messages:
        rounded_box(c, M, y, 773, 51, SOFT_WHITE, INK, 10)
        pill(c, when, M + 13, y + 26, color, INK if color not in (ROSE, BLUE) else white, 7.0)
        draw_text(c, purpose, M + 112, y + 36, 82, 7.8, FONT_XB, ROSE)
        draw_text(c, msg, M + 200, y + 37, 550, 7.4, FONT_SEMI, INK, leading=10, max_lines=2)
        y -= 57
    rounded_box(c, M, 51, 773, 45, INK, INK, 11)
    draw_text(c, "리플레이 규칙", M + 14, 80, 88, 8, FONT_XB, YELLOW)
    draw_text(c, "라이브 채팅 언급을 제거한 별도 판을 만든다. 가격·환불·기능은 현재 유효한 조건과 갱신일을 같이 표시한다.", M + 108, 81, 640, 8.2, FONT_BOLD, white)
    c.showPage()


def repurpose_page(c: canvas.Canvas, page_no: int) -> None:
    page_base(c, page_no, "EXACT REPURPOSING")
    title(c, "변환 예시", "DAY 1 P1 하나를 8개 채널에서 이렇게 바꾼다")
    rows = [
        ("Threads", "‘링크는 골랐는데 첫 문장에서 40분 멈췄다.’로 시작하는 6문장 경험담. 링크 없음. 마지막 질문.", ROSE),
        ("Instagram", "15초 Reel: 얼굴 2초 → 40:00 타이머 → 빈 문서 → 실제 앱 3초. 표지 7단어.", YELLOW),
        ("YouTube", "Short 제목 ‘쇼핑 제휴 글쓰기, 첫 문장에서 40분 멈추는 이유’. 검색어를 제목에만 자연스럽게.", MINT),
        ("TikTok", "원테이크 12초: ‘나 오늘 상품 찾는 데 3분, 첫 문장에 40분 썼습니다.’ 자막 크게, 편집 거칠게.", LILAC),
        ("Naver Blog", "900~1,500자: 멈춘 과정 4단계 + 실제 화면 3장 + 해결 흐름 + 한계. P2·P3는 비교/FAQ 글로 분리.", CORAL),
        ("Facebook", "얼굴 Reel 1개 + 타이머 이미지 경험담 1개 + 실제 화면 장문 1개. 문제→과정→한계→CTA.", BLUE),
        ("커뮤니티", "‘홍보’가 아니라 ‘첫 문장에 오래 걸리는 분들은 어떻게 해결하나요?’ 경험과 체크리스트. 첫 글 링크 금지.", ROSE),
        ("강의 웹", "첫 화면 헤드라인 교체 + 18초 실제 데모 + FAQ ‘프롬프트를 배워야 하나요?’ 업데이트.", MINT),
    ]
    y = 421
    for name, text_value, color in rows:
        rounded_box(c, M, y, 773, 49, SOFT_WHITE, INK, 10)
        c.setFillColor(color)
        c.roundRect(M, y, 8, 49, 4, fill=1, stroke=0)
        draw_text(c, name, M + 20, y + 32, 92, 8.5, FONT_XB, INK)
        draw_text(c, text_value, M + 118, y + 34, 637, 7.5, FONT_SEMI, INK, leading=10, max_lines=2)
        y -= 55
    c.showPage()


def response_page(c: canvas.Canvas, page_no: int) -> None:
    page_base(c, page_no, "COMMENTS & DM")
    title(c, "응대 멘트", "호기심을 만든 뒤 설명을 늘이지 말고 다음 행동 하나만 준다")
    items = [
        ("‘가격이 얼마예요?’", "70만원입니다. 프로그램 1년·개인 강의·원격 과외·사용법 PDF가 모두 포함됩니다. 지원 범위부터 확인해드릴까요?", ROSE),
        ("‘쿠팡만 되나요?’", "아닙니다. 쿠팡·네이버·토스·오늘의집·무신사·컬리·올리브영의 공식 제휴 프로그램 7곳을 지원합니다.", YELLOW),
        ("‘완전 자동인가요?’", "링크 분석부터 문안·대기열까지 자동화하고, 게시 전 링크·고지·계정·첫 문장은 사람이 승인하는 방식입니다.", MINT),
        ("‘초보도 가능한가요?’", "혼자 설치만 하게 두지 않습니다. 1:1 강의에서 본인 PC로 첫 게시까지 끝내는 것이 기준입니다.", LILAC),
        ("‘수익 나나요?’", "수익은 보장하지 않습니다. 프로그램은 반복 작업을 줄이고 게시 흐름을 유지하도록 돕습니다. 실제 운영 지표로 판단해주세요.", CORAL),
        ("‘원격 지원은 무제한인가요?’", "예약제이며 포함 횟수·회당 시간·응답 SLA를 결제 전에 공개합니다. 사용법·설정 범위와 지원 제외도 함께 안내합니다.", BLUE),
    ]
    positions = [(M, 320), (430, 320), (M, 199), (430, 199), (M, 78), (430, 78)]
    for (question, answer, color), (x, y) in zip(items, positions):
        rounded_box(c, x, y, 377, 103, SOFT_WHITE, INK, 13, 1, shadow=True)
        pill(c, question, x + 14, y + 72, color, INK if color not in (ROSE, BLUE) else white, 7.3)
        draw_text(c, answer, x + 15, y + 53, 345, 7.8, FONT_SEMI, INK, leading=11, max_lines=4)
    c.showPage()


def qa_page(c: canvas.Canvas, page_no: int) -> None:
    page_base(c, page_no, "DAILY QA", dark=True)
    title(c, "게시 전 10분", "후킹은 세게, 사실 검수는 더 세게", dark=True)
    checks = [
        ("HOOK", "첫 화면 8단어 이하 · 0.3초 안에 첫 문장 · 궁금증 1개", YELLOW),
        ("PROOF", "실제 화면 표기 · 미측정 시간/성과 삭제 · 연출 장면 표시", MINT),
        ("LINK", "목적지 직접 클릭 · UTM · 제휴사별 고지와 활동 채널 확인", LILAC),
        ("VISUAL", "개인정보/토큰 블러 · 자막 2줄 · 얼굴/화면 대비 · 저작권", CORAL),
        ("CHANNEL", "같은 문장 복사 금지 · 커뮤니티 첫 글 링크 금지 · 제목 현지화", BLUE),
        ("CTA", "댓글·저장·체험·진단·결제 중 한 가지 · 동시에 두 개 금지", ROSE),
    ]
    y = 389
    for idx, (name, desc, color) in enumerate(checks, 1):
        rounded_box(c, M, y, 773, 45, HexColor("#1D2029"), HexColor("#454956"), 10)
        c.setFillColor(color)
        c.circle(M + 24, y + 22.5, 11, fill=1, stroke=0)
        draw_centered(c, str(idx), M + 13, y + 19, 22, 7, FONT_XB, INK if color not in (ROSE, BLUE) else white)
        draw_text(c, name, M + 50, y + 29, 78, 8.5, FONT_XB, white)
        draw_text(c, desc, M + 132, y + 29, 642, 7.8, FONT_SEMI, HexColor("#D7D9E0"), max_lines=1)
        y -= 55

    rounded_box(c, M, 47, 773, 50, ROSE, ROSE, 11)
    draw_text(c, "중단 기준", M + 16, 79, 70, 8.3, FONT_XB, white)
    draw_text(c, "링크 오류 · 고지 누락 · 다른 계정 로그인 · 실제와 다른 호환 주장 · 가짜 좌석/마감 · 고객 화면 동의 없음 중 하나라도 있으면 예약 게시를 멈춘다.", M + 91, 80, 670, 8, FONT_BOLD, white, leading=10, max_lines=2)
    c.showPage()


def build() -> Path:
    register_fonts()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(PDF_PATH), pagesize=(PAGE_W, PAGE_H), pageCompression=1)
    c.setTitle("Thread Auto 10일 240회 마지막 날 라이브 후킹 콘텐츠 실전 제작북")
    c.setAuthor("OpenAI Codex")
    c.setSubject("국내 쇼핑 제휴 7개 지원을 전면에 내세워 매일 3개 원본을 8개 채널에 배포하고 마지막 60분 무료 라이브를 진행하는 제작안")

    cover(c)
    math_page(c, 2)
    labor_model_page(c, 3)
    savings_table_page(c, 4)
    savings_content_page(c, 5)
    channel_map_page(c, 6)
    timing_page(c, 7)
    visual_rules_page(c, 8)
    asset_page(c, 9)
    support_platform_content_page(c, 10)
    page_no = 11
    for day in DAYS:
        day_page(c, page_no, day)
        page_no += 1
    for day in DAYS:
        channel_schedule_page(c, page_no, day)
        page_no += 1
    live_page(c, page_no)
    page_no += 1
    free_class_pattern_page(c, page_no)
    page_no += 1
    live_promise_page(c, page_no)
    page_no += 1
    live_run_of_show_page(c, page_no)
    page_no += 1
    live_opening_script_page(c, page_no)
    page_no += 1
    live_demo_script_page(c, page_no)
    page_no += 1
    live_boundary_script_page(c, page_no)
    page_no += 1
    live_offer_script_page(c, page_no)
    page_no += 1
    live_ops_page(c, page_no)
    page_no += 1
    live_followup_page(c, page_no)
    page_no += 1
    repurpose_page(c, page_no)
    page_no += 1
    response_page(c, page_no)
    page_no += 1
    qa_page(c, page_no)
    c.save()
    return PDF_PATH


if __name__ == "__main__":
    print(build())
