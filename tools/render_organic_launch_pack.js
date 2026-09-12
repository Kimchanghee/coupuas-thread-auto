const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const root = path.resolve(__dirname, '..');
const out = path.join(root, 'output', 'organic-launch-pack');
const work = path.join(out, '_render');
const sources = path.join(out, 'sources');

for (const dir of ['instagram', 'stories', 'tiktok', 'youtube', 'facebook', 'threads', 'blog', 'previews', '_render']) {
  fs.mkdirSync(path.join(out, dir), { recursive: true });
}

const bold = 'fonts/Pretendard-ExtraBold.ttf';
const semi = 'fonts/Pretendard-SemiBold.ttf';
const navy = '0x0D1B2E';
const orange = '0xF26B3A';
const cream = '0xF7F3EC';
const white = '0xFFFFFF';

function run(args) {
  const result = spawnSync('ffmpeg', args, { cwd: root, stdio: 'inherit' });
  if (result.status !== 0) throw new Error(`ffmpeg failed: ${args.join(' ')}`);
}

function esc(value) {
  return String(value).replace(/\\/g, '\\\\').replace(/:/g, '\\:').replace(/'/g, "\\'").replace(/%/g, '\\%');
}

function textFilter(item) {
  const font = item.font === 'semi' ? semi : bold;
  const x = item.x ?? '(w-text_w)/2';
  return `drawtext=fontfile='${font}':text='${esc(item.text)}':fontcolor=${item.color || navy}:fontsize=${item.size}:x=${x}:y=${item.y}`;
}

function writeFilter(name, value) {
  const file = path.join(work, `${name}.ffscript`);
  fs.writeFileSync(file, value, 'utf8');
  return file;
}

function renderSolid(name, width, height, bg, boxes, texts, targetDir) {
  const filters = [
    ...boxes.map((box) => `drawbox=x=${box.x}:y=${box.y}:w=${box.w}:h=${box.h}:color=${box.color}:t=fill`),
    ...texts.map(textFilter),
  ];
  const script = writeFilter(name, `[0:v]${filters.join(',')}[out]`);
  const target = path.join(out, targetDir, `${name}.png`);
  run(['-y', '-f', 'lavfi', '-i', `color=c=${bg}:s=${width}x${height}`, '-filter_complex_script', script, '-map', '[out]', '-frames:v', '1', '-update', '1', target]);
  return target;
}

function renderPhoto(name, sourceName, width, height, dark, boxes, texts, targetDir) {
  const filters = [
    `scale=${width}:${height}:force_original_aspect_ratio=increase`,
    `crop=${width}:${height}`,
    dark ? `eq=brightness=${dark}` : null,
    ...boxes.map((box) => `drawbox=x=${box.x}:y=${box.y}:w=${box.w}:h=${box.h}:color=${box.color}:t=fill`),
    ...texts.map(textFilter),
  ].filter(Boolean);
  const script = writeFilter(name, `[0:v]${filters.join(',')}[out]`);
  const target = path.join(out, targetDir, `${name}.png`);
  run(['-y', '-i', path.join(sources, sourceName), '-filter_complex_script', script, '-map', '[out]', '-frames:v', '1', '-update', '1', target]);
  return target;
}

function renderProof(name, width, height, top, appWidth, appY, texts, footer, targetDir, bg = navy) {
  const footerFilters = footer ? [
    `drawbox=x=${footer.x}:y=${footer.y}:w=${footer.w}:h=${footer.h}:color=${footer.color}:t=fill`,
    textFilter(footer.text),
  ] : [];
  const overlayChain = [
    `[0:v][app]overlay=(W-w)/2:${appY}`,
    ...texts.map(textFilter),
    ...footerFilters,
  ].join(',');
  const script = writeFilter(
    name,
    `[1:v]scale=${appWidth}:-1[app];${overlayChain}[out]`,
  );
  const target = path.join(out, targetDir, `${name}.png`);
  run(['-y', '-f', 'lavfi', '-i', `color=c=${bg}:s=${width}x${height}`, '-i', path.join(sources, 'app-proof.png'), '-filter_complex_script', script, '-map', '[out]', '-frames:v', '1', '-update', '1', target]);
  return target;
}

function makeVideo(name, segments, targetDir) {
  const args = ['-y'];
  segments.forEach((segment) => {
    if (segment.kind === 'image') args.push('-loop', '1', '-i', segment.file);
    else args.push('-i', segment.file);
  });
  const chains = segments.map((segment, index) =>
    `[${index}:v]fps=30,trim=duration=${segment.duration},setpts=PTS-STARTPTS,scale=1080:1920,setsar=1,format=yuv420p[v${index}]`,
  );
  chains.push(`${segments.map((_, index) => `[v${index}]`).join('')}concat=n=${segments.length}:v=1:a=0[out]`);
  const target = path.join(out, targetDir, `${name}.mp4`);
  args.push('-filter_complex', chains.join(';'), '-map', '[out]', '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-movflags', '+faststart', target);
  run(args);
  return target;
}

function contactSheet(name, files, tileW, tileH, columns, targetDir) {
  const rows = Math.ceil(files.length / columns);
  const args = ['-y'];
  files.forEach((file) => args.push('-i', file));
  const chains = files.map((_, i) => `[${i}:v]scale=${tileW}:${tileH},setsar=1[v${i}]`);
  const layout = files.map((_, i) => `${(i % columns) * tileW}_${Math.floor(i / columns) * tileH}`).join('|');
  chains.push(`${files.map((_, i) => `[v${i}]`).join('')}xstack=inputs=${files.length}:layout=${layout}:fill=${cream}[out]`);
  const target = path.join(out, targetDir, `${name}.png`);
  args.push('-filter_complex', chains.join(';'), '-map', '[out]', '-frames:v', '1', '-update', '1', target);
  run(args);
  return target;
}

const ig = [];
ig.push(renderPhoto('ig-carousel-01-cover', 'ugc-night.png', 1080, 1350, -0.2,
  [{ x: 50, y: 65, w: 980, h: 330, color: `${navy}@0.92` }],
  [
    { text: '상품 링크는 있는데', size: 68, color: white, y: 115 },
    { text: '글 쓰다 멈췄다면?', size: 82, color: orange, y: 205 },
    { text: '반복 작업을 실제 화면으로 줄여봤습니다', size: 34, color: white, font: 'semi', y: 320 },
  ], 'instagram'));

ig.push(renderSolid('ig-carousel-02-pain', 1080, 1350, cream,
  [
    { x: 70, y: 255, w: 940, h: 150, color: `${white}@1` },
    { x: 70, y: 430, w: 940, h: 150, color: `${white}@1` },
    { x: 70, y: 605, w: 940, h: 150, color: `${white}@1` },
    { x: 70, y: 780, w: 940, h: 150, color: `${white}@1` },
    { x: 70, y: 1030, w: 940, h: 160, color: `${navy}@1` },
  ], [
    { text: '매일 이걸 다 하고 있었어요', size: 66, y: 80 },
    { text: '1  상품 확인', size: 48, y: 300, x: 130 },
    { text: '2  타깃에 맞는 글 작성', size: 48, y: 475, x: 130 },
    { text: '3  계정 바꿔가며 업로드', size: 48, y: 650, x: 130 },
    { text: '4  어디까지 올렸는지 다시 확인', size: 48, y: 825, x: 130 },
    { text: '문제는 한 번이 아니라 매일이라는 것', size: 42, color: white, y: 1085 },
  ], 'instagram'));

ig.push(renderSolid('ig-carousel-03-quiz', 1080, 1350, navy,
  [
    { x: 60, y: 280, w: 960, h: 280, color: `${white}@1` },
    { x: 60, y: 600, w: 960, h: 350, color: `${white}@1` },
    { x: 190, y: 1050, w: 700, h: 130, color: `${orange}@1` },
  ], [
    { text: '어느 글을 누르시겠어요?', size: 72, color: white, y: 90 },
    { text: 'A', size: 64, color: orange, y: 330, x: 110 },
    { text: '가볍고 편리한 휴대용 선풍기입니다', size: 40, y: 365, x: 220 },
    { text: 'B', size: 64, color: orange, y: 650, x: 110 },
    { text: '선풍기 꺼낸 친구를 비웃었는데', size: 40, y: 690, x: 220 },
    { text: '5분 뒤 내가 빌려달라고 했다', size: 44, y: 760, x: 220 },
    { text: '정답은 다음 장', size: 44, color: white, y: 1088 },
  ], 'instagram'));

ig.push(renderSolid('ig-carousel-04-angles', 1080, 1350, cream,
  [
    { x: 70, y: 260, w: 450, h: 330, color: `${navy}@1` },
    { x: 560, y: 260, w: 450, h: 330, color: `${navy}@1` },
    { x: 70, y: 630, w: 450, h: 330, color: `${navy}@1` },
    { x: 560, y: 630, w: 450, h: 330, color: `${navy}@1` },
  ], [
    { text: '같은 상품도 시작점이 달라야 합니다', size: 60, y: 85 },
    { text: '타깃 직격', size: 48, color: orange, y: 325, x: 150 },
    { text: '누가 필요한지 먼저', size: 29, color: white, font: 'semi', y: 410, x: 130 },
    { text: '편의 대비', size: 48, color: orange, y: 325, x: 650 },
    { text: '전과 후를 비교', size: 29, color: white, font: 'semi', y: 410, x: 650 },
    { text: '재미 반전', size: 48, color: orange, y: 695, x: 150 },
    { text: '예상 밖 상황으로 시작', size: 29, color: white, font: 'semi', y: 780, x: 115 },
    { text: '사용 장면', size: 48, color: orange, y: 695, x: 650 },
    { text: '쓰는 순간을 보여주기', size: 29, color: white, font: 'semi', y: 780, x: 625 },
    { text: '말투만 바꾸는 4개가 아닙니다', size: 39, y: 1065 },
  ], 'instagram'));

ig.push(renderProof('ig-carousel-05-proof', 1080, 1350, 0, 960, 345,
  [
    { text: '설명 말고 실제 프로그램 화면', size: 61, color: navy, y: 80 },
    { text: '링크 입력 → 문안 생성 → 계정별 대기열', size: 35, color: orange, font: 'semi', y: 185 },
  ], { x: 90, y: 1100, w: 900, h: 140, color: `${navy}@1`, text: { text: '작동하는 장면을 영상으로 공개합니다', size: 40, color: white, y: 1145 } },
  'instagram', cream));

ig.push(renderPhoto('ig-carousel-06-cta', 'ugc-relief.png', 1080, 1350, -0.12,
  [{ x: 55, y: 70, w: 970, h: 380, color: `${navy}@0.92` }, { x: 145, y: 1030, w: 790, h: 150, color: `${orange}@0.98` }],
  [
    { text: '강의 안 팝니다', size: 78, color: white, y: 120 },
    { text: '프로그램을 직접 확인하세요', size: 57, color: orange, y: 225 },
    { text: '매월 5번 무료', size: 69, color: white, y: 1068 },
    { text: '프로필 링크', size: 31, color: white, font: 'semi', y: 1150 },
  ], 'instagram'));

const stories = [];
stories.push(renderPhoto('story-01-poll', 'ugc-multiaccount.png', 1080, 1920, -0.12,
  [{ x: 45, y: 70, w: 990, h: 370, color: `${navy}@0.92` }, { x: 100, y: 1500, w: 880, h: 220, color: `${white}@0.94` }],
  [
    { text: '계정 3개 운영하면', size: 76, color: white, y: 125 },
    { text: '어디까지 올렸는지 기억나요?', size: 58, color: orange, y: 235 },
    { text: '항상 기억함', size: 38, y: 1545, x: 200 },
    { text: '매번 헷갈림', size: 38, color: orange, y: 1630, x: 630 },
  ], 'stories'));

stories.push(renderSolid('story-02-pain', 1080, 1920, cream,
  [
    { x: 90, y: 360, w: 900, h: 170, color: `${white}@1` },
    { x: 90, y: 570, w: 900, h: 170, color: `${white}@1` },
    { x: 90, y: 780, w: 900, h: 170, color: `${white}@1` },
    { x: 90, y: 990, w: 900, h: 170, color: `${white}@1` },
    { x: 90, y: 1330, w: 900, h: 210, color: `${navy}@1` },
  ], [
    { text: '게시 하나에 숨은 반복 작업', size: 70, y: 120 },
    { text: '상품 확인', size: 51, y: 410 },
    { text: '문안 작성', size: 51, y: 620 },
    { text: '계정 전환', size: 51, y: 830 },
    { text: '게시 상태 재확인', size: 51, y: 1040 },
    { text: '이걸 한 대기열로 묶었습니다', size: 52, color: white, y: 1405 },
  ], 'stories'));

stories.push(renderProof('story-03-proof', 1080, 1920, 0, 980, 540,
  [
    { text: '실제 화면입니다', size: 82, color: white, y: 120 },
    { text: '링크를 넣고 자동화 시작', size: 42, color: orange, font: 'semi', y: 250 },
  ], { x: 100, y: 1480, w: 880, h: 190, color: `${orange}@1`, text: { text: '영상에서 게시 완료까지 확인', size: 45, color: white, y: 1545 } },
  'stories', navy));

stories.push(renderSolid('story-04-quiz', 1080, 1920, navy,
  [
    { x: 70, y: 400, w: 940, h: 310, color: `${white}@1` },
    { x: 70, y: 770, w: 940, h: 430, color: `${white}@1` },
    { x: 170, y: 1400, w: 740, h: 160, color: `${orange}@1` },
  ], [
    { text: '어느 쪽이 더 궁금해요?', size: 74, color: white, y: 140 },
    { text: 'A  가볍고 편리한 선풍기', size: 45, y: 500 },
    { text: 'B  친구를 비웃었는데', size: 45, y: 875 },
    { text: '5분 뒤 내가 빌려달라고 했다', size: 45, y: 970 },
    { text: 'A / B 투표하기', size: 54, color: white, y: 1450 },
  ], 'stories'));

stories.push(renderPhoto('story-05-cta', 'ugc-relief.png', 1080, 1920, -0.1,
  [{ x: 45, y: 75, w: 990, h: 430, color: `${navy}@0.92` }, { x: 120, y: 1470, w: 840, h: 210, color: `${orange}@0.98` }],
  [
    { text: '강의 안 팝니다', size: 86, color: white, y: 135 },
    { text: '직접 써보고 판단하세요', size: 62, color: orange, y: 260 },
    { text: '매월 5번 무료', size: 76, color: white, y: 1520 },
    { text: '링크 스티커', size: 36, color: white, font: 'semi', y: 1620 },
  ], 'stories'));

const threadImages = [];
threadImages.push(renderSolid('threads-01-quiz', 1200, 1200, navy,
  [{ x: 70, y: 250, w: 1060, h: 250, color: `${white}@1` }, { x: 70, y: 550, w: 1060, h: 330, color: `${white}@1` }],
  [
    { text: '어느 글을 누를 것 같아요?', size: 72, color: white, y: 70 },
    { text: 'A  가볍고 편리한 휴대용 선풍기', size: 42, y: 340 },
    { text: 'B  비웃던 친구에게', size: 46, color: orange, y: 630, x: 150 },
    { text: '5분 뒤 빌려달라고 했다', size: 50, y: 720, x: 280 },
    { text: '댓글에 A 또는 B', size: 38, color: white, font: 'semi', y: 1000 },
  ], 'threads'));

threadImages.push(renderSolid('threads-02-four-angles', 1200, 1200, cream,
  [
    { x: 70, y: 250, w: 500, h: 300, color: `${navy}@1` }, { x: 630, y: 250, w: 500, h: 300, color: `${navy}@1` },
    { x: 70, y: 610, w: 500, h: 300, color: `${navy}@1` }, { x: 630, y: 610, w: 500, h: 300, color: `${navy}@1` },
  ], [
    { text: '같은 상품도 4개의 출발점', size: 68, y: 80 },
    { text: '타깃 직격', size: 46, color: orange, y: 330, x: 190 },
    { text: '편의 대비', size: 46, color: orange, y: 330, x: 750 },
    { text: '재미 반전', size: 46, color: orange, y: 690, x: 190 },
    { text: '사용 장면', size: 46, color: orange, y: 690, x: 750 },
    { text: '말투만 바꾼 글 4개가 아닙니다', size: 41, y: 1030 },
  ], 'threads'));

threadImages.push(renderProof('threads-03-real-screen', 1200, 1200, 0, 1080, 320,
  [
    { text: '설명 말고 실제 화면', size: 72, color: navy, y: 70 },
    { text: '링크 입력 → 계정별 대기열', size: 38, color: orange, font: 'semi', y: 180 },
  ], { x: 150, y: 1000, w: 900, h: 120, color: `${navy}@1`, text: { text: '매월 5번 무료로 확인', size: 43, color: white, y: 1035 } },
  'threads', cream));

const blog = [];
blog.push(renderProof('blog-01-hero', 1600, 900, 0, 880, 210,
  [
    { text: '쿠팡 링크 하나로 어디까지 자동화될까?', size: 66, color: navy, y: 55 },
    { text: '문안 4종부터 계정별 Threads 대기열까지', size: 38, color: orange, font: 'semi', y: 145 },
  ], { x: 1050, y: 600, w: 430, h: 120, color: `${orange}@1`, text: { text: '실제 화면으로 확인', size: 35, color: white, y: 640, x: 1120 } },
  'blog', cream));

blog.push(renderSolid('blog-02-workflow', 1600, 900, cream,
  [
    { x: 70, y: 300, w: 300, h: 200, color: `${navy}@1` }, { x: 450, y: 300, w: 300, h: 200, color: `${navy}@1` },
    { x: 830, y: 300, w: 300, h: 200, color: `${navy}@1` }, { x: 1210, y: 300, w: 300, h: 200, color: `${navy}@1` },
  ], [
    { text: '반복 작업을 한 흐름으로', size: 72, y: 70 },
    { text: '상품 링크', size: 39, color: white, y: 370, x: 135 },
    { text: '타깃 분석', size: 39, color: white, y: 370, x: 515 },
    { text: '문안 4종', size: 39, color: white, y: 370, x: 895 },
    { text: '계정별 게시', size: 39, color: white, y: 370, x: 1265 },
    { text: '→', size: 55, color: orange, y: 360, x: 390 }, { text: '→', size: 55, color: orange, y: 360, x: 770 }, { text: '→', size: 55, color: orange, y: 360, x: 1150 },
    { text: '수익을 보장하는 도구가 아니라 반복 시간을 줄이는 도구입니다', size: 38, y: 690 },
  ], 'blog'));

blog.push(renderSolid('blog-03-four-angles', 1600, 900, navy,
  [
    { x: 80, y: 260, w: 330, h: 300, color: `${white}@1` }, { x: 450, y: 260, w: 330, h: 300, color: `${white}@1` },
    { x: 820, y: 260, w: 330, h: 300, color: `${white}@1` }, { x: 1190, y: 260, w: 330, h: 300, color: `${white}@1` },
  ], [
    { text: '같은 상품을 다르게 시작하는 네 가지 방식', size: 66, color: white, y: 70 },
    { text: '타깃 직격', size: 36, color: orange, y: 350, x: 150 }, { text: '편의 대비', size: 36, color: orange, y: 350, x: 520 },
    { text: '재미 반전', size: 36, color: orange, y: 350, x: 890 }, { text: '사용 장면', size: 36, color: orange, y: 350, x: 1260 },
    { text: '누가 필요한가', size: 25, y: 450, x: 145 }, { text: '전후가 어떻게 다른가', size: 25, y: 450, x: 485 },
    { text: '예상 밖 상황은 무엇인가', size: 25, y: 450, x: 835 }, { text: '어디서 편해지는가', size: 25, y: 450, x: 1235 },
  ], 'blog'));

const appDemo = path.join(sources, 'app-demo.mp4');
const v = {
  pain: stories[1], poll: stories[0], proof: stories[2], quiz: stories[3], cta: stories[4], angles: ig[3],
};

const videos = [];
videos.push(makeVideo('reel-01-real-demo', [
  { kind: 'image', file: ig[0], duration: 2.5 }, { kind: 'video', file: appDemo, duration: 15 }, { kind: 'image', file: v.cta, duration: 3.5 },
], 'instagram'));
videos.push(makeVideo('reel-02-multiaccount', [
  { kind: 'image', file: v.poll, duration: 3 }, { kind: 'image', file: v.proof, duration: 7 }, { kind: 'image', file: v.quiz, duration: 5 }, { kind: 'image', file: v.cta, duration: 3 },
], 'instagram'));
videos.push(makeVideo('tiktok-01-which-copy', [
  { kind: 'image', file: v.quiz, duration: 4 }, { kind: 'image', file: v.proof, duration: 7 }, { kind: 'image', file: v.cta, duration: 3 },
], 'tiktok'));
videos.push(makeVideo('tiktok-02-multiaccount', [
  { kind: 'image', file: v.poll, duration: 3 }, { kind: 'image', file: v.proof, duration: 7 }, { kind: 'image', file: v.cta, duration: 3 },
], 'tiktok'));
videos.push(makeVideo('tiktok-03-no-course', [
  { kind: 'image', file: v.cta, duration: 3 }, { kind: 'video', file: appDemo, duration: 15 }, { kind: 'image', file: v.cta, duration: 3 },
], 'tiktok'));
videos.push(makeVideo('short-01-real-demo', [
  { kind: 'image', file: v.pain, duration: 2.5 }, { kind: 'video', file: appDemo, duration: 15 }, { kind: 'image', file: v.cta, duration: 3.5 },
], 'youtube'));
videos.push(makeVideo('short-02-four-angles', [
  { kind: 'image', file: v.quiz, duration: 4 }, { kind: 'image', file: v.proof, duration: 7 }, { kind: 'image', file: v.cta, duration: 4 },
], 'youtube'));
videos.push(makeVideo('facebook-reel-01-explainer', [
  { kind: 'image', file: v.pain, duration: 4 }, { kind: 'video', file: appDemo, duration: 15 }, { kind: 'image', file: v.quiz, duration: 5 }, { kind: 'image', file: v.cta, duration: 4 },
], 'facebook'));

fs.copyFileSync(ig[4], path.join(out, 'facebook', 'facebook-feed-01-real-screen.png'));

contactSheet('instagram-carousel-preview', ig, 360, 450, 3, 'previews');
contactSheet('instagram-stories-preview', stories, 216, 384, 5, 'previews');
contactSheet('threads-preview', threadImages, 400, 400, 3, 'previews');
contactSheet('blog-preview', blog, 533, 300, 3, 'previews');

const manifest = {
  generatedAt: new Date().toISOString(),
  counts: {
    instagramCarousel: ig.length,
    instagramStories: stories.length,
    threadsImages: threadImages.length,
    blogGraphics: blog.length,
    videos: videos.length,
  },
  files: { instagram: ig, stories, threads: threadImages, blog, videos },
};
fs.writeFileSync(path.join(out, 'manifest.json'), JSON.stringify(manifest, null, 2), 'utf8');
console.log(JSON.stringify(manifest.counts));
