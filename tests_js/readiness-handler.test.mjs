import assert from "node:assert/strict";
import test from "node:test";

import { readinessPayload } from "../api/readiness.mjs";

const readyNotices = async () => ({
  latest: {
    version: "3.0.72",
    downloadUrl: "https://example.com/setup.exe",
    checksumUrl: "https://example.com/setup.exe.sha256",
  },
});

test("production readiness confirms every safe external boundary", async () => {
  const payload = await readinessPayload(
    { headers: { "x-vercel-oidc-token": "oidc-token" } },
    {
      fetchImpl: async () => ({
        ok: true,
        async json() {
          return { status: "healthy" };
        },
      }),
      noticesLoader: readyNotices,
      passwordResetProtectionConfigured: true,
    },
  );

  assert.deepEqual(payload, {
    ok: true,
    service: "coupuas-thread-production-readiness",
    gatewayConfigured: true,
    authServiceReady: true,
    releaseReady: true,
    passwordResetProtectionConfigured: true,
    latestVersion: "v3.0.72",
  });
});

test("production readiness fails closed when a dependency is unavailable", async () => {
  const payload = await readinessPayload(
    { headers: { "x-vercel-oidc-token": "oidc-token" } },
    {
      fetchImpl: async () => {
        throw new Error("offline");
      },
      noticesLoader: readyNotices,
      passwordResetProtectionConfigured: true,
    },
  );

  assert.equal(payload.ok, false);
  assert.equal(payload.authServiceReady, false);
  assert.equal(payload.releaseReady, true);
});

test("production readiness fails closed without password-reset abuse protection", async () => {
  const payload = await readinessPayload(
    { headers: { "x-vercel-oidc-token": "oidc-token" } },
    {
      fetchImpl: async () => ({
        ok: true,
        async json() {
          return { status: "healthy" };
        },
      }),
      noticesLoader: readyNotices,
      passwordResetProtectionConfigured: false,
    },
  );

  assert.equal(payload.ok, false);
  assert.equal(payload.passwordResetProtectionConfigured, false);
});
