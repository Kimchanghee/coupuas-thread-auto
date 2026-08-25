import assert from "node:assert/strict";
import test from "node:test";
import { handleSurveyDelete, handleSurveyHealth, handleSurveyMirrorRetry, handleSurveyPost, isSecureSurveySecret, MAX_REQUEST_BYTES, readJsonBody, type SurveyMirror, type SurveyServiceDependencies } from "../app/api/reservations/service.ts";
import { MemoryRateLimiter, MemorySurveyStore, resolveRedisRestConfig, UpstashRedis } from "../app/api/reservations/store.ts";
import type { SurveyResponse, SurveySubmission } from "../app/lib/survey.ts";
import { validSubmission } from "./fixtures.ts";

class FakeMirror implements SurveyMirror {
  appended: string[] = [];
  removed: string[] = [];
  rows = new Set<string>();
  appendFailures = 0;
  removeFailures = 0;
  healthCalls = 0;

  async append(response: SurveyResponse) {
    if (this.appendFailures-- > 0) throw new Error("sheet unavailable");
    this.appended.push(response.id);
    this.rows.add(response.id);
  }
  async remove(responseId: string) {
    if (this.removeFailures-- > 0) throw new Error("sheet unavailable");
    this.removed.push(responseId);
    this.rows.delete(responseId);
  }
  async health() { this.healthCalls += 1; return true; }
}

class DeferredAppendMirror extends FakeMirror {
  private releaseAppend!: () => void;
  private markStarted!: () => void;
  readonly appendStarted = new Promise<void>((resolve) => { this.markStarted = resolve; });
  private readonly appendReleased = new Promise<void>((resolve) => { this.releaseAppend = resolve; });

  release() { this.releaseAppend(); }

  override async append(response: SurveyResponse) {
    this.markStarted();
    await this.appendReleased;
    await super.append(response);
  }
}

class CountingStore extends MemorySurveyStore {
  healthCalls = 0;
  override async health() { this.healthCalls += 1; return true; }
}

const SECRET = "s".repeat(32);

function dependencies(overrides: Partial<SurveyServiceDependencies> = {}): SurveyServiceDependencies {
  return {
    store: new MemorySurveyStore(),
    rateLimiter: new MemoryRateLimiter(100, 100),
    mirror: new FakeMirror(),
    hmacSecret: SECRET,
    now: () => new Date("2026-08-26T01:02:03.000Z"),
    logger: { error() {}, warn() {} },
    ...overrides,
  };
}

function jsonRequest(method: "POST" | "PATCH" | "DELETE", value: unknown, ip = "203.0.113.8") {
  return new Request("https://survey.example/api/reservations", {
    method,
    headers: { "content-type": "application/json", "x-forwarded-for": ip },
    body: JSON.stringify(value),
  });
}

async function body(response: Response) {
  return await response.json() as Record<string, unknown>;
}

test("body reader enforces byte limit for declared and streamed bodies", async () => {
  const declared = new Request("https://survey.example", {
    method: "POST",
    headers: { "content-length": String(MAX_REQUEST_BYTES + 1) },
    body: "{}",
  });
  assert.deepEqual(await readJsonBody(declared), { ok: false, status: 413, message: "요청 본문은 32KiB 이하여야 합니다." });

  const streamed = new Request("https://survey.example", { method: "POST", body: JSON.stringify({ value: "가".repeat(MAX_REQUEST_BYTES) }) });
  const streamedResult = await readJsonBody(streamed);
  assert.equal(streamedResult.ok, false);
  if (!streamedResult.ok) assert.equal(streamedResult.status, 413);
});

test("API boundary requires JSON content type", async () => {
  const request = new Request("https://survey.example/api/reservations", {
    method: "POST",
    headers: { "content-type": "text/plain" },
    body: JSON.stringify(validSubmission()),
  });
  assert.equal((await handleSurveyPost(request, dependencies())).status, 415);
});

test("server owns timestamp, score and segment and rejects client analytics", async () => {
  const deps = dependencies();
  const rejected = await handleSurveyPost(jsonRequest("POST", { ...validSubmission(), demandScore: 100 }), deps);
  assert.equal(rejected.status, 400);

  const accepted = await handleSurveyPost(jsonRequest("POST", validSubmission()), deps);
  assert.equal(accepted.status, 201);
  const result = await body(accepted);
  const response = result.response as SurveyResponse;
  assert.equal(response.createdAt, "2026-08-26T01:02:03.000Z");
  assert.equal(response.demandScore, 91);
  assert.equal(response.segment, "우선 상담 고객");
  assert.equal("withdrawalToken" in response, false);
});

test("shared store gives stable-ID idempotency without treating email as exclusive ownership", async () => {
  const store = new MemorySurveyStore();
  const mirror = new FakeMirror();
  const shared = { store, mirror, rateLimiter: new MemoryRateLimiter(100, 100) };
  const firstDeps = dependencies(shared);
  const secondDeps = dependencies(shared);
  const submission = validSubmission();

  const [first, replay] = await Promise.all([
    handleSurveyPost(jsonRequest("POST", submission, "203.0.113.1"), firstDeps),
    handleSurveyPost(jsonRequest("POST", submission, "203.0.113.2"), secondDeps),
  ]);
  assert.deepEqual([first.status, replay.status].sort(), [200, 201]);
  assert.equal(mirror.appended.length, 1);

  const competing: SurveySubmission = {
    ...submission,
    id: "223e4567-e89b-42d3-a456-426614174001",
    email: " PERSON@example.com",
    withdrawalToken: "b".repeat(43),
  };
  const sameEmail = await handleSurveyPost(jsonRequest("POST", competing), firstDeps);
  assert.equal(sameEmail.status, 201);
  assert.equal(mirror.appended.length, 2);

  const stolenId = await handleSurveyPost(jsonRequest("POST", { ...submission, withdrawalToken: "c".repeat(43) }), firstDeps);
  assert.equal(stolenId.status, 409);
});

test("a failed Sheets mirror is retried from canonical storage with credentials only", async () => {
  const mirror = new FakeMirror();
  const logArguments: unknown[][] = [];
  mirror.appendFailures = 1;
  const deps = dependencies({
    mirror,
    logger: {
      error: (...args: unknown[]) => { logArguments.push(args); },
      warn: (...args: unknown[]) => { logArguments.push(args); },
    } as Pick<Console, "error" | "warn">,
  });
  const submission = validSubmission();
  const first = await handleSurveyPost(jsonRequest("POST", submission), deps);
  assert.equal(first.status, 201);
  assert.equal((await body(first)).mirrorStatus, "pending");

  const wrongProof = await handleSurveyMirrorRetry(jsonRequest("PATCH", {
    id: submission.id,
    withdrawalToken: "z".repeat(43),
  }), deps);
  assert.equal(wrongProof.status, 403);

  const replay = await handleSurveyMirrorRetry(jsonRequest("PATCH", {
    id: submission.id,
    withdrawalToken: submission.withdrawalToken,
  }), deps);
  assert.equal(replay.status, 200);
  const replayBody = await body(replay);
  assert.equal(replayBody.mirrorStatus, "mirrored");
  assert.deepEqual(Object.keys(replayBody.response as object).sort(), [
    "createdAt", "id", "surveyVersion",
  ]);
  assert.equal("email" in (replayBody.response as object), false);
  assert.deepEqual(mirror.appended, [submission.id]);
  assert.ok(logArguments.length >= 1);
  assert.equal(logArguments.every((args) => args.length === 1 && typeof args[0] === "string"), true);
});

test("proof-token withdrawal removes the canonical response and its mirror", async () => {
  const mirror = new FakeMirror();
  const deps = dependencies({ mirror });
  const submission = validSubmission();
  assert.equal((await handleSurveyPost(jsonRequest("POST", submission), deps)).status, 201);

  const wrong = await handleSurveyDelete(jsonRequest("DELETE", { id: submission.id, withdrawalToken: "z".repeat(43) }), deps);
  assert.equal(wrong.status, 403);

  mirror.removeFailures = 1;
  const mirrorFailure = await handleSurveyDelete(jsonRequest("DELETE", { id: submission.id, withdrawalToken: submission.withdrawalToken }), deps);
  assert.equal(mirrorFailure.status, 503);

  const deleted = await handleSurveyDelete(jsonRequest("DELETE", { id: submission.id, withdrawalToken: submission.withdrawalToken }), deps);
  assert.equal(deleted.status, 200);
  assert.deepEqual(mirror.removed, [submission.id]);

  const reusedEmail = await handleSurveyPost(jsonRequest("POST", {
    ...submission,
    id: "323e4567-e89b-42d3-a456-426614174002",
    withdrawalToken: "d".repeat(43),
  }), deps);
  assert.equal(reusedEmail.status, 201);
});

test("withdrawal wins a deferred Sheets append race and the late append is compensated", async () => {
  const mirror = new DeferredAppendMirror();
  const deps = dependencies({ mirror });
  const submission = validSubmission();

  const postPromise = handleSurveyPost(jsonRequest("POST", submission), deps);
  await mirror.appendStarted;
  const deleted = await handleSurveyDelete(jsonRequest("DELETE", {
    id: submission.id,
    withdrawalToken: submission.withdrawalToken,
  }), deps);
  assert.equal(deleted.status, 200);
  assert.equal(mirror.rows.has(submission.id), false);

  mirror.release();
  const post = await postPromise;
  assert.equal(post.status, 410);
  assert.equal(mirror.rows.has(submission.id), false);
  assert.deepEqual(mirror.appended, [submission.id]);
  assert.deepEqual(mirror.removed, [submission.id, submission.id]);
});

test("health check rejects unauthenticated requests before external calls and accepts its separate secret", async () => {
  const store = new CountingStore();
  const mirror = new FakeMirror();
  const healthSecret = "h".repeat(32);

  const unauthenticated = await handleSurveyHealth(new Request("https://survey.example/api/reservations"), { store, mirror, healthSecret });
  assert.equal(unauthenticated.status, 404);
  assert.equal(store.healthCalls, 0);
  assert.equal(mirror.healthCalls, 0);

  const authenticated = await handleSurveyHealth(new Request("https://survey.example/api/reservations", {
    headers: { "x-survey-health-check-secret": healthSecret },
  }), { store, mirror, healthSecret });
  assert.equal(authenticated.status, 200);
  assert.equal(store.healthCalls, 1);
  assert.equal(mirror.healthCalls, 1);
  assert.deepEqual(await body(authenticated), {
    ok: true,
    authoritative: "upstash-redis",
    mirror: "reachable",
  });
});

test("shared rate limits fail closed and HMAC configuration is mandatory", async () => {
  const deps = dependencies({ rateLimiter: new MemoryRateLimiter(1, 1) });
  assert.equal((await handleSurveyPost(jsonRequest("POST", validSubmission()), deps)).status, 201);
  assert.equal((await handleSurveyPost(jsonRequest("POST", validSubmission()), deps)).status, 429);
  assert.equal((await handleSurveyPost(jsonRequest("POST", validSubmission()), { ...deps, hmacSecret: "short" })).status, 503);
  assert.equal((await handleSurveyPost(jsonRequest("POST", validSubmission()), { ...deps, hmacSecret: "replace-with-at-least-32-random-characters" })).status, 503);
  assert.equal(isSecureSurveySecret("a".repeat(32), "a".repeat(32)), false);
  assert.equal(isSecureSurveySecret("a".repeat(32), "b".repeat(32)), true);
});

test("Redis env resolver prefers UPSTASH and supports Vercel KV REST aliases", () => {
  assert.deepEqual(resolveRedisRestConfig({
    UPSTASH_REDIS_REST_URL: "https://preferred.upstash.io",
    UPSTASH_REDIS_REST_TOKEN: "preferred-token",
    KV_REST_API_URL: "https://fallback.upstash.io",
    KV_REST_API_TOKEN: "fallback-token",
  }), { url: "https://preferred.upstash.io", token: "preferred-token" });
  assert.deepEqual(resolveRedisRestConfig({
    KV_REST_API_URL: "https://fallback.upstash.io",
    KV_REST_API_TOKEN: "fallback-token",
  }), { url: "https://fallback.upstash.io", token: "fallback-token" });
  assert.throws(() => resolveRedisRestConfig({ UPSTASH_REDIS_REST_URL: "https://partial.upstash.io", KV_REST_API_URL: "https://fallback", KV_REST_API_TOKEN: "token" }));
});

test("Redis REST calls reject embedded credentials, redirects and slow responses", async (t) => {
  assert.throws(() => new UpstashRedis("https://user:pass@example.upstash.io", "token"));
  assert.throws(() => new UpstashRedis("http://example.upstash.io", "token"));

  const originalFetch = globalThis.fetch;
  let redirect = "";
  let sawAbort = false;
  globalThis.fetch = async (_url, options) => {
    redirect = String(options?.redirect ?? "");
    const signal = options?.signal;
    if (!signal) throw new Error("missing abort signal");
    await new Promise<void>((_resolve, reject) => {
      const guard = setTimeout(() => reject(new Error("abort signal did not fire")), 100);
      signal.addEventListener("abort", () => {
        clearTimeout(guard);
        sawAbort = true;
        reject(new Error("request aborted"));
      }, { once: true });
    });
    throw new Error("unreachable");
  };
  t.after(() => { globalThis.fetch = originalFetch; });

  await assert.rejects(
    new UpstashRedis("https://example.upstash.io", "token", 5).command(["PING"]),
    /request aborted/,
  );
  assert.equal(redirect, "error");
  assert.equal(sawAbort, true);
});
