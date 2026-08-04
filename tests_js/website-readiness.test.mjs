import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const read = (name) => fs.readFileSync(new URL(`../public/${name}`, import.meta.url), "utf8");

test("landing page publishes search, social, legal, and real purchase guidance", () => {
  const html = read("index.html");
  assert.match(html, /rel="canonical"/);
  assert.match(html, /name="google-site-verification" content="[A-Za-z0-9_-]+"/);
  assert.match(html, /property="og:image"/);
  assert.match(html, /application\/ld\+json/);
  assert.match(html, /앱에서 월간 쇼핑 프로 결제/);
  for (const label of ["네이버쇼핑", "토스쇼핑", "AliExpress", "29,000원", "69,000원"]) {
    assert.match(html, new RegExp(label));
  }
  for (const path of ["/terms", "/privacy", "/refund", "/support"]) {
    assert.match(html, new RegExp(`href="${path}"`));
  }
  assert.doesNotMatch(html, /이용권 문의/);
});

test("legal and discovery files contain launch-critical information", () => {
  for (const name of ["terms.html", "privacy.html", "refund.html", "support.html"]) {
    const html = read(name);
    assert.match(html, /367-07-03291/);
    assert.match(html, /rel="canonical"/);
  }
  assert.match(read("robots.txt"), /Sitemap: https:\/\//);
});
