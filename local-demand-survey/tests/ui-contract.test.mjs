import assert from "node:assert/strict";
import { access } from "node:fs/promises";
import { constants } from "node:fs";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("public UI is truthful and contains no query-string admin or PII export", async () => {
  const layout = await readFile(new URL("../app/layout.tsx", import.meta.url), "utf8");
  const source = await readFile(new URL("../app/DemandSurvey.tsx", import.meta.url), "utf8");
  assert.match(layout, /THREAD AUTO 개인 강의 사전조사/);
  assert.doesNotMatch(layout, /무료 혜택/);
  assert.match(source, /신청 접수 완료/);
  assert.match(source, /무료 이용권 발급이나 구매 계약을 의미하지 않습니다/);
  assert.doesNotMatch(source, /\?admin|exportCsv|exportJson|importJson|JSON\.stringify\(lastResponse\)|관리자 분석/);
  assert.match(source, /navigator\.clipboard\.writeText\(lastResponse\.id\)/);
});

test("choice, progress, range and consent controls expose accessible semantics", async () => {
  const source = await readFile(new URL("../app/DemandSurvey.tsx", import.meta.url), "utf8");
  assert.match(source, /role="radiogroup"/);
  assert.match(source, /type="radio"/);
  assert.match(source, /className="choice-native"/);
  assert.match(source, /aria-pressed=/);
  assert.match(source, /role="progressbar"/);
  assert.match(source, /htmlFor="manual-minutes"/);
  assert.match(source, /htmlFor="privacy-consent"/);
  for (const [id, question] of [["desired-outcome", "20"], ["buy-condition", "21"], ["pain-words", "22"]]) {
    assert.match(source, new RegExp(`id="${id}" aria-labelledby="question-${question}"`));
  }
  assert.doesNotMatch(source, /type="file"/);
});

test("pending mirror UI keeps only minimal persistent state and retries with the credential", async () => {
  const source = await readFile(new URL("../app/DemandSurvey.tsx", import.meta.url), "utf8");
  assert.match(source, /mirrorStatus: body\.mirrorStatus/);
  assert.match(source, /method: "PATCH"/);
  assert.match(source, /body: JSON\.stringify\(credential\)/);
  assert.match(source, /receiptSummary\(body\.response\)/);
  assert.match(source, /form\.privacyConsent\) saveDraft\(sessionStorage/);
  assert.doesNotMatch(source, /saveDraft\(localStorage|submissionFromReceipt/);
  assert.match(source, /분석용 사본 다시 동기화/);
  assert.doesNotMatch(source, /동일 이메일 중복 방지|정규화한 동일 이메일 기준 1회/);
});

test("Next config applies restrictive browser security headers", async () => {
  const { default: nextConfig } = await import(new URL("../next.config.ts", import.meta.url));
  const rules = await nextConfig.headers();
  const headers = Object.fromEntries(rules[0].headers.map(({ key, value }) => [key, value]));
  assert.match(headers["Content-Security-Policy"], /frame-ancestors 'none'/);
  assert.equal(headers["X-Frame-Options"], "DENY");
  assert.equal(headers["X-Content-Type-Options"], "nosniff");
  assert.equal(headers["Referrer-Policy"], "strict-origin-when-cross-origin");
  assert.match(headers["Permissions-Policy"], /camera=\(\).*microphone=\(\).*geolocation=\(\)/);
});

test("example secrets are empty and production rejects placeholders or duplicates", async () => {
  const example = await readFile(new URL("../.env.example", import.meta.url), "utf8");
  const route = await readFile(new URL("../app/api/reservations/route.ts", import.meta.url), "utf8");
  assert.match(example, /^SURVEY_SECURITY_HMAC_SECRET=\s*$/m);
  assert.match(example, /^SURVEY_HEALTH_CHECK_SECRET=\s*$/m);
  assert.doesNotMatch(example, /SURVEY_(?:SECURITY_HMAC|HEALTH_CHECK)_SECRET=replace-with-/);
  assert.match(route, /requiredSecretEnv\("SURVEY_SECURITY_HMAC_SECRET", "SURVEY_HEALTH_CHECK_SECRET"\)/);
  assert.match(route, /requiredSecretEnv\("SURVEY_HEALTH_CHECK_SECRET", "SURVEY_SECURITY_HMAC_SECRET"\)/);
});

test("Vercel-only project has no hidden Vinext, Cloudflare or D1 scaffold", async () => {
  const removed = [
    "../vite.config.ts", "../drizzle.config.ts", "../worker/index.ts", "../db/index.ts",
    "../build/sites-vite-plugin.ts", "../app/chatgpt-auth.ts", "../.openai/hosting.json",
  ];
  for (const relative of removed) {
    await assert.rejects(access(new URL(relative, import.meta.url), constants.F_OK));
  }
  const tsconfig = await readFile(new URL("../tsconfig.json", import.meta.url), "utf8");
  assert.doesNotMatch(tsconfig, /"worker"|"db"|"drizzle"|"vite\.config\.ts"/);
});

test("Windows launcher uses Next.js lockfile install and real build artifact", async () => {
  const launcher = await readFile(new URL("../로컬_설문_실행.bat", import.meta.url), "utf8");
  assert.match(launcher, /node_modules\\\.bin\\next\.cmd/);
  assert.match(launcher, /npm ci/);
  assert.match(launcher, /\.next\\BUILD_ID/);
  assert.doesNotMatch(launcher, /vinext|dist\\server/i);
});
