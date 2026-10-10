import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const read = (path) => fs.readFileSync(new URL(path, import.meta.url), "utf8").replace(/\r\n/g, "\n");

test("Store workflow installs locked Node 22 dependencies before Node tests", () => {
  const workflow = read("../.github/workflows/store-release.yml");
  const setupNode = workflow.indexOf("actions/setup-node@");
  const npmCi = workflow.indexOf("npm ci");
  const nodeTests = workflow.indexOf("node --test tests_js/*.test.mjs");
  assert.ok(setupNode > 0);
  assert.match(workflow.slice(setupNode, npmCi), /node-version: "22"/);
  assert.ok(setupNode < npmCi && npmCi < nodeTests);

  const buildJob = workflow.split("  build-store-package:\n", 2)[1]
    .split("  publish-store-package:\n", 1)[0];
  const publishJob = workflow.split("  publish-store-package:\n", 2)[1];
  assert.doesNotMatch(buildJob, /AZURE_AD_APPLICATION_SECRET/);
  assert.match(publishJob, /environment: production-store-publishing/);
  assert.match(publishJob, /actions\/download-artifact@[0-9a-f]{40}/);
  assert.doesNotMatch(publishJob, /actions\/checkout/);
  assert.match(publishJob, /Store package checksum mismatch/);
});

test("public release uses isolated OIDC managed signing and verified promotion", () => {
  const workflow = read("../.github/workflows/build-release.yml");
  const verifier = read("../.github/scripts/assert-public-authenticode.ps1");
  const executableSigner = workflow.split("  sign-executable:\n", 2)[1]
    .split("  build-installer:\n", 1)[0];
  const installerSigner = workflow.split("  sign-installer:\n", 2)[1]
    .split("  verify-release:\n", 1)[0];
  for (const signer of [executableSigner, installerSigner]) {
    assert.match(signer, /environment: production-code-signing/);
    assert.match(signer, /id-token: write/);
    assert.match(signer, /azure\/login@[0-9a-f]{40}/);
    assert.match(signer, /azure\/artifact-signing-action@[0-9a-f]{40}/);
    assert.doesNotMatch(signer, /actions\/checkout|WINDOWS_CODE_SIGN_CERT|CERT_PASSWORD|Exportable/);
  }
  assert.match(verifier, /X509RevocationMode\]::Online/);
  assert.match(verifier, /TrustedThumbprints/);
  assert.doesNotMatch(verifier, /AllowPinnedSelfSigned|NotTrusted|UnknownError|NoCheck/);
  const release = workflow.split("  release:\n", 2)[1];
  assert.match(release, /needs: verify-release/);
  assert.match(release, /verified-release-/);
});

test("branch CI covers master and codex branches with locked Python and Node checks", () => {
  const workflow = read("../.github/workflows/ci.yml");
  assert.match(workflow, /master/);
  assert.match(workflow, /codex\/\*\*/);
  assert.match(workflow, /python-version: "3\.11"/);
  assert.match(workflow, /node-version: "22"/);
  assert.match(workflow, /pip install --require-hashes -r requirements\.lock/);
  assert.match(workflow, /npm ci/);
  assert.match(workflow, /python -m pytest -q/);
  assert.match(workflow, /npm test/);
  assert.match(workflow, /local-demand-survey\/package-lock\.json/);
  assert.match(workflow, /npm ci --prefix local-demand-survey/);
  assert.match(workflow, /npm run lint --prefix local-demand-survey/);
  assert.match(workflow, /npm run build --prefix local-demand-survey/);
});
