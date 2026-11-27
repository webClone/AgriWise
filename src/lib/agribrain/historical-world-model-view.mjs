/**
 * Pure epistemic badge and summary derivation for ASMAE World Model V1/V2 UI panels.
 */

export function summarizeWorldModelV1View(payload) {
  const dom = payload?.domain_identity || null;
  const cropAsOf = payload?.crop_context_as_of || null;
  const timeline = Array.isArray(payload?.crop_identity_timeline) ? payload.crop_identity_timeline : [];
  const exploratory36_90 =
    payload?.retrovalidation_summary?.exploratory_by_horizon?.exploratory_36_90d ||
    payload?.exploratory_by_horizon?.exploratory_36_90d ||
    null;
  const failureDiag =
    payload?.retrovalidation_summary?.scientific_failure_diagnosis ||
    payload?.scientific_failure_diagnosis ||
    null;

  const cropVerified = Boolean(dom?.crop_identity_verified);
  const tenantVerified = Boolean(dom?.tenant_identity_verified);
  const syntheticRejected = Boolean(dom?.synthetic_label_rejected);
  const cropDeclarationAuthority =
    dom?.crop_declaration_authority || cropAsOf?.crop_declaration_authority || null;
  const tenantOwnershipSource = dom?.tenant_ownership_source || null;

  const cropBadgeLabel = dom
    ? cropVerified
      ? `Verified CropCycle: ${dom.resolved_crop_code || "unknown"}`
      : cropDeclarationAuthority === "REGISTRY_DECLARED"
        ? `Registry Declared (${dom.resolved_crop_code || "unconfirmed"} · Unconfirmed)`
        : "Unverified Crop (EO Group Posterior Only)"
    : null;

  const tenantLabel = dom
    ? tenantVerified
      ? "Verified"
      : dom.is_isolated_dev_fixture === false
        ? "Unverified Tenant Partition"
        : "Isolated Dev Fixture"
    : null;
  const latestSeason = timeline.length > 0 ? timeline[timeline.length - 1] : null;
  const latestEoGroup = latestSeason?.top_group || cropAsOf?.crop_group_posterior ? latestSeason?.top_group || "unknown" : null;
  const physicalRegime = cropAsOf?.physical_regime || null;

  return {
    cropVerified,
    tenantVerified,
    syntheticRejected,
    cropBadgeLabel,
    cropDeclarationAuthority,
    tenantLabel,
    tenantOwnershipSource,
    asOfCropLabel: cropAsOf ? (cropAsOf.crop_identity_verified ? cropAsOf.crop || "unknown" : "unknown / EO mixture") : null,
    physicalRegime,
    preKnownCycleUnknown: physicalRegime === "PRE_KNOWN_CYCLE_UNKNOWN",
    unknownMassPct: typeof cropAsOf?.unknown_probability === "number" ? Math.round(cropAsOf.unknown_probability * 100) : null,
    latestEoGroup,
    withheldReprocessedAfterK:
      typeof payload?.withheld_reprocessed_after_k_count === "number"
        ? payload.withheld_reprocessed_after_k_count
        : 0,
    cropChronologyHash: payload?.crop_chronology_hash || null,
    weatherLineageHash: payload?.weather_lineage_hash || null,
    crossLayerPriorVersion: payload?.cross_layer_prior_version || null,
    exploratory36_90d: exploratory36_90 && Number(exploratory36_90.n || 0) > 0
      ? {
          n: Number(exploratory36_90.n),
          skillVsPersistence: exploratory36_90.skill_vs_persistence ?? null,
          rmse: exploratory36_90.joint_forecast_rmse ?? null,
          exploratoryOnly: true,
        }
      : null,
    primaryFailureCause: failureDiag?.primary_cause || null,
    primaryFailureAction: Array.isArray(failureDiag?.recommended_evidence_to_unblock)
      ? failureDiag.recommended_evidence_to_unblock[0] || null
      : null,
  };
}
