const VARIANT_IDS = Object.freeze([
  "target_direct",
  "convenience_contrast",
  "fun_reveal",
  "use_scene_story",
]);

const AFFILIATE_DISCLOSURE =
  "이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.";
const GENERAL_AFFILIATE_DISCLOSURE =
  "이 게시물에는 광고·제휴 링크가 포함될 수 있으며, 구매 시 작성자가 일정액의 수수료를 제공받을 수 있습니다.";

const MARKETPLACES = Object.freeze([
  { id: "coupang", label: "쿠팡", hosts: ["coupang.com"], disclosure: AFFILIATE_DISCLOSURE },
  {
    id: "naver",
    label: "네이버쇼핑",
    hosts: ["shopping.naver.com", "smartstore.naver.com", "brand.naver.com", "shoppinglive.naver.com", "naver.me"],
    disclosure: GENERAL_AFFILIATE_DISCLOSURE,
  },
  {
    id: "toss",
    label: "토스쇼핑",
    hosts: ["shopping.toss.im", "shopping-view.toss.im", "link.toss.im", "toss.im"],
    disclosure: GENERAL_AFFILIATE_DISCLOSURE,
  },
  { id: "aliexpress", label: "AliExpress", hosts: ["aliexpress.com"], disclosure: GENERAL_AFFILIATE_DISCLOSURE },
]);

const BLOCKED_ROOT_PATTERNS = [
  /https?:\/\//i,
  /link\.coupang\.com/i,
  /www\.coupang\.com/i,
  /쿠팡\s*파트너스/i,
  /(?:네이버|토스)\s*쇼핑/i,
  /ali\s*express/i,
  /광고[·\s]*제휴\s*링크/i,
  /수수료를\s*제공받/i,
];

const FORBIDDEN_CLAIM_PATTERNS = [
  /100\s*%/i,
  /무조건/i,
  /완치/i,
  /치료/i,
  /부작용\s*없/i,
  /품절\s*확정/i,
  /최저가\s*보장/i,
];

export { AFFILIATE_DISCLOSURE, GENERAL_AFFILIATE_DISCLOSURE, MARKETPLACES, VARIANT_IDS };

function marketplaceForHost(hostname) {
  const host = String(hostname || "").toLowerCase().replace(/\.$/, "");
  return MARKETPLACES.find((marketplace) =>
    marketplace.hosts.some((allowed) =>
      host === allowed
      || (["coupang", "aliexpress"].includes(marketplace.id) && host.endsWith(`.${allowed}`)),
    ),
  );
}

export function sanitizeText(value, maxLength = 500) {
  return String(value ?? "")
    .replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/g, " ")
    .replace(/\r/g, "\n")
    .replace(/[ \t]+/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .trim()
    .slice(0, maxLength);
}

export function normalizeProduct(rawProduct) {
  const raw = rawProduct && typeof rawProduct === "object" ? rawProduct : {};
  const title = sanitizeText(raw.title, 300);
  const url = sanitizeText(raw.url, 1000);
  const claimedMarketplace = sanitizeText(raw.marketplace, 40).toLowerCase();
  const keywords = sanitizeText(raw.keywords, 500);
  const featureSource = Array.isArray(raw.features) ? raw.features : [];
  const features = featureSource
    .map((item) => sanitizeText(item, 240))
    .filter(Boolean)
    .slice(0, 12);

  if (title.length < 2) {
    throw new ManagedAiError("INVALID_PRODUCT_FACTS", 422, "상품명이 필요합니다.");
  }
  let parsedUrl;
  try {
    parsedUrl = new URL(url);
  } catch {
    throw new ManagedAiError("INVALID_PRODUCT_FACTS", 422, "올바른 상품 링크가 필요합니다.");
  }
  if (
    parsedUrl.protocol !== "https:"
    || parsedUrl.username
    || parsedUrl.password
    || (parsedUrl.port && parsedUrl.port !== "443")
  ) {
    throw new ManagedAiError("INVALID_PRODUCT_FACTS", 422, "지원하지 않는 상품 링크입니다.");
  }
  const marketplace = marketplaceForHost(parsedUrl.hostname);
  if (!marketplace || (claimedMarketplace && claimedMarketplace !== marketplace.id)) {
    throw new ManagedAiError("INVALID_PRODUCT_FACTS", 422, "지원하지 않는 상품 링크입니다.");
  }
  return {
    title,
    url: parsedUrl.toString(),
    keywords,
    features,
    marketplace: marketplace.id,
    marketplaceLabel: marketplace.label,
    affiliateDisclosure: marketplace.disclosure,
  };
}

export class ManagedAiError extends Error {
  constructor(code, status, message, details = undefined) {
    super(message);
    this.name = "ManagedAiError";
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

export function buildPrompt(product) {
  const facts = product.features.length
    ? product.features.map((feature, index) => `${index + 1}. ${feature}`).join("\n")
    : "확인된 추가 특징 없음. 상품명과 키워드 범위 안에서만 표현할 것.";

  return `당신은 한국 Threads용 짧은 상품 스토리 카피를 만드는 편집자다.

[검증된 상품 정보]
상품명: ${product.title}
쇼핑몰: ${product.marketplaceLabel}
키워드: ${product.keywords || "없음"}
확인된 특징:
${facts}

[공통 규칙]
- 한국어로만 작성한다.
- 각 버전은 2~3문장, 45~150자다.
- 첫 글에는 상품명 전체, URL, 상품·구매·제휴 링크, 쇼핑몰명, 광고·수수료 고지를 넣지 않는다.
- 첫 글에는 이미지가 있다고 암시하거나 사진·영상 공개를 예고하지 않는다.
- 확인되지 않은 가격, 할인율, 재고, 후기, 효능, 성능을 만들지 않는다.
- 과장된 치료·보장·100% 표현을 쓰지 않는다.
- 광고 문구처럼 나열하지 말고 실제 사람이 겪는 짧은 장면이나 반응으로 시작한다.
- 두 번째 글을 눌러 정체와 링크를 확인하고 싶게 미완의 호기심으로 끝낸다.
- 네 버전의 첫 문장과 상황, 표현을 서로 겹치지 않게 만든다.

[버전]
1. target_direct: 가장 편해질 타깃 한 명과 반복되는 불편을 직격한다.
2. convenience_contrast: 기존의 번거로운 방식과 사용 후 변화를 대비한다.
3. fun_reveal: 상품의 모양이나 사용 장면을 재치 있게 비유하고 정체를 궁금하게 한다.
4. use_scene_story: 실제 사용 순간을 3초짜리 장면처럼 보여주고 반전 질문으로 끝낸다.

지정된 JSON 스키마만 출력한다.`;
}

export function buildFallbackVariants(product) {
  const categoryText = String(product.title + " " + product.keywords).toLowerCase();
  let roots;

  if (/웨건|카트|수레/.test(categoryText)) {
    roots = [
      "캠핑 갈 때 짐을 한 번에 못 옮겨 주차장을 몇 번씩 오가는 사람 있지? 텐트보다 먼저 체력이 빠지는 그 동선을 줄여주는 정체가 아래에 있어.",
      "양손에 가방을 매달고 걷던 방식과 한곳에 싣고 끄는 방식은 출발부터 다르더라. 쓰고 나서 접어둘 수 있다면 캠핑 준비가 어디까지 가벼워질까?",
      "캠핑장에 작은 트럭을 끌고 온 줄 알았어. 짐을 다 내린 뒤 납작하게 접히는 걸 보니 더 웃김. 이 수상한 짐꾼의 정체는 아래에서 확인해봐.",
      "주차장에서 텐트, 의자, 아이스박스를 싣고 출발했다. 한 번에 사이트 앞에 도착하고 손잡이를 놓는 순간, 왜 이 방식이 편한지 장면이 다 설명하더라.",
    ];
  } else if (/액션캠|카메라|브이로그/.test(categoryText)) {
    roots = [
      "여행 장면을 남기려다 한 손이 늘 휴대폰에 묶이는 사람 있지? 놀기는 했는데 정작 내 모습은 없던 그날을 바꿔줄 작은 정체가 아래에 있어.",
      "휴대폰을 꺼내고 잠금을 풀고 구도를 잡는 사이 장면은 지나가 버리더라. 몸에 가깝게 두고 바로 기록하는 방식이면 결과가 얼마나 달라질까?",
      "처음엔 장난감 카메라인 줄 알았어. 그런데 작은 몸에 영상 기능과 여러 구성품을 챙겨둔 걸 보니 여행 가방에서 제일 바쁠 얼굴이더라.",
      "물가에 도착하고, 버튼을 누르고, 두 손은 다시 자유로워졌다. 지나가는 순간을 따라다니는 작은 기록 도구의 정체는 아래에서 이어진다.",
    ];
  } else if (/카약|보트|패들/.test(categoryText)) {
    roots = [
      "물놀이는 기대되는데 보트 부피 때문에 출발 전부터 포기한 사람 있지? 차에 싣는 순간 여행이 아니라 이사가 되던 문제를 다르게 푸는 정체가 있어.",
      "단단한 보트를 통째로 옮기는 방식과 필요할 때 공기를 넣는 방식은 보관부터 다르더라. 접어서 가져가는 선택지가 생기면 물가가 얼마나 가까워질까?",
      "커다란 가방에서 보트가 나온다길래 과장인 줄 알았어. 공기를 넣을수록 탈것의 얼굴이 되는 모습은 볼 때마다 휴대용 섬을 펼치는 기분임.",
      "차에서 가방을 내리고, 물가에서 펼치고, 공기를 채웠다. 조금 전까지 접혀 있던 물건이 사람을 태우는 장면으로 바뀌는 순간이 꽤 재밌다.",
    ];
  } else {
    roots = [
      "쓸 때마다 반복되는 작은 불편인데 그냥 참고 있던 사람 있지? 행동 한 단계를 줄여주는 물건은 의외로 이런 평범한 순간에서 티가 나더라.",
      "늘 하던 번거로운 방식과 한 번에 정리되는 방식을 나란히 두면 차이가 더 선명해진다. 사소한 동선 하나가 얼마나 달라질지 궁금해진다.",
      "처음엔 용도를 맞히기 어려운 물건인 줄 알았어. 그런데 쓰는 장면을 보고 나니 왜 이런 모양이 됐는지 바로 이해되는 반전이 있더라.",
      "꺼내고, 펼치고, 바로 사용했다. 설명보다 짧은 그 장면 하나가 누구에게 편한 물건인지 보여준다. 정체와 확인할 점은 아래에서 이어진다.",
    ];
  }

  return {
    variants: VARIANT_IDS.map((variantId, index) => ({
      variant_id: variantId,
      root_text: roots[index],
    })),
  };
}

export const RESPONSE_SCHEMA = Object.freeze({
  type: "object",
  additionalProperties: false,
  properties: {
    variants: {
      type: "array",
      minItems: 4,
      maxItems: 4,
      items: {
        type: "object",
        additionalProperties: false,
        properties: {
          variant_id: { type: "string", enum: VARIANT_IDS },
          root_text: { type: "string" },
        },
        required: ["variant_id", "root_text"],
      },
    },
  },
  required: ["variants"],
});

function tokenizeForSimilarity(value) {
  return new Set(
    sanitizeText(value, 500)
      .toLowerCase()
      .replace(/[^0-9a-z가-힣\s]/g, " ")
      .split(/\s+/)
      .filter((token) => token.length >= 2),
  );
}

function jaccardSimilarity(left, right) {
  const a = tokenizeForSimilarity(left);
  const b = tokenizeForSimilarity(right);
  if (!a.size || !b.size) return 0;
  let intersection = 0;
  for (const token of a) {
    if (b.has(token)) intersection += 1;
  }
  return intersection / (a.size + b.size - intersection);
}

export function validateVariants(rawValue, product) {
  const variants = rawValue?.variants;
  if (!Array.isArray(variants) || variants.length !== VARIANT_IDS.length) {
    throw new ManagedAiError("INVALID_AI_OUTPUT", 502, "AI가 네 가지 문안을 완성하지 못했습니다.");
  }

  const byId = new Map();
  for (const rawVariant of variants) {
    const variantId = sanitizeText(rawVariant?.variant_id, 60);
    const rootText = sanitizeText(rawVariant?.root_text, 220);
    if (!VARIANT_IDS.includes(variantId) || byId.has(variantId)) {
      throw new ManagedAiError("INVALID_AI_OUTPUT", 502, "AI 문안 버전 구성이 올바르지 않습니다.");
    }
    const compactLength = rootText.replace(/\s/g, "").length;
    if (compactLength < 25 || rootText.length > 180) {
      throw new ManagedAiError("INVALID_AI_OUTPUT", 502, "AI 문안 길이가 기준을 벗어났습니다.");
    }
    if (BLOCKED_ROOT_PATTERNS.some((pattern) => pattern.test(rootText))) {
      throw new ManagedAiError("INVALID_AI_OUTPUT", 502, "첫 글에 링크 또는 광고 고지가 포함되었습니다.");
    }
    if (FORBIDDEN_CLAIM_PATTERNS.some((pattern) => pattern.test(rootText))) {
      throw new ManagedAiError("INVALID_AI_OUTPUT", 502, "확인되지 않은 과장 표현이 포함되었습니다.");
    }
    byId.set(variantId, rootText);
  }

  for (let i = 0; i < VARIANT_IDS.length; i += 1) {
    for (let j = i + 1; j < VARIANT_IDS.length; j += 1) {
      const score = jaccardSimilarity(byId.get(VARIANT_IDS[i]), byId.get(VARIANT_IDS[j]));
      if (score >= 0.68) {
        throw new ManagedAiError("INVALID_AI_OUTPUT", 502, "AI 문안 간 표현이 지나치게 비슷합니다.");
      }
    }
  }

  const commentText = [
    `🔗 ${sanitizeText(product.title, 80)}`,
    product.url,
    product.affiliateDisclosure,
  ].join("\n\n");

  return VARIANT_IDS.map((variantId) => ({
    variant_id: variantId,
    root_text: byId.get(variantId),
    product_comment_text: commentText,
  }));
}

export function parseGatewayContent(payload) {
  const content = payload?.choices?.[0]?.message?.content;
  if (typeof content !== "string" || !content.trim()) {
    throw new ManagedAiError("INVALID_AI_OUTPUT", 502, "AI 응답이 비어 있습니다.");
  }
  try {
    return JSON.parse(content);
  } catch {
    throw new ManagedAiError("INVALID_AI_OUTPUT", 502, "AI 응답을 해석할 수 없습니다.");
  }
}

export function isAllowedQuotaPayload(payload) {
  if (!payload || typeof payload !== "object") return false;
  if ("available" in payload) return Boolean(payload.available);
  if ("allowed" in payload) return Boolean(payload.allowed);
  if ("success" in payload) return Boolean(payload.success);
  if ("status" in payload) return Boolean(payload.status);
  return false;
}

export function extractReservationId(payload) {
  return sanitizeText(
    payload?.reservation_id ?? payload?.reserve_id ?? payload?.work_token,
    200,
  );
}
