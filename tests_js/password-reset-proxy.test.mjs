import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

import { proxyPasswordReset } from "../api/_lib/password-reset-proxy.mjs";
import {
  createPasswordResetQueueMessage,
  PermanentPasswordResetQueueError,
  passwordResetRetryDirective,
  processPasswordResetQueueMessage,
} from "../api/_lib/password-reset-queue.mjs";

process.env.PASSWORD_RESET_PROXY_SECRET = "test-password-reset-proxy-secret-at-least-32-chars";

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
    { enqueueImpl: async (message) => { envelope = message; } },
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
