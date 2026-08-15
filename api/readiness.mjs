import { hasGatewayCredentials } from "./_lib/gateway-auth.mjs";
import { loadNoticePayload } from "./notices.mjs";

const AUTH_HEALTH_URL = "https://newshopping-shorts-auth.vercel.app/health";

export async function readinessPayload(
  req,
  { fetchImpl = globalThis.fetch, noticesLoader = loadNoticePayload } = {},
) {
  const [authResult, noticeResult] = await Promise.allSettled([
    fetchImpl(AUTH_HEALTH_URL, {
      headers: { Accept: "application/json" },
      signal: AbortSignal.timeout(5_000),
    }),
    noticesLoader(),
  ]);

  let authServiceReady = false;
  if (authResult.status === "fulfilled" && authResult.value?.ok) {
    try {
      const payload = await authResult.value.json();
      authServiceReady = payload?.status === "healthy" || payload?.status === "ok";
    } catch {
      authServiceReady = false;
    }
  }

  const notices = noticeResult.status === "fulfilled" ? noticeResult.value : {};
  const latest = notices?.latest || {};
  const releaseReady = Boolean(
    latest.version && latest.downloadUrl && latest.checksumUrl,
  );
  const gatewayConfigured = hasGatewayCredentials(req);
  const ok = gatewayConfigured && authServiceReady && releaseReady;

  return {
    ok,
    service: "coupuas-thread-production-readiness",
    gatewayConfigured,
    authServiceReady,
    releaseReady,
    latestVersion: latest.version ? `v${latest.version}` : null,
  };
}

export default async function handler(req, res) {
  if (req.method && req.method !== "GET") {
    res.statusCode = 405;
    res.setHeader("Allow", "GET");
    res.end(JSON.stringify({ ok: false, code: "METHOD_NOT_ALLOWED" }));
    return;
  }

  const payload = await readinessPayload(req);
  res.statusCode = payload.ok ? 200 : 503;
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.setHeader("Cache-Control", "no-store");
  res.end(JSON.stringify(payload));
}
