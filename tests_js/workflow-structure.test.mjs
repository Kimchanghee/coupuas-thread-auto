import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const read = (path) => fs.readFileSync(new URL(path, import.meta.url), "utf8");

test("Store workflow installs locked Node 22 dependencies before Node tests", () => {
  const workflow = read("../.github/workflows/store-release.yml");
  const setupNode = workflow.indexOf("actions/setup-node@");
  const npmCi = workflow.indexOf("npm ci");
  const nodeTests = workflow.indexOf("node --test tests_js/*.test.mjs");
  assert.ok(setupNode > 0);
  assert.match(workflow.slice(setupNode, npmCi), /node-version: "22"/);
  assert.ok(setupNode < npmCi && npmCi < nodeTests);
});

test("public release requires a publicly trusted certificate", () => {
  const workflow = read("../.github/workflows/build-release.yml");
  const signer = read("../.github/scripts/sign-windows-artifact.ps1");
  const verifier = read("../.github/scripts/assert-public-authenticode.ps1");
  assert.equal(workflow.includes("-AllowPinnedSelfSigned"), false);
  assert.equal((workflow.match(/assert-public-authenticode\.ps1/g) || []).length, 2);
  assert.match(signer, /AllowPinnedSelfSigned is restricted to explicit local development use/);
  assert.match(verifier, /AllowPinnedSelfSigned is restricted to explicit local development use/);
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
