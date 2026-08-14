import assert from "node:assert/strict";
import test from "node:test";

import handler from "../api/health.mjs";

function mockResponse() {
  return {
    statusCode: 0,
    body: "",
    setHeader() {},
    end(value = "") {
      this.body = String(value);
    },
  };
}

test("health detects the Vercel OIDC request header", () => {
  const res = mockResponse();
  handler({ headers: { "x-vercel-oidc-token": "oidc-token" } }, res);
  assert.equal(res.statusCode, 200);
  assert.equal(JSON.parse(res.body).gatewayConfigured, true);
});
