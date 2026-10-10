import assert from "node:assert/strict";
import test from "node:test";

import { buildSitemap, getSiteUrl } from "../api/sitemap.mjs";

test("sitemap includes core pages and safely encoded notice URLs", () => {
  const xml = buildSitemap([
    {
      id: "release-123&unsafe",
      kind: "release",
      publishedAt: "2026-08-02T00:00:00Z",
    },
  ], "https://example.com");

  assert.match(xml, /<loc>https:\/\/example\.com\/<\/loc>/);
  assert.match(xml, /<loc>https:\/\/example\.com\/privacy<\/loc>/);
  assert.match(xml, /notices\?id=release-123%26unsafe/);
  assert.doesNotMatch(xml, /<loc>[^<]*&[^a]/);
});

test("sitemap uses the production domain and a deployment URL for previews", () => {
  assert.equal(
    getSiteUrl({ VERCEL_ENV: "production", PUBLIC_SITE_URL: "https://old-preview.vercel.app" }),
    "https://coupasthreadauto.me",
  );
  assert.equal(
    getSiteUrl({ VERCEL_ENV: "preview", VERCEL_URL: "branch-preview.vercel.app", PUBLIC_SITE_URL: "https://old-preview.vercel.app" }),
    "https://branch-preview.vercel.app",
  );
  assert.ok(buildSitemap().includes("<loc>https://coupasthreadauto.me/</loc>"));
});
