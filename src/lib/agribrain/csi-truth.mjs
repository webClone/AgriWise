/**
 * Canonical CSI Presentation Truth & Fail-Closed Calibration Authority.
 *
 * Enforces Principle P-08 Scientific Truth:
 * 1. Physical presence requires authentic waves measured.
 * 2. Explicit negative flags (is_active_stream === false, is_calibrated === false)
 *    strictly win and can never be overridden by status strings or reference tokens.
 * 3. Freshness is strictly verified and cannot masquerade as calibration.
 */

export function computeCsiTruthBadges(inSituWifi, ambientWifi) {
  const hasPhysicalWifi = Boolean(
    inSituWifi?.physical_waves_measured ?? ambientWifi?.physical_waves_measured ?? false
  );

  // Strict fail-closed active stream derivation:
  // Explicit false or null in inSituWifi strictly rejects active stream, regardless of status string
  let isActiveStream = false;
  if (inSituWifi) {
    if (inSituWifi.is_active_stream === true) {
      isActiveStream = true;
    } else if (inSituWifi.is_active_stream === false) {
      isActiveStream = false; // Explicit false strictly wins
    } else {
      isActiveStream = inSituWifi.status === "LIVE_CSI_STREAM" && inSituWifi.presentation_state === "LIVE";
    }
  } else if (ambientWifi) {
    isActiveStream = ambientWifi.is_active_stream === true && ambientWifi.status === "LIVE_CSI_STREAM";
  }

  // Strict fail-closed freshness derivation:
  let isFresh = false;
  if (inSituWifi) {
    if (inSituWifi.is_fresh === true || inSituWifi.freshness === "FRESH") {
      isFresh = true;
    } else {
      isFresh = false;
    }
  } else if (ambientWifi) {
    isFresh = ambientWifi.is_fresh === true || ambientWifi.freshness === "FRESH";
  }

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

  // Strict fail-closed calibration status:
  // Requires positive validation (is_calibrated === true AND calibration_status === "CALIBRATED")
  // An arbitrary calibration_state_ref NEVER overrides is_calibrated === false or UNCALIBRATED!
  const isCalibrated = Boolean(
    inSituWifi?.is_calibrated === true &&
    inSituWifi?.calibration_status === "CALIBRATED" &&
    inSituWifi?.calibration_state_ref &&
    inSituWifi.calibration_state_ref !== "CALIB-UNVERIFIED-DEMONSTRATOR"
  );
  const calBadgeText = isCalibrated ? "✓ CALIBRATED" : "⚠ UNCALIBRATED";
  const calBadgeBg = isCalibrated ? "rgba(34, 197, 94, 0.15)" : "rgba(245, 158, 11, 0.15)";
  const calBadgeColor = isCalibrated ? "#4ade80" : "#fbbf24";
  const calBadgeBorder = isCalibrated ? "rgba(34, 197, 94, 0.4)" : "rgba(245, 158, 11, 0.4)";

  return {
    hasPhysicalWifi,
    isActiveStream,
    isFresh,
    csiBadgeText,
    csiBadgeBg,
    csiBadgeColor,
    csiBadgeBorder,
    isCalibrated,
    calBadgeText,
    calBadgeBg,
    calBadgeColor,
    calBadgeBorder,
  };
}
