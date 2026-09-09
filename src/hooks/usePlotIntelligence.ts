"use client";

/**
 * usePlotIntelligence — Supplementary hook for the Plot Overview dashboard.
 *
 * Provides:
 *   - Timeline data (7 days back + 7 days forward)
 *   - Engine pipeline statuses (L0–L10)
 *   - Farmer/Expert + Assimilated/Raw mode toggles
 *   - Raw data access for expert mode
 *   - Sidebar toggle states
 *
 * Does NOT provide L10 surfaces — use useLayer10 for map overlays.
 */

import {
  createContext,
  useContext,
  useState,
  useCallback,
  useRef,
  type ReactNode,
  createElement,
} from "react";
import { normalizeEngineCollection } from "@/lib/agribrain/normalize-engines";

// ── Types ─────────────────────────────────────────────────────────────────────

export type DetailMode = "farmer" | "expert";
export type DataView = "assimilated" | "raw";

export interface EngineStatus {
  id: string;
  name: string;
  nameAr: string;
  icon: string;
  status: "OK" | "DEGRADED" | "SKIPPED" | "UNAVAILABLE" | "FAILED" | "OFFLINE" | "LOADING";
  statusLabel: string;
  summary: string;
  summaryAr: string;
  lastUpdate: string | null;
  data: Record<string, unknown>;
  raw?: Record<string, unknown>;
}

export interface TimelineData {
  weather: Record<string, unknown>[];
  ndvi: Record<string, unknown>[];
  sar: Record<string, unknown>[];
  waterBalance: Record<string, unknown>[];
  forecast: Record<string, unknown>[];
  dateRange: { from: string; to: string; today: string };
}

export interface AssimilationMeta {
  dataAge_days: number;
  sources_used: string[];
  sources_count: number;
  freshness_score: number;
  assimilated: boolean;
  raw_available: boolean;
}

export interface CropPhenology {
  stage: string;
  dap: number | null;
  plant_date?: string;
  basis: string;
}

export interface UserInputsData {
  irrigation_type: string | null;
  soil_type: string | null;
  soil_analysis: Record<string, unknown> | null;
  soil_source: string;
  physical_constraints: string[];
  area_ha: number | null;
}

export interface SensorContextData {
  count: number;
  active: number;
  types: string[];
  soil_moisture_pct: number | null;
  soil_ec_ds_m: number | null;
  field_temperature_c: number | null;
  field_humidity_pct: number | null;
  field_wind_speed_ms: number | null;
  field_rainfall_mm: number | null;
  data_source: string;
}

export interface DnaStatus {
  sequenced: boolean;
  hash: string | null;
  traits?: {
    theta_retention: number | null;
    beta_resilience: number | null;
    alpha_vigor: number | null;
    t_shift: number | null;
  };
  data_quality_pct?: number;
  ndvi_observations?: number;
  physics_injected: boolean;
  error?: string;
}

export interface PlotIntelligenceData {
  timeline: TimelineData;
  engines: EngineStatus[];
  current: {
    weather: Record<string, unknown> | null;
    indices: Record<string, unknown> | null;
    soil: Record<string, unknown> | null;
    waterBalance: Record<string, unknown> | null;
  };
  rawData?: Record<string, unknown>;
  assimilation: AssimilationMeta;
  cropPhenology?: CropPhenology | null;
  userInputs?: UserInputsData | null;
  sensorContext?: SensorContextData | null;
  dnaStatus?: DnaStatus | null;
}

// ── Context ───────────────────────────────────────────────────────────────────

export type CacheStatus = "HIT" | "STALE" | "MISS" | "REFRESHED" | null;

interface PlotIntelligenceContextType {
  // Data
  data: PlotIntelligenceData | null;
  loading: boolean;
  error: string | null;

  // Cache status
  cacheStatus: CacheStatus;
  refreshing: boolean;
  lastCaptured: string | null;

  // Timeline
  timeline: TimelineData | null;
  selectedDate: string | null;
  setSelectedDate: (date: string | null) => void;

  // Engines
  engines: EngineStatus[];
  expandedEngine: string | null;
  setExpandedEngine: (id: string | null) => void;

  // Mode toggles
  detailMode: DetailMode;
  setDetailMode: (mode: DetailMode) => void;
  dataView: DataView;
  setDataView: (view: DataView) => void;

  // Sidebar toggles
  showEnginePanel: boolean;
  setShowEnginePanel: (v: boolean) => void;
  showAnalysisSidebar: boolean;
  setShowAnalysisSidebar: (v: boolean) => void;
  activeSidebarTab: "analysis" | "layers" | "raw";
  setActiveSidebarTab: (tab: "analysis" | "layers" | "raw") => void;

  // Assimilation
  assimilation: AssimilationMeta | null;
  rawData: Record<string, unknown> | null;

  // GAP F: Live weather from PI pipeline
  currentWeather: Record<string, unknown> | null;

  // GAP A: Real agronomic crop stage
  cropPhenology: CropPhenology | null;

  // DNA 4.0: Biophysical trait provenance
  dnaStatus: DnaStatus | null;

  // Fetch / Sync
  fetchIntelligence: (plotId: string, farmId: string) => Promise<void>;
  forceRefresh: (plotId: string, farmId: string) => Promise<void>;
  injectData: (data: any) => void;
}

const PlotIntelligenceContext = createContext<PlotIntelligenceContextType | null>(null);

// Canonical Subsystem Metadata (Eliminates L0..L10 in UI)
export interface SubsystemMetadata {
  name: string;
  nameAr: string;
  icon: string;
  tag: string;
  farmerGroup: "conditions" | "crop" | "planning" | "intelligence";
}

export const SUBSYSTEM_METADATA: Record<string, SubsystemMetadata> = {
  L0: { name: "Microclimate & Weather", nameAr: "المناخ والطقس الجوي", icon: "🌤️", tag: "METEO", farmerGroup: "conditions" },
  L1: { name: "Multi-Source Sensor Fusion", nameAr: "دمج مصادر البيانات", icon: "📡", tag: "FUSION", farmerGroup: "conditions" },
  L2: { name: "ASMAE Canopy Vigor & Biophysics", nameAr: "قوة المظلة والفيزياء الحيوية (ASMAE)", icon: "🌿", tag: "CANOPY", farmerGroup: "crop" },
  L3: { name: "Water Balance & Root Moisture", nameAr: "توازن الماء ورطوبة الجذور", icon: "💧", tag: "WATER", farmerGroup: "crop" },
  L4: { name: "Subsurface Soil Profile", nameAr: "الملف الجوفي للتربة", icon: "🪨", tag: "SOIL", farmerGroup: "crop" },
  L5: { name: "Crop Pathology & Pest Risk", nameAr: "أمراض المحصول ومخاطر الآفات", icon: "🦠", tag: "PATHOLOGY", farmerGroup: "crop" },
  L6: { name: "Yield Potential & Calibration", nameAr: "إمكانات الإنتاج والمعايرة", icon: "📊", tag: "YIELD", farmerGroup: "planning" },
  L7: { name: "Agronomic Calendar & Tasks", nameAr: "الجدول الزراعي والمهام", icon: "📅", tag: "CALENDAR", farmerGroup: "planning" },
  L8: { name: "Precision Prescriptions", nameAr: "التوصيات والتدخلات الميدانية", icon: "⚡", tag: "ACTIONS", farmerGroup: "planning" },
  L9: { name: "AgriBrain AI Advisory", nameAr: "استشارات ذكاء أغريبرين", icon: "💬", tag: "ADVISORY", farmerGroup: "intelligence" },
  L10: { name: "MESIA World Model Synthesis", nameAr: "نموذج العالم والتوليف الميداني", icon: "🧠", tag: "MESIA", farmerGroup: "intelligence" },
};

// ── Provider ──────────────────────────────────────────────────────────────────

export function PlotIntelligenceProvider({ children }: { children: ReactNode }) {
  const [data, setData] = useState<PlotIntelligenceData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Cache status
  const [cacheStatus, setCacheStatus] = useState<CacheStatus>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [lastCaptured, setLastCaptured] = useState<string | null>(null);

  // Timeline
  const [selectedDate, setSelectedDate] = useState<string | null>(null);

  // Engines
  const [expandedEngine, setExpandedEngine] = useState<string | null>(null);

  // Mode toggles
  const [detailMode, setDetailMode] = useState<DetailMode>("farmer");
  const [dataView, setDataView] = useState<DataView>("assimilated");

  // Sidebar toggles
  const [showEnginePanel, setShowEnginePanel] = useState(true);
  const [showAnalysisSidebar, setShowAnalysisSidebar] = useState(true);
  const [activeSidebarTab, setActiveSidebarTab] = useState<"analysis" | "layers" | "raw">("analysis");

  // In-memory cache for session (prevents redundant API calls during navigation)
  const cacheRef = useRef<Record<string, { data: PlotIntelligenceData; timestamp: number }>>({})
  const CACHE_TTL = 5 * 60 * 1000; // 5 minutes in-memory
  // GAP 16: Abort controller for background refresh race prevention
  const refreshAbortRef = useRef<AbortController | null>(null);

  // Normalize Python engine card shape → EngineStatus interface
  const normalizeEngine = (e: any): EngineStatus => {
    const statusLabelMap: Record<string, string> = {
      OK: "Good",
      DEGRADED: "Watch",
      SKIPPED: "Skipped",
      UNAVAILABLE: "Unavailable",
      FAILED: "Failed",
      OFFLINE: "Action Needed",
      LOADING: "Loading…",
    };
    const meta = SUBSYSTEM_METADATA[e.id] || {
      name: e.name || "Agronomic Subsystem",
      nameAr: e.nameAr || e.name || "نظام زراعي",
      icon: "🌱",
      tag: "SUBSYSTEM",
      farmerGroup: "conditions",
    };

    const cleanText = (txt: any) => {
      if (typeof txt !== "string") return "";
      return txt
        .replace(/SoilGrids-ISRIC/gi, "Regional Soil Survey")
        .replace(/SoilGrids Proxy/gi, "Regional Soil Survey Baseline")
        .replace(/SoilGrids/gi, "Regional Soil Survey")
        .replace(/\bL([0-9]{1,2})\b/g, (match) => SUBSYSTEM_METADATA[match]?.name || match);
    };

    return {
      id: e.id ?? "",
      name: meta.name,
      nameAr: meta.nameAr,
      icon: meta.icon,
      status: e.status ?? "LOADING",
      statusLabel: e.statusLabel ?? statusLabelMap[e.status] ?? e.status ?? "",
      summary: cleanText(e.summary ?? e.detail ?? e.value ?? ""),
      summaryAr: cleanText(e.summaryAr ?? e.summary ?? e.detail ?? ""),
      lastUpdate: e.lastUpdate ?? null,
      data: (e.data ?? e.expert ?? {}) as Record<string, unknown>,
      raw: e.raw,
    };
  };

  // Map API response to internal data shape
  const mapResponse = useCallback((json: any): PlotIntelligenceData => {
    const rawSources: string[] = json?.assimilation?.sources_used || [];
    const sanitizedSources = rawSources
      .map(s => (s.toLowerCase().includes("soilgrid") ? "Regional Soil Survey" : s))
      .filter(Boolean);

    return {
      timeline: json.timeline || {
        weather: [], ndvi: [], sar: [], waterBalance: [], forecast: [],
        dateRange: { from: "", to: "", today: "" },
      },
      engines: normalizeEngineCollection(json?.engines).map(normalizeEngine),
      current: json.current || { weather: null, indices: null, soil: null, waterBalance: null },
      rawData: json.rawData,
      assimilation: json.assimilation ? {
        ...json.assimilation,
        sources_used: sanitizedSources,
      } : {
        dataAge_days: 0, sources_used: [], sources_count: 0,
        freshness_score: 0, assimilated: false, raw_available: false,
      },
      cropPhenology: json.crop_phenology ?? null,
      userInputs: json.user_inputs ?? null,
      sensorContext: json.sensor_context ?? null,
      dnaStatus: json.dna_status ?? null,
    };
  }, []);

  const fetchIntelligence = useCallback(
    async (plotId: string, farmId: string) => {
      const cacheKey = `${plotId}:${farmId}`;
      const cached = cacheRef.current[cacheKey];
      // In-memory cache still valid → skip API call entirely
      if (cached && Date.now() - cached.timestamp < CACHE_TTL && cached.data.timeline.weather.length > 0) {
        setData(cached.data);
        return;
      }

      setLoading(true);
      setError(null);

      try {
        // Phase 1: Fetch (may return DB-cached data instantly)
        const res = await fetch("/api/agribrain/plot-intelligence", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            plotId,
            farmId,
            expertMode: true,
          }),
        });

        const serverCacheStatus = res.headers.get("X-Cache-Status") as CacheStatus;
        const capturedAt = res.headers.get("X-Captured-At");
        const json = await res.json();

        if (!json.success && !json.engines) {
          throw new Error(json.error || "Intelligence fetch failed");
        }

        const mapped = mapResponse(json);
        setData(mapped);
        setCacheStatus(serverCacheStatus || "MISS");
        setLastCaptured(capturedAt || json._cache?.capturedAt || null);
        cacheRef.current[cacheKey] = { data: mapped, timestamp: Date.now() };

        // Phase 2: If server returned stale data, trigger background refresh
        if (serverCacheStatus === "STALE") {
          // GAP 16: Abort any in-flight refresh before starting a new one
          refreshAbortRef.current?.abort();
          const abortCtrl = new AbortController();
          refreshAbortRef.current = abortCtrl;

          setRefreshing(true);
          fetch("/api/agribrain/plot-intelligence/refresh", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ plotId, farmId }),
            signal: abortCtrl.signal,
          })
            .then((r) => r.json())
            .then((freshJson) => {
              // Only apply if this refresh wasn't aborted
              if (!abortCtrl.signal.aborted && (freshJson.engines || freshJson.success)) {
                const freshMapped = mapResponse(freshJson);
                setData(freshMapped);
                setCacheStatus("REFRESHED");
                setLastCaptured(freshJson._cache?.capturedAt || new Date().toISOString());
                cacheRef.current[cacheKey] = { data: freshMapped, timestamp: Date.now() };
                console.log("[usePlotIntelligence] Background refresh complete");
              }
            })
            .catch((err) => {
              if (err?.name !== "AbortError") {
                console.warn("[usePlotIntelligence] Background refresh failed:", err);
              }
            })
            .finally(() => setRefreshing(false));
        }
      } catch (e) {
        console.error("[usePlotIntelligence] Fetch failed:", e);
        setError(e instanceof Error ? e.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    },
    [mapResponse]
  );

  // Manual force refresh — always calls AgriBrain live
  const forceRefresh = useCallback(
    async (plotId: string, farmId: string) => {
      setRefreshing(true);
      try {
        const res = await fetch("/api/agribrain/plot-intelligence", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ plotId, farmId, expertMode: true, forceRefresh: true }),
        });
        const json = await res.json();
        if (json.engines || json.success) {
          const mapped = mapResponse(json);
          setData(mapped);
          setCacheStatus("REFRESHED");
          setLastCaptured(json._cache?.capturedAt || new Date().toISOString());
          const cacheKey = `${plotId}:${farmId}`;
          cacheRef.current[cacheKey] = { data: mapped, timestamp: Date.now() };
        }
      } catch (e) {
        console.warn("[usePlotIntelligence] Force refresh failed:", e);
      } finally {
        setRefreshing(false);
      }
    },
    [mapResponse]
  );

  const injectData = useCallback((payload: any) => {
    if (!payload) return;
    const mapped: PlotIntelligenceData = {
      timeline: payload.timeline || {
        weather: [], ndvi: [], sar: [], waterBalance: [], forecast: [],
        dateRange: { from: "", to: "", today: "" },
      },
      engines: normalizeEngineCollection(payload.engines).map(normalizeEngine),
      current: payload.current || { weather: null, indices: null, soil: null, waterBalance: null },
      rawData: payload.rawData,
      assimilation: payload.assimilation || {
        dataAge_days: 0, sources_used: [], sources_count: 0,
        freshness_score: 0, assimilated: false, raw_available: false,
      },
      cropPhenology: payload.crop_phenology ?? payload.cropPhenology ?? null,
      userInputs: payload.user_inputs ?? payload.userInputs ?? null,
      sensorContext: payload.sensor_context ?? payload.sensorContext ?? null,
      dnaStatus: payload.dna_status ?? payload.dnaStatus ?? null,
    };
    setData(mapped);
  }, []);

  return createElement(
    PlotIntelligenceContext.Provider,
    {
      value: {
        data,
        loading,
        error,

        // Cache status
        cacheStatus,
        refreshing,
        lastCaptured,

        timeline: data?.timeline || null,
        selectedDate,
        setSelectedDate,

        engines: data?.engines || [],
        expandedEngine,
        setExpandedEngine,

        detailMode,
        setDetailMode,
        dataView,
        setDataView,

        showEnginePanel,
        setShowEnginePanel,
        showAnalysisSidebar,
        setShowAnalysisSidebar,
        activeSidebarTab,
        setActiveSidebarTab,

        assimilation: data?.assimilation || null,
        rawData: data?.rawData || null,

        // GAP F: live temperature from PI pipeline
        currentWeather: (data?.current?.weather as Record<string, unknown>) || null,

        // GAP A: real agronomic stage
        cropPhenology: data?.cropPhenology || null,

        // DNA 4.0: biophysical trait provenance
        dnaStatus: data?.dnaStatus || null,

        fetchIntelligence,
        forceRefresh,
        injectData,
      },
    },
    children
  );
}

export function usePlotIntelligence() {
  const context = useContext(PlotIntelligenceContext);
  if (!context) {
    throw new Error("usePlotIntelligence must be used within a PlotIntelligenceProvider");
  }
  return context;
}
