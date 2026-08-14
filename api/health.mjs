import { hasGatewayCredentials } from "./_lib/gateway-auth.mjs";

export default function handler(req, res) {
  res.statusCode = 200;
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.setHeader("Cache-Control", "no-store");
  res.end(
    JSON.stringify({
      ok: true,
      service: "coupuas-thread-managed-ai",
      gatewayConfigured: hasGatewayCredentials(req),
    }),
  );
}
