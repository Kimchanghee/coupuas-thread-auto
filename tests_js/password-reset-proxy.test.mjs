import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

import { proxyPasswordReset } from "../api/_lib/password-reset-proxy.mjs";
import {
  createPasswordResetRateLimiter,
  createSupabaseFixedWindowStore,
  createUpstashFixedWindowStore,
  passwordResetRateLimitConfiguration,
} from "../api/_lib/password-reset-rate-limit.mjs";
import {
  createPasswordResetQueueMessage,
  PermanentPasswordResetQueueError,
  passwordResetRetryDirective,
  processPasswordResetQueueMessage,
} from "../api/_lib/password-reset-queue.mjs";

process.env.PASSWORD_RESET_PROXY_SECRET = "test-password-reset-proxy-secret-at-least-32-chars";

const allowRateLimit = async () => ({ allowed: true });

const jsonPost = (body, headers = {}) => ({
  method: "POST",
  headers: { "content-type": "application/json", ...headers },
  body,
});


test("password reset proxy validates methods and request shape", async () => {
  assert.equal((await proxyPasswordReset({ method: "GET" }, "request")).status, 405);
  assert.equal(
    (await proxyPasswordReset(jsonPost({ identifier: "x" }), "request")).status,
    400,
  );
  assert.equal(
    (await proxyPasswordReset(jsonPost({ token: "short", password: "Password1" }), "confirm")).status,
    400,
  );
  assert.equal(
    (await proxyPasswordReset(jsonPost({ identifier: "사용자계정", program_type: "stmaker" }), "request")).status,
    400,
  );
  assert.equal(
    (await proxyPasswordReset({ method: "POST", body: {} }, "request")).status,
    415,
  );
});

test("password reset proxy fails closed without its signing secret", async () => {
  const saved = process.env.PASSWORD_RESET_PROXY_SECRET;
  delete process.env.PASSWORD_RESET_PROXY_SECRET;
  try {
    const result = await proxyPasswordReset(
      jsonPost({ identifier: "user@example.com", program_type: "stmaker" }),
      "request",
    );
    assert.equal(result.status, 503);
  } finally {
    process.env.PASSWORD_RESET_PROXY_SECRET = saved;
  }
});


test("password reset request durably queues only validated data and returns generic response", async () => {
  let queued;
  const result = await proxyPasswordReset(
    jsonPost(
      { identifier: "USER@example.com", program_type: "stmaker", extra: "not-forwarded" },
      { "x-forwarded-for": "203.0.113.7, 10.0.0.1" },
    ),
    "request",
    {
      rateLimitImpl: allowRateLimit,
      enqueueImpl: async (message) => {
        queued = message;
        return { messageId: "msg_test" };
      },
    },
  );
  assert.equal(result.status, 202);
  assert.equal(result.body.success, true);
  assert.match(queued.request_id, /^[a-f0-9-]{36}$/);
  assert.equal(queued.v, 1);
  assert.match(queued.ciphertext, /^[A-Za-z0-9_-]+$/);
  assert.doesNotMatch(JSON.stringify(queued), /user@example\.com|203\.0\.113\.7/);
});


test("private queue consumer signs a fixed auth payload and retries non-success", async () => {
  const requestId = "123e4567-e89b-42d3-a456-426614174000";
  const envelope = createPasswordResetQueueMessage(
    { identifier: "user@example.com", ipAddress: "203.0.113.7" },
    { requestId, randomBytesImpl: () => Buffer.alloc(12, 7) },
  );
  let call;
  await processPasswordResetQueueMessage(envelope, {
    nowImpl: () => 1_700_000_000_000,
    fetchImpl: async (url, options) => {
      call = { url, options };
      return { ok: true, status: 200 };
    },
  });
  assert.match(call.url, /\/user\/password-reset\/process$/);
  assert.equal(call.options.headers["X-Reset-Worker-Timestamp"], "1700000000");
  assert.match(call.options.headers["X-Reset-Worker-Signature"], /^[a-f0-9]{64}$/);
  assert.deepEqual(JSON.parse(call.options.body), {
    request_id: requestId,
    identifier: "user@example.com",
    program_type: "stmaker",
    ip_address: "203.0.113.7",
  });

  await assert.rejects(() =>
    processPasswordResetQueueMessage(envelope, {
      fetchImpl: async () => ({ ok: false, status: 503 }),
    }),
  );
  const tampered = {
    ...envelope,
    ciphertext: `${envelope.ciphertext.slice(0, -1)}${envelope.ciphertext.endsWith("A") ? "B" : "A"}`,
  };
  await assert.rejects(() => processPasswordResetQueueMessage(tampered));
});


test("IPv6 is canonicalized before encryption and worker signing", async () => {
  let envelope;
  const result = await proxyPasswordReset(
    jsonPost(
      { identifier: "reset-user", program_type: "stmaker" },
      { "x-forwarded-for": "2001:0DB8:0000:0000:0000:0000:0000:0001" },
    ),
    "request",
    {
      rateLimitImpl: allowRateLimit,
      enqueueImpl: async (message) => { envelope = message; },
    },
  );
  assert.equal(result.status, 202);
  let body;
  await processPasswordResetQueueMessage(envelope, {
    fetchImpl: async (_url, options) => {
      body = JSON.parse(options.body);
      return { ok: true, status: 200 };
    },
  });
  assert.equal(body.ip_address, "2001:db8::1");
});


test("permanent worker validation errors are acknowledged instead of retried", async () => {
  const envelope = createPasswordResetQueueMessage(
    { identifier: "reset-user", ipAddress: "203.0.113.7" },
    { requestId: "123e4567-e89b-42d3-a456-426614174001" },
  );
  const error = await processPasswordResetQueueMessage(envelope, {
    fetchImpl: async () => ({ ok: false, status: 422 }),
  }).catch((caught) => caught);
  assert.ok(error instanceof PermanentPasswordResetQueueError);
  assert.deepEqual(passwordResetRetryDirective(error, { deliveryCount: 1 }), {
    acknowledge: true,
  });
  assert.deepEqual(passwordResetRetryDirective(new Error("temporary"), { deliveryCount: 2 }), {
    afterSeconds: 20,
  });
});

test("temporary queue delivery is acknowledged after five total attempts", () => {
  const events = [];
  assert.deepEqual(
    passwordResetRetryDirective(
      new Error("temporary"),
      { deliveryCount: 4, messageId: "message-1" },
      { logger: { error: (value) => events.push(JSON.parse(value)) } },
    ),
    { afterSeconds: 80 },
  );
  assert.deepEqual(
    passwordResetRetryDirective(
      new Error("temporary"),
      { deliveryCount: 5, messageId: "message-1" },
      { logger: { error: (value) => events.push(JSON.parse(value)) } },
    ),
    { acknowledge: true },
  );
  assert.deepEqual(events, [{
    event: "password_reset_queue_retry_exhausted",
    delivery_count: 5,
    message_id: "message-1",
    error_type: "Error",
  }]);
});

test("server password policy requires both an ASCII letter and a number", async () => {
  for (const password of ["aaaaaaaa", "12345678", "한글비밀번호1234"]) {
    const result = await proxyPasswordReset(
      jsonPost({ token: "x".repeat(43), password }),
      "confirm",
      { fetchImpl: async () => { throw new Error("must not call upstream"); } },
    );
    assert.equal(result.status, 400);
  }
});

test("rate-limited requests keep the same enumeration-safe accepted response", async () => {
  let enqueueCalls = 0;
  const result = await proxyPasswordReset(
    jsonPost(
      { identifier: "user@example.com", program_type: "stmaker" },
      { "x-forwarded-for": "203.0.113.7" },
    ),
    "request",
    {
      rateLimitImpl: async () => ({ allowed: false, retryAfterSeconds: 600 }),
      enqueueImpl: async () => { enqueueCalls += 1; },
    },
  );
  assert.deepEqual(result, {
    status: 202,
    body: {
      success: true,
      message: "계정이 확인되면 비밀번호 재설정 메일을 보내드립니다.",
    },
  });
  assert.equal(enqueueCalls, 0);
});

test("rate-limit backend failures fail closed before enqueue", async () => {
  let enqueueCalls = 0;
  const result = await proxyPasswordReset(
    jsonPost(
      { identifier: "user@example.com", program_type: "stmaker" },
      { "x-forwarded-for": "203.0.113.7" },
    ),
    "request",
    {
      rateLimitImpl: async () => { throw new Error("redis unavailable"); },
      enqueueImpl: async () => { enqueueCalls += 1; },
    },
  );
  assert.equal(result.status, 503);
  assert.doesNotMatch(JSON.stringify(result), /redis unavailable/);
  assert.equal(enqueueCalls, 0);
});

test("missing durable rate-limit configuration fails closed", async (t) => {
  const names = [
    "UPSTASH_REDIS_REST_URL",
    "UPSTASH_REDIS_REST_TOKEN",
    "KV_REST_API_URL",
    "KV_REST_API_TOKEN",
    "PASSWORD_RESET_SUPABASE_URL",
    "PASSWORD_RESET_SUPABASE_PUBLISHABLE_KEY",
    "PASSWORD_RESET_SUPABASE_RPC_SECRET",
    "PASSWORD_RESET_RATE_LIMIT_HMAC_SECRET",
  ];
  const saved = new Map(names.map((name) => [name, process.env[name]]));
  for (const name of names) delete process.env[name];
  t.after(() => {
    for (const [name, value] of saved) {
      if (value === undefined) delete process.env[name];
      else process.env[name] = value;
    }
  });

  let enqueueCalls = 0;
  const result = await proxyPasswordReset(
    jsonPost(
      { identifier: "user@example.com", program_type: "stmaker" },
      { "x-forwarded-for": "203.0.113.7" },
    ),
    "request",
    { enqueueImpl: async () => { enqueueCalls += 1; } },
  );
  assert.equal(result.status, 503);
  assert.equal(enqueueCalls, 0);
});

test("rate-limit configuration supports Vercel KV aliases with Upstash names preferred", () => {
  const common = {
    PASSWORD_RESET_PROXY_SECRET: "proxy-secret-that-is-at-least-32-characters",
    PASSWORD_RESET_RATE_LIMIT_HMAC_SECRET: "distinct-rate-hmac-secret-at-least-32-characters",
    KV_REST_API_URL: "https://legacy-kv.example.upstash.io",
    KV_REST_API_TOKEN: "legacy-kv-token",
  };
  const fallback = passwordResetRateLimitConfiguration(common);
  assert.equal(fallback.backend, "redis");
  assert.equal(fallback.url, "https://legacy-kv.example.upstash.io/");
  assert.equal(fallback.token, "legacy-kv-token");

  const preferred = passwordResetRateLimitConfiguration({
    ...common,
    UPSTASH_REDIS_REST_URL: "https://preferred.example.upstash.io",
    UPSTASH_REDIS_REST_TOKEN: "preferred-token",
  });
  assert.equal(preferred.url, "https://preferred.example.upstash.io/");
  assert.equal(preferred.token, "preferred-token");
});

test("rate-limit configuration supports the existing Supabase backend", () => {
  const config = passwordResetRateLimitConfiguration({
    PASSWORD_RESET_PROXY_SECRET: "proxy-secret-that-is-at-least-32-characters",
    PASSWORD_RESET_RATE_LIMIT_HMAC_SECRET: "distinct-rate-hmac-secret-at-least-32-characters",
    PASSWORD_RESET_SUPABASE_URL: "https://project-ref.supabase.co",
    PASSWORD_RESET_SUPABASE_PUBLISHABLE_KEY: "sb_publishable_test-value-with-safe-characters",
    PASSWORD_RESET_SUPABASE_RPC_SECRET: "distinct-supabase-rpc-secret-at-least-32-characters",
  });
  assert.equal(config.backend, "supabase");
  assert.equal(config.url, "https://project-ref.supabase.co/");
  assert.equal(config.publishableKey, "sb_publishable_test-value-with-safe-characters");
});

test("Supabase rate-limit configuration rejects unsafe origins and reused secrets", () => {
  const common = {
    PASSWORD_RESET_PROXY_SECRET: "proxy-secret-that-is-at-least-32-characters",
    PASSWORD_RESET_RATE_LIMIT_HMAC_SECRET: "distinct-rate-hmac-secret-at-least-32-characters",
    PASSWORD_RESET_SUPABASE_PUBLISHABLE_KEY: "sb_publishable_test-value-with-safe-characters",
    PASSWORD_RESET_SUPABASE_RPC_SECRET: "distinct-supabase-rpc-secret-at-least-32-characters",
  };

  for (const url of [
    "http://project-ref.supabase.co",
    "https://project-ref.supabase.co/rest/v1",
    "https://user:password@project-ref.supabase.co",
  ]) {
    assert.throws(
      () =>
        passwordResetRateLimitConfiguration({
          ...common,
          PASSWORD_RESET_SUPABASE_URL: url,
        }),
      /must be an HTTPS origin/,
    );
  }

  assert.throws(
    () =>
      passwordResetRateLimitConfiguration({
        ...common,
        PASSWORD_RESET_SUPABASE_URL: "https://project-ref.supabase.co",
        PASSWORD_RESET_SUPABASE_RPC_SECRET: common.PASSWORD_RESET_RATE_LIMIT_HMAC_SECRET,
      }),
    /must be distinct/,
  );
});

test("rate-limit configuration rejects partial or mixed Redis credential pairs", () => {
  const common = {
    PASSWORD_RESET_PROXY_SECRET: "proxy-secret-that-is-at-least-32-characters",
    PASSWORD_RESET_RATE_LIMIT_HMAC_SECRET: "distinct-rate-hmac-secret-at-least-32-characters",
  };
  const fullKv = {
    KV_REST_API_URL: "https://legacy-kv.example.upstash.io",
    KV_REST_API_TOKEN: "legacy-kv-token",
  };
  const partialCases = [
    { ...common, ...fullKv, UPSTASH_REDIS_REST_URL: "https://partial.example.upstash.io" },
    { ...common, ...fullKv, UPSTASH_REDIS_REST_TOKEN: "partial-token" },
    { ...common, KV_REST_API_URL: "https://partial-kv.example.upstash.io" },
    { ...common, KV_REST_API_TOKEN: "partial-kv-token" },
  ];
  for (const env of partialCases) {
    assert.throws(
      () => passwordResetRateLimitConfiguration(env),
      /must be configured together/,
    );
  }

  for (const env of [
    { ...common, PASSWORD_RESET_SUPABASE_URL: "https://project-ref.supabase.co" },
    {
      ...common,
      PASSWORD_RESET_SUPABASE_URL: "https://project-ref.supabase.co",
      PASSWORD_RESET_SUPABASE_PUBLISHABLE_KEY: "sb_publishable_test-value",
    },
  ]) {
    assert.throws(
      () => passwordResetRateLimitConfiguration(env),
      /must be configured together/,
    );
  }
});

test("configured CAPTCHA denial is enumeration-safe and suppresses queueing", async () => {
  let enqueueCalls = 0;
  const result = await proxyPasswordReset(
    jsonPost(
      {
        identifier: "user@example.com",
        program_type: "stmaker",
        captcha_token: "invalid-token",
      },
      { "x-forwarded-for": "203.0.113.7" },
    ),
    "request",
    {
      rateLimitImpl: allowRateLimit,
      captchaImpl: async () => false,
      enqueueImpl: async () => { enqueueCalls += 1; },
    },
  );
  assert.equal(result.status, 202);
  assert.equal(result.body.success, true);
  assert.equal(enqueueCalls, 0);
});

test("shared fixed-window state limits IP and identifier across instances", async () => {
  const counts = new Map();
  const sharedStore = {
    async increment(keys) {
      return keys.map((key) => {
        const next = (counts.get(key) || 0) + 1;
        counts.set(key, next);
        return next;
      });
    },
  };
  const options = {
    store: sharedStore,
    hmacSecret: "test-rate-limit-hmac-secret-at-least-32-characters",
    nowImpl: () => 1_700_000_000_000,
    ipLimit: 2,
    identifierLimit: 2,
  };
  const firstInstance = createPasswordResetRateLimiter(options);
  const secondInstance = createPasswordResetRateLimiter(options);

  assert.equal((await firstInstance({ ipAddress: "203.0.113.7", identifier: "User@example.com" })).allowed, true);
  assert.equal((await secondInstance({ ipAddress: "203.0.113.7", identifier: "user@example.com" })).allowed, true);
  assert.equal((await firstInstance({ ipAddress: "203.0.113.7", identifier: "USER@example.com" })).allowed, false);
  assert.equal([...counts.keys()].some((key) => /203\.0\.113\.7|user@example\.com/i.test(key)), false);
});

test("Upstash rate-limit command is atomic and contains only HMAC-derived keys", async () => {
  let request;
  const store = createUpstashFixedWindowStore({
    url: "https://example.upstash.io",
    token: "test-upstash-token",
    fetchImpl: async (url, options) => {
      request = { url, options };
      return new Response(JSON.stringify({ result: [1, 1] }), { status: 200 });
    },
  });
  const limiter = createPasswordResetRateLimiter({
    store,
    hmacSecret: "test-rate-limit-hmac-secret-at-least-32-characters",
    nowImpl: () => 1_700_000_000_000,
  });
  const outcome = await limiter({
    ipAddress: "203.0.113.7",
    identifier: "user@example.com",
  });

  assert.equal(outcome.allowed, true);
  assert.equal(request.url, "https://example.upstash.io/");
  const command = JSON.parse(request.options.body);
  assert.equal(command[0], "EVAL");
  assert.equal(command[2], 2);
  assert.match(command[3], /^password-reset:v1:ip:[a-f0-9]{64}:/);
  assert.match(command[4], /^password-reset:v1:identifier:[a-f0-9]{64}:/);
  assert.doesNotMatch(request.options.body, /203\.0\.113\.7|user@example\.com/i);
});

test("Supabase rate-limit RPC is atomic and contains only HMAC-derived keys", async () => {
  let request;
  const store = createSupabaseFixedWindowStore({
    url: "https://project-ref.supabase.co",
    publishableKey: "sb_publishable_test-value-with-safe-characters",
    rpcSecret: "test-supabase-rpc-secret-at-least-32-characters",
    fetchImpl: async (url, options) => {
      request = { url, options };
      return new Response(JSON.stringify([{ ip_count: 1, identifier_count: 1 }]), {
        status: 200,
      });
    },
  });
  const limiter = createPasswordResetRateLimiter({
    store,
    hmacSecret: "test-rate-limit-hmac-secret-at-least-32-characters",
    nowImpl: () => 1_700_000_000_000,
  });
  assert.equal(
    (await limiter({ ipAddress: "203.0.113.7", identifier: "user@example.com" })).allowed,
    true,
  );

  assert.equal(
    request.url,
    "https://project-ref.supabase.co/rest/v1/rpc/consume_password_reset_rate_limit",
  );
  assert.equal(request.options.headers.apikey, "sb_publishable_test-value-with-safe-characters");
  const payload = JSON.parse(request.options.body);
  assert.match(payload.p_ip_key, /^password-reset:v1:ip:[a-f0-9]{64}:/);
  assert.match(payload.p_identifier_key, /^password-reset:v1:identifier:[a-f0-9]{64}:/);
  assert.equal(payload.p_ttl_seconds, 605);
  assert.doesNotMatch(request.options.body, /203\.0\.113\.7|user@example\.com/i);
});


test("password reset proxy never reflects upstream secrets or exception text", async () => {
  const upstream = await proxyPasswordReset(
    jsonPost({ token: "x".repeat(43), password: "Password1" }),
    "confirm",
    {
      fetchImpl: async () => ({
        ok: false,
        status: 500,
        async json() {
          return { detail: "DATABASE_URL=secret raw-token=secret" };
        },
      }),
    },
  );
  assert.equal(upstream.status, 503);
  assert.doesNotMatch(JSON.stringify(upstream), /DATABASE_URL|raw-token|secret/);

  const offline = await proxyPasswordReset(
    jsonPost({ token: "x".repeat(43), password: "Password1" }),
    "confirm",
    { fetchImpl: async () => { throw new Error("provider secret"); } },
  );
  assert.equal(offline.status, 503);
  assert.doesNotMatch(JSON.stringify(offline), /provider secret/);
});


test("recovery pages use fragment tokens and avoid browser storage", () => {
  const requestHtml = fs.readFileSync(new URL("../public/forgot-password.html", import.meta.url), "utf8");
  const confirmHtml = fs.readFileSync(new URL("../public/reset-password.html", import.meta.url), "utf8");
  const script = fs.readFileSync(new URL("../public/password-reset.js", import.meta.url), "utf8");
  const config = fs.readFileSync(new URL("../vercel.json", import.meta.url), "utf8");
  assert.match(requestHtml, /아이디 또는 이메일/);
  assert.match(confirmHtml, /autocomplete="new-password"/);
  assert.match(script, /location\.hash/);
  assert.match(script, /history\.replaceState/);
  assert.doesNotMatch(script, /localStorage|sessionStorage/);
  assert.match(config, /forgot-password\|reset-password/);
  assert.match(config, /queue\/v2beta/);
  assert.match(config, /thread-pilot-password-reset/);
});
