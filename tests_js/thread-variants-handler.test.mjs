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

test("fails closed without calling AI when atomic reservation is unsupported", async (t) => {
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
  globalThis.fetch = async (url) => {
    calls.push(String(url));
    return jsonResponse(404, { success: false });
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
  assert.equal(res.statusCode, 503);
  assert.equal(payload.success, false);
  assert.equal(payload.code, "ATOMIC_QUOTA_UNAVAILABLE");
  assert.match(calls[0], /\/user\/work\/reserve$/);
  assert.equal(calls.length, 1);
});

test("rejects an idempotency replay without calling AI again", async (t) => {
  const originalFetch = globalThis.fetch;
  const originalGatewayKey = process.env.AI_GATEWAY_API_KEY;
  process.env.AI_GATEWAY_API_KEY = "test-gateway-key";
  t.after(() => {
    globalThis.fetch = originalFetch;
    if (originalGatewayKey === undefined) delete process.env.AI_GATEWAY_API_KEY;
    else process.env.AI_GATEWAY_API_KEY = originalGatewayKey;
  });

  const calls = [];
  globalThis.fetch = async (url) => {
    calls.push(String(url));
    return jsonResponse(200, {
      success: false,
      allowed: false,
      code: "IDEMPOTENCY_REPLAY",
      reservation_id: "existing-reservation",
    });
  };

  const req = {
    method: "POST",
    headers: {
      authorization: "Bearer login-token",
      "idempotency-key": "already-used-request",
    },
    body: {
      user_id: "user-1",
      product: {
        title: "접이식 캠핑 웨건 카트",
        url: "https://link.coupang.com/a/example",
        keywords: "캠핑 웨건",
        features: ["접이식"],
      },
      client: { schema_version: 1 },
    },
  };
  const res = mockResponse();

  await handler(req, res);

  const payload = JSON.parse(res.body);
  assert.equal(res.statusCode, 409);
  assert.equal(payload.code, "DUPLICATE_REQUEST");
  assert.equal(calls.length, 1);
  assert.match(calls[0], /\/user\/work\/reserve$/);
});

test("reserves atomically and releases the reservation when generation fails", async (t) => {
  const originalFetch = globalThis.fetch;
  const originalGatewayKey = process.env.AI_GATEWAY_API_KEY;
  process.env.AI_GATEWAY_API_KEY = "test-gateway-key";
  t.after(() => {
    globalThis.fetch = originalFetch;
    if (originalGatewayKey === undefined) delete process.env.AI_GATEWAY_API_KEY;
    else process.env.AI_GATEWAY_API_KEY = originalGatewayKey;
  });

  const requests = [];
  globalThis.fetch = async (url, options = {}) => {
    requests.push({ url: String(url), body: JSON.parse(options.body || "{}") });
    if (requests.length === 1) {
      return jsonResponse(200, { success: true, reservation_id: "reserve-1" });
    }
    if (requests.length === 2) {
      return jsonResponse(500, { error: { message: "provider unavailable" } });
    }
    return jsonResponse(200, { success: true, released: true });
  };

  const req = {
    method: "POST",
    headers: {
      authorization: "Bearer login-token",
      "idempotency-key": "request-atomic-1",
    },
    body: {
      user_id: "user-1",
      product: {
        title: "접이식 캠핑 웨건 카트",
        url: "https://link.coupang.com/a/example",
        keywords: "캠핑 웨건",
        features: ["접이식"],
      },
      client: { schema_version: 1 },
    },
  };
  const res = mockResponse();

  await handler(req, res);

  const payload = JSON.parse(res.body);
  assert.equal(res.statusCode, 503);
  assert.equal(payload.success, false);
  assert.equal(payload.code, "AI_TEMPORARILY_UNAVAILABLE");
  assert.deepEqual(
    requests.map((item) => new URL(item.url).pathname),
    ["/user/work/reserve", "/v1/chat/completions", "/user/work/release"],
  );
  assert.equal(requests[0].body.idempotency_key, "request-atomic-1");
  assert.equal(requests[2].body.reservation_id, "reserve-1");
  assert.equal(requests[2].body.idempotency_key, "request-atomic-1");
});

test("returns an atomic reservation for the desktop to commit after upload", async (t) => {
  const originalFetch = globalThis.fetch;
  const originalGatewayKey = process.env.AI_GATEWAY_API_KEY;
  process.env.AI_GATEWAY_API_KEY = "test-gateway-key";
  t.after(() => {
    globalThis.fetch = originalFetch;
    if (originalGatewayKey === undefined) delete process.env.AI_GATEWAY_API_KEY;
    else process.env.AI_GATEWAY_API_KEY = originalGatewayKey;
  });

  const requests = [];
  globalThis.fetch = async (url, options = {}) => {
    requests.push({ url: String(url), body: JSON.parse(options.body || "{}") });
    if (requests.length === 1) {
      return jsonResponse(200, { allowed: true, work_token: "reserve-success-1" });
    }
    return jsonResponse(200, {
      choices: [{ message: { content: JSON.stringify(gatewayVariants) } }],
    });
  };

  const req = {
    method: "POST",
    headers: {
      authorization: "Bearer login-token",
      "idempotency-key": "request-success-1",
    },
    body: {
      user_id: "user-1",
      product: {
        title: "접이식 캠핑 웨건 카트",
        url: "https://link.coupang.com/a/example",
        keywords: "캠핑 웨건",
        features: ["접이식"],
      },
      client: { schema_version: 1 },
    },
  };
  const res = mockResponse();

  await handler(req, res);

  const payload = JSON.parse(res.body);
  assert.equal(res.statusCode, 200);
  assert.equal(payload.success, true);
  assert.equal(payload.reservation_id, "reserve-success-1");
  assert.equal(payload.quota_mode, "reservation");
  assert.equal(payload.variants.length, 4);
  assert.deepEqual(
    requests.map((item) => new URL(item.url).pathname),
    ["/user/work/reserve", "/v1/chat/completions"],
  );
  assert.equal(requests[0].body.idempotency_key, "request-success-1");
});
