import assert from "node:assert/strict";
import test from "node:test";

import { buildSitemap } from "../api/sitemap.mjs";

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
