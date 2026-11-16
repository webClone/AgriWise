import { readdirSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const testsDir = path.resolve(__dirname, "../tests/frontend");

const testFiles = readdirSync(testsDir)
  .filter((f) => f.endsWith(".test.mjs"))
  .sort()
  .map((f) => path.join(testsDir, f));

if (testFiles.length === 0) {
  console.error("No test files found in tests/frontend");
  process.exit(1);
}

console.log(`[test:frontend] Executing all ${testFiles.length} test files in tests/frontend...`);

const result = spawnSync(
  process.execPath,
  ["--experimental-vm-modules", "--test", ...testFiles],
  { stdio: "inherit" }
);

process.exit(result.status ?? 1);
