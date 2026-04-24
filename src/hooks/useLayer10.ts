"use client";

import {
  createContext,
  useContext,
  useState,
  useCallback,
  useRef,
  useMemo,
  type ReactNode,
  createElement,
} from "react";


// ============================================================================
// TYPES
// ============================================================================

export type MapMode =
  | "vegetation"  // Compatibility alias → treated as canopy
  | "canopy"
  | "veg_attention"
  | "water_stress"
  | "nutrient_risk"
  | "composite_risk"
  | "uncertainty";

export interface SurfaceData {
  type: string;
  values: (number | null)[][];
  grounding_class: string;
  units: string;
  render_range: [number, number];
  palette_id: string;
  source_layers: string[];
  provenance: Record<string, unknown>;
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

export interface Layer10Result {
  run_id: string;
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
    grid_alignment_ok: boolean;
    detail_conservation_ok: boolean;
    zone_state_by_surface: Record<string, string>;
    warnings: string[];
  };
  provenance: Record<string, unknown>;
  grid: { height: number; width: number };
  explainability_pack: Record<string, ExplainabilityPack>;
  scenario_pack?: ScenarioDefinition[];
  history_pack?: HistoryEvent[];
  fallback_guidance?: Record<string, FallbackGuidance>;
}

export interface FallbackGuidance {
  action_mode: "field_wide" | "plot_level_only" | "insufficient_data";
  recommended_next_step: string;
  why: string;
  confidence: number;
  data_basis: string;
}

export type MapSemantics = "plot_level" | "field_wide" | "localized_alert" | "management_zone" | "no_data";

export const MAP_SEMANTICS_LABELS: Record<MapSemantics, string> = {
  plot_level: "Plot-level estimate",
  field_wide: "Field-wide condition",
  localized_alert: "Localized alert zones",
  management_zone: "Management zones",
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
  composite_risk: "COMPOSITE_RISK",
  uncertainty: "UNCERTAINTY_SIGMA",
};

export const MODE_ZONE_SURFACE_MAP: Record<MapMode, string> = {
  vegetation: "",                  // Alias → canopy (no zone promise)
  canopy: "",                      // No zone promise in canopy mode
  veg_attention: "NDVI_DEVIATION",
  water_stress: "WATER_STRESS_PROB",
  nutrient_risk: "NUTRIENT_STRESS_PROB",
  composite_risk: "BIOTIC_PRESSURE",
  uncertainty: "UNCERTAINTY_SIGMA",
};

export const MODE_CONFIG: Record<
  MapMode,
  { label: string; icon: string; colors: [string, string, string] }
> = {
  vegetation: {
    label: "Canopy",
    icon: "🌿",
    colors: ["#8B0000", "#FFD700", "#006400"],
  },
  canopy: {
    label: "Canopy",
    icon: "🌿",
    colors: ["#8B0000", "#FFD700", "#006400"],
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
  composite_risk: {
    label: "Risk",
    icon: "⚠️",
    colors: ["#2ecc71", "#e67e22", "#e74c3c"],
  },
  uncertainty: {
    label: "Confidence",
    icon: "🔍",
    colors: ["#2c3e50", "#8e44ad", "#e74c3c"],
  },
};

// ============================================================================
// NORMALIZERS
// ============================================================================

function normalizeSurface(raw: Record<string, any>): SurfaceData {
  return {
    type: raw.type ?? raw.semantic_type ?? "",
    values: Array.isArray(raw.values) ? raw.values : [],
    grounding_class: raw.grounding_class ?? "UNIFORM",
    units: raw.units ?? "",
    render_range: Array.isArray(raw.render_range)
      ? [Number(raw.render_range[0] ?? 0), Number(raw.render_range[1] ?? 1)]
      : [0, 1],
    palette_id: raw.palette_id ?? "viridis",
    source_layers: Array.isArray(raw.source_layers) ? raw.source_layers : [],
    provenance: raw.provenance ?? {},
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

// ============================================================================
// CONTEXT & PROVIDER
// ============================================================================

interface Layer10ContextType {
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
  fetchLayer10: (plotId: string, farmId: string, lat?: number, lng?: number, crop?: string) => Promise<void>;
  activeSurface: SurfaceData | null;
  activeConfidenceSurface: SurfaceData | null;
  activeReliabilitySurface: SurfaceData | null;
  activeHistogram: HistogramData | null;
  activeDelta: DeltaHistogramData | null;
  activeColors: [string, string, string];
  activeSurfaceType: string;
  activeZoneSurfaceType: string;
  plotDataAvailable: boolean;
  spatialSurfaceAvailable: boolean;
  localizedZoneAvailable: boolean;
  fallbackGuidance: FallbackGuidance | null;
  mapSemantics: MapSemantics;
}

const Layer10Context = createContext<Layer10ContextType | null>(null);

export function Layer10Provider({ children }: { children: ReactNode }) {
  const [data, setData] = useState<Layer10Result | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeMode, setActiveMode] = useState<MapMode>("canopy");
  const [detailMode, setDetailMode] = useState<"farmer" | "expert">("farmer");
  const [selectedZone, setSelectedZone] = useState<string | null>(null);
  const [histogramExpanded, setHistogramExpanded] = useState(false);
  const [isDecideMode, setIsDecideMode] = useState(false);
  const cacheRef = useRef<Record<string, Layer10Result>>({});

  const fetchLayer10 = useCallback(
    async (plotId: string, _farmId: string, _lat?: number, _lng?: number, _crop?: string) => {
      const cacheKey = `${plotId}`;
      if (cacheRef.current[cacheKey]) {
        if (data !== cacheRef.current[cacheKey]) {
          setData(cacheRef.current[cacheKey]);
        }
        return;
      }

      setLoading(true);
      setError(null);

      try {
        const res = await fetch("/api/agribrain/run", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ plotId, mode: "surfaces", query: "" }),
        });

        const json = await res.json();

        if (json.error || json.success === false) {
          throw new Error(json.error || "AgriBrain surfaces pipeline failed");
        }

        // Support either raw result or wrapped { data: ... }
        const runData = json.data ?? json;

        const surfaces = Array.isArray(runData.surfaces)
          ? runData.surfaces.map(normalizeSurface)
          : [];

        const mapped: Layer10Result = {
          run_id: runData.run_id || "",
          plot_id: runData.plot_id || plotId,
          timestamp: runData.timestamp || runData.audit?.timestamp_utc || new Date().toISOString(),

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
            degradation_mode:
              runData.quality?.degradation_mode ||
              runData.global_quality?.degradation_modes?.[0] ||
              "NORMAL",
            reliability_score:
              Number(runData.quality?.reliability_score ?? runData.global_quality?.reliability ?? 0),
            surfaces_generated:
              Number(runData.quality?.surfaces_generated ?? surfaces.length),
            zones_generated:
              Number(runData.quality?.zones_generated ?? runData.zones?.length ?? 0),
            grid_alignment_ok: Boolean(runData.quality?.grid_alignment_ok ?? true),
            detail_conservation_ok: Boolean(runData.quality?.detail_conservation_ok ?? true),
            zone_state_by_surface: runData.quality?.zone_state_by_surface || {},
            warnings: Array.isArray(runData.quality?.warnings)
              ? runData.quality.warnings
              : Array.isArray(runData.global_quality?.critical_errors)
              ? runData.global_quality.critical_errors
              : [],
          },

          provenance: runData.provenance ?? runData.audit ?? {},
          grid: deriveGrid(runData.grid, surfaces),
          explainability_pack: runData.explainability_pack ?? {},
          scenario_pack: runData.scenario_pack ?? [],
          history_pack: runData.history_pack ?? [],
        };

        setData(mapped);
        cacheRef.current[cacheKey] = mapped;
      } catch (e) {
        setError(e instanceof Error ? e.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    },
    [data]
  );

  // Derived state
  const { activeSurfaceType, activeZoneSurfaceType } = useMemo(() => {
    let sType = MODE_SURFACE_MAP[activeMode];
    let zType = MODE_ZONE_SURFACE_MAP[activeMode];

    if (activeMode === "veg_attention" && data?.quality?.zone_state_by_surface) {
      const states = data.quality.zone_state_by_surface;
      const devState = states["NDVI_DEVIATION"];
      const baseState = states["BASELINE_ANOMALY"];
      
      // Patch 1 & 4: Veg Attention composite anomaly mode
      if (devState === "localized") {
        sType = "NDVI_DEVIATION";
        zType = "NDVI_DEVIATION";
      } else if (baseState === "field_wide" || baseState === "localized") {
        sType = "BASELINE_ANOMALY";
        zType = "BASELINE_ANOMALY";
      } else {
        sType = "NDVI_DEVIATION";
        zType = "NDVI_DEVIATION";
      }
    }
    
    return { activeSurfaceType: sType, activeZoneSurfaceType: zType };
  }, [activeMode, data]);

  const activeSurface =
    data?.surfaces.find((s) => s.type === activeSurfaceType) || null;

  const activeHistogram =
    data?.histograms.field.find((h) => h.surface_type === activeSurfaceType) || null;

  const activeDelta =
    data?.histograms.delta.find((d) => d.surface_type === activeSurfaceType) || null;

  const activeColors = MODE_CONFIG[activeMode].colors;

  const activeConfidenceSurface =
    data?.surfaces.find((s) => s.type === "UNCERTAINTY_SIGMA") || null;

  // WS6: DATA_RELIABILITY has priority over inverted UNCERTAINTY_SIGMA
  const activeReliabilitySurface =
    data?.surfaces.find((s) => s.type === "DATA_RELIABILITY") || null;

  // Data Grades Computation
  const { plotDataAvailable, spatialSurfaceAvailable, localizedZoneAvailable } = useMemo(() => {
    const hasSurfaceValues = data?.surfaces?.some(s => s.type === activeSurfaceType && s.values?.length > 0 && s.values.some(row => row.some(v => v !== null)));
    
    // Check if localized zones exist for the active mode's zone surface type or a fallback
    const hasZones = data?.zones?.some(z => 
      z.source_surface_type === activeZoneSurfaceType || 
      z.zone_type.includes(activeZoneSurfaceType.toLowerCase())
    ) || false;

    // Check backend quality flags
    const modeState = data?.quality?.zone_state_by_surface?.[activeZoneSurfaceType] || "unknown";

    const isLocalized = modeState === "localized" || hasZones;
    const isSpatial = modeState === "field_wide" || hasSurfaceValues || isLocalized;
    const isPlot = !!data; 

    return {
      plotDataAvailable: isPlot,
      spatialSurfaceAvailable: isSpatial,
      localizedZoneAvailable: isLocalized
    };
  }, [data, activeSurfaceType, activeZoneSurfaceType]);

  const fallbackGuidance = data?.fallback_guidance?.[activeSurfaceType] || data?.fallback_guidance?.[activeZoneSurfaceType] || null;

  // Compute map semantics from data grades
  const mapSemantics: MapSemantics = useMemo(() => {
    if (!plotDataAvailable) return "no_data";
    if (!spatialSurfaceAvailable) return "plot_level";
    // Check if management zones exist for this mode
    const hasMgmtZones = data?.zones?.some(z => z.zone_id?.startsWith("MZ_")) || false;
    if (hasMgmtZones && localizedZoneAvailable) return "management_zone";
    if (localizedZoneAvailable) return "localized_alert";
    return "field_wide";
  }, [plotDataAvailable, spatialSurfaceAvailable, localizedZoneAvailable, data?.zones]);

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
        setActiveMode,
        setDetailMode,
        setSelectedZone,
        setHistogramExpanded,
        setIsDecideMode,
        fetchLayer10,
        activeSurface,
        activeConfidenceSurface,
        activeReliabilitySurface,
        activeHistogram,
        activeDelta,
        activeColors,
        activeSurfaceType,
        activeZoneSurfaceType,
        plotDataAvailable,
        spatialSurfaceAvailable,
        localizedZoneAvailable,
        fallbackGuidance,
        mapSemantics,
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
