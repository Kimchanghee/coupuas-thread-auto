export default function handler(_req, res) {
  res.statusCode = 200;
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.setHeader("Cache-Control", "no-store");
  res.end(
    JSON.stringify({
      ok: true,
      service: "coupuas-thread-managed-ai",
      gatewayConfigured: Boolean(
        process.env.AI_GATEWAY_API_KEY || process.env.VERCEL_OIDC_TOKEN,
      ),
    }),
  );
}
