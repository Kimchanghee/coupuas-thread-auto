import assert from "node:assert/strict";
import test from "node:test";

import {
  AFFILIATE_DISCLOSURE,
  buildFallbackVariants,
  buildPrompt,
  extractReservationId,
  isAllowedQuotaPayload,
  normalizeProduct,
  parseGatewayContent,
  validateVariants,
} from "../api/_lib/managed-ai.mjs";

const product = normalizeProduct({
  title: "휴대용 미니 선풍기",
  url: "https://link.coupang.com/a/example",
  keywords: "출퇴근 여름 휴대용",
  features: ["손에 들고 사용할 수 있음", "충전식"],
});

const validVariants = {
  variants: [
    {
      variant_id: "target_direct",
      root_text: "출근길마다 손부채질하다 지치는 사람만 봐. 가방 한쪽에 넣어둔 작은 해결책이 생각보다 자주 손에 잡히더라.",
    },
    {
      variant_id: "convenience_contrast",
      root_text: "종이 부채는 손이 바쁘고 큰 선풍기는 들고 갈 수 없잖아. 버튼 한 번으로 바람을 데리고 다니는 방식은 좀 궁금하지 않아?",
    },
    {
      variant_id: "fun_reveal",
      root_text: "처음엔 손바닥만 한 장난감인 줄 알았는데 켜는 순간 혼자 여름과 협상하더라. 이 조그만 녀석의 정체가 은근 반전이야.",
    },
    {
      variant_id: "use_scene_story",
      root_text: "버스를 기다리는 삼 분 동안 목덜미에 땀이 맺히는 순간. 가방에서 꺼낸 작은 물건 하나로 표정이 먼저 달라진다면 뭘까?",
    },
  ],
};

test("normalizes a valid product and builds a fact-bounded prompt", () => {
  assert.equal(product.title, "휴대용 미니 선풍기");
  assert.match(buildPrompt(product), /확인된 특징/);
  assert.match(buildPrompt(product), /target_direct/);
});

test("rejects invalid product URLs", () => {
  assert.throws(
    () => normalizeProduct({ title: "상품", url: "javascript:alert(1)" }),
    /지원하지 않는 상품 링크/,
  );
});

test("builds four distinct Korean fallback variants from verified product facts", () => {
  const fallback = buildFallbackVariants(
    normalizeProduct({
      title: "접이식 캠핑 웨건 카트",
      url: "https://link.coupang.com/a/example",
      keywords: "캠핑 웨건 폴딩 카트",
      features: ["접이식", "최대무게 100kg"],
    }),
  );
  const result = validateVariants(fallback, product);
  assert.equal(result.length, 4);
  assert.equal(new Set(result.map((item) => item.root_text)).size, 4);
  assert.match(result[0].root_text, /캠핑/);
  assert.doesNotMatch(result[0].root_text, /https?:\/\//);
});

test("validates all four variants and adds deterministic product comment", () => {
  const result = validateVariants(validVariants, product);
  assert.equal(result.length, 4);
  assert.equal(result[0].variant_id, "target_direct");
  assert.match(result[0].product_comment_text, /link\.coupang\.com/);
  assert.match(result[0].product_comment_text, new RegExp(AFFILIATE_DISCLOSURE));
  assert.doesNotMatch(result[0].root_text, /https?:\/\//);
});

test("rejects links and disclosure in the root post", () => {
  const invalid = structuredClone(validVariants);
  invalid.variants[0].root_text += " https://link.coupang.com/a/example";
  assert.throws(() => validateVariants(invalid, product), /링크 또는 광고 고지/);
});

test("parses gateway content and quota contracts", () => {
  assert.deepEqual(
    parseGatewayContent({ choices: [{ message: { content: JSON.stringify(validVariants) } }] }),
    validVariants,
  );
  assert.equal(isAllowedQuotaPayload({ available: true }), true);
  assert.equal(isAllowedQuotaPayload({ success: false }), false);
  assert.equal(extractReservationId({ work_token: "res-123" }), "res-123");
});
