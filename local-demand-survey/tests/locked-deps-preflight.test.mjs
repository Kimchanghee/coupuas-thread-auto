import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import {
  dependenciesAreCurrent,
  dependencyManifestDigest,
  lockfileDigest,
  recordInstalledLockfile,
} from "../scripts/ensure-locked-deps.mjs";

test("dependency preflight records and compares the exact lockfile digest", (t) => {
  const tempRoot = mkdtempSync(join(tmpdir(), "thread-auto-lock-preflight-"));
  const nodeModules = join(tempRoot, "node_modules");
  const lockfile = join(tempRoot, "package-lock.json");
  const packageJson = join(tempRoot, "package.json");
  const marker = join(nodeModules, ".lock.sha256");
  const nextCommand = join(nodeModules, "next.cmd");
  mkdirSync(nodeModules, { recursive: true });
  writeFileSync(lockfile, '{"lockfileVersion":3}\n', "utf8");
  writeFileSync(packageJson, '{"name":"test"}\n', "utf8");
  writeFileSync(nextCommand, "", "utf8");
  t.after(() => rmSync(tempRoot, { recursive: true, force: true }));

  const paths = { marker, nextCommand, lockfile, packageJson };
  assert.equal(dependenciesAreCurrent(paths), false);
  recordInstalledLockfile(paths);
  assert.equal(dependenciesAreCurrent(paths), true);
  assert.equal(
    lockfileDigest(lockfile),
    createHash("sha256").update('{"lockfileVersion":3}\n').digest("hex"),
  );

  writeFileSync(lockfile, '{"lockfileVersion":3,"changed":true}\n', "utf8");
  assert.equal(dependenciesAreCurrent(paths), false);

  recordInstalledLockfile(paths);
  writeFileSync(packageJson, '{"name":"changed"}\n', "utf8");
  assert.equal(dependenciesAreCurrent(paths), false);
  assert.notEqual(
    dependencyManifestDigest({ lockfile, packageJson }),
    lockfileDigest(lockfile),
  );
});
