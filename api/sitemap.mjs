import { loadNoticePayload } from "./notices.mjs";

const DEFAULT_SITE_URL = "https://coupuas-thread-auto-three.vercel.app";
const CORE_PATHS = ["/", "/notices", "/terms", "/privacy", "/refund", "/support"];

function escapeXml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");
}

function siteUrl() {
  const configured = String(process.env.PUBLIC_SITE_URL || DEFAULT_SITE_URL).trim();
  try {
    const parsed = new URL(configured);
    if (parsed.protocol !== "https:") return DEFAULT_SITE_URL;
    return parsed.origin;
  } catch {
    return DEFAULT_SITE_URL;
  }
}

export function buildSitemap(posts = [], origin = DEFAULT_SITE_URL) {
  const now = new Date().toISOString().slice(0, 10);
  const urls = CORE_PATHS.map((path) => ({
    loc: `${origin}${path}`,
    lastmod: now,
    priority: path === "/" ? "1.0" : path === "/notices" ? "0.9" : "0.5",
  }));
  for (const post of Array.isArray(posts) ? posts : []) {
    if (!post?.id) continue;
    const published = new Date(post.updatedAt || post.publishedAt || Date.now());
    urls.push({
      loc: `${origin}/notices?id=${encodeURIComponent(post.id)}`,
      lastmod: Number.isNaN(published.getTime()) ? now : published.toISOString().slice(0, 10),
      priority: post.kind === "event" ? "0.7" : "0.8",
    });
  }
  const body = urls.map(({ loc, lastmod, priority }) => [
    "  <url>",
    `    <loc>${escapeXml(loc)}</loc>`,
    `    <lastmod>${lastmod}</lastmod>`,
    `    <priority>${priority}</priority>`,
    "  </url>",
  ].join("\n")).join("\n");
  return `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${body}\n</urlset>\n`;
}

export default async function handler(req, res) {
  if (req.method !== "GET") {
    res.setHeader("Allow", "GET");
    res.statusCode = 405;
    res.end("Method not allowed");
    return;
  }
  let posts = [];
  try {
    posts = (await loadNoticePayload()).posts || [];
  } catch {
    // Core crawlable pages remain discoverable if GitHub is temporarily unavailable.
  }
  res.statusCode = 200;
  res.setHeader("Content-Type", "application/xml; charset=utf-8");
  res.setHeader("Cache-Control", "public, s-maxage=900, stale-while-revalidate=86400");
  res.setHeader("X-Content-Type-Options", "nosniff");
  res.end(buildSitemap(posts, siteUrl()));
}
