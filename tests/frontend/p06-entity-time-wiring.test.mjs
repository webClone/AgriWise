import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const source = (relative) => readFileSync(path.join(root, relative), "utf8");
const actions = source("src/components/farm/workspace/WorkspaceContextActionsP04.tsx");
const host = source("src/components/farm/workspace/WorkspaceInvestigationHostP04.tsx");
const shell = source("src/components/farm/workspace/PlotWorkspaceShell.tsx");

test("P06: zone and all four entity actions can open Compare Time", () => {
  assert.equal((actions.match(/onLaunch\("compare"\)/g) || []).length, 5);
});
test("P06: in-place host consumes current authenticated entity list, not selection.metadata", () => {
  assert.match(shell, /workspaceEntities=\{(scopedEntities|entities)\}/);
  assert.match(host, /workspaceEntities\.find\(/);
  assert.match(host, /buildEntityTemporalComparison/);
  assert.doesNotMatch(host, /selectedEntity\.metadata/);
});
test("P06: comparison explicitly exposes epistemic class, availability and scientific cutoff", () => {
  assert.match(host, /Epistemic class/);
  assert.match(host, /First available at/);
  assert.match(host, /Scientific cutoff/);
  assert.match(host, /No point-to-raster numerical comparison/);
});
