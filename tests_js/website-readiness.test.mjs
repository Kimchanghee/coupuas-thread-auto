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
  for (const label of [
    "쿠팡 파트너스",
    "네이버 쇼핑 커넥트",
    "토스 쇼핑 쉐어링크",
    "오늘의집 큐레이터",
    "무신사 큐레이터",
    "컬리 큐레이터",
    "올리브영 쇼핑 큐레이터",
    "AliExpress",
    "29,000원",
    "69,000원",
  ]) {
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

test("privacy and terms pages include Korean signup-required disclosures", () => {
  const privacy = read("privacy.html");
  const terms = read("terms.html");

  for (const label of [
    "개인정보의 처리 목적",
    "처리하는 개인정보의 항목",
    "개인정보의 처리 및 보유 기간",
    "개인정보 처리의 위탁",
    "개인정보의 파기",
    "정보주체의 권리",
    "개인정보 보호책임자",
    "권익침해 구제방법",
  ]) {
    assert.match(privacy, new RegExp(label));
  }
  assert.match(terms, /회원가입/);
  assert.match(terms, /서비스 이용계약/);
  assert.match(terms, /회원의 의무/);
  assert.match(terms, /계약 해지/);
  assert.match(terms, /게시일: 2026년 8월 8일/);
});
