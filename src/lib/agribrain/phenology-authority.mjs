const CANONICAL_SOURCE = "layer2_canonical_phenology";
const STAGES = new Set([
  "BARE_SOIL",
  "EMERGENCE",
  "VEGETATIVE",
  "REPRODUCTIVE",
  "SENESCENCE",
  "HARVESTED",
  "DORMANCY",
  "UNKNOWN",
]);
const AUTHORITIES = new Set(["unavailable", "diagnostic", "calibrated"]);
const STAGE_AUTHORITIES = new Set(["diagnostic", "calibrated"]);
const SHA256 = /^[0-9a-f]{64}$/;

function unknownContext(reason) {
  return {
    resolved_crop_stage: "UNKNOWN",
    phenology_evidence_class: "unavailable",
    phenology_authority: "unavailable",
    phenology_source: "unavailable",
    required_phenology_source: CANONICAL_SOURCE,
    phenology_confidence: 0,
    phenology_posterior_hash: "",
    phenology_receipt_valid: false,
    phenology_evidence_needed_reason:
      reason || "canonical_layer2_phenology_receipt_required",
    stage_available: false,
    contract_version: "phenology_authority_v2_consumer",
  };
}

/**
 * Browser fail-closed phenology boundary. A database CropStatus, DAP value,
 * NDVI curve, or raw Layer-2 stage array can never satisfy this contract.
 */
export function normalizeCanonicalPhenologyPublication(input = {}) {
  const rawContext = input.phenologyContext;
  const context = rawContext && typeof rawContext === "object" ? { ...rawContext } : {};
  const envelopeStage = String(input.resolvedCropStage || "")
    .trim().toUpperCase().replaceAll(" ", "_");
  const receiptStage = String(context.resolved_crop_stage || "")
    .trim().toUpperCase().replaceAll(" ", "_");
  const stage = envelopeStage || receiptStage || "UNKNOWN";
  const authority = String(
    context.phenology_authority || context.phenology_evidence_class || "unavailable",
  ).trim().toLowerCase();
  const source = String(context.phenology_source || "").trim();
  const receiptHash = String(context.phenology_posterior_hash || "").trim().toLowerCase();
  const rawConfidence = Number(context.phenology_confidence);
  const confidenceValid = Number.isFinite(rawConfidence)
    && rawConfidence >= 0
    && rawConfidence <= 1;
  const stageAliasesAgree = !envelopeStage || !receiptStage || envelopeStage === receiptStage;
  const authorityAliasesAgree = !context.phenology_evidence_class
    || String(context.phenology_evidence_class).trim().toLowerCase() === authority;
  const receiptValid =
    source === CANONICAL_SOURCE &&
    AUTHORITIES.has(authority) &&
    SHA256.test(receiptHash) &&
    context.phenology_receipt_valid === true &&
    stageAliasesAgree &&
    authorityAliasesAgree;
  const reason = String(
    context.phenology_evidence_needed_reason ||
      "additional_independent_phenology_evidence_required",
  );

  if (
    !receiptValid ||
    !STAGES.has(stage) ||
    stage === "UNKNOWN" ||
    !STAGE_AUTHORITIES.has(authority) ||
    !confidenceValid ||
    context.stage_available === false
  ) {
    if (!receiptValid) {
      return {
        resolvedCropStage: "UNKNOWN",
        phenologyContext: unknownContext(
          context.phenology_evidence_needed_reason ||
            "canonical_layer2_phenology_receipt_required",
        ),
      };
    }
    return {
      resolvedCropStage: "UNKNOWN",
      phenologyContext: {
        ...context,
        resolved_crop_stage: "UNKNOWN",
        phenology_authority: authority,
        phenology_evidence_class: authority,
        phenology_source: CANONICAL_SOURCE,
        phenology_posterior_hash: receiptHash,
        phenology_receipt_valid: true,
        phenology_evidence_needed_reason: reason,
        phenology_confidence: 0,
        stage_available: false,
        contract_version: "phenology_authority_v2_consumer",
      },
    };
  }

  return {
    resolvedCropStage: stage,
    phenologyContext: {
      ...context,
      resolved_crop_stage: stage,
      phenology_authority: authority,
      phenology_evidence_class: authority,
      phenology_source: CANONICAL_SOURCE,
      phenology_posterior_hash: receiptHash,
      phenology_receipt_valid: true,
      phenology_evidence_needed_reason: "",
      phenology_confidence: rawConfidence,
      stage_available: true,
      contract_version: "phenology_authority_v2_consumer",
    },
  };
}

export function phenologyEvidenceReasonLabel(reason) {
  const labels = {
    canonical_layer2_phenology_receipt_required:
      "A canonical canopy phenology receipt is required.",
    canonical_layer2_phenology_receipt_invalid:
      "The canopy phenology receipt could not be validated.",
    canonical_layer2_phenology_namespace_mismatch:
      "The phenology receipt belongs to a different plot.",
    additional_independent_phenology_evidence_required:
      "Additional independent phenology evidence is needed.",
    confirmed_or_bounded_plant_date_required:
      "A confirmed or bounded planting date is needed.",
    season_weather_archive_required:
      "Season weather history is needed to resolve growth stage.",
  };
  return labels[String(reason || "")] || String(reason || "Additional phenology evidence is needed.").replaceAll("_", " ");
}
