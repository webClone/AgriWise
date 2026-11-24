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
  // 1. Explicit false strictly wins.
  // 2. Conflicting presentation_state ("REPLAY", "ARCHIVED", "STORED") strictly forbids active stream.
  // 3. Ambient fallback only if authentic and not replay.
  let isActiveStream = false;
  if (inSituWifi) {
    if (inSituWifi.is_active_stream === false) {
      isActiveStream = false;
    } else if (inSituWifi.presentation_state === "REPLAY" || inSituWifi.presentation_state === "ARCHIVED") {
      isActiveStream = false;
    } else if (inSituWifi.is_active_stream === true) {
      isActiveStream = true;
    } else {
      isActiveStream = inSituWifi.status === "LIVE_CSI_STREAM" && inSituWifi.presentation_state === "LIVE";
    }
  } else if (ambientWifi) {
    if (ambientWifi.is_active_stream === false || ambientWifi.presentation_state === "REPLAY" || ambientWifi.presentation_state === "ARCHIVED") {
      isActiveStream = false;
    } else if (ambientWifi.is_active_stream === true) {
      isActiveStream = ambientWifi.status === "LIVE_CSI_STREAM";
    }
  }

  // Strict fail-closed freshness derivation:
  // 1. Explicit negative boolean (is_fresh === false) strictly wins over any freshness string ("FRESH").
  // 2. Negative freshness strings ("STALE", "ARCHIVED", "EXPIRED") strictly force isFresh = false.
  // 3. Positive freshness requires is_fresh === true OR (is_fresh !== false AND freshness === "FRESH").
  let isFresh = false;
  if (inSituWifi) {
    if (inSituWifi.is_fresh === false) {
      isFresh = false; // Explicit false strictly wins over conflicting freshness="FRESH"
    } else if (inSituWifi.freshness === "STALE" || inSituWifi.freshness === "ARCHIVED" || inSituWifi.freshness === "EXPIRED") {
      isFresh = false;
    } else if (inSituWifi.is_fresh === true) {
      isFresh = true;
    } else if (inSituWifi.freshness === "FRESH") {
      isFresh = true;
    }
  } else if (ambientWifi) {
    if (ambientWifi.is_fresh === false) {
      isFresh = false;
    } else if (ambientWifi.freshness === "STALE" || ambientWifi.freshness === "ARCHIVED" || ambientWifi.freshness === "EXPIRED") {
      isFresh = false;
    } else if (ambientWifi.is_fresh === true || ambientWifi.freshness === "FRESH") {
      isFresh = true;
    }
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
