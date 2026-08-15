import { request as httpsRequest } from "node:https";

const GITHUB_OWNER = "Kimchanghee";
const GITHUB_OWNER_ID = 9594198;
const GITHUB_REPO = "coupuas-thread-auto";
const API_ROOT = `https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}`;
const LATEST_INSTALLER_URL = `https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}/releases/latest/download/CoupangThreadAutoSetup.exe`;
const CACHE_TTL_MS = 5 * 60 * 1000;
const GENERIC_RELEASE_SUMMARY = "각종 오류와 안정성 문제를 개선했습니다.";

let cachedPayload = null;
let cachedAt = 0;
let cachedReleases = [];
let cachedIssues = [];
let inFlightPayload = null;

function text(value) {
  return String(value ?? "").trim();
}

function firstUsefulLine(body, title = "") {
  const normalizedTitle = text(title).toLocaleLowerCase();
  const lines = text(body)
    .split(/\r?\n/)
    .map((raw) => ({
      heading: /^#{1,6}\s+/.test(raw.trim()),
      value: raw.replace(/^#{1,6}\s+/, "").replace(/^[-*]\s+/, "").trim(),
    }))
    .filter(({ value }) => value && !value.startsWith("<!--"));
  const useful = lines.find(({ heading, value }) => {
    const normalized = value.toLocaleLowerCase();
    return !heading && normalized !== normalizedTitle &&
      normalized !== "이번 버전에 포함된 주요 변경 사항입니다.";
  });
  return useful?.value || lines[0]?.value || "자세한 내용을 확인해 주세요.";
}

function legacyReleaseSummary(source) {
  const textValue = text(source).toLocaleLowerCase();
  const namedChanges = [
    ["seven korean partner channels", "이용할 수 있는 국내 쇼핑 제휴 채널을 일곱 곳으로 늘렸습니다."],
    ["signup consent", "회원가입 과정에서 필수 동의 내용이 빠지지 않도록 개선했습니다."],
    ["console flashes", "로그인할 때 불필요한 검은 창이 나타나던 문제를 개선했습니다."],
    ["login and installer naming", "로그인 화면과 설치 파일의 이름을 같게 맞췄습니다."],
    ["responsive settings", "화면 크기에 맞춰 설정 화면을 더 편하게 볼 수 있도록 개선했습니다."],
    ["major changes for every github release", "새 버전의 주요 변경 내용을 공지에서 확인할 수 있도록 개선했습니다."],
  ];
  return namedChanges.find(([needle]) => textValue.includes(needle))?.[1] || GENERIC_RELEASE_SUMMARY;
}

function releaseCopyNeedsSimplifying(source, summary) {
  if (!/[가-힣]/.test(text(summary))) return true;
  return /(?:src\/|tests?\/|pytest|pip-audit|compileall|makeappx|authenticode|oidc|msix|api gateway|\.py\b|\.mjs\b|\\n)/i.test(
    text(source),
  );
}

function simpleReleaseBody(version, summary) {
  return [
    `# Thread Auto v${version}`,
    "",
    "## 이번 버전에서 달라진 점",
    "",
    `- ${summary}`,
    "",
    "## 설치 안내",
    "",
    "- 아래 설치 파일을 받아 실행해 주세요.",
    "- 사용하던 설정과 남은 작업은 그대로 유지됩니다.",
  ].join("\n");
}

function findAsset(assets, name) {
  const wanted = text(name).toLowerCase();
  return (Array.isArray(assets) ? assets : []).find(
    (asset) => text(asset?.name).toLowerCase() === wanted,
  );
}

function extractSection(body, headings) {
  const source = text(body);
  if (!source) return "";
  const names = headings.map((heading) => heading.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const pattern = new RegExp(
    `(?:^|\\n)#{2,4}\\s*(?:${names.join("|")})\\s*\\n([\\s\\S]*?)(?=\\n#{2,4}\\s|$)`,
    "i",
  );
  return text(source.match(pattern)?.[1]);
}

function releaseToPost(release) {
  const assets = Array.isArray(release?.assets) ? release.assets : [];
  const installer = findAsset(assets, "CoupangThreadAutoSetup.exe");
  const checksum = findAsset(assets, "CoupangThreadAutoSetup.exe.sha256");
  const version = text(release?.tag_name).replace(/^v/i, "");
  const originalBody = text(release?.body) || `${version} 버전이 공개되었습니다.`;
  const originalSummary = firstUsefulLine(originalBody, text(release?.name));
  const simplifyCopy = releaseCopyNeedsSimplifying(originalBody, originalSummary);
  const summary = simplifyCopy ? legacyReleaseSummary(originalBody) : originalSummary;
  const body = simplifyCopy ? simpleReleaseBody(version, summary) : originalBody;
  return {
    id: `release-${release.id}`,
    kind: "release",
    badge: "업데이트",
    title: text(release?.name) || `Thread Auto v${version}`,
    summary,
    body,
    version,
    publishedAt: release?.published_at || release?.created_at || null,
    sourceUrl: release?.html_url || null,
    downloadUrl:
      installer?.browser_download_url ||
      LATEST_INSTALLER_URL,
    checksumUrl: checksum?.browser_download_url || null,
    pinned: false,
  };
}

function eventDate(value, endOfDay = false) {
  const normalized = text(value);
  if (/^\d{4}-\d{2}-\d{2}$/.test(normalized)) {
    return Date.parse(`${normalized}T${endOfDay ? "23:59:59.999" : "00:00:00"}+09:00`);
  }
  return Date.parse(normalized);
}

function eventStatus(startsAt, endsAt) {
  const now = Date.now();
  const start = eventDate(startsAt);
  const end = eventDate(endsAt, true);
  if (Number.isFinite(end) && end < now) return "종료";
  if (Number.isFinite(start) && start > now) return "예정";
  return "진행 중";
}

function issueToPost(issue) {
  const body = text(issue?.body);
  const startsAt = extractSection(body, ["시작일", "이벤트 시작일", "시작"]);
  const endsAt = extractSection(body, ["종료일", "이벤트 종료일", "종료"]);
  const ctaUrl = extractSection(body, ["참여 링크", "버튼 링크", "CTA 링크"]);
  const ctaLabel = extractSection(body, ["버튼 문구", "CTA 문구"]) || "이벤트 참여하기";
  return {
    id: `event-${issue.number}`,
    kind: "event",
    badge: "이벤트",
    title: text(issue?.title).replace(/^\[EVENT\]\s*/i, "") || "Thread Auto 이벤트",
    summary: extractSection(body, ["한 줄 소개", "요약"]) || firstUsefulLine(body),
    body,
    publishedAt: issue?.created_at || null,
    updatedAt: issue?.updated_at || null,
    sourceUrl: issue?.html_url || null,
    startsAt: startsAt || null,
    endsAt: endsAt || null,
    eventStatus: eventStatus(startsAt, endsAt),
    ctaUrl: /^https:\/\//i.test(ctaUrl) ? ctaUrl : null,
    ctaLabel,
    pinned: (issue?.labels || []).some((label) => text(label?.name).toLowerCase() === "pinned"),
  };
}

export function githubRequestConfig(path) {
  const token = text(process.env.GITHUB_TOKEN || process.env.GITHUB_READ_TOKEN);
  const headers = {
    Accept: "application/vnd.github+json",
    "User-Agent": "Thread-Auto-Website",
    "X-GitHub-Api-Version": "2022-11-28",
  };
  if (token) headers.Authorization = `Bearer ${token}`;
  return {
    url: new URL(`${API_ROOT}${path}`),
    options: { method: "GET", headers },
  };
}

async function githubJson(path) {
  const { url, options } = githubRequestConfig(path);
  return new Promise((resolve, reject) => {
    const request = httpsRequest(url, options, (response) => {
      const chunks = [];
      let receivedBytes = 0;
      response.on("data", (chunk) => {
        receivedBytes += chunk.length;
        if (receivedBytes > 8 * 1024 * 1024) {
          request.destroy(new Error("GitHub API response too large"));
          return;
        }
        chunks.push(chunk);
      });
      response.on("end", () => {
        const status = Number(response.statusCode || 0);
        if (status < 200 || status >= 300) {
          reject(new Error(`GitHub API ${status}`));
          return;
        }
        try {
          resolve(JSON.parse(Buffer.concat(chunks).toString("utf8")));
        } catch {
          reject(new Error("GitHub API returned invalid JSON"));
        }
      });
      response.on("error", reject);
    });
    request.setTimeout(12_000, () => request.destroy(new Error("GitHub API timeout")));
    request.on("error", reject);
    request.end();
  });
}

export function combineNoticePayload(releases, issues) {
  const releasePosts = (Array.isArray(releases) ? releases : [])
    .filter((release) => !release?.draft && !release?.prerelease)
    .map(releaseToPost);
  const eventPosts = (Array.isArray(issues) ? issues : [])
    .filter((issue) => {
      if (issue?.pull_request) return false;
      const ownerMatch = Number(issue?.user?.id) === GITHUB_OWNER_ID;
      const eventLabel = (issue?.labels || []).some((label) => text(label?.name).toLowerCase() === "event");
      return ownerMatch && eventLabel;
    })
    .map(issueToPost);

  const posts = [...releasePosts, ...eventPosts].sort((a, b) => {
    if (Boolean(a.pinned) !== Boolean(b.pinned)) return a.pinned ? -1 : 1;
    return Date.parse(b.publishedAt || 0) - Date.parse(a.publishedAt || 0);
  });
  return {
    latest: releasePosts[0] || null,
    latestDownloadUrl: LATEST_INSTALLER_URL,
    posts,
    eventAuthorUrl: `https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}/issues/new?template=event-post.yml`,
    generatedAt: new Date().toISOString(),
  };
}

export async function loadNoticePayload() {
  if (cachedPayload && Date.now() - cachedAt < CACHE_TTL_MS) return cachedPayload;
  if (inFlightPayload) return inFlightPayload;
  inFlightPayload = (async () => {
    const [releaseResult, issueResult] = await Promise.allSettled([
      githubJson("/releases?per_page=100"),
      githubJson("/issues?state=all&labels=event&per_page=100&sort=created&direction=desc"),
    ]);
    if (releaseResult.status === "fulfilled") cachedReleases = releaseResult.value;
    if (issueResult.status === "fulfilled") cachedIssues = issueResult.value;
    if (!cachedReleases.length) throw releaseResult.reason || new Error("No releases available");
    cachedPayload = combineNoticePayload(cachedReleases, cachedIssues);
    cachedAt = Date.now();
    return cachedPayload;
  })();
  try {
    return await inFlightPayload;
  } finally {
    inFlightPayload = null;
  }
}

export default async function handler(req, res) {
  if (req.method !== "GET") {
    res.setHeader("Allow", "GET");
    return res.status(405).json({ error: "Method not allowed" });
  }
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.setHeader("X-Content-Type-Options", "nosniff");
  try {
    const payload = await loadNoticePayload();
    const requestedId = text(req.query?.id);
    res.setHeader("Cache-Control", "public, s-maxage=300, stale-while-revalidate=3600");
    if (requestedId) {
      const post = payload.posts.find((item) => item.id === requestedId);
      if (!post) return res.status(404).json({ error: "Post not found" });
      return res.status(200).json({
        post,
        latest: payload.latest,
        latestDownloadUrl: payload.latestDownloadUrl,
      });
    }
    return res.status(200).json(payload);
  } catch (error) {
    return res.status(502).json({ error: "공지사항을 불러오지 못했습니다." });
  }
}
