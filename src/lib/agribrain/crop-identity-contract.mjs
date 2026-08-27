/**
 * Browser-side helpers for the public crop-identification DTO.
 * Ranking shares are diagnostics, never calibrated species probabilities.
 */

export function getCropCandidateRankingShare(candidate) {
  const value = candidate?.ranking_share;
  return Number.isFinite(value) && value >= 0 && value <= 1 ? value : null;
}

export function buildCropLabelConfirmationPayload({
  plotId,
  cropCode,
}) {
  return {
    plotId: String(plotId || ""),
    cropCode: String(cropCode || "").trim().toLowerCase().replace(/\s+/g, "_"),
    synthetic: false,
  };
}

export function humanizeCropAuthority(authority) {
  const normalized = String(authority || "UNKNOWN").trim().toUpperCase();
  if (normalized === "REGISTRY_DECLARED") return "Registry declaration";
  if (normalized === "USER_CONFIRMED" || normalized === "FARMER_CONFIRMED") {
    return "Farmer-confirmed declaration";
  }
  if (normalized === "OFFICIAL_PARCEL_LABEL") return "Official parcel declaration";
  if (normalized === "AGRONOMIST_CONFIRMED") return "Agronomist-confirmed declaration";
  return "Identity unresolved";
}
