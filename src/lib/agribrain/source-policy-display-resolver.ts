// Central display resolver mapping user selection policy and modes to active surfaces
// Isomorphic and pure. No React, DOM, or window.

import type { RenderMaterializationResult } from "./render-materialization";
import { resolvePixelInspectorCapabilities } from "./pixel-inspector-authority.mjs";

export type RenderKind =
  | "full_raster"
  | "proxy_overlay"
  | "diagnostic_overlay"
  | "uniform_tint"
  | "card_only"
  | "none";

export type RenderRole = "base" | "overlay" | "candidate" | "inspector";

export interface RenderAuthorization {
  surfaceType: string;
  policy: "satellite" | "experimental" | "asmae_diagnostic" | "hybrid";
  mode: string;
  role: RenderRole;
  authorized: boolean;
  renderKind: RenderKind;
  reason: string;
  proofRequired: string[];
  proofPresent: string[];
  requiresObservedMask?: boolean;
  requiresGapFillMask?: boolean;
  observedMaskType?: string;
  gapFillMaskType?: string;
  validMaskType?: string;
  observedRatio?: number;
  trustAlphaScale?: number;
  inspectorAllowed?: boolean;
  maskAlignmentPolicy?: "exact_grid" | "nearest_shared_bounds";
}

export interface SourcePolicyDisplayResolverInput {
  surfaces: any[];
  requestedPolicy: string;
  activeMode: string;
  sourcePolicyDisplayState?: any;
  asmaeEvidenceState?: any;
  experimentalVisualLadder?: any;
  showExperimental1m?: boolean;
  asmae_proof?: any;
  renderAuthorizations?: any;
  experimentalMaterialization?: RenderMaterializationResult | null;
}

export interface SourcePolicyDisplayResolverOutput {
  activeDisplay: {
    surface: any | null;
    surfaceType: string | null;
    sourceLabel: string;
    authorityLabel: string;
    groundingDetail: string;
    renderKind: RenderKind;
    displayLevel: "raster" | "asmae_diagnostic" | "proxy" | "plot_level" | "unavailable";
    bannerState: "composite_advisory_active" | "hybrid_active" | "asmae_diagnostic_active" | null;
    canShowPixelDiagnosis: boolean;
    canShowPixelHint: boolean;
    canSamplePixel: boolean;
    canInterpretForScouting: boolean;
    canInterpretDiagnostically: boolean;
    canUseForPrescription: boolean;
    shouldShowPlotLevel: boolean;
    shouldShowNoData: boolean;
    canShowExperimentalDetail: boolean;
    reason?: string;
  };
  surfaceAvailabilityByMode: Record<string, {
    surfaceType: string | null;
    status: "available_raster" | "available_overlay" | "card_only" | "unavailable_missing_proof" | "unavailable_missing_feature_family";
    levelLabel: string;
  }>;
  activeSurface: any | null;
  activeSurfaceType: string | null;
  activeSourceLabel: string;
  activeAuthorityLabel: string;
  bannerState: "composite_advisory_active" | "hybrid_active" | "asmae_diagnostic_active" | null;
  canShowPixelDiagnosis: boolean;
  canShowPixelHint: boolean;
  canSamplePixel: boolean;
  canInterpretForScouting: boolean;
  canInterpretDiagnostically: boolean;
  canUseForPrescription: boolean;
  canShowExperimentalDetail: boolean;
  shouldShowNoData: boolean;
  shouldShowPlotLevel: boolean;
}

export interface AuthorizedSurfaceResolution {
  requestedSurfaceType: string | null;
  resolvedSurfaceType: string | null;
  surface: any | null;
  authorization: RenderAuthorization | null;
  fallbackUsed: boolean;
  fallbackReason: string | null;
  availabilityStatus:
    | "available_raster"
    | "available_overlay"
    | "card_only"
    | "unavailable_missing_proof";
}

export function isCompositeAdvisorySurface(type?: string | null): boolean {
  const t = String(type || "").toUpperCase();
  return t.startsWith("COMPOSITE_");
}

export function isCoreAsmaeDiagnosticSurface(type?: string | null): boolean {
  const t = String(type || "").toUpperCase();
  return (
    t.startsWith("ASMAE_") ||
    t.includes("_ASMAE_") ||
    t.endsWith("_ASMAE") ||
    t.startsWith("CANOPY_ASMAE") ||
    t.startsWith("WATER_ASMAE") ||
    t.startsWith("NUTRIENT_ASMAE") ||
    t.startsWith("SALINITY_ASMAE") ||
    t.startsWith("RISK_ASMAE") ||
    t.startsWith("CONFIDENCE_ASMAE") ||
    t.startsWith("RESOLUTION_ASMAE") ||
    t.startsWith("VEG_ATTENTION_ASMAE")
  );
}

// Backward-compatible name, now intentionally limited to the core ASMAE
// family. Composite scouting products have a distinct authority contract.
export function isAsmaeSurfaceType(type?: string | null): boolean {
  return isCoreAsmaeDiagnosticSurface(type);
}

export function isExperimentalSurfaceType(type?: string | null): boolean {
  const t = String(type || "").toUpperCase();
  return t.includes("EXPERIMENTAL") || t === "NDVI_CLEAN_EXPERIMENTAL_FINE_DETAIL";
}

/**
 * A surface or coverage claim is not an experimental visual layer until the
 * browser has created the exact authorized overlay.  Keep this structural
 * check here so the resolver, map evidence model, and React hook all consume
 * the same proof without creating a runtime dependency cycle.
 */
export function hasRenderedExperimentalOverlay(
  materialization?: RenderMaterializationResult | null,
  expectedSurfaceType?: string | null,
  expectedMode?: string | null,
): boolean {
  if (
    materialization?.status !== "rendered"
    || materialization.role !== "overlay"
    || materialization.policy !== "experimental"
    || !materialization.layerId
    || !isExperimentalSurfaceType(materialization.surfaceType)
  ) {
    return false;
  }
  if (expectedSurfaceType && materialization.surfaceType !== expectedSurfaceType) {
    return false;
  }
  return !expectedMode || normalizeMode(materialization.mode) === normalizeMode(expectedMode);
}

export function getRenderAuthorization(
  surfaceType: string,
  policy: string,
  mode: string,
  role: RenderRole,
  renderAuthorizations: any
): RenderAuthorization {
  const normalizedMode = normalizeMode(mode);
  const auth = renderAuthorizations?.[policy]?.[normalizedMode]?.[role]?.[surfaceType];
  if (auth) {
    return auth;
  }
  // Deny by default
  return {
    surfaceType,
    policy: policy as any,
    mode: normalizedMode,
    role,
    authorized: false,
    renderKind: "none",
    reason: "missing_render_authorization",
    proofRequired: [],
    proofPresent: []
  };
}

export function normalizeMode(mode: string): string {
  if (!mode) return "canopy";
  const m = mode.toLowerCase().trim();
  if (m === "canopy" || m === "vegetation" || m === "ndvi") {
    return "canopy";
  }
  if (m === "water_stress" || m === "water") {
    return "water";
  }
  if (m === "nutrient_risk" || m === "nutrients") {
    return "nutrients";
  }
  if (m === "salinity_stress" || m === "salinity") {
    return "salinity";
  }
  if (m === "composite_risk" || m === "risk") {
    return "risk";
  }
  if (m === "vegetation_attention" || m === "veg_attention") {
    return "veg_attention";
  }
  if (m === "uncertainty") {
    return "uncertainty";
  }
  if (m === "resolution_coverage") {
    return "resolution_coverage";
  }
  return m;
}

/**
 * Resolve one authorized base surface for a policy/mode. This is the only
 * candidate loop used by the active map and the layer-panel availability
 * model; a finite but unauthorized candidate never hides a later authorized
 * fallback.
 */
export function resolveAuthorizedSurfaceForMode(input: {
  surfaces: any[];
  priorities: string[];
  policy: string;
  mode: string;
  renderAuthorizations?: any;
}): AuthorizedSurfaceResolution {
  const requestedSurfaceType = input.priorities[0] || null;
  let firstBlockedType: string | null = null;
  let firstBlockedAuth: RenderAuthorization | null = null;

  for (const candidateType of input.priorities) {
    const surface = input.surfaces.find(
      (candidate) => candidate
        && (candidate.type === candidateType || candidate.semantic_type === candidateType),
    );
    if (!surface || !hasFiniteValues(surface)) continue;

    const authorization = getRenderAuthorization(
      candidateType,
      input.policy,
      input.mode,
      "base",
      input.renderAuthorizations,
    );
    if (
      authorization.authorized
      && isRenderKindAllowedForRole(authorization.renderKind, "base")
    ) {
      return {
        requestedSurfaceType,
        resolvedSurfaceType: candidateType,
        surface,
        authorization,
        fallbackUsed: !!requestedSurfaceType && candidateType !== requestedSurfaceType,
        fallbackReason: candidateType !== requestedSurfaceType
          ? firstBlockedAuth?.reason || "requested_surface_not_authorized"
          : null,
        availabilityStatus: authorization.renderKind === "full_raster"
          ? "available_raster"
          : "available_overlay",
      };
    }
    if (!firstBlockedType) {
      firstBlockedType = candidateType;
      firstBlockedAuth = authorization;
    }
  }

  return {
    requestedSurfaceType,
    resolvedSurfaceType: firstBlockedType,
    surface: null,
    authorization: firstBlockedAuth,
    fallbackUsed: false,
    fallbackReason: firstBlockedAuth?.reason || "no_authorized_surface",
    availabilityStatus: firstBlockedAuth?.renderKind === "card_only"
      ? "card_only"
      : "unavailable_missing_proof",
  };
}

export function hasFiniteValues(s: any): boolean {
  if (!s) return false;
  const valuesArr = s.values || s.grid || s.data || s.matrix || s.raster?.values;
  if (!valuesArr) return false;
  
  if (Array.isArray(valuesArr)) {
    for (const row of valuesArr) {
      if (Array.isArray(row)) {
        for (const val of row) {
          if (typeof val === "number" && Number.isFinite(val)) {
            return true;
          }
        }
      } else {
        if (typeof row === "number" && Number.isFinite(row)) {
          return true;
        }
      }
    }
  }
  return false;
}

export function getPriorityList(
  normalizedMode: string,
  requestedPolicy: string,
  realAsmae: boolean,
  showExperimental1m: boolean
): string[] {
  // Lock 3: If satellite policy is active, never allow experimental or ASMAE bases.
  const isSatellite = requestedPolicy === "satellite";
  const isAsmaeDiag = requestedPolicy === "asmae_diagnostic";
  const isHybrid = requestedPolicy === "hybrid";
  const isExpPolicy = requestedPolicy === "experimental";

  const allowExp = showExperimental1m && !isSatellite && !isAsmaeDiag;
  const isAsmaeOrHybrid = isAsmaeDiag || isHybrid;

  if (normalizedMode === "canopy") {
    if (isSatellite) {
      return ["NDVI_CLEAN"];
    } else if (isExpPolicy) {
      return ["NDVI_CLEAN_EXPERIMENTAL_FINE_DETAIL", "NDVI_CLEAN"];
    } else if (isAsmaeDiag) {
      return ["CANOPY_ASMAE_VIGOR", "ASMAE_VISUAL_FUSION_CANOPY", "COMPOSITE_ADVISORY_CANOPY", "NDVI_CLEAN"];
    } else if (isHybrid) {
      return [
        "ASMAE_VISUAL_FUSION_CANOPY",
        "COMPOSITE_ADVISORY_CANOPY",
        "NDVI_CLEAN_EXPERIMENTAL_FINE_DETAIL",
        "NDVI_CLEAN"
      ];
    }
  }

  let list: string[] = [];

  if (normalizedMode === "water") {
    if (isAsmaeOrHybrid) {
      if (realAsmae) {
        list.push("WATER_ASMAE_CANOPY_WATER", "WATER_ASMAE_ROOT_ZONE_WATER");
      }
      list.push("COMPOSITE_WATER_SUPPORT");
    }
    if (allowExp) {
      list.push("WATER_STRESS_PROB_EXPERIMENTAL_FINE_DETAIL");
    }
    list.push("WATER_STRESS_PROB");
  } else if (normalizedMode === "nutrients") {
    if (isAsmaeOrHybrid) {
      if (realAsmae) {
        list.push("NUTRIENT_ASMAE_CHLOROPHYLL_PROXY");
      }
      list.push("COMPOSITE_NUTRIENT_SUPPORT");
    }
    if (allowExp) {
      list.push("NUTRIENT_STRESS_PROB_EXPERIMENTAL_FINE_DETAIL");
    }
    list.push("NUTRIENT_STRESS_PROB");
  } else if (normalizedMode === "salinity") {
    if (isAsmaeOrHybrid) {
      if (realAsmae) {
        list.push("SALINITY_ASMAE_STRESS");
      }
      list.push("COMPOSITE_SALINITY_STRESS");
    }
    if (allowExp) {
      list.push("SALINITY_STRESS_EXPERIMENTAL_FINE_DETAIL");
    }
    list.push("SALINITY_STRESS");
  } else if (normalizedMode === "risk") {
    if (isAsmaeOrHybrid) {
      if (realAsmae) {
        list.push("RISK_ASMAE_DIAGNOSTIC");
      }
      list.push("COMPOSITE_RISK_DIAGNOSTIC");
    }
    if (allowExp) {
      list.push("COMPOSITE_RISK_EXPERIMENTAL_FINE_DETAIL");
    }
    list.push("COMPOSITE_RISK");
  } else if (normalizedMode === "veg_attention") {
    if (isAsmaeOrHybrid) {
      if (realAsmae) {
        list.push(
          "VEG_ATTENTION_ASMAE_DIAGNOSTIC",
          "VEG_ATTENTION_ASMAE_CONFLICT",
          "VEG_ATTENTION_ASMAE_DISAGREEMENT",
          "ASMAE_BMA_DISAGREEMENT",
          "ASMAE_CROSS_LAYER_CONFLICT",
          "ASMAE_VIGOR"
        );
      }
      list.push("COMPOSITE_VEG_ATTENTION");
    }
    if (allowExp) {
      list.push("NDVI_DEVIATION_EXPERIMENTAL_FINE_DETAIL");
    }
    list.push("NDVI_DEVIATION", "BASELINE_ANOMALY");
  } else if (normalizedMode === "uncertainty") {
    if (isAsmaeOrHybrid) {
      if (realAsmae) {
        list.push("ASMAE_POSTERIOR_CONCENTRATION");
      }
      list.push("COMPOSITE_CONFIDENCE");
    }
    if (allowExp) {
      list.push("DATA_RELIABILITY_EXPERIMENTAL_FINE_DETAIL");
    }
    list.push("DATA_RELIABILITY", "DATA_CONFIDENCE", "UNCERTAINTY_SIGMA");
  } else if (normalizedMode === "resolution_coverage") {
    if (isAsmaeOrHybrid) {
      if (realAsmae) {
        list.push("RESOLUTION_ASMAE_EFFECTIVE");
      }
      list.push("COMPOSITE_EFFECTIVE_RESOLUTION");
    }
    if (allowExp) {
      list.push("RESOLUTION_COVERAGE_EXPERIMENTAL_FINE_DETAIL");
    }
    list.push("RESOLUTION_COVERAGE");
  }

  return list;
}

function hasAsmaeSupportForMode(
  mode: string,
  spatialPosteriorAvailable: boolean,
  proof: any,
  requestedPolicy?: string,
): boolean {
  if (!spatialPosteriorAvailable) return false;
  if (requestedPolicy === "asmae_diagnostic") return true;
  const ledger = proof?.state_support_ledger || {};
  const supported = (state: string) =>
    Number(ledger?.[state]?.accepted_update_count || 0) > 0;
  if (mode === "canopy") return supported("vigor");
  if (mode === "water") return supported("canopy_water") || supported("root_zone_water");
  if (mode === "nutrients") return supported("chlorophyll");
  if (mode === "salinity") return supported("salinity_stress");
  if (mode === "risk") {
    return proof?.bma_proof?.production_bma_valid === true
      && Number(proof?.retrovalidation_proof?.real_holdout_count || 0) > 0;
  }
  if (mode === "resolution_coverage") {
    return proof?.authority_proof?.field_approval_allowed === true
      && !proof?.resolution_proof?.missing_local_maps?.length;
  }
  if (mode === "uncertainty") return true;
  if (mode === "veg_attention") {
    return supported("vigor") || supported("stress_memory");
  }
  return false;
}

/** Keep resolver selection and map materialization on one render-kind contract. */
export function isRenderKindAllowedForRole(
  renderKind: RenderKind | string | null | undefined,
  role: RenderRole,
): boolean {
  if (role === "base") {
    return renderKind === "full_raster"
      || renderKind === "diagnostic_overlay"
      || renderKind === "proxy_overlay";
  }
  if (role === "overlay" || role === "candidate") {
    return renderKind === "proxy_overlay" || renderKind === "diagnostic_overlay";
  }
  return false;
}



export function resolveSourcePolicyDisplay(input: SourcePolicyDisplayResolverInput): SourcePolicyDisplayResolverOutput {
  const surfaces = Array.isArray(input.surfaces) ? input.surfaces : [];
  const requestedPolicy = input.requestedPolicy || "satellite";
  const activeMode = input.activeMode || "canopy";
  const asmaeEvidenceState = input.asmaeEvidenceState;
  const showExperimental1m = input.showExperimental1m ?? false;

  const normalized = normalizeMode(activeMode);

  // Multidimensional ASMAE state evaluation
  const spatialPosteriorAvailable =
    asmaeEvidenceState?.spatial_posterior_available === true ||
    asmaeEvidenceState?.spatialPosteriorAvailable === true ||
    asmaeEvidenceState?.real_asmae_evidence === true ||
    asmaeEvidenceState?.realAsmaeEvidence === true ||
    surfaces.some(s => s?.provenance?.real_asmae_evidence === true || s?.provenance?.realAsmaeEvidence === true || s?.provenance?.spatial_posterior_available === true);

  const realAsmae = hasAsmaeSupportForMode(
    normalized, spatialPosteriorAvailable, input.asmae_proof, requestedPolicy,
  );

  const priorities = getPriorityList(normalized, requestedPolicy, realAsmae, showExperimental1m);

  const activeResolution = resolveAuthorizedSurfaceForMode({
    surfaces,
    priorities,
    policy: requestedPolicy,
    mode: normalized,
    renderAuthorizations: input.renderAuthorizations,
  });
  const activeSurface = activeResolution.surface;
  const activeAuth = activeResolution.authorization;
  const blockedSurfaceType = activeSurface ? null : activeResolution.resolvedSurfaceType;
  const blockedReason = activeResolution.fallbackReason;

  let activeSurfaceType = activeSurface ? (activeSurface.type || activeSurface.semantic_type || null) : null;
  let renderKind: RenderKind = "none";
  let displayLevel: "raster" | "asmae_diagnostic" | "proxy" | "plot_level" | "unavailable" = "unavailable";
  let blockedCandidateSurfaceType: string | null = null;
  if (activeSurface) {
    renderKind = activeAuth?.renderKind || "none";
    const gc = activeSurface.grounding_class || "UNIFORM";
    const stype = String(activeSurfaceType || "").toUpperCase();
    if (gc === "RASTER_GROUNDED" || gc === "PARTIAL_RASTER_GROUNDED" || gc === "MODEL_ASSISTED_RASTER") {
      displayLevel = (isAsmaeSurfaceType(stype) || isCompositeAdvisorySurface(stype))
        ? "asmae_diagnostic"
        : "raster";
    } else if (gc === "PROXY_SPATIAL") {
      displayLevel = "proxy";
    } else {
      displayLevel = "plot_level";
    }
  } else if (blockedSurfaceType) {
    blockedCandidateSurfaceType = blockedSurfaceType;
    activeSurfaceType = null;
    renderKind = "card_only";
    displayLevel = "unavailable";
  }

  const stype = String(activeSurfaceType || blockedCandidateSurfaceType || "").toUpperCase();
  const isCompositeSurface = isCompositeAdvisorySurface(stype);
  const compositeEpistemicClass = String(
    activeSurface?.provenance?.epistemic_class || ""
  ).toLowerCase();
  const isModelPriorScouting =
    isCompositeSurface && compositeEpistemicClass === "model_prior_scouting_overlay";

  // derive footer labels
  let activeSourceLabel = "SATELLITE";
  if (isModelPriorScouting) {
    activeSourceLabel = "MODEL-PRIOR SCOUTING";
  } else if (isCompositeSurface) {
    activeSourceLabel = "MULTI-SENSOR COMPOSITE";
  } else if (stype.startsWith("ASMAE_VISUAL_FUSION") || stype === "ASMAE_VISUAL_FUSION_CANOPY") {
    activeSourceLabel = "ASMAE FUSION";
  } else if (isAsmaeSurfaceType(stype)) {
    activeSourceLabel = "ASMAE ADVISORY";
  } else if (isExperimentalSurfaceType(stype)) {
    activeSourceLabel = "EXPERIMENTAL";
  } else {
    activeSourceLabel = "SATELLITE";
  }

  const gc = activeSurface?.grounding_class || "UNIFORM";

  // Derive authority label from grounding or type
  let activeAuthorityLabel = "observed provider data";
  if (isModelPriorScouting) {
    activeAuthorityLabel = "Model-prior scouting overlay";
  } else if (isCompositeSurface) {
    activeAuthorityLabel = "Composite scouting raster";
  } else if (isExperimentalSurfaceType(stype)) {
    activeAuthorityLabel = "Experimental fine-detail model";
  } else if (isAsmaeSurfaceType(stype)) {
    activeAuthorityLabel = "ASMAE state posterior";
  } else {
    activeAuthorityLabel = "observed provider data";
  }

  const inspectorAuthorization = activeSurfaceType
    ? getRenderAuthorization(
        activeSurfaceType,
        requestedPolicy,
        normalized,
        "inspector",
        input.renderAuthorizations,
      )
    : null;
  const inspectorCapabilities = resolvePixelInspectorCapabilities({
    surface: activeSurface,
    inspectorAuthorization,
  });
  const {
    canSamplePixel,
    canInterpretForScouting,
    canInterpretDiagnostically,
    canUseForPrescription,
  } = inspectorCapabilities;
  // Compatibility aliases. Diagnosis is now strictly the backend-authorized
  // interpretation capability; sampling/scouting no longer promotes it.
  const canShowPixelHint = canSamplePixel;

  // Lock 4: policy-aware and materialization-aware experimental detail. A
  // backend ladder or a serialized surface is evidence, not a rendered layer.
  const materializedExperimentalType = input.experimentalMaterialization?.surfaceType || null;
  const hasMaterializedExperimentalSurface = !!materializedExperimentalType && surfaces.some((s: any) => {
    const type = String(s?.type || s?.semantic_type || "");
    return type === materializedExperimentalType && hasFiniteValues(s);
  });
  const experimentalRequested = requestedPolicy === "experimental" || requestedPolicy === "hybrid";
  const canShowExperimentalDetail = experimentalRequested
    && hasMaterializedExperimentalSurface
    && hasRenderedExperimentalOverlay(
      input.experimentalMaterialization,
      materializedExperimentalType,
      normalized,
    );

  const shouldShowNoData = !activeSurface || !hasFiniteValues(activeSurface);
  const shouldShowPlotLevel = !shouldShowNoData && (gc === "UNIFORM" || gc === "BROADCAST");

  // Derive grounding suffix
  let groundingDetail = "";
  if (isExperimentalSurfaceType(stype)) {
    if (gc === "PROXY_SPATIAL" || gc === "MODEL_ASSISTED_RASTER") {
      groundingDetail = "(Scouting Hint)";
    } else {
      groundingDetail = "";
    }
  } else if (shouldShowPlotLevel) {
    groundingDetail = "(Plot-Level)";
  } else if (isCompositeSurface) {
    groundingDetail = "(Scouting Overlay)";
  } else if (activeSurface) {
    if (gc === "PROXY_SPATIAL") {
      groundingDetail = "(Scouting Hint)";
    } else if (gc === "MODEL_ASSISTED_RASTER") {
      groundingDetail = "(Estimated Local Signal)";
    }
  }

  let bannerState: "composite_advisory_active" | "hybrid_active" | "asmae_diagnostic_active" | null = null;
  if (!!activeSurface && isCompositeSurface) {
    bannerState = requestedPolicy === "hybrid"
      ? "hybrid_active"
      : "composite_advisory_active";
  } else if (!!activeSurface && isAsmaeSurfaceType(activeSurfaceType)) {
    bannerState = "asmae_diagnostic_active";
  } else if (!!activeSurface && requestedPolicy === "hybrid") {
    bannerState = "hybrid_active";
  }

  const canShowPixelDiagnosis = canInterpretDiagnostically;

  const activeDisplay = {
    surface: activeSurface,
    surfaceType: activeSurfaceType,
    sourceLabel: activeSourceLabel,
    authorityLabel: activeAuthorityLabel,
    groundingDetail,
    renderKind,
    displayLevel,
    bannerState,
    canShowPixelDiagnosis,
    canShowPixelHint,
    canSamplePixel,
    canInterpretForScouting,
    canInterpretDiagnostically,
    canUseForPrescription,
    shouldShowPlotLevel,
    shouldShowNoData,
    canShowExperimentalDetail,
    reason: blockedReason || undefined
  };

  // Build availability mapping for all standard modes
  const surfaceAvailabilityByMode: Record<string, {
    surfaceType: string | null;
    status: "available_raster" | "available_overlay" | "card_only" | "unavailable_missing_proof" | "unavailable_missing_feature_family";
    levelLabel: string;
  }> = {};
  const standardModes = ["canopy", "water", "nutrients", "salinity", "risk", "veg_attention", "uncertainty", "resolution_coverage"];
  for (const m of standardModes) {
    const normMode = normalizeMode(m);
    const modePriorities = getPriorityList(
      normMode,
      requestedPolicy,
      hasAsmaeSupportForMode(
        normMode, spatialPosteriorAvailable, input.asmae_proof,
      ),
      showExperimental1m,
    );
    const modeResolution = resolveAuthorizedSurfaceForMode({
      surfaces,
      priorities: modePriorities,
      policy: requestedPolicy,
      mode: normMode,
      renderAuthorizations: input.renderAuthorizations,
    });
    const foundSurf = modeResolution.surface;
    const authObj = modeResolution.authorization;
    
    if (foundSurf && authObj) {
      const st = foundSurf.semantic_type || foundSurf.type;
      const experimentalSurfaceMaterialized = !isExperimentalSurfaceType(st)
        || hasRenderedExperimentalOverlay(input.experimentalMaterialization, st, normMode);
      if (authObj.authorized && authObj.renderKind === "full_raster" && experimentalSurfaceMaterialized) {
        surfaceAvailabilityByMode[m] = {
          surfaceType: st,
          status: "available_raster",
          levelLabel: isCompositeAdvisorySurface(st)
            ? "composite scouting diagnostic available"
            : isAsmaeSurfaceType(st) ? "ASMAE diagnostic available" : "raster"
        };
      } else if (
        authObj.authorized
        && authObj.renderKind === "full_raster"
        && isExperimentalSurfaceType(st)
        && !experimentalSurfaceMaterialized
      ) {
        surfaceAvailabilityByMode[m] = {
          surfaceType: st,
          status: "unavailable_missing_proof",
          levelLabel: "unavailable: experimental overlay not materialized"
        };
      } else if (
        authObj.authorized
        && (authObj.renderKind === "proxy_overlay"
          || authObj.renderKind === "diagnostic_overlay"
          || authObj.renderKind === "uniform_tint")
      ) {
        surfaceAvailabilityByMode[m] = {
          surfaceType: st,
          status: "available_overlay",
          levelLabel: authObj.renderKind === "uniform_tint"
            ? "plot-level tint"
            : authObj.renderKind === "proxy_overlay"
              ? "scouting overlay"
              : "diagnostic overlay",
        };
      } else if (authObj.renderKind === "card_only") {
        const reason = authObj.reason || "";
        if (isAsmaeSurfaceType(st)) {
          if (reason.startsWith("missing_water_")) {
            surfaceAvailabilityByMode[m] = {
              surfaceType: st,
              status: "unavailable_missing_feature_family",
              levelLabel: "unavailable: no NDMI/SAR/weather water proof"
            };
          } else if (reason.startsWith("missing_nutrient_")) {
            surfaceAvailabilityByMode[m] = {
              surfaceType: st,
              status: "unavailable_missing_feature_family",
              levelLabel: "unavailable: no red-edge/chlorophyll proof"
            };
          } else if (reason.startsWith("missing_salinity_")) {
            surfaceAvailabilityByMode[m] = {
              surfaceType: st,
              status: "unavailable_missing_feature_family",
              levelLabel: "unavailable: no SWIR/soil/salinity proof"
            };
          } else if (reason.startsWith("missing_risk_")) {
            surfaceAvailabilityByMode[m] = {
              surfaceType: st,
              status: "unavailable_missing_feature_family",
              levelLabel: "unavailable: no BMA/retro/uncertainty proof"
            };
          } else {
            surfaceAvailabilityByMode[m] = {
              surfaceType: st,
              status: "unavailable_missing_proof",
              levelLabel: "unavailable: no real proof"
            };
          }
        } else {
          surfaceAvailabilityByMode[m] = {
            surfaceType: st,
            status: "card_only",
            levelLabel: `card only: ${reason}`
          };
        }
      } else {
        surfaceAvailabilityByMode[m] = {
          surfaceType: st,
          status: "unavailable_missing_proof",
          levelLabel: "unavailable: no authorization"
        };
      }
    } else {
      surfaceAvailabilityByMode[m] = {
        surfaceType: null,
        status: "unavailable_missing_proof",
        levelLabel: "Plot-level estimate"
      };
    }
  }

  surfaceAvailabilityByMode.water_stress = surfaceAvailabilityByMode.water;
  surfaceAvailabilityByMode.nutrient_risk = surfaceAvailabilityByMode.nutrients;
  surfaceAvailabilityByMode.composite_risk = surfaceAvailabilityByMode.risk;
  surfaceAvailabilityByMode.vegetation_attention = surfaceAvailabilityByMode.veg_attention;

  surfaceAvailabilityByMode.water = surfaceAvailabilityByMode.water || surfaceAvailabilityByMode.water_stress;
  surfaceAvailabilityByMode.nutrients = surfaceAvailabilityByMode.nutrients || surfaceAvailabilityByMode.nutrient_risk;
  surfaceAvailabilityByMode.risk = surfaceAvailabilityByMode.risk || surfaceAvailabilityByMode.composite_risk;

  return {
    activeDisplay,
    surfaceAvailabilityByMode,
    activeSurface: activeDisplay.surface,
    activeSurfaceType: activeDisplay.surfaceType,
    activeSourceLabel: activeDisplay.sourceLabel,
    activeAuthorityLabel: activeDisplay.authorityLabel,
    bannerState: activeDisplay.bannerState,
    canShowPixelDiagnosis: activeDisplay.canShowPixelDiagnosis,
    canShowPixelHint: activeDisplay.canShowPixelHint,
    canSamplePixel: activeDisplay.canSamplePixel,
    canInterpretForScouting: activeDisplay.canInterpretForScouting,
    canInterpretDiagnostically: activeDisplay.canInterpretDiagnostically,
    canUseForPrescription: activeDisplay.canUseForPrescription,
    canShowExperimentalDetail: activeDisplay.canShowExperimentalDetail,
    shouldShowNoData: activeDisplay.shouldShowNoData,
    shouldShowPlotLevel: activeDisplay.shouldShowPlotLevel
  };
}
