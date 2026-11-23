import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";

const root = process.cwd();
const inSituTabSrc = readFileSync(
  path.join(root, "src/components/farm/intelligence/mesia/tabs/InSituTab.tsx"),
  "utf8"
);

// Pure helper replicating the presentation logic in InSituTab.tsx
function computeCsiBadges(inSituWifi, ambientWifi) {
  const hasPhysicalWifi = Boolean(
    inSituWifi?.physical_waves_measured || ambientWifi?.physical_waves_measured
  );
  const isActiveStream = Boolean(
    inSituWifi?.is_active_stream ?? ambientWifi?.is_active_stream ?? false
  );
  const isFresh = Boolean(
    inSituWifi?.is_fresh ||
    inSituWifi?.freshness === "FRESH" ||
    ambientWifi?.is_fresh ||
    ambientWifi?.freshness === "FRESH"
  );

  let csiBadgeText = "○ No verified CSI capture";
  let csiBadgeBg = "rgba(100, 116, 139, 0.2)";
  let csiBadgeColor = "#94a3b8";
  let csiBadgeBorder = "rgba(100, 116, 139, 0.4)";

  if (!hasPhysicalWifi) {
    csiBadgeText = "○ No verified CSI capture";
  } else if (isActiveStream && isFresh) {
    csiBadgeText = "● Live CSI stream";
    csiBadgeBg = "rgba(236, 72, 153, 0.2)";
    csiBadgeColor = "#f472b6";
    csiBadgeBorder = "#f472b6";
  } else if (isFresh) {
    csiBadgeText = "● Recorded capture";
    csiBadgeBg = "rgba(56, 189, 248, 0.2)";
    csiBadgeColor = "#38bdf8";
    csiBadgeBorder = "#38bdf8";
  } else {
    csiBadgeText = "○ Archived capture";
    csiBadgeBg = "rgba(245, 158, 11, 0.2)";
    csiBadgeColor = "#f59e0b";
    csiBadgeBorder = "rgba(245, 158, 11, 0.5)";
  }

  const isCalibrated = Boolean(
    inSituWifi?.is_calibrated ||
    inSituWifi?.calibration_status === "CALIBRATED" ||
    (inSituWifi?.calibration_state_ref && inSituWifi.calibration_state_ref !== "CALIB-UNVERIFIED-DEMONSTRATOR")
  );
  const calBadgeText = isCalibrated ? "✓ CALIBRATED" : "⚠ UNCALIBRATED";
  const calBadgeBg = isCalibrated ? "rgba(34, 197, 94, 0.15)" : "rgba(245, 158, 11, 0.15)";
  const calBadgeColor = isCalibrated ? "#4ade80" : "#fbbf24";
  const calBadgeBorder = isCalibrated ? "rgba(34, 197, 94, 0.4)" : "rgba(245, 158, 11, 0.4)";

  return {
    hasPhysicalWifi,
    csiBadgeText,
    csiBadgeColor,
    isCalibrated,
    calBadgeText,
    calBadgeColor,
  };
}

test("MESIA-CSI-01: InSituTab source code defines 4 distinct truthful CSI presentation states", () => {
  assert.match(inSituTabSrc, /"● Live CSI stream"/);
  assert.match(inSituTabSrc, /"● Recorded capture"/);
  assert.match(inSituTabSrc, /"○ Archived capture"/);
  assert.match(inSituTabSrc, /"○ No verified CSI capture"/);
  assert.doesNotMatch(inSituTabSrc, /"● PHYSICAL CSI ACTIVE"/);
});

test("MESIA-CSI-02: InSituTab source code decouples calibration status from freshness", () => {
  assert.match(inSituTabSrc, /"✓ CALIBRATED"/);
  assert.match(inSituTabSrc, /"⚠ UNCALIBRATED"/);
  assert.match(inSituTabSrc, /data-testid="csi-stream-badge"/);
  assert.match(inSituTabSrc, /data-testid="csi-calibration-badge"/);
  assert.match(inSituTabSrc, /CALIB-UNVERIFIED-DEMONSTRATOR/);
});

test("MESIA-CSI-03: No physical capture displays '○ No verified CSI capture'", () => {
  const result = computeCsiBadges(null, null);
  assert.equal(result.hasPhysicalWifi, false);
  assert.equal(result.csiBadgeText, "○ No verified CSI capture");
  assert.equal(result.csiBadgeColor, "#94a3b8");

  const unmeasured = computeCsiBadges({ physical_waves_measured: false }, {});
  assert.equal(unmeasured.hasPhysicalWifi, false);
  assert.equal(unmeasured.csiBadgeText, "○ No verified CSI capture");
});

test("MESIA-CSI-04: Active fresh stream displays '● Live CSI stream'", () => {
  const result = computeCsiBadges(
    { physical_waves_measured: true, is_active_stream: true, is_fresh: true },
    null
  );
  assert.equal(result.hasPhysicalWifi, true);
  assert.equal(result.csiBadgeText, "● Live CSI stream");
  assert.equal(result.csiBadgeColor, "#f472b6");
});

test("MESIA-CSI-05: Stored physical capture with fresh acquisition displays '● Recorded capture'", () => {
  const result = computeCsiBadges(
    { physical_waves_measured: true, is_active_stream: false, is_fresh: true },
    null
  );
  assert.equal(result.hasPhysicalWifi, true);
  assert.equal(result.csiBadgeText, "● Recorded capture");
  assert.equal(result.csiBadgeColor, "#38bdf8");
});

test("MESIA-CSI-06: Stored physical capture with stale acquisition displays '○ Archived capture'", () => {
  const result = computeCsiBadges(
    { physical_waves_measured: true, is_active_stream: false, is_fresh: false },
    null
  );
  assert.equal(result.hasPhysicalWifi, true);
  assert.equal(result.csiBadgeText, "○ Archived capture");
  assert.equal(result.csiBadgeColor, "#f59e0b");
});

test("MESIA-CSI-07: Calibration is independently verified and false for unverified demonstrator", () => {
  // Fresh recorded capture that is uncalibrated demonstrator
  const uncalibrated = computeCsiBadges(
    {
      physical_waves_measured: true,
      is_active_stream: false,
      is_fresh: true,
      is_calibrated: false,
      calibration_status: "UNCALIBRATED",
      calibration_state_ref: "CALIB-UNVERIFIED-DEMONSTRATOR",
    },
    null
  );
  assert.equal(uncalibrated.csiBadgeText, "● Recorded capture");
  assert.equal(uncalibrated.isCalibrated, false);
  assert.equal(uncalibrated.calBadgeText, "⚠ UNCALIBRATED");
  assert.equal(uncalibrated.calBadgeColor, "#fbbf24");

  // Calibrated capture
  const calibrated = computeCsiBadges(
    {
      physical_waves_measured: true,
      is_active_stream: false,
      is_fresh: true,
      is_calibrated: true,
      calibration_status: "CALIBRATED",
      calibration_state_ref: "CALIB-ANECHOIC-50OHM-V1",
    },
    null
  );
  assert.equal(calibrated.csiBadgeText, "● Recorded capture");
  assert.equal(calibrated.isCalibrated, true);
  assert.equal(calibrated.calBadgeText, "✓ CALIBRATED");
  assert.equal(calibrated.calBadgeColor, "#4ade80");
});
