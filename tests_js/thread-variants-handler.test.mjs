import assert from "node:assert/strict";
import test from "node:test";

import handler from "../api/ai/thread-variants.mjs";

function jsonResponse(status, payload) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function mockResponse() {
  return {
    statusCode: 0,
    headers: {},
    body: "",
    setHeader(name, value) {
      this.headers[String(name).toLowerCase()] = value;
    },
    end(value = "") {
      this.body = String(value);
    },
  };
}

const gatewayVariants = {
  variants: [
    {
      variant_id: "target_direct",
      root_text:
        "캠핑 갈 때 짐보다 웨건 손잡이와 먼저 씨름하는 사람 있지? 한 번에 옮기려다 결국 두 번 왕복했던 장면이 떠오른다면 아래 정체가 꽤 궁금할 거야.",
    },
    {
      variant_id: "convenience_contrast",
      root_text:
        "양손에 가방을 매달고 걷던 방식과 한곳에 싣고 끄는 방식은 출발부터 다르더라. 접어둘 수 있는 큰 수레 하나가 캠핑 준비 동선을 얼마나 바꿀까?",
    },
    {
      variant_id: "fun_reveal",
      root_text:
        "처음엔 캠핑장에 작은 트럭을 가져온 줄 알았어. 그런데 짐을 다 내리고 납작하게 접히는 걸 보니 정체가 더 웃기고 궁금해지더라.",
    },
    {
      variant_id: "use_scene_story",
      root_text:
        "주차장에서 텐트와 아이스박스를 싣고 출발했다. 한 번에 사이트 앞까지 도착한 뒤 손잡이를 놓는 순간, 왜 사람들이 이걸 찾는지 장면이 설명해줬다.",
    },
  ],
};

test("falls back to legacy check/use quota contract when reserve is unsupported", async (t) => {
  const originalFetch = globalThis.fetch;
  const originalGatewayKey = process.env.AI_GATEWAY_API_KEY;
  process.env.AI_GATEWAY_API_KEY = "test-gateway-key";
  t.after(() => {
    globalThis.fetch = originalFetch;
    if (originalGatewayKey === undefined) {
      delete process.env.AI_GATEWAY_API_KEY;
    } else {
      process.env.AI_GATEWAY_API_KEY = originalGatewayKey;
    }
  });

  const calls = [];
  const gatewayRequests = [];
  globalThis.fetch = async (url, options = {}) => {
    calls.push(String(url));
    if (calls.length === 1) {
      return jsonResponse(404, { success: false });
    }
    if (calls.length === 2) {
      return jsonResponse(200, { available: true });
    }
    gatewayRequests.push(JSON.parse(options.body));
    return jsonResponse(403, {
      error: {
        message: "AI Gateway requires a valid credit card on file.",
      },
    });
  };

  const req = {
    method: "POST",
    headers: {
      authorization: "Bearer login-token",
      "idempotency-key": "request-1",
      "x-forwarded-for": "127.0.0.1",
    },
    body: {
      user_id: "user-1",
      product: {
        title: "접이식 캠핑 웨건 카트",
        url: "https://link.coupang.com/a/example",
        keywords: "캠핑 웨건 폴딩 카트",
        features: ["접이식", "최대무게 100kg"],
      },
      client: { schema_version: 1 },
    },
  };
  const res = mockResponse();

  await handler(req, res);

  const payload = JSON.parse(res.body);
  assert.equal(res.statusCode, 200);
  assert.equal(payload.success, true);
  assert.equal(payload.quota_mode, "legacy");
  assert.equal(payload.model, "template-fallback");
  assert.equal(payload.degraded, true);
  assert.equal(payload.degraded_reason, "ai_credits_required");
  assert.match(payload.reservation_id, /^legacy:/);
  assert.equal(payload.variants.length, 4);
  assert.match(calls[0], /\/user\/work\/reserve$/);
  assert.match(calls[1], /\/user\/work\/check$/);
  assert.equal(calls[2], "https://ai-gateway.vercel.sh/v1/chat/completions");
  assert.equal(calls.length, 3);
  assert.equal(gatewayRequests.length, 1);
  assert.equal(gatewayRequests[0].model, "xai/grok-4.3");
});
