import { createHash } from "node:crypto";
import { spawnSync } from "node:child_process";
import {
  existsSync,
  readFileSync,
  renameSync,
  writeFileSync,
} from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = resolve(SCRIPT_DIR, "..");
const LOCKFILE = join(PROJECT_ROOT, "package-lock.json");
const PACKAGE_JSON = join(PROJECT_ROOT, "package.json");
const NODE_MODULES = join(PROJECT_ROOT, "node_modules");
const MARKER = join(NODE_MODULES, ".thread-auto-package-lock.sha256");
const NEXT_COMMAND = join(
  NODE_MODULES,
  ".bin",
  process.platform === "win32" ? "next.cmd" : "next",
);

export function lockfileDigest(lockfile = LOCKFILE) {
  return createHash("sha256").update(readFileSync(lockfile)).digest("hex");
}

export function dependencyManifestDigest({
  lockfile = LOCKFILE,
  packageJson = PACKAGE_JSON,
} = {}) {
  return createHash("sha256")
    .update(readFileSync(lockfile))
    .update("\0")
    .update(readFileSync(packageJson))
    .digest("hex");
}

export function dependenciesAreCurrent({
  marker = MARKER,
  nextCommand = NEXT_COMMAND,
  lockfile = LOCKFILE,
  packageJson = PACKAGE_JSON,
} = {}) {
  if (!existsSync(nextCommand) || !existsSync(marker)) return false;
  return (
    readFileSync(marker, "utf8").trim() ===
    dependencyManifestDigest({ lockfile, packageJson })
  );
}

function assertSupportedNode() {
  const packageJson = JSON.parse(readFileSync(PACKAGE_JSON, "utf8"));
  const minimum = String(packageJson.engines?.node ?? "").match(
    /^>=([0-9]+)\.([0-9]+)\.([0-9]+)$/,
  );
  if (!minimum) throw new Error("package.json must declare an exact >= Node.js engine");

  const current = process.versions.node.split(".").map(Number);
  const required = minimum.slice(1).map(Number);
  for (let index = 0; index < 3; index += 1) {
    if (current[index] > required[index]) return;
    if (current[index] < required[index]) {
      throw new Error(
        `Node.js ${required.join(".")} or newer is required; found ${process.versions.node}`,
      );
    }
  }
}

export function recordInstalledLockfile({
  marker = MARKER,
  lockfile = LOCKFILE,
  packageJson = PACKAGE_JSON,
} = {}) {
  const temporaryMarker = `${marker}.${process.pid}.tmp`;
  writeFileSync(
    temporaryMarker,
    `${dependencyManifestDigest({ lockfile, packageJson })}\n`,
    "utf8",
  );
  renameSync(temporaryMarker, marker);
}

export function ensureLockedDependencies() {
  assertSupportedNode();
  if (dependenciesAreCurrent()) {
    console.log("package-lock.json과 설치된 의존성이 일치합니다.");
    return;
  }

  console.log("package-lock.json 기준으로 의존성을 다시 설치합니다...");
  const npm = process.platform === "win32" ? "npm.cmd" : "npm";
  const completed = spawnSync(npm, ["ci", "--no-audit", "--no-fund"], {
    cwd: PROJECT_ROOT,
    stdio: "inherit",
    shell: false,
  });
  if (completed.error) throw completed.error;
  if (completed.status !== 0) {
    throw new Error(`npm ci failed with exit code ${completed.status}`);
  }
  if (!existsSync(NEXT_COMMAND)) {
    throw new Error("npm ci completed but the Next.js command is missing");
  }
  recordInstalledLockfile();
}

const invokedPath = process.argv[1] ? pathToFileURL(resolve(process.argv[1])).href : "";
if (invokedPath === import.meta.url) {
  try {
    ensureLockedDependencies();
  } catch (error) {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
  }
}
