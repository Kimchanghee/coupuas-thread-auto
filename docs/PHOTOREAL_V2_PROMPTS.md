# 실사 v2 이미지 프롬프트 및 제작법

## 제작 방식

- 생성 도구: Codex에 설치된 OpenAI 공식 `imagegen` 스킬의 내장 이미지 생성 경로
- 분류: `photorealistic-natural`
- 용도: 2026-08-11~2026-08-20 마케팅 캠페인의 날짜별 세로형 촬영 원본
- 생성 단위: 날짜마다 독립된 프롬프트 1개, 총 10개 원본
- 후처리: 원본 사진을 4:5·9:16에 맞게 크롭하고, 텍스트 영역에만 국소 암부를 추가한다. 증명 카드에서는 실제 프로그램 캡처를 별도 합성한다.
- 표기: AI 생성 촬영 원본은 `실사 연출 사진`, 실제 프로그램 캡처가 들어간 카드는 `REAL SCREEN 합성`

## 공통 실사 기준

모든 프롬프트에 실제 카메라 촬영 문법, 자연광 또는 생활 조명, 피부·천·종이·책상·기기의 미세 질감, 생활 흔적, 미세 센서 그레인을 지정했다. 다음 요소는 공통으로 제외했다.

`CGI, 3D render, illustration, plastic skin, beauty retouching, fake floating UI, holograms, neon cyberpunk, perfect showroom, excessive bokeh, over-sharpening, extra fingers, readable text, logos, watermark`

## DAY01 — 야간 수작업 피로

Authentic candid photograph of a Korean solo online seller in their late 30s working alone after midnight, manually copying product links between laptop and smartphone. Small lived-in Seoul apartment office, cables, sticky notes, half-finished iced coffee, rainy city glow. Three-quarter back/side profile, tired natural posture. Full-frame 35mm, eye-level medium-wide, dark negative space in upper third. Mixed warm desk lamp and cool monitor spill, realistic low-light exposure, skin pores, under-eye texture, worn cotton, fingerprints, wood grain, subtle sensor grain. No staged pose, readable screen, logo, or watermark.

## DAY02 — 수작업 시간비용

Real overhead editorial photograph of two natural Korean adult hands moving between laptop trackpad, smartphone, paper checklist, and inexpensive digital timer. Lived-in wooden dining table used as a work desk, coffee ring, pen marks, tangled cable, soft morning daylight. Full-frame 40mm equivalent, top-down vertical composition with open upper area. Dry skin creases, short natural nails, worn keycaps, scratched phone case, paper fibers. No infographic, pristine stock-photo desk, fake UI, logo, or watermark.

## DAY03 — 실제 화면 합성용 노트북

Authentic photograph of a compact Korean creator desk with an open laptop facing almost straight toward the camera. Laptop screen is completely blank dark charcoal with four straight corners for later screenshot compositing. Smartphone stand, notebook, generic parcel, cable clutter, one natural hand near trackpad. Full-frame 50mm, minimal perspective distortion, soft side-window daylight, faint realistic reflections, aluminum micro-scratches, fingerprints, wood and skin texture, subtle sensor grain. No fake UI, warped laptop, logo, or watermark.

## DAY04 — 7개 제휴처 운영

Candid photograph of a Korean affiliate marketer at an ordinary apartment desk organizing multiple shopping-affiliate link tasks across laptop and smartphone. Parcels with labels turned away, notebook with seven unlabeled checkbox rows, reusable tumbler. Over-the-shoulder, full-frame 35mm, warm late-afternoon window light, flyaway hair, cotton weave, scuffed desk, paper fibers, fingerprint smudges. No platform logo, hologram, staged smile, readable text, or watermark.

## DAY05 — 자동화로 되찾는 시간

Candid real photograph of a Korean solo creator stepping away from a working desk to stretch while the laptop remains open. Modest bright home office, sunlit curtain, ordinary lamp, laundry basket slightly out of focus, notebook and phone on desk. Full-frame 35mm environmental portrait, late-morning window light, real skin and hair, wrinkled cotton shirt, curtain weave, worn furniture. No fantasy automation graphics, luxury office, corporate stock pose, logo, or watermark.

## DAY06 — 원격 과외 지원

Authentic candid photograph of a Korean adult receiving one-to-one remote software guidance at home, speaking on a phone with wired earphones and naturally pointing toward the laptop after solving a setup problem. Small evening apartment desk, troubleshooting notes, router lights, cables, mug, ordinary bookshelf. Full-frame 50mm, warm lamp and cool dusk window, skin pores, hair strands, knit texture, scratched desk, fingerprinted device. No call-center cliché, fake UI, logo, or watermark.

## DAY07 — 프롬프트 노가다 대비

Real editorial photograph of a Korean solo creator comparing a thick, messy handwritten prompt notebook with a simple laptop workflow. Natural hands only: one holding a pen over crossed-out pages, the other near trackpad. Dark blank laptop screen for later actual screenshot composite. Full-frame 45mm, slightly elevated three-quarter angle, directional afternoon light, hand creases, ink bleed, dog-eared paper, worn keycaps, bezel dust, wood grain. No split-screen graphics, arrows, fake interface, logo, or watermark.

## DAY08 — 70만원 패키지 구성

Authentic editorial still life of a real service bundle on a Korean home desk: laptop, printed PDF workbook in a binder, smartphone with a generic video-call silhouette, twelve-month calendar, and handwritten support note. Slightly imperfect arrangement with cable and coffee ring. Full-frame 50mm from slightly above, soft side daylight, contact shadows, paper edges, binder scratches, fingerprints, matte plastic and wood grain. Laptop screen blank for actual software capture composite. No glossy ecommerce render, money stacks, gold coins, logo, or watermark.

## DAY09 — 라이브 전날

Photorealistic behind-the-scenes documentary photo of a Korean creator preparing for tomorrow's single live demonstration at night. Compact mirrorless camera on tripod, inexpensive microphone, ring light switched off, run sheet, water bottle, cables taped to floor. Creator seen from behind adjusting the camera. Full-frame 35mm environmental shot, warm practical lamp, subtle monitor light, realistic low-light noise, tripod scratches, rubber cable and paper creases. No futuristic studio, holographic countdown, logo, or watermark.

## DAY10 — 단 한 번의 라이브 당일

Authentic event-documentary photograph moments before a one-time live software demonstration. Korean creator at a compact apartment desk facing laptop and camera, one hand on mouse and the other greeting viewers naturally. Mirrorless camera with small tally light, microphone, modest key light, notebook, water and lived-in cables. Full-frame 35mm, three-quarter rear view, accurate skin tones, subtle sensor grain, visible skin texture, flyaway hair, fabric wrinkles, microphone mesh and scratched desk. No floating chat bubbles, stadium setup, beauty retouching, logo, or watermark.

## 참고한 공개 원칙

- OpenAI Image Generation Guide: https://developers.openai.com/api/docs/guides/image-generation
- OpenAI Codex imagegen skill: https://github.com/openai/codex/blob/main/codex-rs/skills/src/assets/samples/imagegen/SKILL.md
- ComfyUI reproducible workflow examples: https://github.com/comfyanonymous/ComfyUI_examples
- ComfyUI core workflow features: https://github.com/Comfy-Org/ComfyUI

ComfyUI 자료에서는 전체 워크플로를 재현 가능하게 보존하고 img2img·인페인팅·업스케일을 단계별로 분리하는 원칙만 참고했다. 이번 원본 생성에는 임의의 서드파티 체크포인트나 커스텀 노드를 설치하지 않았다.
