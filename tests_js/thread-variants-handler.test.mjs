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

test("releases an idempotency replay and asks the client for a new key", async (t) => {
  const originalFetch = globalThis.fetch;
  const originalGatewayKey = process.env.AI_GATEWAY_API_KEY;
  process.env.AI_GATEWAY_API_KEY = "test-gateway-key";
  t.after(() => {
    globalThis.fetch = originalFetch;
    if (originalGatewayKey === undefined) delete process.env.AI_GATEWAY_API_KEY;
    else process.env.AI_GATEWAY_API_KEY = originalGatewayKey;
  });

  const calls = [];
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ path: new URL(url).pathname, body: JSON.parse(options.body || "{}") });
    if (calls.length === 1) {
      return jsonResponse(409, {
        success: false,
        allowed: false,
        code: "IDEMPOTENCY_REPLAY",
        reservation_status: "reserved",
        reservation_id: "existing-reservation",
      });
    }
    if (calls.length === 2) {
      return jsonResponse(200, { success: true, released: true });
    }
    if (calls.length === 3) {
      return jsonResponse(200, {
        success: true,
        allowed: true,
        reservation_id: "new-key-reservation",
      });
    }
    return jsonResponse(200, {
      choices: [{ message: { content: JSON.stringify(gatewayVariants) } }],
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
  assert.equal(payload.retry_with_new_idempotency_key, true);
  assert.equal(payload.ai_job_id, "already-used-request");
  assert.equal(payload.reservation_id, undefined);
  assert.equal(payload.reservation_release_pending, undefined);
  assert.deepEqual(calls.map((call) => call.path), [
    "/user/work/reserve",
    "/user/work/release",
  ]);
  assert.equal(calls[1].body.reservation_id, "existing-reservation");
  assert.equal(calls[1].body.idempotency_key, "already-used-request");

  const retryReq = {
    ...req,
    headers: {
      ...req.headers,
      "idempotency-key": "replacement-request",
    },
  };
  const retryRes = mockResponse();
  await handler(retryReq, retryRes);

  const retryPayload = JSON.parse(retryRes.body);
  assert.equal(retryRes.statusCode, 200);
  assert.equal(retryPayload.success, true);
  assert.equal(retryPayload.reservation_id, "new-key-reservation");
  assert.equal(calls[2].body.idempotency_key, "replacement-request");
  assert.equal(calls[3].path, "/v1/chat/completions");
});

test("keeps replay reservation metadata when server-side release fails", async (t) => {
  const originalFetch = globalThis.fetch;
  const originalConsoleError = console.error;
  console.error = () => {};
  const calls = [];
  globalThis.fetch = async (url) => {
    calls.push(new URL(url).pathname);
    if (calls.length === 1) {
      return jsonResponse(409, {
        success: false,
        code: "IDEMPOTENCY_REPLAY",
        reservation_status: "reserved",
        reservation_id: "replay-release-pending",
      });
    }
    return jsonResponse(200, { success: false, released: false });
  };
  t.after(() => {
    globalThis.fetch = originalFetch;
    console.error = originalConsoleError;
  });

  const req = {
    method: "POST",
    headers: {
      authorization: "Bearer login-token",
      "idempotency-key": "replay-release-failed-request",
    },
    body: {
      user_id: "user-1",
      product: {
        title: "접이식 캠핑 웨건 카트",
        url: "https://link.coupang.com/a/example",
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
  assert.equal(payload.retry_with_new_idempotency_key, undefined);
  assert.equal(payload.reservation_release_pending, true);
  assert.equal(payload.reservation_id, "replay-release-pending");
  assert.equal(payload.ai_job_id, "replay-release-failed-request");
  assert.deepEqual(calls, ["/user/work/reserve", "/user/work/release"]);
});

test("handles released, committed, and unknown replay states without refunding", async (t) => {
  const originalFetch = globalThis.fetch;
  t.after(() => { globalThis.fetch = originalFetch; });

  for (const reservationStatus of ["committed", "released", "unknown"]) {
    const calls = [];
    globalThis.fetch = async (url) => {
      calls.push(new URL(url).pathname);
      return jsonResponse(409, {
        success: false,
        code: "IDEMPOTENCY_REPLAY",
        reservation_status: reservationStatus,
        reservation_id: `must-not-release-${reservationStatus}`,
      });
    };
    const req = {
      method: "POST",
      headers: {
        authorization: "Bearer login-token",
        "idempotency-key": `replay-${reservationStatus}`,
      },
      body: {
        user_id: "user-1",
        product: {
          title: "접이식 캠핑 웨건 카트",
          url: "https://link.coupang.com/a/example",
          features: ["접이식"],
        },
        client: { schema_version: 1 },
      },
    };
    const res = mockResponse();

    await handler(req, res);

    const payload = JSON.parse(res.body);
    assert.equal(res.statusCode, 409);
    assert.equal(
      payload.retry_with_new_idempotency_key,
      reservationStatus === "released" ? true : undefined,
    );
    if (reservationStatus === "released") {
      assert.equal(payload.ai_job_id, `replay-${reservationStatus}`);
    }
    assert.equal(payload.reservation_release_pending, undefined);
    assert.deepEqual(calls, ["/user/work/reserve"]);
  }
});

test("releases an explicitly pending reservation from a failed reserve response", async (t) => {
  const originalFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url) => {
    calls.push(new URL(url).pathname);
    if (calls.length === 1) {
      return jsonResponse(503, {
        success: false,
        reservation_release_pending: true,
        reservation_id: "partial-reservation",
      });
    }
    return jsonResponse(200, { success: true, released: true });
  };
  t.after(() => { globalThis.fetch = originalFetch; });

  const req = {
    method: "POST",
    headers: {
      authorization: "Bearer login-token",
      "idempotency-key": "request-partial-reserve",
    },
    body: {
      user_id: "user-1",
      product: {
        title: "접이식 캠핑 웨건 카트",
        url: "https://link.coupang.com/a/example",
        features: ["접이식"],
      },
      client: { schema_version: 1 },
    },
  };
  const res = mockResponse();

  await handler(req, res);

  const payload = JSON.parse(res.body);
  assert.equal(res.statusCode, 503);
  assert.equal(payload.code, "QUOTA_RESERVATION_FAILED");
  assert.equal(payload.reservation_release_pending, undefined);
  assert.deepEqual(calls, ["/user/work/reserve", "/user/work/release"]);
});

test("never releases an untrusted reservation id from an authentication error", async (t) => {
  const originalFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url) => {
    calls.push(new URL(url).pathname);
    return jsonResponse(401, {
      success: false,
      reservation_release_pending: true,
      reservation_id: "not-owned-reservation",
    });
  };
  t.after(() => { globalThis.fetch = originalFetch; });

  const req = {
    method: "POST",
    headers: {
      authorization: "Bearer expired-token",
      "idempotency-key": "request-auth-error",
    },
    body: {
      user_id: "user-1",
      product: {
        title: "접이식 캠핑 웨건 카트",
        url: "https://link.coupang.com/a/example",
        features: ["접이식"],
      },
      client: { schema_version: 1 },
    },
  };
  const res = mockResponse();

  await handler(req, res);

  assert.equal(res.statusCode, 401);
  assert.equal(JSON.parse(res.body).code, "AUTH_REQUIRED");
  assert.deepEqual(calls, ["/user/work/reserve"]);
});

test("releases a reservation returned inside a denied quota payload", async (t) => {
  const originalFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url) => {
    calls.push(new URL(url).pathname);
    if (calls.length === 1) {
      return jsonResponse(200, {
        success: false,
        allowed: false,
        reservation_id: "unexpected-reservation",
        message: "quota response was inconsistent",
      });
    }
    return jsonResponse(200, { success: true, released: true });
  };
  t.after(() => { globalThis.fetch = originalFetch; });

  const req = {
    method: "POST",
    headers: {
      authorization: "Bearer login-token",
      "idempotency-key": "request-inconsistent-quota",
    },
    body: {
      user_id: "user-1",
      product: {
        title: "접이식 캠핑 웨건 카트",
        url: "https://link.coupang.com/a/example",
        features: ["접이식"],
      },
      client: { schema_version: 1 },
    },
  };
  const res = mockResponse();

  await handler(req, res);

  const payload = JSON.parse(res.body);
  assert.equal(res.statusCode, 403);
  assert.equal(payload.code, "SUBSCRIPTION_REQUIRED");
  assert.equal(payload.reservation_release_pending, undefined);
  assert.deepEqual(calls, ["/user/work/reserve", "/user/work/release"]);
});

test("reports reconciliation metadata when denied-payload release fails", async (t) => {
  const originalFetch = globalThis.fetch;
  const originalConsoleError = console.error;
  const calls = [];
  console.error = () => {};
  globalThis.fetch = async (url) => {
    calls.push(new URL(url).pathname);
    if (calls.length === 1) {
      return jsonResponse(200, {
        available: false,
        work_token: "pending-denied-reservation",
      });
    }
    return jsonResponse(503, { success: false });
  };
  t.after(() => {
    globalThis.fetch = originalFetch;
    console.error = originalConsoleError;
  });

  const req = {
    method: "POST",
    headers: {
      authorization: "Bearer login-token",
      "idempotency-key": "request-denied-release-failed",
    },
    body: {
      user_id: "user-1",
      product: {
        title: "접이식 캠핑 웨건 카트",
        url: "https://link.coupang.com/a/example",
        features: ["접이식"],
      },
      client: { schema_version: 1 },
    },
  };
  const res = mockResponse();

  await handler(req, res);

  const payload = JSON.parse(res.body);
  assert.equal(res.statusCode, 403);
  assert.equal(payload.reservation_release_pending, true);
  assert.equal(payload.reservation_id, "pending-denied-reservation");
  assert.equal(payload.ai_job_id, "request-denied-release-failed");
  assert.deepEqual(calls, ["/user/work/reserve", "/user/work/release"]);
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

test("rejects oversized pre-parsed object and string bodies before reservation", async (t) => {
  const originalFetch = globalThis.fetch;
  let fetchCalls = 0;
  globalThis.fetch = async () => {
    fetchCalls += 1;
    throw new Error("must not call dependencies");
  };
  t.after(() => { globalThis.fetch = originalFetch; });

  for (const body of [
    { padding: "x".repeat(32 * 1024) },
    JSON.stringify({ padding: "x".repeat(32 * 1024) }),
  ]) {
    const req = {
      method: "POST",
      headers: { authorization: "Bearer login-token" },
      body,
    };
    const res = mockResponse();
    await handler(req, res);
    assert.equal(res.statusCode, 413);
    assert.equal(JSON.parse(res.body).code, "INVALID_REQUEST");
  }
  assert.equal(fetchCalls, 0);
});

test("rejects oversized streamed bodies by bytes before reservation", async (t) => {
  const originalFetch = globalThis.fetch;
  let fetchCalls = 0;
  globalThis.fetch = async () => {
    fetchCalls += 1;
    throw new Error("must not call dependencies");
  };
  t.after(() => { globalThis.fetch = originalFetch; });

  const req = {
    method: "POST",
    headers: { authorization: "Bearer login-token" },
    async *[Symbol.asyncIterator]() {
      yield Buffer.from(JSON.stringify({ padding: "가".repeat(12_000) }));
    },
  };
  const res = mockResponse();
  await handler(req, res);
  assert.equal(res.statusCode, 413);
  assert.equal(JSON.parse(res.body).code, "INVALID_REQUEST");
  assert.equal(fetchCalls, 0);
});

test("non-success reservation release is reported as reconciliation pending", async (t) => {
  const originalFetch = globalThis.fetch;
  const originalGatewayKey = process.env.AI_GATEWAY_API_KEY;
  const originalConsoleError = console.error;
  const errorEvents = [];
  process.env.AI_GATEWAY_API_KEY = "test-gateway-key";
  console.error = (value) => errorEvents.push(JSON.parse(value));
  t.after(() => {
    globalThis.fetch = originalFetch;
    console.error = originalConsoleError;
    if (originalGatewayKey === undefined) delete process.env.AI_GATEWAY_API_KEY;
    else process.env.AI_GATEWAY_API_KEY = originalGatewayKey;
  });

  const calls = [];
  globalThis.fetch = async (url) => {
    calls.push(new URL(url).pathname);
    if (calls.length === 1) {
      return jsonResponse(200, { success: true, reservation_id: "reserve-release-failed" });
    }
    if (calls.length === 2) {
      return jsonResponse(500, { error: { message: "provider unavailable" } });
    }
    return jsonResponse(503, { success: false });
  };

  const req = {
    method: "POST",
    headers: {
      authorization: "Bearer login-token",
      "idempotency-key": "request-release-failed",
    },
    body: {
      user_id: "user-1",
      product: {
        title: "접이식 캠핑 웨건 카트",
        url: "https://link.coupang.com/a/example",
        features: ["접이식"],
      },
      client: { schema_version: 1 },
    },
  };
  const res = mockResponse();
  await handler(req, res);

  const payload = JSON.parse(res.body);
  assert.equal(res.statusCode, 503);
  assert.equal(payload.reservation_release_pending, true);
  assert.equal(payload.reservation_id, "reserve-release-failed");
  assert.equal(payload.ai_job_id, "request-release-failed");
  assert.deepEqual(calls, [
    "/user/work/reserve",
    "/v1/chat/completions",
    "/user/work/release",
  ]);
  assert.deepEqual(errorEvents, [{
    event: "managed_ai_reservation_release_pending",
    request_id: "request-release-failed",
    release_status: 503,
  }]);
});
