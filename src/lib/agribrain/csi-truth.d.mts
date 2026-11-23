export interface CsiPresentationBadges {
  hasPhysicalWifi: boolean;
  isActiveStream: boolean;
  isFresh: boolean;
  csiBadgeText: string;
  csiBadgeBg: string;
  csiBadgeColor: string;
  csiBadgeBorder: string;
  isCalibrated: boolean;
  calBadgeText: string;
  calBadgeBg: string;
  calBadgeColor: string;
  calBadgeBorder: string;
}

export function computeCsiTruthBadges(
  inSituWifi?: {
    physical_waves_measured?: boolean;
    is_active_stream?: boolean | null;
    status?: string | null;
    presentation_state?: string | null;
    is_fresh?: boolean | null;
    freshness?: string | null;
    is_calibrated?: boolean | null;
    calibration_status?: string | null;
    calibration_state_ref?: string | null;
  } | null,
  ambientWifi?: {
    physical_waves_measured?: boolean;
    is_active_stream?: boolean | null;
    status?: string | null;
    is_fresh?: boolean | null;
    freshness?: string | null;
  } | null
): CsiPresentationBadges;
