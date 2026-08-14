function requestHeader(req, name) {
  const headers = req?.headers;
  if (!headers) return "";
  if (typeof headers.get === "function") {
    return String(headers.get(name) || "").trim();
  }
  const value = headers[String(name).toLowerCase()];
  return String(Array.isArray(value) ? value[0] || "" : value || "").trim();
}

export function gatewayToken(req, env = process.env) {
  return (
    String(env.AI_GATEWAY_API_KEY || "").trim() ||
    requestHeader(req, "x-vercel-oidc-token") ||
    String(env.VERCEL_OIDC_TOKEN || "").trim()
  );
}

export function hasGatewayCredentials(req, env = process.env) {
  return Boolean(gatewayToken(req, env));
}
