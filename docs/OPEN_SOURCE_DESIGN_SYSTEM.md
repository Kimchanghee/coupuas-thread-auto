# 오픈소스 디자인 시스템 적용 기록

기록일: 2026-08-03

## 사용한 프로젝트

- 이름: UI UX Pro Max
- 저장소: https://github.com/nextlevelbuilder/ui-ux-pro-max-skill
- 적용 커밋: `14ddef5c05e52d7c253b8f0129de7bcd1045ae5b`
- 커밋 일시: 2026-08-01T08:29:30+07:00
- 라이선스: MIT
- 선택 이유: AI 에이전트가 색상, 타이포그래피, 스타일, 레이아웃, 접근성 규칙을 검색해 프로젝트별 디자인 시스템을 만들 수 있다.

## 프로젝트에 남겨둔 결과

- 디자인 원본 규칙: `design-system/showshortsthreadmaker/MASTER.md`
- V2 적용 설명: `output/organic-launch-pack-v2/DESIGN_NOTES.md`
- V2 렌더러: `tools/render_organic_launch_pack_v2.py`
- V2 결과물: `output/organic-launch-pack-v2/`

## 디자인 시스템 생성 조건

검색 문장:

```text
Korean creator marketing automation social media premium editorial warm vibrant human authentic mobile content
```

설정값:

```text
variance: 8/10 — 비대칭과 강한 시각 변화
motion: 6/10 — 표준 수준 영상 전환
density: 3/10 — 넓은 여백과 낮은 정보 밀도
```

재생성 명령 형식:

```powershell
python <ui-ux-pro-max>/scripts/search.py `
  "Korean creator marketing automation social media premium editorial warm vibrant human authentic mobile content" `
  --design-system --variance 8 --motion 6 --density 3 `
  --persist --output-dir "D:\Dithub\coupuas-thread-auto" `
  -p "ShowShortsThreadMaker" -f markdown
```

## 한국어 콘텐츠용 조정값

오픈소스 추천 결과를 그대로 복제하지 않고 다음처럼 조정했다.

| 역할 | 적용값 |
|---|---|
| 한글 제목 | Pretendard ExtraBold |
| 한글 본문 | Pretendard SemiBold |
| 배경 | `#FFF8F0` 크림 종이색 |
| 기본 글자 | `#15151A` |
| 핵심 색상 | `#E11D48` 로즈 |
| 클릭·상호작용 | `#2563EB` 코발트 |
| 보조 색상 | `#FFD84D`, `#A7F3D0`, `#C4B5FD` |
| 카드 모서리 | 28–56px |
| 레이아웃 | 잡지형 비대칭 콜라주 |
| 그림자 | 블러 없는 오프셋 스티커 그림자 |
| 실제 기능 증명 | 실제 앱 화면을 가장 큰 시각 요소로 사용 |

## 유지 규칙

- 이후 생성되는 홍보물은 `MASTER.md`를 먼저 읽고 제작한다.
- 한 게시물에 핵심 메시지는 하나만 둔다.
- 모든 채널에 동일한 레이아웃을 복사하지 않는다.
- AI 생성 인물은 `AI 연출 이미지`라고 표시한다.
- 실제 앱 화면에는 `REAL SCREEN` 또는 `실제 화면`을 표시한다.
- 매출, 수익, 클릭률 및 노출 결과를 보장하는 문구를 사용하지 않는다.
