import assert from "node:assert/strict";
import test from "node:test";
import { initializePasswordReset } from "../public/password-reset-controller.mjs";
import { proxyPasswordReset } from "../api/_lib/password-reset-proxy.mjs";
import { consumePasswordResetRateLimit, isPasswordResetProtectionConfigured } from "../api/_lib/password-reset-rate-limit.mjs";
process.env.PASSWORD_RESET_PROXY_SECRET = "offline-proxy-test-secret-at-least-32-characters";
const request = body => ({method:"POST", headers:{"content-type":"application/json","x-forwarded-for":"203.0.113.1"}, body});
const validBody = {identifier:"test@example.test",program_type:"stmaker"};

test("blocked source never consumes another account delivery quota", async () => {
  let deliveries = 0, queued = 0;
  const result = await proxyPasswordReset(request(validBody), "request", {
    rateLimitImpl: async ({ phase }) => {
      if (phase === "admission") return { allowed: false };
      deliveries++;
      return { allowed: true };
    },
    enqueueImpl: async () => { queued++; },
  });
  assert.equal(result.status, 202);
  assert.equal(deliveries, 0);
  assert.equal(queued, 0);
});

test("confirm is limited before upstream even for changing valid-shaped tokens", async () => {
  let attempts=0, upstream=0;
  for(let i=0;i<12;i++) {
    const result=await proxyPasswordReset(request({token:String(i).padStart(43,"a"),password:"Correct Horse Battery 72"}),"confirm",{
      rateLimitImpl:async({phase})=>{assert.equal(phase,"confirm"); return {allowed:++attempts<=3};},
      fetchImpl:async()=>{upstream++;return new Response('{}',{status:400});},
    });
    assert.equal(result.status,i<3?400:429);
  }
  assert.equal(upstream,3);
});

test("confirm fails closed for missing IP or unavailable shared limiter", async () => {
  const body={token:"a".repeat(43),password:"Correct Horse Battery 72"};
  for(const req of [request(body),{...request(body),headers:{"content-type":"application/json"}}]) {
    let upstream=0;
    const result=await proxyPasswordReset(req,"confirm",{rateLimitImpl:async()=>{throw Error("offline")},fetchImpl:async()=>{upstream++;}});
    assert.equal(result.status,503); assert.equal(upstream,0);
  }
});

const env = {
  PASSWORD_RESET_PROXY_SECRET: "p".repeat(32),
  PASSWORD_RESET_RATE_LIMIT_HMAC_SECRET: "h".repeat(32),
  UPSTASH_REDIS_REST_URL: "https://example.upstash.io",
  UPSTASH_REDIS_REST_TOKEN: "test-token",
};

test("protection requires shared storage and signing, without external CAPTCHA keys", () => {
  assert.equal(isPasswordResetProtectionConfigured(env), true);
  assert.equal(isPasswordResetProtectionConfigured({}), false);
  assert.equal(isPasswordResetProtectionConfigured({ ...env, UPSTASH_REDIS_REST_TOKEN: "" }), false);
});

test("global cap is shared across IPs and concurrent serverless instances", async () => {
  const counts = new Map();
  const fetchImpl = async (_url, options) => {
    const command = JSON.parse(options.body);
    const keys = command.slice(3, 5);
    const result = keys.map(key => {
      const count = (counts.get(key) || 0) + 1;
      counts.set(key, count);
      return count;
    });
    return new Response(JSON.stringify({ result }));
  };
  const results = await Promise.all(Array.from({ length: 150 }, (_, i) =>
    consumePasswordResetRateLimit({ phase: "global", ipAddress: `203.0.113.${i}` }, {
      env, fetchImpl, nowImpl: () => 1_700_000_000_000,
    })));
  assert.equal(results.filter(result => result.allowed).length, 120);
  assert.equal(counts.size, 2);
});

test("delivery and global store outages prevent queueing", async () => {
  for (const failingPhase of ["delivery", "global"]) {
    let queued = 0;
    const result = await proxyPasswordReset(request(validBody), "request", {
      rateLimitImpl: async ({ phase }) => {
        if (phase === failingPhase) throw Error("offline");
        return { allowed: true };
      },
      enqueueImpl: async () => { queued++; },
    });
    assert.equal(result.status, 503);
    assert.equal(queued, 0);
  }
});

test("cross-site browser requests are rejected before consuming quotas", async () => {
  let calls = 0;
  for (const site of ["cross-site", "same-site"]) {
    const req = request(validBody);
    req.headers["sec-fetch-site"] = site;
    const result = await proxyPasswordReset(req, "request", {
      rateLimitImpl: async () => { calls++; return { allowed: true }; },
    });
    assert.equal(result.status, 403);
  }
  assert.equal(calls, 0);
});

test("recovery browser submits without third-party scripts and permits retry", async () => {
  let submit, submitted;
  const button = { disabled: false };
  const elements = {
    "#submit-button": button, "#status": { dataset: {} },
    "#identifier": { value: "test@example.test" },
    "#recovery-form": { reportValidity: () => true, addEventListener: (_, cb) => { submit = cb; } },
  };
  initializePasswordReset({
    window: {},
    document: { body: { dataset: { recoveryPage: "request" } }, querySelector: key => elements[key] },
    fetch: async (url, options) => {
      assert.equal(url, "/api/password-reset/request");
      submitted = JSON.parse(options.body);
      return { ok: false, status: 503, json: async () => ({ message: "temporary" }) };
    },
  });
  assert.equal(button.disabled, false);
  await submit({ preventDefault() {} });
  assert.deepEqual(submitted, validBody);
  assert.equal(button.disabled, false);
});
