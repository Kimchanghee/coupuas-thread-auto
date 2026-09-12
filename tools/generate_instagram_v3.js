const fs = require('fs');
const path = require('path');
const sharp = require('sharp');

const root = path.resolve(__dirname, '..');
const out = path.join(root, 'output', 'instagram-v3');
const proof = fs.readFileSync(path.join(out, 'app-proof.png')).toString('base64');
const avatar = fs.readFileSync(path.join(out, 'profile-avatar-v2.png')).toString('base64');

const C = {
  navy: '#07111F',
  navy2: '#0D1B2E',
  coral: '#F26B3A',
  orange: '#FF9B32',
  cream: '#F7F3EC',
  white: '#FFFFFF',
  muted: '#AAB6C7',
  green: '#2CCB85',
};

function defs() {
  return `
    <defs>
      <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="${C.navy}"/>
        <stop offset="1" stop-color="${C.navy2}"/>
      </linearGradient>
      <linearGradient id="hot" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="${C.coral}"/>
        <stop offset="1" stop-color="${C.orange}"/>
      </linearGradient>
      <filter id="shadow" x="-30%" y="-30%" width="160%" height="160%">
        <feDropShadow dx="0" dy="20" stdDeviation="22" flood-color="#000" flood-opacity=".38"/>
      </filter>
      <clipPath id="screen"><rect x="90" y="520" width="900" height="560" rx="34"/></clipPath>
      <clipPath id="storyScreen"><rect x="72" y="560" width="936" height="720" rx="36"/></clipPath>
    </defs>`;
}

function brand(x, y, size = 68, dark = true) {
  const color = dark ? C.white : C.navy;
  return `
    <image href="data:image/png;base64,${avatar}" x="${x}" y="${y}" width="${size}" height="${size}"/>
    <text x="${x + size + 18}" y="${y + size * .46}" fill="${color}" font-size="26" font-weight="800">쿠파스 스레드 오토</text>
    <text x="${x + size + 18}" y="${y + size * .8}" fill="${dark ? C.muted : '#5D6775'}" font-size="16" font-weight="700" letter-spacing="2">COUPAS THREAD AUTO</text>`;
}

function svg(w, h, body) {
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">
    ${defs()}
    <style>text{font-family:'Malgun Gothic','Arial',sans-serif}</style>
    ${body}
  </svg>`;
}

async function write(name, markup, width, height) {
  await sharp(Buffer.from(markup)).resize(width, height).png({ compressionLevel: 9 }).toFile(path.join(out, name));
}

const feed1 = svg(1080, 1350, `
  <rect width="1080" height="1350" fill="url(#bg)"/>
  <circle cx="930" cy="240" r="210" fill="${C.coral}" opacity=".10"/>
  <circle cx="120" cy="1140" r="220" fill="${C.orange}" opacity=".07"/>
  ${brand(110, 170, 60)}
  <rect x="110" y="286" width="240" height="48" rx="24" fill="${C.coral}"/>
  <text x="230" y="319" fill="white" font-size="20" font-weight="800" text-anchor="middle">지금도 하나씩?</text>
  <text x="110" y="456" fill="${C.white}" font-size="68" font-weight="900">쿠팡 링크 10개</text>
  <text x="110" y="548" fill="${C.white}" font-size="68" font-weight="900">손으로 올리면</text>
  <text x="110" y="682" fill="url(#hot)" font-size="112" font-weight="900">100~150분</text>
  <text x="110" y="760" fill="${C.muted}" font-size="28" font-weight="700">상품 확인 · 문구 · 이미지 · 고지 · 게시</text>
  <g transform="translate(110 840)">
    <rect width="860" height="210" rx="30" fill="#111F33" stroke="#263753" stroke-width="2"/>
    <text x="36" y="74" fill="${C.muted}" font-size="25" font-weight="700">해야 할 일은 그대로인데</text>
    <text x="36" y="146" fill="${C.white}" font-size="43" font-weight="900">반복 작업만 자동으로.</text>
    <circle cx="772" cy="105" r="48" fill="url(#hot)"/>
    <text x="772" y="121" fill="white" font-size="50" font-weight="900" text-anchor="middle">→</text>
  </g>
  <text x="110" y="1140" fill="${C.muted}" font-size="23" font-weight="700">옆으로 넘겨 실제 화면 보기</text>
  <text x="970" y="1140" fill="${C.coral}" font-size="23" font-weight="900" text-anchor="end">1 / 4</text>`);

const feed2 = svg(1080, 1350, `
  <rect width="1080" height="1350" fill="${C.cream}"/>
  ${brand(110, 170, 60, false)}
  <text x="110" y="348" fill="${C.navy}" font-size="68" font-weight="900">링크만 넣으세요.</text>
  <text x="110" y="410" fill="#5D6775" font-size="26" font-weight="700">시작 버튼 한 번, 나머지는 자동으로 이어집니다.</text>
  <rect x="110" y="458" width="860" height="78" rx="26" fill="${C.navy}"/>
  <text x="540" y="509" fill="${C.white}" font-size="24" font-weight="800" text-anchor="middle">분석 → AI 문구 → 이미지 → 고지 → Threads 게시</text>
  <g filter="url(#shadow)">
    <rect x="100" y="572" width="880" height="500" rx="38" fill="#0B111B"/>
    <image href="data:image/png;base64,${proof}" x="115" y="587" width="850" height="470" preserveAspectRatio="xMidYMid slice"/>
  </g>
  <rect x="120" y="1010" width="270" height="52" rx="26" fill="${C.green}"/>
  <text x="255" y="1045" fill="${C.navy}" font-size="20" font-weight="900" text-anchor="middle">실제 프로그램 화면</text>
  <text x="110" y="1150" fill="${C.navy}" font-size="38" font-weight="900">설명이 아니라, 작동 화면으로 확인.</text>
  <text x="970" y="1190" fill="${C.coral}" font-size="23" font-weight="900" text-anchor="end">2 / 4</text>`);

const feed3 = svg(1080, 1350, `
  <rect width="1080" height="1350" fill="url(#bg)"/>
  ${brand(110, 170, 60)}
  <text x="110" y="356" fill="${C.white}" font-size="62" font-weight="900">게시할 때마다</text>
  <text x="110" y="438" fill="${C.white}" font-size="62" font-weight="900">빠뜨리던 것까지.</text>
  <g transform="translate(110 508)">
    <rect width="410" height="148" rx="26" fill="#111F33" stroke="#263753" stroke-width="2"/>
    <circle cx="58" cy="58" r="25" fill="${C.green}"/>
    <path d="M46 58l9 9 18-22" fill="none" stroke="white" stroke-width="6" stroke-linecap="round"/>
    <text x="98" y="65" fill="${C.white}" font-size="28" font-weight="900">고지 문구 자동</text>
    <text x="32" y="113" fill="${C.muted}" font-size="19" font-weight="700">파트너스 필수 고지</text>
  </g>
  <g transform="translate(560 508)">
    <rect width="410" height="148" rx="26" fill="#111F33" stroke="#263753" stroke-width="2"/>
    <circle cx="58" cy="58" r="25" fill="${C.green}"/>
    <path d="M46 58l9 9 18-22" fill="none" stroke="white" stroke-width="6" stroke-linecap="round"/>
    <text x="98" y="65" fill="${C.white}" font-size="28" font-weight="900">중복 업로드 방지</text>
    <text x="32" y="113" fill="${C.muted}" font-size="19" font-weight="700">올린 링크 자동 기억</text>
  </g>
  <g transform="translate(110 688)">
    <rect width="410" height="148" rx="26" fill="#111F33" stroke="#263753" stroke-width="2"/>
    <circle cx="58" cy="58" r="25" fill="${C.green}"/>
    <path d="M46 58l9 9 18-22" fill="none" stroke="white" stroke-width="6" stroke-linecap="round"/>
    <text x="98" y="65" fill="${C.white}" font-size="28" font-weight="900">대량 업로드</text>
    <text x="32" y="113" fill="${C.muted}" font-size="19" font-weight="700">여러 링크 한 번에 처리</text>
  </g>
  <g transform="translate(560 688)">
    <rect width="410" height="148" rx="26" fill="#111F33" stroke="#263753" stroke-width="2"/>
    <circle cx="58" cy="58" r="25" fill="${C.green}"/>
    <path d="M46 58l9 9 18-22" fill="none" stroke="white" stroke-width="6" stroke-linecap="round"/>
    <text x="98" y="65" fill="${C.white}" font-size="28" font-weight="900">텔레그램 알림</text>
    <text x="32" y="113" fill="${C.muted}" font-size="19" font-weight="700">완료·실패 결과 확인</text>
  </g>
  <rect x="110" y="886" width="860" height="172" rx="30" fill="url(#hot)"/>
  <text x="146" y="950" fill="white" font-size="23" font-weight="800">반복은 프로그램에 맡기고</text>
  <text x="146" y="1018" fill="white" font-size="40" font-weight="900">상품 선택에만 집중하세요.</text>
  <text x="970" y="1140" fill="${C.coral}" font-size="23" font-weight="900" text-anchor="end">3 / 4</text>`);

const feed4 = svg(1080, 1350, `
  <rect width="1080" height="1350" fill="${C.cream}"/>
  <circle cx="900" cy="250" r="220" fill="${C.coral}" opacity=".11"/>
  ${brand(110, 170, 60, false)}
  <text x="110" y="390" fill="${C.navy}" font-size="68" font-weight="900">무료 설치로</text>
  <text x="110" y="478" fill="${C.navy}" font-size="68" font-weight="900">먼저 확인하세요.</text>
  <text x="110" y="548" fill="#5D6775" font-size="25" font-weight="700">수익 약속 대신 실제 프로그램을 공개합니다.</text>
  <g transform="translate(110 620)">
    <rect width="860" height="238" rx="34" fill="${C.navy}"/>
    <text x="42" y="66" fill="${C.muted}" font-size="23" font-weight="800">월간 구독</text>
    <text x="42" y="145" fill="${C.white}" font-size="62" font-weight="900">49,000원</text>
    <text x="42" y="198" fill="${C.muted}" font-size="21" font-weight="700">결제 후 7일 이내 전액 환불</text>
    <rect x="570" y="58" width="244" height="122" rx="28" fill="url(#hot)"/>
    <text x="692" y="108" fill="white" font-size="20" font-weight="800" text-anchor="middle">WINDOWS</text>
    <text x="692" y="149" fill="white" font-size="29" font-weight="900" text-anchor="middle">무료 다운로드</text>
  </g>
  <rect x="110" y="916" width="860" height="104" rx="52" fill="url(#hot)"/>
  <text x="540" y="983" fill="white" font-size="31" font-weight="900" text-anchor="middle">프로필 링크에서 실제 영상 보기 →</text>
  <text x="540" y="1110" fill="${C.navy}" font-size="29" font-weight="900" text-anchor="middle">coupasthreadauto.me</text>
  <text x="970" y="1160" fill="${C.coral}" font-size="23" font-weight="900" text-anchor="end">4 / 4</text>`);

function storyBase(number, body) {
  return svg(1080, 1920, `
    <rect width="1080" height="1920" fill="url(#bg)"/>
    <rect x="72" y="76" width="936" height="6" rx="3" fill="#2A3850"/>
    <rect x="72" y="76" width="${number * 312}" height="6" rx="3" fill="${C.coral}"/>
    ${brand(72, 124, 70)}
    ${body}
    <text x="1008" y="1838" fill="${C.muted}" font-size="22" font-weight="800" text-anchor="end">${number} / 3</text>`);
}

const story1 = storyBase(1, `
  <text x="72" y="430" fill="${C.white}" font-size="82" font-weight="900">오늘 쿠팡 링크</text>
  <text x="72" y="542" fill="${C.white}" font-size="82" font-weight="900">몇 개 올렸나요?</text>
  <rect x="72" y="650" width="936" height="446" rx="46" fill="#111F33" stroke="#263753" stroke-width="2"/>
  <text x="120" y="748" fill="${C.muted}" font-size="28" font-weight="800">손으로 10개 게시할 때</text>
  <text x="120" y="912" fill="url(#hot)" font-size="140" font-weight="900">100~150분</text>
  <text x="120" y="1018" fill="${C.white}" font-size="34" font-weight="800">상품 확인부터 문구·이미지·고지까지</text>
  <text x="72" y="1270" fill="${C.muted}" font-size="30" font-weight="700">열심히보다 먼저 바꿔야 할 건</text>
  <text x="72" y="1352" fill="${C.white}" font-size="62" font-weight="900">반복 방식입니다.</text>
  <rect x="72" y="1510" width="936" height="142" rx="36" fill="url(#hot)"/>
  <text x="540" y="1598" fill="white" font-size="36" font-weight="900" text-anchor="middle">다음 스토리에서 실제 화면 공개 →</text>`);

const story2 = storyBase(2, `
  <text x="72" y="420" fill="${C.white}" font-size="76" font-weight="900">링크 붙여넣기</text>
  <text x="72" y="520" fill="url(#hot)" font-size="76" font-weight="900">→ 자동화 시작</text>
  <g filter="url(#shadow)">
    <rect x="54" y="542" width="972" height="786" rx="48" fill="#0B111B"/>
    <image href="data:image/png;base64,${proof}" x="72" y="560" width="936" height="720" preserveAspectRatio="xMidYMid slice" clip-path="url(#storyScreen)"/>
  </g>
  <rect x="72" y="1252" width="310" height="58" rx="29" fill="${C.green}"/>
  <text x="227" y="1291" fill="${C.navy}" font-size="22" font-weight="900" text-anchor="middle">실제 프로그램 화면</text>
  <text x="72" y="1456" fill="${C.muted}" font-size="27" font-weight="800">프로그램이 이어서 처리</text>
  <text x="72" y="1534" fill="${C.white}" font-size="42" font-weight="900">분석 · AI 문구 · 이미지 · 고지 · 게시</text>
  <text x="72" y="1668" fill="${C.coral}" font-size="32" font-weight="900">말보다 화면으로 확인하세요.</text>`);

const story3 = storyBase(3, `
  <circle cx="854" cy="410" r="250" fill="${C.coral}" opacity=".13"/>
  <text x="72" y="452" fill="${C.white}" font-size="84" font-weight="900">무료 설치로</text>
  <text x="72" y="562" fill="${C.white}" font-size="84" font-weight="900">직접 확인.</text>
  <text x="72" y="662" fill="${C.muted}" font-size="30" font-weight="700">수익 보장 같은 말은 하지 않습니다.</text>
  <g transform="translate(72 780)">
    <rect width="936" height="394" rx="46" fill="#111F33" stroke="#263753" stroke-width="2"/>
    <text x="48" y="86" fill="${C.muted}" font-size="28" font-weight="800">월간 구독</text>
    <text x="48" y="205" fill="${C.white}" font-size="84" font-weight="900">49,000원</text>
    <text x="48" y="285" fill="${C.green}" font-size="28" font-weight="900">✓ Windows 무료 다운로드</text>
    <text x="48" y="340" fill="${C.green}" font-size="28" font-weight="900">✓ 결제 후 7일 이내 전액 환불</text>
  </g>
  <rect x="72" y="1290" width="936" height="162" rx="40" fill="url(#hot)"/>
  <text x="540" y="1360" fill="white" font-size="27" font-weight="800" text-anchor="middle">프로필 링크</text>
  <text x="540" y="1410" fill="white" font-size="38" font-weight="900" text-anchor="middle">coupasthreadauto.me</text>
  <text x="72" y="1605" fill="${C.white}" font-size="40" font-weight="900">궁금한 점은 DM으로 남겨주세요.</text>
  <text x="72" y="1670" fill="${C.muted}" font-size="25" font-weight="700">설치 · 사용법 · 구독 문의</text>`);

(async () => {
  await Promise.all([
    write('feed-01-hook.png', feed1, 1080, 1350),
    write('feed-02-proof.png', feed2, 1080, 1350),
    write('feed-03-features.png', feed3, 1080, 1350),
    write('feed-04-cta.png', feed4, 1080, 1350),
    write('story-01-pain.png', story1, 1080, 1920),
    write('story-02-proof.png', story2, 1080, 1920),
    write('story-03-cta.png', story3, 1080, 1920),
  ]);
  console.log('Generated Instagram v3 assets.');
})();
