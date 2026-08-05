import assert from "node:assert/strict";
import test from "node:test";

import { combineNoticePayload, githubRequestConfig } from "../api/notices.mjs";

const owner = { id: 9594198, login: "Kimchanghee" };

test("GitHub notice requests use the WHATWG URL API", () => {
  const { url, options } = githubRequestConfig("/releases?per_page=100");
  assert.ok(url instanceof URL);
  assert.equal(url.protocol, "https:");
  assert.equal(url.hostname, "api.github.com");
  assert.equal(url.pathname, "/repos/Kimchanghee/coupuas-thread-auto/releases");
  assert.equal(options.method, "GET");
});

test("release notices expose the installer and ignore unpublished builds", () => {
  const payload = combineNoticePayload(
    [
      {
        id: 54,
        tag_name: "v3.0.54",
        name: "Thread Auto v3.0.54",
        body: "## 주요 변경 사항\n- 공지사항을 추가했습니다.",
        published_at: "2026-08-02T00:00:00Z",
        html_url: "https://github.com/Kimchanghee/coupuas-thread-auto/releases/tag/v3.0.54",
        assets: [
          {
            name: "CoupangThreadAutoSetup.exe",
            browser_download_url: "https://github.com/example/setup.exe",
          },
          {
            name: "CoupangThreadAutoSetup.exe.sha256",
            browser_download_url: "https://github.com/example/setup.exe.sha256",
          },
        ],
      },
      { id: 55, tag_name: "v3.0.55", draft: true },
    ],
    [],
  );

  assert.equal(payload.posts.length, 1);
  assert.equal(payload.latest.version, "3.0.54");
  assert.equal(payload.latest.downloadUrl, "https://github.com/example/setup.exe");
  assert.equal(
    payload.latestDownloadUrl,
    "https://github.com/Kimchanghee/coupuas-thread-auto/releases/latest/download/CoupangThreadAutoSetup.exe",
  );
  assert.match(payload.latest.body, /공지사항/);
  assert.equal(payload.latest.summary, "공지사항을 추가했습니다.");
});

test("only owner-authored event issues are published", () => {
  const eventBody = [
    "### 한 줄 소개",
    "첫 달 할인 이벤트",
    "### 시작일",
    "2026-08-02",
    "### 종료일",
    "2026-08-31",
    "### 상세 내용",
    "월간 이용권 할인",
    "### 참여 링크",
    "https://example.com/join",
    "### 버튼 문구",
    "할인 받기",
  ].join("\n");
  const payload = combineNoticePayload([], [
    {
      number: 1,
      title: "[EVENT] 여름 할인",
      body: eventBody,
      user: owner,
      labels: [{ name: "event" }, { name: "pinned" }],
      created_at: "2026-08-02T00:00:00Z",
    },
    {
      number: 2,
      title: "[EVENT] 위조 글",
      body: eventBody,
      user: { id: 123, login: "attacker" },
      labels: [{ name: "event" }],
    },
  ]);

  assert.equal(payload.posts.length, 1);
  assert.equal(payload.posts[0].title, "여름 할인");
  assert.equal(payload.posts[0].summary, "첫 달 할인 이벤트");
  assert.equal(payload.posts[0].ctaUrl, "https://example.com/join");
  assert.equal(payload.posts[0].pinned, true);
});

test("event CTA rejects non-HTTPS links", () => {
  const payload = combineNoticePayload([], [
    {
      number: 3,
      title: "[EVENT] 안전 링크 검사",
      body: "### 한 줄 소개\n검사\n### 참여 링크\njavascript:alert(1)",
      user: owner,
      labels: [{ name: "event" }],
    },
  ]);
  assert.equal(payload.posts[0].ctaUrl, null);
});

test("event authorization requires the immutable owner id", () => {
  const payload = combineNoticePayload([], [
    {
      number: 4,
      title: "[EVENT] login spoof",
      body: "### 한 줄 소개\n노출되면 안 됩니다.",
      user: { id: 123, login: "Kimchanghee" },
      labels: [{ name: "event" }],
    },
  ]);
  assert.equal(payload.posts.length, 0);
});
