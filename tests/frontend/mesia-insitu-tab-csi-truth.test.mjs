import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { computeCsiTruthBadges } from "../../src/lib/agribrain/csi-truth.mjs";

const root = process.cwd();
const inSituTabSrc = readFileSync(
  path.join(root, "src/components/farm/intelligence/mesia/tabs/InSituTab.tsx"),
  "utf8"
);

test("MESIA-CSI-01: InSituTab source code imports canonical computeCsiTruthBadges authority", () => {
  assert.match(inSituTabSrc, /import\s*\{\s*computeCsiTruthBadges\s*\}\s*from\s*["']@\/lib\/agribrain\/csi-truth\.mjs["']/);
  assert.match(inSituTabSrc, /const\s*\{\s*hasPhysicalWifi,\s*csiBadgeText,/);
  assert.match(inSituTabSrc, /data-testid="csi-stream-badge"/);
  assert.match(inSituTabSrc, /data-testid="csi-calibration-badge"/);
});

test("MESIA-CSI-02: Absent physical waves strictly yields '○ No verified CSI capture'", () => {
  const resultNull = computeCsiTruthBadges(null, null);
  assert.equal(resultNull.hasPhysicalWifi, false);
  assert.equal(resultNull.csiBadgeText, "○ No verified CSI capture");
  assert.equal(resultNull.csiBadgeColor, "#94a3b8");

  const resultUnmeasured = computeCsiTruthBadges({ physical_waves_measured: false }, null);
  assert.equal(resultUnmeasured.hasPhysicalWifi, false);
  assert.equal(resultUnmeasured.csiBadgeText, "○ No verified CSI capture");
});

test("MESIA-CSI-03: Explicit is_active_stream=false overrides conflicting LIVE status (F04 fail-closed)", () => {
  // Contradictory fixture: status claims LIVE_CSI_STREAM but is_active_stream is explicitly false
  const contradictoryFixture = {
    physical_waves_measured: true,
    is_active_stream: false,
    status: "LIVE_CSI_STREAM",
    presentation_state: "LIVE",
    is_fresh: true,
    freshness: "FRESH",
  };
  const result = computeCsiTruthBadges(contradictoryFixture, null);
  assert.equal(result.hasPhysicalWifi, true);
  assert.equal(result.isActiveStream, false, "Explicit is_active_stream=false must strictly win over status string");
  assert.equal(result.csiBadgeText, "● Recorded capture", "Must report recorded capture, never false live stream");
  assert.equal(result.csiBadgeColor, "#38bdf8");
});

test("MESIA-CSI-04: Explicit is_calibrated=false overrides arbitrary calibration reference (F04 fail-closed)", () => {
  // Contradictory fixture: calibration_state_ref is present, but is_calibrated is explicitly false
  const uncalibratedFixture = {
    physical_waves_measured: true,
    is_active_stream: false,
    is_fresh: true,
    is_calibrated: false,
    calibration_status: "UNCALIBRATED",
    calibration_state_ref: "CALIB-PROD-50OHM-ANECHOIC-V1",
  };
  const result = computeCsiTruthBadges(uncalibratedFixture, null);
  assert.equal(result.isCalibrated, false, "Explicit is_calibrated=false must not be overridden by calibration_state_ref");
  assert.equal(result.calBadgeText, "⚠ UNCALIBRATED");
  assert.equal(result.calBadgeColor, "#fbbf24");
});

test("MESIA-CSI-05: Non-calibrated status overrides non-empty calibration reference (F04 fail-closed)", () => {
  const uncalibratedStatusFixture = {
    physical_waves_measured: true,
    is_active_stream: false,
    is_fresh: true,
    is_calibrated: true, // Inconsistent positive flag
    calibration_status: "UNCALIBRATED", // Explicit negative status
    calibration_state_ref: "CALIB-PROD-50OHM-ANECHOIC-V1",
  };
  const result = computeCsiTruthBadges(uncalibratedStatusFixture, null);
  assert.equal(result.isCalibrated, false, "calibration_status=UNCALIBRATED must fail closed");
  assert.equal(result.calBadgeText, "⚠ UNCALIBRATED");
});

test("MESIA-CSI-06: Verified active fresh stream displays '● Live CSI stream'", () => {
  const liveFixture = {
    physical_waves_measured: true,
    is_active_stream: true,
    status: "LIVE_CSI_STREAM",
    is_fresh: true,
    freshness: "FRESH",
  };
  const result = computeCsiTruthBadges(liveFixture, null);
  assert.equal(result.hasPhysicalWifi, true);
  assert.equal(result.isActiveStream, true);
  assert.equal(result.isFresh, true);
  assert.equal(result.csiBadgeText, "● Live CSI stream");
  assert.equal(result.csiBadgeColor, "#f472b6");
});

test("MESIA-CSI-07: Stale acquisition displays '○ Archived capture' even if active was claimed", () => {
  const staleFixture = {
    physical_waves_measured: true,
    is_active_stream: true,
    status: "LIVE_CSI_STREAM",
    is_fresh: false,
    freshness: "STALE",
  };
  const result = computeCsiTruthBadges(staleFixture, null);
  assert.equal(result.hasPhysicalWifi, true);
  assert.equal(result.isFresh, false);
  assert.equal(result.csiBadgeText, "○ Archived capture", "Stale stream must downgrade to archived capture");
  assert.equal(result.csiBadgeColor, "#f59e0b");
});

test("MESIA-CSI-08: Fully qualified calibrated capture displays '✓ CALIBRATED'", () => {
  const calibratedFixture = {
    physical_waves_measured: true,
    is_active_stream: false,
    is_fresh: true,
    is_calibrated: true,
    calibration_status: "CALIBRATED",
    calibration_state_ref: "CALIB-PROD-50OHM-ANECHOIC-V1",
  };
  const result = computeCsiTruthBadges(calibratedFixture, null);
  assert.equal(result.isCalibrated, true);
  assert.equal(result.calBadgeText, "✓ CALIBRATED");
  assert.equal(result.calBadgeColor, "#4ade80");
});
