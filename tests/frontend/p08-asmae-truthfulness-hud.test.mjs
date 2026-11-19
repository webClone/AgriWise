import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const canvas = readFileSync("src/components/farm/workspace/WorkspaceSpatialCanvas.tsx", "utf8");

test("P08: HUD only describes an admitted plot estimate as a scalar estimate", () => {
  assert.match(canvas, /canonicalStatus === "PLOT_ESTIMATE"/);
  assert.match(canvas, /activeAsmaeAvailability\.mean !== null/);
  assert.match(canvas, /has an admitted plot-level estimate/);
  assert.match(canvas, /activeAsmaeAvailability\.sigma !== null/);
});

test("P08: blocked scientific authority is not called a scalar measurement", () => {
  assert.match(canvas, /canonicalStatus === "BLOCKED"/);
  assert.match(canvas, /has a blocked scientific publication or authority/);
  assert.doesNotMatch(canvas, /is a scalar-only estimate/);
});

test("P08: absent evidence cannot silently masquerade as an admitted estimate", () => {
  assert.match(canvas, /canonicalStatus === "UNAVAILABLE"/);
  assert.match(canvas, /has no admitted scientific estimate/);
});

test("P08: every non-renderable state continues to withhold raster pixels", () => {
  assert.match(canvas, /!activeAsmaeAvailability\.canRenderPixels/);
  assert.match(canvas, /const effectiveSurface = isSpatialWithheld/);
  assert.match(canvas, /data-testid="pw-truthfulness-hud"/);
});
