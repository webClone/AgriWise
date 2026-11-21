/** Client-side projections only: never grant backend scientific authority. */
export function isTransectDiagnosisAuthorized(canInterpretDiagnostically) {
  return canInterpretDiagnostically === true;
}

/** No 1m-approval claim from a missing, zero, invalid or unqualified ratio. */
export function hasQualifiedOneMeterApproval(percentage, backendApprovalAllowed) {
  return typeof percentage === "number"
    && Number.isFinite(percentage)
    && percentage > 0 && percentage <= 100
    && backendApprovalAllowed === true;
}
