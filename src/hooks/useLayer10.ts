"use client";

import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  type ReactNode,
  createElement,
} from "react";

import {
  resolvePlotMapEvidenceState,
  getModeAvailability,
  buildSurfaceInventory,
  buildOverlayAvailability,
  resolveModeSurfaceSource,
  type PlotMapEvidenceState,
  type ModeAvailability,
  type BaseSurfaceMode,
  type OverlayKind,
  type OverlayToggles,
  type OverlayAvailability,
  type SurfaceInventoryItem,
  DEFAULT_EVIDENCE_STATE,
  DEFAULT_OVERLAY_TOGGLES,
  OVERLAY_LABELS,
} from "@/lib/agribrain/plot-map-evidence-state";
import {
  hasRenderedExperimentalOverlay,
  resolveSourcePolicyDisplay,
} from "@/lib/agribrain/source-policy-display-resolver";
import {
  isRenderedMaterialization,
  isZoneSpatiallyAuthorized,
  resolveRenderMaterialization,
  type BrowserRenderReceipt,
  type RenderMaterializationResult,
} from "@/lib/agribrain/render-materialization";
import { normalizeCanonicalPhenologyPublication } from "@/lib/agribrain/phenology-authority.mjs";
import {
  browserRenderReceiptSignature,
  buildLayer10RequestIdentity,
  buildRenderViewIdentity,
  classifyCanonicalHeadValidation,
  isLatestLayer10Request,
  normalizeSourcePolicy,
  resolveCompoundRenderAttribution,
  shouldRetainLastKnownGood,
  type SourcePolicy,
} from "@/lib/agribrain/layer10-request-state.mjs";
import {
  buildAsmaeLiveStateDetail,
  buildAsmaeRefreshFailedDetail,
  patchLayer10AsmaeCompletion,
  patchLayer10AsmaeFailure,
  patchLayer10AsmaeLiveState,
} from "@/lib/agribrain/asmae-job-state.mjs";


// ============================================================================
// TYPES
// ============================================================================

export type MapMode =
  | "vegetation"  // Compatibility alias → treated as canopy
  | "canopy"
  | "veg_attention"
  | "water_stress"
  | "nutrient_risk"
  | "salinity"
  | "composite_risk"
  | "uncertainty"
  | "resolution_coverage";  // V61: categorical resolution class overlay

export interface CanonicalRenderPlan {
  readonly viewIdentity: string;
  readonly requestedPolicy: "satellite" | "experimental" | "asmae_diagnostic" | "hybrid";
  readonly resolvedBaseSurface: string | null;
  readonly resolvedOverlaySurface: string | null;
  readonly baseMaterialization: RenderMaterializationResult;
  readonly overlayMaterialization: RenderMaterializationResult;
  readonly authoritativeLadder: {
    sourceEvidenceResolutionM: number;
    displayGridResolutionM: number;
    displayGridFootprintPct: number;
    textureAppliedPct: number;
    unvalidatedCandidatePct: number;
    validatedFineDetailPct: number;
    fieldApproved1mPct: number;
    status?: string;
    authority: "scouting_only";
  };
  readonly fallbackReason: string | null;
}

export interface SurfaceGridSpec {
  crs?: string;
  transform?: number[];
  width?: number;
  height?: number;
  bounds?: number[];
  resolution?: number;
}

export interface SurfaceData {
  surface_id: string;
  type: string;
  semantic_type?: string;
  values: (number | null)[][];
  grounding_class: string;
  units: string;
  render_range: [number, number];
  palette_id: string;
  source_layers: string[];
  provenance: Record<string, unknown>;
  raster_basis?: string[];
  observed_ratio?: number;
  // V92.4: GIS grid specification for spatial alignment
  grid_spec?: SurfaceGridSpec | null;
  display_grid_spec?: SurfaceGridSpec | null;
  source_grid_spec?: SurfaceGridSpec | null;
  render_kind?: string | null;
  display_level?: string | null;
  source_reality?: string | null;
  diagnostic_only?: boolean | null;
  state_update_allowed?: boolean | null;
  prescription_driver_allowed?: boolean | null;
  confidence?: number | null;
  uncertainty?: number | null;
  authority_block_reason?: string | null;
}

export interface ZoneData {
  zone_id: string;
  label: string;
  zone_type: string;
  zone_family?: string;
  area_fraction: number;
  cell_indices: [number, number][];
  severity: number;
  confidence: number;
  confidence_reasons: string[];
  top_drivers: string[];
  linked_actions: string[];
  surface_stats: Record<string, Record<string, number>>;
  source_dominance?: string;
  source_surface_type?: string;
  evidence_age_days?: number;
  trust_note?: string;
  is_inferred?: boolean;
  calculation_trace?: Record<string, unknown>;
  authority?: "management_zone" | "algorithmic_scouting_region" | "plot_level_heterogeneity_notice" | string;
  grid_validity?: string | { valid?: boolean; status?: string; reason?: string };
  observed_cell_share?: number;
  gap_filled_share?: number;
  confidence_basis?: string | string[];
  authority_block_reason?: string | null;
}

export interface HistogramData {
  surface_type: string;
  region_id?: string;
  bin_edges: number[];
  bin_counts: number[];
  mean: number;
  std: number;
  p10?: number;
  p90?: number;
  valid_pixels?: number;
  total_pixels?: number;
}

export interface DeltaHistogramData {
  surface_type: string;
  date_from: string;
  date_to: string;
  bin_edges: number[];
  bin_counts: number[];
  mean_change: number;
  shift_direction: string;
}

export interface DriverWeight {
  name: string;
  value: number;
  role: "positive" | "negative" | "uncertainty";
}

export interface ModelEquation {
  label: string;
  expression: string;
  plain_language: string;
}

export interface ExplainabilityProvenance {
  sources: string[];
  timestamps: string[];
  model_version: string;
  run_id: string;
  degraded_reasons: string[];
}

export interface ConfidencePenalty {
  reason: string;
  impact: number;
}

export interface ExplainabilityConfidence {
  score: number;
  penalties: ConfidencePenalty[];
  quality_scored_layers: string[];
}

export interface ExplainabilityPack {
  summary: string;
  top_drivers: DriverWeight[];
  equations: ModelEquation[];
  charts: Record<string, unknown>;
  provenance: ExplainabilityProvenance;
  confidence: ExplainabilityConfidence;
  dominant_driver?: string;
  evidence?: string[];
  recommended_action?: string;
  driver_confidence?: number;
  action_level?: string;
}

export interface ScenarioOutcome {
  label: string;
  value: string;
  sentiment: "positive" | "negative" | "neutral";
}

export interface ScenarioDefinition {
  title: string;
  description: string;
  outcomes: ScenarioOutcome[];
  val_at_risk?: number;
  cost_of_action?: number;
  yield_impact_pct?: number;
}

export interface HistoryEvent {
  timestamp: string;
  type: "USER_ACTION" | "SYSTEM" | "EXTERNAL";
  title: string;
  description: string;
}

// V60B: Ground Truth Registry Summary Types
export interface ResolutionPercentages {
  three_cm_pct: number;
  one_meter_pct: number;
  fallback_pct: number;
  three_cm_external_ground_truth_pct: number;
  one_meter_advisory_pct: number;
  two_meter_model_assisted_pct?: number;
  three_meter_model_assisted_pct?: number;
  five_meter_model_assisted_pct?: number;
  adaptive_production_fallback_pct: number;
}

export interface GroundTruthDrone3cm {
  status: string;
  coverage_pct: number;
  gsd_m: number;
  scope: string;
}

export interface GroundTruthCertification {
  three_cm_allowed: boolean;
  one_meter_certified: boolean;
  state_updates_blocked: boolean;
}

export interface GroundTruthEvidenceSource {
  type: string;
  status: string;
  scope: string;
}

export interface GroundTruthSummary {
  resolution_percentages: ResolutionPercentages;
  drone_3cm: GroundTruthDrone3cm;
  certification_decision: GroundTruthCertification;
  evidence_sources: GroundTruthEvidenceSource[];
}

export interface Layer10Result {
  run_id: string;
  publication_id?: string;
  plot_id: string;
  timestamp: string;
  surfaces: SurfaceData[];
  zones: ZoneData[];
  histograms: {
    field: HistogramData[];
    zone: HistogramData[];
    delta: DeltaHistogramData[];
    uncertainty: HistogramData[];
  };
  quicklooks: Record<string, string>;
  raster_pack: Record<string, unknown>[];
  vector_pack: Record<string, unknown>[];
  tile_manifest: Record<string, unknown>;
  quality: {
    degradation_mode: string;
    reliability_score: number;
    surfaces_generated: number;
    zones_generated: number;
    grid_alignment_ok: boolean | null;
    detail_conservation_ok: boolean | null;
    zone_state_by_surface: Record<string, string>;
    warnings: string[];
    coverage_ratio?: number;  // optional: fraction of field grid with valid pixel coverage
  };
  rendering_quality?: Record<string, unknown>;
  scientific_pipeline_quality?: Record<string, unknown>;
  global_quality?: Record<string, unknown>;
  layer_results?: Record<string, {
    status?: string;
    run_id?: string;
    errors?: string[];
    degradation_flags?: string[];
    confidence?: number;
    sources?: string[];
  }>;
  provenance: Record<string, unknown>;
  resolved_crop_stage?: string;
  phenology_context?: {
    resolved_crop_stage?: string;
    phenology_evidence_class?: string;
    phenology_authority?: string;
    phenology_source?: string;
    phenology_confidence?: number;
    phenology_posterior_hash?: string;
    phenology_receipt_valid?: boolean;
    phenology_evidence_needed_reason?: string;
    stage_available?: boolean;
    season_anchor_status?: string;
    calibration_status?: string;
    effective_at?: string;
    crop_cycle_id?: string | null;
    contract_version?: string;
  };
  grid: { height: number; width: number };
  explainability_pack: Record<string, ExplainabilityPack>;
  scenario_pack?: ScenarioDefinition[];
  history_pack?: HistoryEvent[];
  fallback_guidance?: Record<string, FallbackGuidance>;

  // V60B: Ground Truth Registry Summary
  ground_truth_summary?: GroundTruthSummary;

  // V61D: Latest Free Visual Basemap Provider
  visual_source?: {
    status: "available" | "fallback" | "esri_basemap";
    provider: string;
    collection: string;
    native_resolution_m: number;
    scene_date: string;
    tile_url: string;
    is_mock: boolean;
    role: string;
    state_update_allowed: boolean;
    used_for_agronomic_inference: boolean;
    fallback_reason?: string;
  };
  
  // Plot Intelligence Injections
  timeline?: any;
  engines?: any[];
  current?: any;
  rawData?: any;
  assimilation?: any;

  // V92.4: Mode surface plan and surface inventory
  mode_surface_plan?: Record<string, {
    selected_surface_type: string | null;
    source_class: string;
    spatial: boolean;
    fallback_rank: number;
    reason: string;
    trust_badges: string[];
  }>;
  surface_inventory?: Record<string, any>;
  surface_inventory_hash?: string;
  // V92.4-BC: Backend-authoritative display state per mode
  mode_display_state?: Record<string, any>;
  source_policy_display_state?: Record<string, any>;
  asmae_evidence_state?: any;
  asmae_feature_pack?: any;
  render_authorizations?: any;
  render_authorization_version?: string;
  intelligence_snapshot_id?: string;
  agribrain_run_id?: string;
  generated_at?: string;
  source_window?: [string, string];
  surface_schema_version?: string;
  temporal_evidence_contract_version?: string;
  asmae_proof?: any;
  surface_behavior_proof?: any;
  display_trace?: any;
  /** Browser acquisition identity; never used as scientific provenance. */
  request_identity?: string;
  requested_source_policy?: SourcePolicy;
  requested_visual_intensity?: number;
}

export interface FallbackGuidance {
  action_mode: "field_wide" | "plot_level_only" | "insufficient_data" | "scouting_only";
  recommended_next_step: string;
  why: string;
  confidence: number;
  data_basis: string;
  displayed_surface_type?: string;
  guidance_surface_type?: string;
  guidance_relation?: "same_surface" | "separate_operational_surface";
}

export type MapSemantics = "plot_level" | "field_wide" | "localized_alert" | "management_zone" | "no_data";

export const MAP_SEMANTICS_LABELS: Record<MapSemantics, string> = {
  plot_level: "Plot-level estimate",
  field_wide: "Field-wide condition",
  localized_alert: "Localized alert zones",
  management_zone: "Scouting regions",
  no_data: "No spatial data",
};

// ============================================================================
// MODE → SURFACE TYPE MAPPING
// ============================================================================

export const MODE_SURFACE_MAP: Record<MapMode, string> = {
  vegetation: "NDVI_CLEAN",       // Alias → canopy
  canopy: "NDVI_CLEAN",
  veg_attention: "NDVI_DEVIATION",
  water_stress: "WATER_STRESS_PROB",
  nutrient_risk: "NUTRIENT_STRESS_PROB",
  salinity: "SALINITY_STRESS",
  composite_risk: "COMPOSITE_RISK",
  uncertainty: "DATA_RELIABILITY",
  resolution_coverage: "RESOLUTION_COVERAGE",  // V61
};

export function modeFromSurfaceType(surfaceType: string): string {
  if (!surfaceType) return "";
  const cleanType = surfaceType.replace("_EXPERIMENTAL_FINE_DETAIL", "");
  if (cleanType.includes("NDVI_CLEAN") || cleanType.includes("CANOPY")) return "canopy";
  if (cleanType.includes("NDVI_DEVIATION") || cleanType.includes("BASELINE_ANOMALY") || cleanType.includes("VEG_ATTENTION")) return "veg_attention";
  if (cleanType.includes("WATER_STRESS") || cleanType.includes("WATER_ASMAE")) return "water_stress";
  if (cleanType.includes("NUTRIENT_STRESS") || cleanType.includes("NUTRIENT_ASMAE")) return "nutrient_risk";
  if (cleanType.includes("SALINITY")) return "salinity";
  if (cleanType.includes("COMPOSITE_RISK") || cleanType.includes("RISK_ASMAE")) return "composite_risk";
  if (cleanType.includes("DATA_RELIABILITY") || cleanType.includes("DATA_CONFIDENCE") || cleanType.includes("UNCERTAINTY_SIGMA") || cleanType.includes("POSTERIOR_CONCENTRATION") || cleanType.includes("CONFIDENCE_ASMAE")) return "uncertainty";
  if (cleanType.includes("RESOLUTION_COVERAGE") || cleanType.includes("RESOLUTION_ASMAE")) return "resolution_coverage";
  return "";
}

export const EXPERIMENTAL_DETAIL_BY_MODE = {
  canopy: "NDVI_CLEAN_EXPERIMENTAL_FINE_DETAIL",
  vegetation: "NDVI_CLEAN_EXPERIMENTAL_FINE_DETAIL",
  veg_attention: "NDVI_DEVIATION_EXPERIMENTAL_FINE_DETAIL",
  water_stress: "WATER_STRESS_PROB_EXPERIMENTAL_FINE_DETAIL",
  nutrient_risk: "NUTRIENT_STRESS_PROB_EXPERIMENTAL_FINE_DETAIL",
  salinity: "SALINITY_STRESS_EXPERIMENTAL_FINE_DETAIL",
  composite_risk: "COMPOSITE_RISK_EXPERIMENTAL_FINE_DETAIL",
  uncertainty: "DATA_RELIABILITY_EXPERIMENTAL_FINE_DETAIL",
  resolution_coverage: "RESOLUTION_COVERAGE_EXPERIMENTAL_FINE_DETAIL",
};

export function getExperimentalSurfaceType(activeMode: string, activeSurfaceType: string): string {
  const modeKey = activeMode === "vegetation" ? "canopy" : activeMode;
  return (
    EXPERIMENTAL_DETAIL_BY_MODE[modeKey as keyof typeof EXPERIMENTAL_DETAIL_BY_MODE] ||
    (activeSurfaceType ? EXPERIMENTAL_DETAIL_BY_MODE[modeFromSurfaceType(activeSurfaceType) as keyof typeof EXPERIMENTAL_DETAIL_BY_MODE] : undefined) ||
    `${activeSurfaceType}_EXPERIMENTAL_FINE_DETAIL`
  );
}

export const MODE_ZONE_SURFACE_MAP: Record<MapMode, string> = {
  vegetation: "",                  // Alias → canopy (no zone promise)
  canopy: "",                      // No zone promise in canopy mode
  veg_attention: "NDVI_DEVIATION",
  water_stress: "WATER_STRESS_PROB",
  nutrient_risk: "NUTRIENT_STRESS_PROB",
  salinity: "SALINITY_STRESS",
  composite_risk: "COMPOSITE_RISK",
  uncertainty: "DATA_RELIABILITY",
  resolution_coverage: "",  // V61: no zone promise for resolution mode
};

export const MODE_CONFIG: Record<
  MapMode,
  { label: string; icon: string; colors: [string, string, string] }
> = {
  vegetation: {
    label: "Canopy",
    icon: "🌿",
    colors: ["#FF0000", "#FFFF00", "#00CC00"],
  },
  canopy: {
    label: "Canopy",
    icon: "🌿",
    colors: ["#FF0000", "#FFFF00", "#00CC00"],
  },
  veg_attention: {
    label: "Vegetation Attention",
    icon: "🎯",
    colors: ["#8B4513", "#F5F5DC", "#228B22"],  // Brown → neutral → green diverging
  },
  water_stress: {
    label: "Water",
    icon: "💧",
    colors: ["#1a5276", "#f39c12", "#e74c3c"],
  },
  nutrient_risk: {
    label: "Nutrients",
    icon: "🧪",
    colors: ["#27ae60", "#f1c40f", "#c0392b"],
  },
  salinity: {
    label: "Salinity",
    icon: "🧂",
    colors: ["#0d9488", "#22d3ee", "#ef4444"],
  },
  composite_risk: {
    label: "Risk",
    icon: "⚠️",
    colors: ["#2ecc71", "#e67e22", "#e74c3c"],
  },
  uncertainty: {
    label: "Confidence",
    icon: "🔍",
    colors: ["#e74c3c", "#f1c40f", "#2ecc71"],
  },
  resolution_coverage: {
    label: "Resolution",
    icon: "📐",
    colors: ["#06b6d4", "#f59e0b", "#64748b"],  // cyan → amber → slate
  },
};

// ============================================================================
// NORMALIZERS
// ============================================================================

/**
 * Decode a base64-encoded Float32Array grid into a 2D array.
 * NaN values in the buffer are converted to null.
 * This is ~6× more compact than nested JSON number arrays over the wire.
 */
function decodeGridB64(b64: string, width: number, height: number): (number | null)[][] {
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  const float32 = new Float32Array(bytes.buffer);

  const grid: (number | null)[][] = [];
  for (let r = 0; r < height; r++) {
    const row: (number | null)[] = [];
    for (let c = 0; c < width; c++) {
      const v = float32[r * width + c];
      row.push(Number.isNaN(v) ? null : v);
    }
    grid.push(row);
  }
  return grid;
}

function normalizeSurface(raw: Record<string, any>): SurfaceData {
  // Support compact binary grid format: grid_b64 + grid_width + grid_height
  let values: (number | null)[][] = [];
  if (raw.grid_b64 && raw.grid_width && raw.grid_height) {
    values = decodeGridB64(raw.grid_b64, raw.grid_width, raw.grid_height);
  } else if (Array.isArray(raw.values)) {
    values = raw.values;
  }

  return {
    surface_id: String(raw.surface_id || "").trim(),
    type: raw.type ?? raw.semantic_type ?? "",
    semantic_type: raw.semantic_type ?? raw.type ?? "",
    values,
    grounding_class: raw.grounding_class ?? "UNIFORM",
    units: raw.units ?? "",
    render_range: Array.isArray(raw.render_range)
      ? [Number(raw.render_range[0] ?? 0), Number(raw.render_range[1] ?? 1)]
      : [0, 1],
    palette_id: raw.palette_id ?? "viridis",
    source_layers: Array.isArray(raw.source_layers) ? raw.source_layers : [],
    provenance: raw.provenance ?? {},
    raster_basis: Array.isArray(raw.raster_basis) ? raw.raster_basis : [],
    observed_ratio: raw.observed_ratio != null ? Number(raw.observed_ratio) : 0,
    // V92.4: GIS grid_spec pass-through
    grid_spec: raw.grid_spec || null,
    display_grid_spec: raw.display_grid_spec || null,
    source_grid_spec: raw.source_grid_spec || null,
    render_kind: raw.render_kind ?? raw.renderKind ?? null,
    display_level: raw.display_level ?? raw.displayLevel ?? null,
    source_reality: raw.source_reality ?? raw.provenance?.source_reality ?? null,
    diagnostic_only: raw.diagnostic_only ?? raw.provenance?.diagnostic_only ?? null,
    state_update_allowed: raw.state_update_allowed ?? raw.provenance?.state_update_allowed ?? null,
    prescription_driver_allowed:
      raw.prescription_driver_allowed ?? raw.provenance?.prescription_driver_allowed ?? null,
    confidence: raw.confidence ?? raw.provenance?.confidence ?? null,
    uncertainty: raw.uncertainty ?? raw.provenance?.uncertainty ?? null,
    authority_block_reason: raw.authority_block_reason ?? raw.provenance?.authority_block_reason ?? null,
  };
}

function normalizeHistogram(raw: Record<string, any>): HistogramData {
  return {
    surface_type: raw.surface_type ?? "",
    region_id: raw.region_id,
    bin_edges: Array.isArray(raw.bin_edges) ? raw.bin_edges.map(Number) : [],
    bin_counts: Array.isArray(raw.bin_counts) ? raw.bin_counts.map(Number) : [],
    mean: Number(raw.mean ?? 0),
    std: Number(raw.std ?? 0),
    p10: raw.p10 != null ? Number(raw.p10) : undefined,
    p90: raw.p90 != null ? Number(raw.p90) : undefined,
    valid_pixels: raw.valid_pixels != null ? Number(raw.valid_pixels) : undefined,
    total_pixels: raw.total_pixels != null ? Number(raw.total_pixels) : undefined,
  };
}

function normalizeDeltaHistogram(raw: Record<string, any>): DeltaHistogramData {
  return {
    surface_type: raw.surface_type ?? "",
    date_from: raw.date_from ?? "",
    date_to: raw.date_to ?? "",
    bin_edges: Array.isArray(raw.bin_edges) ? raw.bin_edges.map(Number) : [],
    bin_counts: Array.isArray(raw.bin_counts) ? raw.bin_counts.map(Number) : [],
    mean_change: Number(raw.mean_change ?? 0),
    shift_direction: raw.shift_direction ?? "STABLE",
  };
}

function normalizeZone(raw: Record<string, any>): ZoneData {
  return {
    zone_id: raw.zone_id ?? "",
    label: raw.label ?? raw.description ?? raw.zone_id ?? "",
    zone_type: raw.zone_type ?? "UNKNOWN",
    zone_family: raw.zone_family,
    area_fraction: Number(raw.area_fraction ?? raw.area_pct ?? 0),
    cell_indices: Array.isArray(raw.cell_indices) ? raw.cell_indices : [],
    severity: Number(raw.severity ?? 0),
    confidence: Number(raw.confidence ?? 0),
    confidence_reasons: Array.isArray(raw.confidence_reasons) ? raw.confidence_reasons : [],
    top_drivers: Array.isArray(raw.top_drivers) ? raw.top_drivers : [],
    linked_actions: Array.isArray(raw.linked_actions) ? raw.linked_actions : [],
    surface_stats: raw.surface_stats ?? {},
    source_dominance: raw.source_dominance,
    source_surface_type: raw.source_surface_type ?? '',
    evidence_age_days:
      raw.evidence_age_days != null ? Number(raw.evidence_age_days) : undefined,
    trust_note: raw.trust_note,
    is_inferred: raw.is_inferred,
    calculation_trace: raw.calculation_trace ?? {},
    authority: raw.authority,
    grid_validity: raw.grid_validity,
    observed_cell_share:
      raw.observed_cell_share != null ? Number(raw.observed_cell_share) : undefined,
    gap_filled_share:
      raw.gap_filled_share != null ? Number(raw.gap_filled_share) : undefined,
    confidence_basis: raw.confidence_basis,
    authority_block_reason: raw.authority_block_reason ?? null,
  };
}

function deriveGrid(
  explicitGrid: any,
  surfaces: SurfaceData[]
): { height: number; width: number } {
  if (
    explicitGrid &&
    typeof explicitGrid.height === "number" &&
    typeof explicitGrid.width === "number"
  ) {
    return explicitGrid;
  }

  const first = surfaces[0];
  const height = first?.values?.length ?? 0;
  const width =
    height > 0 && Array.isArray(first.values[0]) ? first.values[0].length : 0;

  return { height, width };
}

const DEGRADATION_SEVERITY: Record<string, number> = {
  NORMAL: 0,
  LOW_SAR_CADENCE: 1,
  LOW_RESOLUTION: 1,
  NO_SAR: 2,
  L1_ONLY: 2,
  NO_DOWNSTREAM: 2,
  NO_OPTICAL: 3,
  PARTIAL_DATA: 3,
  NO_SPATIAL: 3,
  DATA_GAP: 3,
  DEGRADED: 4,
  CRITICAL: 5,
  CRITICAL_FAILURE: 5,
};

function qualityRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {};
}

function validReliability(value: unknown): number | null {
  const score = Number(value);
  return Number.isFinite(score) && score >= 0 && score <= 1 ? score : null;
}

function degradationSeverity(mode: string): number {
  if (mode in DEGRADATION_SEVERITY) return DEGRADATION_SEVERITY[mode];
  return mode === "NORMAL" ? 0 : 3;
}

function stringArray(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string" && item.trim().length > 0)
    : [];
}

export function reconcileQualitySignals(localValue: unknown, globalValue: unknown): {
  degradationMode: string;
  reliabilityScore: number;
  warnings: string[];
} {
  const local = qualityRecord(localValue);
  const global = qualityRecord(globalValue);
  const localMode = String(local.degradation_mode || "NORMAL").toUpperCase();
  const globalModes = stringArray(global.degradation_modes).map((mode) => mode.toUpperCase());
  const dataHealthStatus = String(global.data_health_status || "").trim().toLowerCase();
  if (["unusable", "invalid", "failed", "critical"].includes(dataHealthStatus)) {
    globalModes.push("CRITICAL_FAILURE");
  } else if (["degraded", "partial", "stale"].includes(dataHealthStatus)) {
    globalModes.push("DEGRADED");
  }
  if (global.critical_failure === true && !globalModes.includes("CRITICAL_FAILURE")) {
    globalModes.push("CRITICAL_FAILURE");
  }
  const degradationMode = [localMode, ...globalModes].reduce((worst, candidate) =>
    degradationSeverity(candidate) > degradationSeverity(worst) ? candidate : worst,
  "NORMAL");

  const reliabilityCandidates = [
    validReliability(local.reliability_score),
    validReliability(global.reliability),
    validReliability(global.confidence_ceiling),
  ].filter((score): score is number => score !== null);

  return {
    degradationMode,
    reliabilityScore: reliabilityCandidates.length > 0
      ? Math.min(...reliabilityCandidates)
      : 0,
    warnings: Array.from(new Set([
      ...stringArray(local.warnings),
      ...stringArray(global.critical_errors),
      ...stringArray(global.alerts),
    ])),
  };
}

// ============================================================================
// CONTEXT & PROVIDER
// ============================================================================

export interface Layer10FetchOptions {
  forceRefresh?: boolean;
  experimental1m?: boolean;
  visualIntensity?: number;
  /** Requested local display policy; the returned publication remains canonical. */
  sourcePolicy?: SourcePolicy;
  snapshotId?: string;
}

export interface Layer10ContextType {
  data: Layer10Result | null;
  loading: boolean;
  error: string | null;
  activeMode: MapMode;
  detailMode: "farmer" | "expert";
  selectedZone: string | null;
  histogramExpanded: boolean;
  isDecideMode: boolean;
  setActiveMode: (mode: MapMode) => void;
  setDetailMode: (mode: "farmer" | "expert") => void;
  setSelectedZone: (zoneId: string | null) => void;
  setHistogramExpanded: (exp: boolean) => void;
  setIsDecideMode: (exp: boolean) => void;
  decideModeQuery: string | null;
  openDecideMode: (query?: string) => void;
  fetchLayer10: (plotId: string, farmId: string, lat?: number, lng?: number, crop?: string, options?: Layer10FetchOptions) => Promise<void>;
  activeDisplay: any;
  activeSurface: SurfaceData | null;
  committedSurface: SurfaceData | null;
  activeSurfaceMaterialized: boolean;
  activeConfidenceSurface: SurfaceData | null;
  activeReliabilitySurface: SurfaceData | null;
  activeHistogram: HistogramData | null;
  activeDelta: DeltaHistogramData | null;
  activeColors: [string, string, string];
  activeSurfaceType: string;
  activeZoneSurfaceType: string;
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
  surfaceAvailabilityByMode: Record<string, any>;
  plotDataAvailable: boolean;
  spatialSurfaceAvailable: boolean;
  localizedZoneAvailable: boolean;
  fallbackGuidance: FallbackGuidance | null;
  mapSemantics: MapSemantics;
  showExperimental1m: boolean;
  setShowExperimental1m: (show: boolean) => void;
  experimentalBaseActive: boolean;
  experimentalOverlayEnabled: boolean;
  showCandidateMask: boolean;
  setShowCandidateMask: (show: boolean) => void;
  experimental1mGenerating: boolean;
  setExperimental1mGenerating: (gen: boolean) => void;
  visualIntensity: number;
  setVisualIntensity: (val: number) => void;
  experimental1mSurfaceActive: boolean;
  experimental1mSurfaceMissingForMode: boolean;
  evidenceState: PlotMapEvidenceState;
  modeAvailability: Record<string, ModeAvailability> | null;
  // V92.3-C: True overlay architecture
  baseSurfaceMode: BaseSurfaceMode;
  setBaseSurfaceMode: (mode: BaseSurfaceMode) => void;
  overlayToggles: OverlayToggles;
  setOverlayToggle: (kind: OverlayKind, value: boolean) => void;
  overlayAvailability: OverlayAvailability | null;
  surfaceInventory: Record<string, SurfaceInventoryItem> | null;
  surfaceByType: Record<string, SurfaceData>;
  activeOverlayCount: number;
  overlayConflictWarning: string | null;
  activeExperimentalSurface: SurfaceData | null;
  activeExperimentalSurfaceType: string | null;
  candidateMaskSurface: SurfaceData | null;
  experimentalCoveragePct: number;
  canopySource: SourcePolicy;
  setCanopySource: (src: SourcePolicy) => void;
  experimentalDisplayState: "active" | "partial" | "base_fallback_experimental_missing" | "disabled";
  tierACoverage: number | null;
  tierBCoverage: number | null;
  tierCCoverage: number | null;
  experimentalVisualLadder: {
    sourceEvidenceResolutionM: number;
    displayGridResolutionM: number;
    displayGridFootprintPct: number;
    textureAppliedPct: number;
    unvalidatedCandidatePct: number;
    validatedFineDetailPct: number;
    fieldApproved1mPct: number;
    status?: string;
    authority: "scouting_only";
  } | null;
  asmaeApprovalLadder: {
    oneMeterAsmaeApprovalPct: number | null;
    modelAssisted2_5mPct: number | null;
    generalized5mPct: number | null;
    unavailableReason?: string | null;
  } | null;
  asmae_evidence_state: any;
  renderPlan: CanonicalRenderPlan;
  renderMaterialization: RenderMaterializationResult | null;
  experimentalRenderMaterialization: RenderMaterializationResult | null;
  browserRenderReceipt: BrowserRenderReceipt | null;
  commitBrowserRenderReceipt: (receipt: BrowserRenderReceipt) => void;
  clearBrowserRenderReceipt: (viewIdentity: string) => void;
}

function canonicalPublicationToRunData(cacheJson: any, plotId: string) {
  return {
    run_id: cacheJson.publication_run_id || cacheJson.agribrain_run_id || cacheJson.run_id || cacheJson.runId || "",
    publication_id: cacheJson.publication_id || cacheJson.publicationId || "",
    plot_id: plotId,
    timestamp: cacheJson.capturedAt,
    surfaces: cacheJson.surfaceGrids || [],
    zones: cacheJson.zones || [],
    histograms: cacheJson.histograms || {},
    quality: cacheJson.quality || {},
    global_quality: cacheJson.global_quality || undefined,
    fallback_guidance: cacheJson.fallback_guidance || {},
    explainability_pack: cacheJson.explainability_pack || {},
    ground_truth_summary: cacheJson.ground_truth_summary || undefined,
    visual_source: cacheJson.visual_source || undefined,
    provenance: { source: "canonical_publication", age_ms: cacheJson.ageMs, ...cacheJson.provenance },
    mode_surface_plan: cacheJson.mode_surface_plan || {},
    surface_inventory: cacheJson.surface_inventory || {},
    surface_inventory_hash: cacheJson.surface_inventory_hash || "",
    mode_display_state: cacheJson.mode_display_state || {},
    source_policy_display_state: cacheJson.source_policy_display_state || {},
    asmae_evidence_state: cacheJson.asmae_evidence_state || null,
    asmae_feature_pack: cacheJson.asmae_feature_pack || {},
    render_authorizations: cacheJson.render_authorizations || {},
    render_authorization_version: cacheJson.render_authorization_version || "",
    intelligence_snapshot_id: cacheJson.intelligence_snapshot_id || cacheJson.snapshot_id || "",
    agribrain_run_id: cacheJson.agribrain_run_id || "",
    generated_at: cacheJson.generated_at || cacheJson.capturedAt,
    source_window: cacheJson.source_window,
    surface_schema_version: cacheJson.surface_schema_version || cacheJson.schema_version,
    temporal_evidence_contract_version: cacheJson.temporal_evidence_contract_version || "",
    asmae_proof: cacheJson.asmae_proof || {},
    surface_behavior_proof: cacheJson.surface_behavior_proof || {},
    display_trace: cacheJson.display_trace || {},
    resolved_crop_stage: cacheJson.resolved_crop_stage || cacheJson.crop_phenology?.resolved_crop_stage || cacheJson.phenology_context?.resolved_crop_stage || null,
    phenology_context: cacheJson.phenology_context || cacheJson.crop_phenology || null,
    crop_phenology: cacheJson.crop_phenology || null,
  };
}

const Layer10Context = createContext<Layer10ContextType | null>(null);

export function Layer10Provider({
  children,
  plotGeoJson: rawPlotGeoJson = null,
}: {
  children: ReactNode;
  plotGeoJson?: unknown;
}) {
  const [publication, setPublication] = useState<{
    data: Layer10Result | null;
    error: string | null;
  }>({ data: null, error: null });
  const data = publication.data;
  const error = publication.error;
  const [loading, setLoading] = useState(false);
  const [detailMode, setDetailMode] = useState<"farmer" | "expert">("farmer");
  const [selectedZone, setSelectedZone] = useState<string | null>(null);
  const [histogramExpanded, setHistogramExpanded] = useState(false);
  const [isDecideMode, setIsDecideMode] = useState(false);
  const [decideModeQuery, setDecideModeQuery] = useState<string | null>(null);
  const [showCandidateMask, setShowCandidateMask] = useState(false);
  const [experimental1mGenerating, setExperimental1mGenerating] = useState(false);
  const [visualIntensity, setVisualIntensityState] = useState(0.40);
  const visualIntensityRef = useRef(visualIntensity);
  const setVisualIntensity = useCallback((value: number) => {
    visualIntensityRef.current = value;
    setVisualIntensityState(value);
  }, []);
  const requestSequenceRef = useRef(0);
  const activeRequestControllerRef = useRef<AbortController | null>(null);
  const canonicalCompletionFetchRef = useRef("");
  const [browserRenderReceiptState, setBrowserRenderReceiptState] = useState<BrowserRenderReceipt | null>(null);
  const renderViewIdentityRef = useRef("");
  const commitBrowserRenderReceipt = useCallback((receipt: BrowserRenderReceipt) => {
    if (!receipt.viewIdentity || receipt.viewIdentity !== renderViewIdentityRef.current) {
      return;
    }
    setBrowserRenderReceiptState((previous) =>
      browserRenderReceiptSignature(previous) === browserRenderReceiptSignature(receipt)
        ? previous
        : receipt,
    );
  }, []);
  const clearBrowserRenderReceipt = useCallback((viewIdentity: string) => {
    setBrowserRenderReceiptState((previous) =>
      previous?.viewIdentity === viewIdentity ? null : previous,
    );
  }, []);
  const plotGeoJson = useMemo(() => {
    if (!rawPlotGeoJson) return null;
    if (typeof rawPlotGeoJson !== "string") return rawPlotGeoJson;
    try {
      return JSON.parse(rawPlotGeoJson);
    } catch {
      return null;
    }
  }, [rawPlotGeoJson]);

  // V92.3-C: True overlay architecture state
  // baseSurfaceMode is the source of truth. activeMode is a derived backward-compat alias.
  const [baseSurfaceMode, setBaseSurfaceModeRaw] = useState<BaseSurfaceMode>("canopy");
  const [overlayToggles, setOverlayTogglesRaw] = useState<OverlayToggles>({ ...DEFAULT_OVERLAY_TOGGLES });
  const [canopySource, setCanopySourceRaw] = useState<SourcePolicy>(
    DEFAULT_OVERLAY_TOGGLES.experimentalDetail ? "experimental" : "satellite"
  );
  const canopySourceRef = useRef<SourcePolicy>(canopySource);
  const setCanopySource = useCallback((value: SourcePolicy) => {
    const src = normalizeSourcePolicy(value);
    canopySourceRef.current = src;
    setCanopySourceRaw(src);
    if (src === "satellite" || src === "asmae_diagnostic") {
      setOverlayTogglesRaw(prev => ({ ...prev, experimentalDetail: false }));
      setShowCandidateMask(false);
    } else if (src === "experimental") {
      setOverlayTogglesRaw(prev => ({ ...prev, experimentalDetail: true }));
      setShowCandidateMask(false);
    }
  }, []);

  const showExperimental1m = canopySource === "experimental" || canopySource === "hybrid";
  const experimentalBaseActive = canopySource === "experimental";
  const experimentalOverlayAllowed = canopySource === "experimental" || canopySource === "hybrid";
  const experimentalOverlayEnabled = experimentalOverlayAllowed && overlayToggles.experimentalDetail === true;

  const setShowExperimental1m = useCallback((value: boolean) => {
    // V92.4-BC.10.6: Experimental checkbox ONLY toggles overlay detail,
    // NEVER mutates canopySource / source policy.
    setOverlayTogglesRaw(prev => ({ ...prev, experimentalDetail: value }));
  }, []);

  const activeMode = (baseSurfaceMode === "canopy" ? "canopy" : baseSurfaceMode) as MapMode;

  // setBaseSurfaceMode: update the source of truth
  const setBaseSurfaceMode = useCallback((mode: BaseSurfaceMode) => {
    setBaseSurfaceModeRaw(mode);
  }, []);

  // setActiveMode: backward-compat wrapper that updates baseSurfaceMode or overlay toggles
  const setActiveMode = useCallback((mode: MapMode) => {
    const BASE_MODES: BaseSurfaceMode[] = ["canopy", "water_stress", "nutrient_risk", "salinity", "composite_risk", "veg_attention"];
    if (BASE_MODES.includes(mode as BaseSurfaceMode)) {
      setBaseSurfaceModeRaw(mode as BaseSurfaceMode);
    } else if (mode === "vegetation") {
      setBaseSurfaceModeRaw("canopy");
    } else if (mode === "uncertainty") {
      // Toggle confidence overlay on, keep current base
      setOverlayTogglesRaw(prev => ({ ...prev, confidence: true }));
    } else if (mode === "resolution_coverage") {
      // Toggle resolution overlay on, keep current base
      setOverlayTogglesRaw(prev => ({ ...prev, resolution: true }));
    }
  }, []);

  // setOverlayToggle: update a single overlay toggle
  const setOverlayToggle = useCallback((kind: OverlayKind, value: boolean) => {
    setOverlayTogglesRaw(prev => ({ ...prev, [kind]: value }));
  }, []);


  const openDecideMode = useCallback((query?: string) => {
    setDecideModeQuery(query || null);
    setIsDecideMode(true);
  }, []);

  useEffect(() => {
    return () => {
      requestSequenceRef.current += 1;
      activeRequestControllerRef.current?.abort();
      activeRequestControllerRef.current = null;
    };
  }, []);

  const fetchLayer10 = useCallback(
    async (
      plotId: string,
      _farmId: string,
      _lat?: number,
      _lng?: number,
      _crop?: string,
      options?: Layer10FetchOptions
    ) => {
      const sequence = requestSequenceRef.current + 1;
      requestSequenceRef.current = sequence;
      activeRequestControllerRef.current?.abort();
      const controller = new AbortController();
      activeRequestControllerRef.current = controller;

      const requestedPolicy = normalizeSourcePolicy(
        options?.sourcePolicy,
        canopySourceRef.current,
      );
      const requestedIntensity = options?.visualIntensity ?? visualIntensityRef.current;
      const isExperimentalRequest = options?.experimental1m === true;
      const requestIdentity = buildLayer10RequestIdentity({
        sequence,
        plotId,
        sourcePolicy: requestedPolicy,
        visualIntensity: requestedIntensity,
        experimental1m: isExperimentalRequest,
      });
      const isLatestRequest = () =>
        isLatestLayer10Request(
          requestSequenceRef.current,
          sequence,
          controller.signal.aborted,
        );

      setExperimental1mGenerating(isExperimentalRequest);
      setLoading(!isExperimentalRequest);
      setPublication((previous) => ({ ...previous, error: null }));

      try {
        // ── CACHE-FIRST: Try loading cached surfaces instantly ──────
        let runData: any = null;
        let usedCache = false;

        try {
          if (options?.snapshotId && options?.forceRefresh) {
            throw new Error("Cannot force-refresh an immutable snapshot.");
          }

          if (!options?.forceRefresh) {
            const cacheRes = await fetch("/api/agribrain/surfaces/latest", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              signal: controller.signal,
              body: JSON.stringify({
                plotId,
                visualIntensity: requestedIntensity,
                sourcePolicy: requestedPolicy,
                snapshotId: options?.snapshotId,
              }),
            });
            const cacheJson = await cacheRes.json();
            if (!isLatestRequest()) return;

            if (options?.snapshotId && (
              !cacheRes.ok || cacheJson.available === false || cacheJson.status !== "fresh"
            )) {
              throw new Error(
                `Exact snapshot ${options.snapshotId} unavailable or superseded: ${cacheJson.reason || cacheRes.status}`,
              );
            }

            if (cacheJson.reason === "canonical_head_validation_failed" || cacheRes.status === 409) {
              throw new Error(cacheJson.error || "Canonical publication head failed integrity validation");
            }

            if (
              cacheRes.ok
              && cacheJson.available !== false
              && cacheJson.status === "fresh"
            ) {
              const validation = cacheJson.validation || {};
              const validationState = classifyCanonicalHeadValidation(validation);
              if (validationState !== "valid") {
                throw new Error(
                  validationState === "corrupt"
                    ? "Canonical publication head integrity validation failed"
                    : "Canonical publication head contract is stale",
                );
              }
              runData = canonicalPublicationToRunData(cacheJson, plotId);
              usedCache = true;
            }
          }
        } catch (cacheError) {
          if (!isLatestRequest()) return;
          // An exact completion request must not silently start a new run or
          // substitute a different publication when its snapshot is missing.
          if (options?.snapshotId) throw cacheError;
          if (
            cacheError instanceof Error
            && cacheError.message.toLowerCase().includes("canonical publication head")
          ) {
            throw cacheError;
          }
          // Cache endpoint failed — fall through to live run
        }

        // ── LIVE RUN: Only if cache missed ─────────────────────────
        if (!runData) {
          if (options?.snapshotId) {
            throw new Error(`Exact snapshot ${options.snapshotId} was not found; execution fallback is denied.`);
          }
          const res = await fetch("/api/agribrain/run", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            signal: controller.signal,
            body: JSON.stringify({
              plotId,
              mode: "surfaces",
              query: "",
              forceRefresh: options?.forceRefresh || false,
              experimental1m: options?.experimental1m || false,
              visualIntensity: requestedIntensity,
              sourcePolicy: requestedPolicy,
            }),
          });
          if (!isLatestRequest()) return;

          const json = await res.json();
          if (!isLatestRequest()) return;

          if (!res.ok || json.error || json.success === false) {
            throw new Error(json.error || "AgriBrain surfaces pipeline failed");
          }

          // `/run` is an execution trigger only. Scientific browser state is
          // accepted exclusively from a validated canonical publication head.
          for (let attempt = 0; attempt < 40 && isLatestRequest(); attempt += 1) {
            const publicationRes = await fetch("/api/agribrain/surfaces/latest", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              cache: "no-store",
              signal: controller.signal,
              body: JSON.stringify({ plotId }),
            });
            const publicationJson = await publicationRes.json();
            if (!isLatestRequest()) return;
            if (
              publicationRes.status === 409
              || publicationJson.reason === "canonical_head_validation_failed"
            ) {
              throw new Error(
                publicationJson.error
                || "Canonical publication head failed integrity validation",
              );
            }
            if (
              publicationRes.ok
              && publicationJson.available !== false
              && publicationJson.status === "fresh"
            ) {
              const validation = publicationJson.validation || {};
              if (classifyCanonicalHeadValidation(validation) !== "valid") {
                throw new Error("Canonical publication head validation is incomplete");
              }
              runData = canonicalPublicationToRunData(publicationJson, plotId);
              break;
            }
            const workerStatus = String(
              publicationJson.workerState?.workerState?.status
              || publicationJson.workerState?.status
              || "",
            ).toLowerCase();
            if (["failed", "superseded"].includes(workerStatus)) {
              throw new Error(
                publicationJson.workerState?.workerState?.error
                || publicationJson.workerState?.error
                || `ASMAE publication failed (${workerStatus})`,
              );
            }
            await new Promise<void>((resolve, reject) => {
              const onAbort = () => {
                clearTimeout(timer);
                reject(new DOMException("Aborted", "AbortError"));
              };
              const timer = setTimeout(() => {
                controller.signal.removeEventListener("abort", onAbort);
                resolve();
              }, 1500);
              controller.signal.addEventListener("abort", onAbort, { once: true });
            });
          }
          if (!runData) {
            throw new Error("Canonical publication is still pending");
          }
        }
        if (!isLatestRequest()) return;

        const surfaces = Array.isArray(runData.surfaces)
          ? runData.surfaces.map((surface: Record<string, any>) => normalizeSurface(surface))
          : [];
        const reconciledQuality = reconcileQualitySignals(
          runData.quality,
          runData.global_quality,
        );
        const normalizedPhenology = normalizeCanonicalPhenologyPublication({
          resolvedCropStage: runData.resolved_crop_stage,
          phenologyContext: runData.phenology_context,
        });

        const mapped: Layer10Result = {
          run_id: runData.run_id || "",
          publication_id: runData.publication_id || "",
          plot_id: runData.plot_id || plotId,
          timestamp: runData.timestamp || runData.audit?.timestamp_utc || "",

          surfaces,

          zones: Array.isArray(runData.zones)
            ? runData.zones.map(normalizeZone)
            : [],

          histograms: {
            field: Array.isArray(runData.histograms?.field)
              ? runData.histograms.field.map(normalizeHistogram)
              : [],
            zone: Array.isArray(runData.histograms?.zone)
              ? runData.histograms.zone.map(normalizeHistogram)
              : [],
            delta: Array.isArray(runData.histograms?.delta)
              ? runData.histograms.delta.map(normalizeDeltaHistogram)
              : [],
            uncertainty: Array.isArray(runData.histograms?.uncertainty)
              ? runData.histograms.uncertainty.map(normalizeHistogram)
              : [],
          },

          quicklooks: runData.quicklooks ?? {},
          raster_pack: Array.isArray(runData.raster_pack) ? runData.raster_pack : [],
          vector_pack: Array.isArray(runData.vector_pack) ? runData.vector_pack : [],
          tile_manifest: runData.tile_manifest ?? {},

          quality: {
            degradation_mode: reconciledQuality.degradationMode,
            reliability_score: reconciledQuality.reliabilityScore,
            surfaces_generated:
              Number(runData.quality?.surfaces_generated ?? surfaces.length),
            zones_generated:
              Number(runData.quality?.zones_generated ?? runData.zones?.length ?? 0),
            grid_alignment_ok: typeof runData.quality?.grid_alignment_ok === "boolean"
              ? runData.quality.grid_alignment_ok
              : null,
            detail_conservation_ok: typeof runData.quality?.detail_conservation_ok === "boolean"
              ? runData.quality.detail_conservation_ok
              : null,
            zone_state_by_surface: runData.quality?.zone_state_by_surface || {},
            warnings: reconciledQuality.warnings,
          },
          rendering_quality: runData.rendering_quality ?? runData.quality ?? {},
          scientific_pipeline_quality: runData.scientific_pipeline_quality ?? runData.global_quality ?? {},
          global_quality: runData.global_quality ?? runData.scientific_pipeline_quality ?? {},
          layer_results: runData.layer_results ?? {},

          provenance: runData.provenance ?? runData.audit ?? {},
          resolved_crop_stage: normalizedPhenology.resolvedCropStage,
          phenology_context: normalizedPhenology.phenologyContext,
          grid: deriveGrid(runData.grid, surfaces),
          explainability_pack: runData.explainability_pack ?? {},
          scenario_pack: runData.scenario_pack ?? [],
          history_pack: runData.history_pack ?? [],
          fallback_guidance: runData.fallback_guidance ?? {},

          // V60B: Ground Truth Registry Summary
          ground_truth_summary: runData.ground_truth_summary ?? undefined,

          // V61D: Latest Free Visual Basemap Provider
          visual_source: runData.visual_source ?? undefined,

          timeline: runData.timeline,
          engines: runData.engines,
          current: runData.current,
          rawData: runData.rawData,
          assimilation: runData.assimilation,

          // V92.4: Mode surface plan and surface inventory
          mode_surface_plan: runData.mode_surface_plan ?? {},
          surface_inventory: runData.surface_inventory ?? {},
          surface_inventory_hash: runData.surface_inventory_hash ?? "",
          // V92.4-BC: Backend-authoritative display state per mode
          mode_display_state: runData.mode_display_state ?? {},
          source_policy_display_state: runData.source_policy_display_state ?? {},
          asmae_evidence_state: runData.asmae_evidence_state ?? runData.source_policy_display_state?.asmaeEvidenceState ?? null,
          asmae_feature_pack: runData.asmae_feature_pack ?? {},
          render_authorizations: runData.render_authorizations ?? {},
          render_authorization_version: runData.render_authorization_version ?? "",
          intelligence_snapshot_id: runData.intelligence_snapshot_id ?? "",
          agribrain_run_id: runData.agribrain_run_id ?? runData.run_id ?? "",
          generated_at: runData.generated_at ?? runData.timestamp,
          source_window: runData.source_window,
          surface_schema_version: runData.surface_schema_version ?? runData.schema_version,
          temporal_evidence_contract_version: runData.temporal_evidence_contract_version ?? "",
          asmae_proof: runData.asmae_proof ?? {},
          surface_behavior_proof: runData.surface_behavior_proof ?? {},
          display_trace: runData.display_trace ?? {},
          request_identity: requestIdentity,
          requested_source_policy: requestedPolicy,
          requested_visual_intensity: requestedIntensity,
        };

        // Immutable LKG Promotion: If current run returns 0 surfaces (degraded result),
        // preserve the entire previous renderable LKG publication without merging new metadata.
        setPublication((previous) => {
          if (!isLatestLayer10Request(
            requestSequenceRef.current,
            sequence,
            controller.signal.aborted,
          )) {
            return previous;
          }
          if (shouldRetainLastKnownGood(previous.data, mapped, plotId)) {
            return {
              data: previous.data,
              error: "Degraded refresh — retaining last-known-good publication",
            };
          }
          return { data: mapped, error: null };
        });

        if (isExperimentalRequest) {
          setShowExperimental1m(true);
        }

        // If we used stale cache, the background refresh is already in progress.
        // When the user manually refreshes, it will get fresh data.
        if (usedCache) {
          console.log("[Layer10] Rendered from cache (instant)");
        }
      } catch (e) {
        if (!isLatestRequest()) return;
        setPublication((previous) =>
          isLatestLayer10Request(
            requestSequenceRef.current,
            sequence,
            controller.signal.aborted,
          )
            ? {
                ...previous,
                error: e instanceof Error ? e.message : "Unknown error",
              }
            : previous,
        );
      } finally {
        if (isLatestRequest()) {
          setLoading(false);
          setExperimental1mGenerating(false);
          activeRequestControllerRef.current = null;
        }
      }
    },
    [setShowExperimental1m] // One canonical science snapshot serves every client-side display policy.
  );

  // 1. Test fixture state
  const isTestFixtureActive = useMemo(() => {
    if (typeof window === "undefined") return false;
    return window.location.search.includes("test_override=true") || (window as any).__ASMAE_TEST_FIXTURE__ === true;
  }, []);

  // 2. Raw base active types
  const rawActiveSurfaceType = useMemo(() => {
    return resolveModeSurfaceSource(data, activeMode);
  }, [data, activeMode]);

  // The exact experimental surface is resolved before any coverage claim so
  // stale materialization from another mode cannot authorize this mode.
  const surfaceByType = useMemo(() => {
    if (!data) return {} as Record<string, SurfaceData>;
    const map: Record<string, SurfaceData> = {};
    for (const surface of data.surfaces) map[surface.type] = surface;
    return map;
  }, [data]);

  const activeExperimentalSurfaceType = useMemo(() => {
    const plannedType = getExperimentalSurfaceType(activeMode, rawActiveSurfaceType);
    const modeKey = activeMode === "vegetation" ? "canopy" : activeMode;
    const candidates = modeKey === "canopy"
      ? [
          "EXPERIMENTAL_VISUAL_CANOPY_HIGHRES",
          plannedType,
          "EXPERIMENTAL_VISUAL_CANOPY",
        ]
      : [plannedType];
    return candidates.find((type) => !!surfaceByType[type]) || plannedType;
  }, [activeMode, rawActiveSurfaceType, surfaceByType]);

  const activeExperimentalSurface = useMemo(() => {
    return surfaceByType[activeExperimentalSurfaceType] || null;
  }, [surfaceByType, activeExperimentalSurfaceType]);

  const experimentalRenderPreflight = useMemo(() => {
    const observedMaskSurface = surfaceByType["OBSERVED_DATA_MASK_NDVI"]
      || surfaceByType["OBSERVED_MASK"]
      || surfaceByType["VALID_DATA_MASK"]
      || surfaceByType["OBSERVED_DATA_MASK"]
      || surfaceByType["CANONICAL_OBSERVED_MASK"]
      || null;
    const gapFillMaskSurface = surfaceByType["GAP_FILL_MASK_NDVI"]
      || surfaceByType["GAP_FILL_MASK"]
      || null;
    const preflight = resolveRenderMaterialization({
      surface: activeExperimentalSurface,
      plotGeoJson,
      policy: "experimental",
      mode: activeMode,
      role: "overlay",
      renderAuthorizationVersion: data?.render_authorization_version,
      renderAuthorizations: data?.render_authorizations,
      observedMaskSurface,
      gapFillMaskSurface,
      modeDisplayState: {
        spatial: true,
        canRenderPixels: true,
        renderKind: "proxy_overlay",
      },
      layerId: "l10-surface-experimental-fine-detail",
    });
    return showExperimental1m
      ? preflight
      : ({ ...preflight, status: "blocked_image_generation" as const, reason: "overlay_not_requested", layerId: null });
  }, [
    activeExperimentalSurface,
    activeMode,
    data?.render_authorization_version,
    data?.render_authorizations,
    plotGeoJson,
    showExperimental1m,
  ]);

  useEffect(() => {
    const handleRefreshProgress = (e: Event) => {
      const customEvt = e as CustomEvent;
      setPublication((previous) => ({
        ...previous,
        data: patchLayer10AsmaeLiveState(previous.data, customEvt.detail),
      }));
    };
    const handleRefreshCompleted = (e: Event) => {
      const customEvt = e as CustomEvent;
      const targetPlotId = customEvt.detail?.plotId;
      const finalSnapshotId = customEvt.detail?.finalSnapshotId;
      if (targetPlotId) {
        const completionIdentity = [
          targetPlotId,
          finalSnapshotId || `job:${customEvt.detail?.jobId || "unknown"}`,
        ].join(":");
        if (canonicalCompletionFetchRef.current === completionIdentity) return;
        canonicalCompletionFetchRef.current = completionIdentity;
        setPublication((previous) => ({
          ...previous,
          data: patchLayer10AsmaeCompletion(previous.data, customEvt.detail),
        }));
        void fetchLayer10(targetPlotId, "", undefined, undefined, undefined, {
          forceRefresh: false,
          snapshotId: finalSnapshotId,
        });
      }
    };
    const handleRefreshFailed = (e: Event) => {
      const customEvt = e as CustomEvent;
      setPublication((previous) => ({
        ...previous,
        data: patchLayer10AsmaeFailure(previous.data, customEvt.detail),
      }));
    };
    if (typeof window !== "undefined") {
      window.addEventListener("agribrain:refresh_progress", handleRefreshProgress);
      window.addEventListener("agribrain:refresh_completed", handleRefreshCompleted);
      window.addEventListener("agribrain:refresh_failed", handleRefreshFailed);
    }
    return () => {
      if (typeof window !== "undefined") {
        window.removeEventListener("agribrain:refresh_progress", handleRefreshProgress);
        window.removeEventListener("agribrain:refresh_completed", handleRefreshCompleted);
        window.removeEventListener("agribrain:refresh_failed", handleRefreshFailed);
      }
    };
  }, [fetchLayer10]);

  // A provider publication remains visible while spatial ASMAE runs in the
  // background. Observe that durable job here, in the persistent data owner,
  // rather than relying on the transient initial-loading overlay.
  const observedAsmaePlotId = String(data?.plot_id || "");
  const observedAsmaePlotState = data?.source_policy_display_state?.asmaePlotState;
  const observedAsmaeJobId = String(observedAsmaePlotState?.activeSpatialJobId || "");
  const observedAsmaeJobStatus = String(
    observedAsmaePlotState?.activeSpatialJobStatus || ""
  ).toLowerCase();
  const observedAsmaePublicationRelation = String(
    observedAsmaePlotState?.publicationRelation || ""
  ).toLowerCase();
  useEffect(() => {
    const awaitingCanonicalPublication = observedAsmaeJobStatus === "completed"
      && observedAsmaePublicationRelation !== "published";
    if (
      !observedAsmaePlotId
      || !observedAsmaeJobId
      || (
        !["queued", "running", "stalled", "completed_reintegration_pending"].includes(observedAsmaeJobStatus)
        && !awaitingCanonicalPublication
      )
    ) {
      return;
    }

    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | null = null;
    const controller = new AbortController();
    const poll = async () => {
      try {
        const response = await fetch(
          `/api/agribrain/progress?plotId=${encodeURIComponent(observedAsmaePlotId)}`,
          { cache: "no-store", signal: controller.signal },
        );
        if (!response.ok || stopped) return;
        const progress = await response.json();
        if (stopped) return;

        const live = buildAsmaeLiveStateDetail(progress, observedAsmaePlotId);
        if (live) {
          setPublication((previous) => ({
            ...previous,
            data: patchLayer10AsmaeLiveState(previous.data, live),
          }));
        }
        const failure = buildAsmaeRefreshFailedDetail(
          progress,
          observedAsmaePlotId,
        );
        if (failure) {
          setPublication((previous) => ({
            ...previous,
            data: patchLayer10AsmaeFailure(previous.data, failure),
          }));
          return;
        }
        if (
          live?.status === "completed"
          && live.publicationRelation === "published"
        ) {
          const completionIdentity = [
            observedAsmaePlotId,
            live.finalSnapshotId || `job:${live.jobId || "unknown"}`,
          ].join(":");
          if (canonicalCompletionFetchRef.current === completionIdentity) return;
          canonicalCompletionFetchRef.current = completionIdentity;
          setPublication((previous) => ({
            ...previous,
            data: patchLayer10AsmaeCompletion(previous.data, live),
          }));
          await fetchLayer10(
            observedAsmaePlotId,
            "",
            undefined,
            undefined,
            undefined,
            { forceRefresh: false, snapshotId: live.finalSnapshotId },
          );
          return;
        }
      } catch (error) {
        if ((error as Error)?.name === "AbortError") return;
      }
      if (!stopped) timer = setTimeout(poll, 1500);
    };

    void poll();
    return () => {
      stopped = true;
      controller.abort();
      if (timer) clearTimeout(timer);
    };
  }, [
    fetchLayer10,
    observedAsmaeJobId,
    observedAsmaeJobStatus,
    observedAsmaePublicationRelation,
    observedAsmaePlotId,
  ]);

  const renderViewIdentity = useMemo(() => buildRenderViewIdentity({
    publicationId: [
      data?.publication_id || "unpublished",
      data?.intelligence_snapshot_id || "snapshot_missing",
      data?.surface_inventory_hash || "inventory_missing",
      data?.render_authorization_version || "authorization_missing",
    ].join("@"),
    plotId: data?.plot_id,
    sourcePolicy: canopySource,
    mode: activeMode,
    surfaceType: rawActiveSurfaceType,
    surfaceId: rawActiveSurfaceType ? surfaceByType[rawActiveSurfaceType]?.surface_id : "",
    overlaySurfaceType: activeExperimentalSurfaceType,
    overlaySurfaceId: activeExperimentalSurface?.surface_id,
    overlayEnabled: experimentalOverlayEnabled,
  }), [
    activeExperimentalSurfaceType,
    activeExperimentalSurface?.surface_id,
    activeMode,
    canopySource,
    data?.agribrain_run_id,
    data?.intelligence_snapshot_id,
    data?.plot_id,
    data?.publication_id,
    data?.surface_inventory_hash,
    data?.render_authorization_version,
    data?.run_id,
    experimentalOverlayEnabled,
    rawActiveSurfaceType,
    surfaceByType,
  ]);
  renderViewIdentityRef.current = renderViewIdentity;

  const browserRenderReceipt = browserRenderReceiptState?.viewIdentity === renderViewIdentity
    ? browserRenderReceiptState
    : null;
  const experimentalRenderMaterialization =
    browserRenderReceipt?.overlayMaterialization || experimentalRenderPreflight;

  const exactExperimentalMaterialization = hasRenderedExperimentalOverlay(
    experimentalRenderMaterialization,
    activeExperimentalSurfaceType,
    activeMode,
  );

  // 3. Experimental visual ladder (needed by resolver). This is canonical
  // scientific metadata and remains available independently of visibility;
  // materialization is tracked separately below.
  const experimentalVisualLadder = useMemo(() => {
    const backend = data?.source_policy_display_state?.experimentalVisualLadder;
    if (!backend || typeof backend !== "object") {
      return {
        sourceEvidenceResolutionM: 10,
        displayGridResolutionM: 10,
        displayGridFootprintPct: 0,
        textureAppliedPct: 0,
        unvalidatedCandidatePct: 0,
        validatedFineDetailPct: 0,
        fieldApproved1mPct: 0,
        status: "blocked_missing_authoritative_ladder",
        authority: "scouting_only" as const,
      };
    }
    const percent = (value: unknown): number => {
      const numeric = Number(value);
      return Number.isFinite(numeric) ? Math.max(0, Math.min(100, numeric)) : 0;
    };
    return {
      sourceEvidenceResolutionM: Number(backend.sourceEvidenceResolutionM) || 10,
      displayGridResolutionM: Number(backend.displayGridResolutionM) || 10,
      displayGridFootprintPct: percent(backend.displayGridFootprintPct),
      textureAppliedPct: percent(backend.textureAppliedPct),
      unvalidatedCandidatePct: percent(backend.unvalidatedCandidatePct),
      validatedFineDetailPct: percent(backend.validatedFineDetailPct),
      fieldApproved1mPct: percent(backend.fieldApproved1mPct),
      status: typeof backend.status === "string"
        ? backend.status
        : exactExperimentalMaterialization
          ? "authoritative_rendered"
          : "authoritative_not_materialized",
      authority: "scouting_only" as const,
    };
  }, [data, exactExperimentalMaterialization]);

  // 4. ASMAE evidence state (needed by resolver)
  const asmae_evidence_state = useMemo(() => {
    const rawState = data?.asmae_evidence_state ?? null;
    if (rawState && rawState.test_override === true && !isTestFixtureActive) {
      return {
        ...rawState,
        state: "unavailable",
        real_asmae_evidence: false,
        visual_fusion_allowed: false,
        current_1m_approval_allowed: false,
        reason: "test_override_blocked_in_production"
      };
    }
    return rawState;
  }, [data, isTestFixtureActive]);

  // 5. Authoritative display state via resolver
  const displayResolution = useMemo(() => {
    return resolveSourcePolicyDisplay({
      surfaces: data?.surfaces || [],
      requestedPolicy: canopySource,
      activeMode,
      sourcePolicyDisplayState: data?.source_policy_display_state,
      asmaeEvidenceState: asmae_evidence_state,
      experimentalVisualLadder,
      showExperimental1m,
      asmae_proof: data?.asmae_proof,
      renderAuthorizations: data?.render_authorizations,
      experimentalMaterialization: experimentalRenderMaterialization,
    });
  }, [
    data,
    canopySource,
    activeMode,
    asmae_evidence_state,
    experimentalVisualLadder,
    showExperimental1m,
    experimentalRenderMaterialization,
  ]);

  const {
    activeDisplay,
    surfaceAvailabilityByMode
  } = displayResolution;

  const {
    surface: activeSurface,
    surfaceType: resolvedActiveSurfaceType,
    sourceLabel: candidateSourceLabel,
    authorityLabel: candidateAuthorityLabel,
    bannerState: candidateBannerState,
    canShowPixelDiagnosis,
    canShowPixelHint,
    canSamplePixel,
    canInterpretForScouting,
    canInterpretDiagnostically,
    canUseForPrescription,
    canShowExperimentalDetail,
    shouldShowNoData,
    shouldShowPlotLevel
  } = activeDisplay;

  const activeSurfaceType = resolvedActiveSurfaceType || "";
  const activeZoneSurfaceType = MODE_ZONE_SURFACE_MAP[activeMode] || "";

  const baseRenderPreflight = useMemo(() => {
    const observedMaskSurface = surfaceByType["OBSERVED_DATA_MASK_NDVI"]
      || surfaceByType["OBSERVED_MASK"]
      || surfaceByType["VALID_DATA_MASK"]
      || surfaceByType["OBSERVED_DATA_MASK"]
      || surfaceByType["CANONICAL_OBSERVED_MASK"]
      || null;
    const gapFillMaskSurface = surfaceByType["GAP_FILL_MASK_NDVI"]
      || surfaceByType["GAP_FILL_MASK"]
      || null;
    const preflight = resolveRenderMaterialization({
      surface: activeSurface,
      plotGeoJson,
      policy: canopySource,
      mode: activeMode,
      role: "base",
      renderAuthorizationVersion: data?.render_authorization_version,
      renderAuthorizations: data?.render_authorizations,
      observedMaskSurface,
      gapFillMaskSurface,
      modeDisplayState: {
        spatial: activeDisplay?.renderKind === "full_raster"
          || activeDisplay?.renderKind === "diagnostic_overlay"
          || activeDisplay?.renderKind === "proxy_overlay",
        canRenderPixels: activeDisplay?.renderKind === "full_raster"
          || activeDisplay?.renderKind === "diagnostic_overlay"
          || activeDisplay?.renderKind === "proxy_overlay",
        renderKind: activeDisplay?.renderKind,
        reason: activeDisplay?.reason,
      },
      layerId: "l10-surface-semantic",
    });
    return preflight;
  }, [
    activeDisplay?.reason,
    activeDisplay?.renderKind,
    activeMode,
    activeSurface,
    canopySource,
    data?.render_authorization_version,
    data?.render_authorizations,
    plotGeoJson,
    surfaceByType,
  ]);

  const renderMaterialization =
    browserRenderReceipt?.baseMaterialization || baseRenderPreflight;

  const renderPlan = useMemo<CanonicalRenderPlan>(() => Object.freeze({
    viewIdentity: renderViewIdentity,
    requestedPolicy: canopySource,
    resolvedBaseSurface: activeSurfaceType || null,
    resolvedOverlaySurface: experimentalRenderMaterialization.status === "rendered"
      ? experimentalRenderMaterialization.surfaceType || null
      : null,
    baseMaterialization: Object.freeze({ ...renderMaterialization }),
    overlayMaterialization: Object.freeze({ ...experimentalRenderMaterialization }),
    authoritativeLadder: Object.freeze({ ...experimentalVisualLadder }),
    fallbackReason: activeDisplay?.reason || null,
  }), [
    activeDisplay?.reason,
    activeSurfaceType,
    canopySource,
    experimentalRenderMaterialization,
    experimentalVisualLadder,
    renderViewIdentity,
    renderMaterialization,
  ]);

  const activeSurfaceMaterialized = isRenderedMaterialization(renderMaterialization, activeSurfaceType);
  const compoundAttribution = resolveCompoundRenderAttribution({
    baseRendered: activeSurfaceMaterialized,
    overlayRendered: exactExperimentalMaterialization,
    baseSourceLabel: candidateSourceLabel,
    baseAuthorityLabel: candidateAuthorityLabel,
  });
  const activeSourceLabel = compoundAttribution.sourceLabel;
  const activeAuthorityLabel = compoundAttribution.authorityLabel;
  const bannerState = activeSurfaceMaterialized ? candidateBannerState : null;
  const committedActiveDisplay = useMemo(() => activeSurfaceMaterialized
    ? activeDisplay
    : {
        ...activeDisplay,
        surface: null,
        surfaceType: null,
        sourceLabel: activeSourceLabel,
        authorityLabel: activeAuthorityLabel,
        bannerState: null,
        shouldShowNoData: true,
      }, [
        activeAuthorityLabel,
        activeDisplay,
        activeSourceLabel,
        activeSurfaceMaterialized,
      ]);
  const activeHistogram = activeSurfaceMaterialized
    ? data?.histograms.field.find((h) => h.surface_type === activeSurfaceType) || null
    : null;

  const activeDelta = activeSurfaceMaterialized
    ? data?.histograms.delta.find((d) => d.surface_type === activeSurfaceType) || null
    : null;

  const activeColors = MODE_CONFIG[activeMode].colors;

  // P0.2: Select trust surfaces matching experimental/certified mode
  // When experimental is active, use fine-detail trust surfaces first.
  const activeConfidenceSurface = useMemo(() => {
    if (!data) return null;
    if (showExperimental1m) {
      return data.surfaces.find((s) => s.type === "UNCERTAINTY_SIGMA_EXPERIMENTAL_FINE_DETAIL") ||
             data.surfaces.find((s) => s.type === "UNCERTAINTY_SIGMA") || null;
    }
    return data.surfaces.find((s) => s.type === "UNCERTAINTY_SIGMA") || null;
  }, [data, showExperimental1m]);

  // WS6: DATA_RELIABILITY has priority over inverted UNCERTAINTY_SIGMA
  // P0.2: Use experimental trust surfaces when experimental mode is active
  const activeReliabilitySurface = useMemo(() => {
    if (!data) return null;

    // Check backend mode plan for uncertainty first
    const plannedType = data.mode_surface_plan?.["uncertainty"]?.selected_surface_type;
    if (plannedType) {
      const plSurf = data.surfaces.find((s) => s.type === plannedType);
      if (plSurf) return plSurf;
    }

    const relType = showExperimental1m ? "DATA_RELIABILITY_EXPERIMENTAL_FINE_DETAIL" : "DATA_RELIABILITY";
    const confType = showExperimental1m ? "DATA_CONFIDENCE_EXPERIMENTAL_FINE_DETAIL" : "DATA_CONFIDENCE";
    const uncertType = showExperimental1m ? "UNCERTAINTY_SIGMA_EXPERIMENTAL_FINE_DETAIL" : "UNCERTAINTY_SIGMA";

    let surface = data.surfaces.find((s) => s.type === relType) || null;
    if (!surface && showExperimental1m) {
      surface = data.surfaces.find((s) => s.type === "DATA_RELIABILITY") || null;
    }
    if (!surface) {
      surface = data.surfaces.find((s) => s.type === confType) || null;
      if (!surface && showExperimental1m) {
        surface = data.surfaces.find((s) => s.type === "DATA_CONFIDENCE") || null;
      }
      if (!surface) {
        // The compatibility alias never owns a second grid.
        surface = data.surfaces.find((s) => s.type === "ASMAE_POSTERIOR_CONCENTRATION") || null;
        if (!surface) {
          const uncertaintySurf = data.surfaces.find((s) => s.type === uncertType) ||
                                  (showExperimental1m ? data.surfaces.find((s) => s.type === "UNCERTAINTY_SIGMA") : null) ||
                                  data.surfaces.find((s) => s.type === "UNCERTAINTY_SIGMA");
          if (uncertaintySurf) {
            const values = uncertaintySurf.values.map((row) =>
              row.map((v) => (v !== null ? 1 - v : null))
            );
            surface = {
              ...uncertaintySurf,
              type: showExperimental1m ? "DATA_RELIABILITY_EXPERIMENTAL_FINE_DETAIL" : "DATA_RELIABILITY",
              values,
              units: "score",
              render_range: [0, 1] as [number, number],
            };
          }
        }
      }
    }
    return surface;
  }, [data, showExperimental1m]);

  // Data Grades Computation
  const { plotDataAvailable, spatialSurfaceAvailable, localizedZoneAvailable } = useMemo(() => {
    // Fix C: a surface only counts as "spatial" if it has non-null values AND is not
    // a UNIFORM/BROADCAST broadcast fill. RASTER and ZONE_RASTERIZE grounding classes
    // indicate real per-cell variation; UNIFORM/BROADCAST are plot-level constants.
    const NON_SPATIAL_GROUNDING = new Set(["UNIFORM", "BROADCAST"]);
    const hasSurfaceValues = data?.surfaces?.some(s =>
      s.type === activeSurfaceType &&
      !NON_SPATIAL_GROUNDING.has(s.grounding_class) &&
      s.values?.length > 0 &&
      s.values.some(row => row.some((v: number | null) => v !== null))
    );
    
    // Check if localized zones exist for the active mode's zone surface type
    // Guard: when activeZoneSurfaceType is "" (canopy mode), no zones should match
    const hasZones = data?.zones?.some((zone) => {
      const hasSpatialAuthority = isZoneSpatiallyAuthorized(
        zone as unknown as Record<string, unknown>,
        renderMaterialization,
        renderMaterialization?.gridHeight || 0,
        renderMaterialization?.gridWidth || 0,
      );
      if (!hasSpatialAuthority) return false;
      return activeZoneSurfaceType
        ? zone.source_surface_type === activeZoneSurfaceType
        : activeMode === "canopy" || activeMode === "vegetation";
    }) || false;

    // Check backend quality flags
    const modeState = data?.quality?.zone_state_by_surface?.[activeZoneSurfaceType] || "unknown";

    const hasMaterializedSurface = isRenderedMaterialization(renderMaterialization, activeSurfaceType);
    const isLocalized = hasMaterializedSurface
      && hasZones
      && modeState !== "field_wide";
    const isSpatial = hasMaterializedSurface && !!hasSurfaceValues;
    const isPlot = !!data; 

    return {
      plotDataAvailable: isPlot,
      spatialSurfaceAvailable: isSpatial,
      localizedZoneAvailable: isLocalized
    };
  }, [data, activeSurfaceType, activeZoneSurfaceType, activeMode, renderMaterialization]);

  const fallbackGuidance = useMemo<FallbackGuidance | null>(() => {
    const exact = data?.fallback_guidance?.[activeSurfaceType];
    if (exact) {
      return {
        ...exact,
        displayed_surface_type: activeSurfaceType,
        guidance_surface_type: exact.guidance_surface_type || activeSurfaceType,
        guidance_relation: "same_surface",
      };
    }
    const operational = data?.fallback_guidance?.[activeZoneSurfaceType];
    if (!operational) return null;
    if (!spatialSurfaceAvailable) {
      return {
        ...operational,
        displayed_surface_type: activeSurfaceType,
        guidance_surface_type: activeZoneSurfaceType,
        guidance_relation: "separate_operational_surface",
      };
    }
    const displayedName = activeSurfaceType.replace(/_/g, " ").toLowerCase();
    const operationalName = activeZoneSurfaceType.replace(/_/g, " ").toLowerCase();
    return {
      ...operational,
      action_mode: "scouting_only",
      why: `The displayed ${displayedName} is a valid scouting raster. Operational guidance is based separately on ${operationalName}; no localized management-zone authority is implied.`,
      recommended_next_step: "Use the displayed pattern for scouting and verify conditions in the field before management action.",
      data_basis: `separate_operational_surface:${activeZoneSurfaceType}`,
      displayed_surface_type: activeSurfaceType,
      guidance_surface_type: activeZoneSurfaceType,
      guidance_relation: "separate_operational_surface",
    };
  }, [data?.fallback_guidance, activeSurfaceType, activeZoneSurfaceType, spatialSurfaceAvailable]);

  // Compute map semantics from data grades
  const mapSemantics: MapSemantics = useMemo(() => {
    if (!plotDataAvailable) return "no_data";
    if (!spatialSurfaceAvailable) return "plot_level";
    
    if (activeMode === "canopy" || activeMode === "vegetation") {
      const hasMgmtZones = data?.zones?.some((zone) =>
        zone.authority?.toLowerCase() === "management_zone"
        && isZoneSpatiallyAuthorized(
          zone as unknown as Record<string, unknown>,
          renderMaterialization,
          renderMaterialization?.gridHeight || 0,
          renderMaterialization?.gridWidth || 0,
        )
      ) || false;
      if (hasMgmtZones) return "management_zone";
    }
    
    if (localizedZoneAvailable) return "localized_alert";
    return "field_wide";
  }, [plotDataAvailable, spatialSurfaceAvailable, localizedZoneAvailable, data?.zones, activeMode, renderMaterialization]);

  const { experimental1mSurfaceActive, experimental1mSurfaceMissingForMode } = useMemo(() => {
    if (!showExperimental1m || activeMode === "resolution_coverage" || !data) {
      return { experimental1mSurfaceActive: false, experimental1mSurfaceMissingForMode: false };
    }
    const rendered = !!activeExperimentalSurface && exactExperimentalMaterialization;
    return {
      experimental1mSurfaceActive: rendered,
      experimental1mSurfaceMissingForMode: !rendered,
    };
  }, [
    showExperimental1m,
    activeMode,
    data,
    activeExperimentalSurface,
    exactExperimentalMaterialization,
  ]);

  const evidenceState = useMemo(() => {
    const meanSurfaceByType = (d: any, type: string): number | null => {
      const surface = d?.surfaces?.find((s: any) => s.type === type);
      if (!surface?.values) return null;

      const vals = surface.values.flat().filter((v: any): v is number => typeof v === "number" && Number.isFinite(v));
      return vals.length ? vals.reduce((a: number, b: number) => a + b, 0) / vals.length : null;
    };

    const extractWaterDeficit = (l3: any): number | null => {
      if (!l3 || !l3.data) return null;
      const d = l3.data;
      if (d.deficit_mm !== undefined && d.deficit_mm !== null) {
        return Number(d.deficit_mm);
      }
      if (d.water_balance && d.water_balance.deficit_mm !== undefined && d.water_balance.deficit_mm !== null) {
        return Number(d.water_balance.deficit_mm);
      }
      if (d.irrigation_deficit_mm !== undefined && d.irrigation_deficit_mm !== null) {
        return Number(d.irrigation_deficit_mm);
      }
      return null;
    };

    if (!data) return DEFAULT_EVIDENCE_STATE;

    const waterStressSurfaceMean = meanSurfaceByType(data, "WATER_STRESS_PROB");
    const l3 = data?.engines?.find((e: any) => e.id === "L3");
    const waterDeficitMm = extractWaterDeficit(l3);

    return resolvePlotMapEvidenceState({
      activeMode,
      activeSurface,
      activeSurfaceType,
      activeZoneSurfaceType,
      zones: (data?.zones || []).filter((zone) => isZoneSpatiallyAuthorized(
        zone as unknown as Record<string, unknown>,
        renderMaterialization,
        renderMaterialization?.gridHeight || 0,
        renderMaterialization?.gridWidth || 0,
      )),
      quality: data?.quality,
      explainPack: data?.explainability_pack?.[activeSurfaceType] || {},
      canonicalCropStage: data?.resolved_crop_stage || null,
      phenologyContext: data?.phenology_context,
      visualSource: data?.visual_source,
      engines: data?.engines,
      waterStressSurfaceMean,
      waterDeficitMm,
    });
  }, [activeMode, activeSurface, activeSurfaceType, activeZoneSurfaceType, data, renderMaterialization]);

  const modeAvailability = useMemo(() => {
    const modes: MapMode[] = [
      "vegetation",
      "canopy",
      "veg_attention",
      "water_stress",
      "nutrient_risk",
      "salinity",
      "composite_risk",
      "uncertainty",
      "resolution_coverage"
    ];
    const avail: Record<string, ModeAvailability> = {};
    for (const m of modes) {
      avail[m] = getModeAvailability(
        data,
        m,
        canopySource,
        showExperimental1m,
        asmae_evidence_state,
        experimentalVisualLadder,
        experimentalRenderMaterialization,
      );
    }
    return avail as Record<string, ModeAvailability>;
  }, [
    data,
    canopySource,
    showExperimental1m,
    asmae_evidence_state,
    experimentalVisualLadder,
    experimentalRenderMaterialization,
  ]);

  const experimentalCoveragePct = useMemo(() => {
    if (!showExperimental1m) return 0;
    return experimentalVisualLadder.textureAppliedPct;
  }, [
    showExperimental1m,
    experimentalVisualLadder,
  ]);

  const candidateMaskSurface = useMemo(() => {
    return surfaceByType["EXPERIMENTAL_STRICT_FINE_DETAIL_CANDIDATE_MASK"] || surfaceByType["EXPERIMENTAL_FINE_DETAIL_CANDIDATE"] || null;
  }, [surfaceByType]);

  const experimentalDisplayState = useMemo(() => {
    if (!showExperimental1m || activeMode === "resolution_coverage") return "disabled";
    if (
      !exactExperimentalMaterialization
      || experimental1mSurfaceMissingForMode
      || experimentalCoveragePct <= 0
    ) {
      return "base_fallback_experimental_missing";
    }
    if (experimentalCoveragePct > 0 && experimentalCoveragePct < 100) return "partial";
    return "active";
  }, [
    showExperimental1m,
    activeMode,
    exactExperimentalMaterialization,
    experimental1mSurfaceMissingForMode,
    experimentalCoveragePct,
  ]);

  const tierACoverage = useMemo(() => {
    if (!showExperimental1m) return null;
    return experimentalVisualLadder.unvalidatedCandidatePct;
  }, [showExperimental1m, experimentalVisualLadder]);

  const tierBCoverage = useMemo(() => {
    if (!showExperimental1m) return null;
    return experimentalVisualLadder.validatedFineDetailPct;
  }, [showExperimental1m, experimentalVisualLadder]);

  const tierCCoverage = useMemo(() => {
    if (!showExperimental1m) return null;
    return experimentalVisualLadder.fieldApproved1mPct;
  }, [showExperimental1m, experimentalVisualLadder]);


  const asmaeApprovalLadder = useMemo(() => {
    const isTestOverride = data?.asmae_evidence_state?.test_override === true;
    if (isTestOverride && !isTestFixtureActive) {
      return {
        oneMeterAsmaeApprovalPct: null,
        modelAssisted2_5mPct: null,
        generalized5mPct: null,
        unavailableReason: "test_override_blocked_in_production"
      };
    }
    if (data?.source_policy_display_state?.asmaeApprovalLadder) {
      return data.source_policy_display_state.asmaeApprovalLadder;
    }
    return {
      oneMeterAsmaeApprovalPct: null,
      modelAssisted2_5mPct: null,
      generalized5mPct: null,
      unavailableReason: asmae_evidence_state?.reason || "no_full_scene_stack"
    };
  }, [data, isTestFixtureActive, asmae_evidence_state]);

  // V92.3-C: Surface inventory
  const surfaceInventory = useMemo(() => {
    if (!data) return null;
    const engineList = data.engines?.map((e: any) => ({ id: e.id, status: e.status || "UNKNOWN" }));
    const localInv = buildSurfaceInventory(data.surfaces, modeAvailability, engineList);
    if (data.surface_inventory) {
      const merged: Record<string, SurfaceInventoryItem> = { ...localInv };
      for (const [key, backendItem] of Object.entries(data.surface_inventory)) {
        const bItem = backendItem as any;
        merged[key] = {
          surfaceType: key,
          status: bItem.status || merged[key]?.status || "missing",
          groundingClass: bItem.groundingClass || bItem.grounding_class || merged[key]?.groundingClass,
          reason: bItem.reason || merged[key]?.reason,
          ...bItem
        };
      }
      return merged;
    }
    return localInv;
  }, [data, modeAvailability]);

  // V92.3-C: Overlay availability
  const overlayAvailability = useMemo(() => {
    if (!data || !surfaceInventory) return null;
    const availability = buildOverlayAvailability(
      data.surfaces,
      data.zones || [],
      surfaceInventory,
      data,
      canopySource,
      showExperimental1m,
      asmae_evidence_state,
      experimentalVisualLadder,
      experimentalRenderMaterialization,
    );
    const materializedZones = (data.zones || []).some((zone) => isZoneSpatiallyAuthorized(
      zone as unknown as Record<string, unknown>,
      renderMaterialization,
      renderMaterialization?.gridHeight || 0,
      renderMaterialization?.gridWidth || 0,
    ));
    availability.zones = {
      ...availability.zones,
      available: materializedZones,
      isSpatial: materializedZones,
      reason: materializedZones
        ? availability.zones?.reason
        : `blocked_by_materialization:${renderMaterialization?.reason || "missing_layer"}`,
    };
    return availability;
  }, [
    data,
    surfaceInventory,
    canopySource,
    showExperimental1m,
    asmae_evidence_state,
    experimentalVisualLadder,
    renderMaterialization,
    experimentalRenderMaterialization,
  ]);

  // V92.3-C.2: Count only overlays that are available AND spatial, not just toggled
  const { activeOverlayCount, overlayConflictWarning } = useMemo(() => {
    const stressKinds: OverlayKind[] = ["water", "nutrients", "risk", "salinity"];
    let count = 0;
    let stressCount = 0;
    for (const kind of Object.keys(overlayToggles) as OverlayKind[]) {
      if (overlayToggles[kind]) {
        const avail = overlayAvailability?.[kind];
        const isVisibleSpatial = avail?.available && avail?.isSpatial;
        if (isVisibleSpatial) {
          count++;
          if (stressKinds.includes(kind)) stressCount++;
        }
      }
    }
    const warning = stressCount >= 2
      ? "Multiple stress overlays active \u2014 colors may overlap"
      : null;
    return { activeOverlayCount: count, overlayConflictWarning: warning };
  }, [overlayToggles, overlayAvailability]);

  return createElement(
    Layer10Context.Provider,
    {
      value: {
        data,
        loading,
        error,
        activeMode,
        detailMode,
        selectedZone,
        histogramExpanded,
        isDecideMode,
        decideModeQuery,
        setActiveMode,
        setDetailMode,
        setSelectedZone,
        setHistogramExpanded,
        setIsDecideMode,
        openDecideMode,
        fetchLayer10,
        activeDisplay: committedActiveDisplay,
        activeSurface,
        committedSurface: activeSurfaceMaterialized ? activeSurface : null,
        activeSurfaceMaterialized,
        activeConfidenceSurface,
        activeReliabilitySurface,
        activeHistogram,
        activeDelta,
        activeColors,
        activeSurfaceType,
        activeZoneSurfaceType,
        activeSourceLabel,
        activeAuthorityLabel,
        bannerState,
        canShowPixelDiagnosis: canShowPixelDiagnosis && activeSurfaceMaterialized,
        canShowPixelHint: canShowPixelHint && activeSurfaceMaterialized,
        canSamplePixel: canSamplePixel && activeSurfaceMaterialized,
        canInterpretForScouting: canInterpretForScouting && activeSurfaceMaterialized,
        canInterpretDiagnostically: canInterpretDiagnostically && activeSurfaceMaterialized,
        canUseForPrescription: canUseForPrescription && activeSurfaceMaterialized,
        canShowExperimentalDetail,
        shouldShowNoData: shouldShowNoData || !activeSurfaceMaterialized,
        shouldShowPlotLevel,
        surfaceAvailabilityByMode,
        plotDataAvailable,
        spatialSurfaceAvailable,
        localizedZoneAvailable,
        fallbackGuidance,
        mapSemantics,
        showExperimental1m,
        setShowExperimental1m,
        experimentalBaseActive,
        experimentalOverlayEnabled,
        showCandidateMask,
        setShowCandidateMask,
        experimental1mGenerating,
        setExperimental1mGenerating,
        visualIntensity,
        setVisualIntensity,
        experimental1mSurfaceActive,
        experimental1mSurfaceMissingForMode,
        evidenceState,
        modeAvailability,
        // V92.3-C: True overlay architecture
        baseSurfaceMode,
        setBaseSurfaceMode,
        overlayToggles,
        setOverlayToggle,
        overlayAvailability,
        surfaceInventory,
        surfaceByType,
        activeOverlayCount,
        overlayConflictWarning,
        activeExperimentalSurface,
        activeExperimentalSurfaceType,
        candidateMaskSurface,
        experimentalCoveragePct,
        canopySource,
        setCanopySource,
        experimentalDisplayState,
        tierACoverage,
        tierBCoverage,
        tierCCoverage,
        experimentalVisualLadder,
        asmaeApprovalLadder,
        asmae_evidence_state,
        renderPlan,
        renderMaterialization,
        experimentalRenderMaterialization,
        browserRenderReceipt,
        commitBrowserRenderReceipt,
        clearBrowserRenderReceipt,
      }
    },
    children
  );
}

export function useLayer10() {
  const context = useContext(Layer10Context);
  if (!context) {
    throw new Error("useLayer10 must be used within a Layer10Provider");
  }
  return context;
}

// priorityList.push("WATER_ASMAE_CANOPY_WATER", "WATER_ASMAE_ROOT_ZONE_WATER", "COMPOSITE_WATER_SUPPORT")
// canopy prioritizations: ASMAE_VISUAL_FUSION_CANOPY, COMPOSITE_ADVISORY_CANOPY, CANOPY_ASMAE_VIGOR
