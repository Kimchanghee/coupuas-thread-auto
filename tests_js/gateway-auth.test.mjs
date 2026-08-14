import assert from "node:assert/strict";
import test from "node:test";

import {
  gatewayToken,
  hasGatewayCredentials,
} from "../api/_lib/gateway-auth.mjs";

test("uses the Vercel function OIDC request header", () => {
  const req = { headers: { "x-vercel-oidc-token": "oidc-token" } };
  assert.equal(gatewayToken(req, {}), "oidc-token");
  assert.equal(hasGatewayCredentials(req, {}), true);
});

test("prefers a configured static gateway key", () => {
  const req = { headers: { "x-vercel-oidc-token": "oidc-token" } };
  assert.equal(
    gatewayToken(req, { AI_GATEWAY_API_KEY: "static-key" }),
    "static-key",
  );
});

test("supports Headers and local OIDC environment fallback", () => {
  assert.equal(
    gatewayToken({ headers: new Headers() }, { VERCEL_OIDC_TOKEN: "local-token" }),
    "local-token",
  );
});

test("reports missing credentials", () => {
  assert.equal(gatewayToken({ headers: {} }, {}), "");
  assert.equal(hasGatewayCredentials({ headers: {} }, {}), false);
});
