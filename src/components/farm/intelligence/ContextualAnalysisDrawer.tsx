"use client";

import type { MapMode, Layer10Result } from "@/hooks/useLayer10";
import { MODE_SURFACE_MAP } from "@/hooks/useLayer10";
import type { ReactNode } from "react";
import {
  computeZonalMean,
  computeZonalStd,
  computeZonalP10,
  computeZonalP90,
} from "@/lib/agri/zonalStats";

interface ContextualAnalysisDrawerProps {
  data: Layer10Result;
  activeMode: MapMode;
  selectedZoneId: string | null;
  onOpenMethodology: (metricKey: string) => void;
  onClose: () => void;
  detailMode?: "farmer" | "expert";
}

// ── UI state tags ─────────────────────────────────────────────────────────────
type MetricState = "measured" | "estimated" | "unavailable";

const StateTag = ({ state }: { state: MetricState }) => {
  if (state === "measured") return null;
  if (state === "estimated")
    return (
      <span className="text-[8px] italic text-slate-500 ml-1">est.</span>
    );
  return <span className="text-[8px] text-slate-600 ml-1">—</span>;
};

// ── Unavailable placeholder ───────────────────────────────────────────────────
const Unavailable = ({ reason }: { reason: string }) => (
  <span className="text-slate-500 text-[10px] uppercase tracking-wide">
    — <span className="normal-case not-italic">{reason}</span>
  </span>
);

// ── MetricRow ─────────────────────────────────────────────────────────────────
const MetricRow = ({
  label,
  value,
  subtext,
  metricKey,
  trend,
  state = "measured",
  onOpenMethodology,
}: {
  label: string;
  value: ReactNode;
  subtext?: string;
  metricKey: string;
  trend?: "up" | "down" | "neutral" | null;
  state?: MetricState;
  onOpenMethodology: (metricKey: string) => void;
}) => (
  <div className="flex flex-col py-2.5 border-b border-slate-700/30 last:border-0 hover:bg-slate-800/10 transition-colors group">
    <div className="flex justify-between items-start">
      <div className="flex flex-col">
        <span className="text-xs text-slate-300 font-medium">
          {label}
          <StateTag state={state} />
        </span>
        {subtext && (
          <span className="text-[10px] text-slate-500 mt-0.5">{subtext}</span>
        )}
      </div>
      <div className="flex flex-col items-end">
        <div className="flex items-center gap-1.5">
          {trend === "up" && (
            <span className="text-[10px] text-emerald-400">↗</span>
          )}
          {trend === "down" && (
            <span className="text-[10px] text-rose-400">↘</span>
          )}
          {trend === "neutral" && (
            <span className="text-[10px] text-slate-400">→</span>
          )}
          <span className="text-sm font-semibold text-white tracking-wide">
            {value}
          </span>
        </div>
      </div>
    </div>
    <button
      onClick={() => onOpenMethodology(metricKey)}
      className="text-[9px] text-indigo-400 hover:text-indigo-300 text-left mt-1.5 opacity-0 group-hover:opacity-100 transition-opacity w-fit flex items-center gap-1"
    >
      <svg
        width="10"
        height="10"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <circle cx="12" cy="12" r="10"></circle>
        <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path>
        <line x1="12" y1="17" x2="12.01" y2="17"></line>
      </svg>
      Why this value?
    </button>
  </div>
);

// ── Grounding label helpers ───────────────────────────────────────────────────
const GROUNDING_TEXT: Record<string, string> = {
  RASTER_GROUNDED: "Pixel-exact layer",
  ZONE_GROUNDED: "Zone-grounded layer",
  PROXY_SPATIAL: "Proxy-spatial estimate",
  UNIFORM: "Field-level proxy",
};

const GROUNDING_COLOR: Record<string, string> = {
  RASTER_GROUNDED: "text-emerald-500",
  ZONE_GROUNDED: "text-violet-500",
  PROXY_SPATIAL: "text-sky-500",
  UNIFORM: "text-amber-500",
};

const GROUNDING_DOT: Record<string, string> = {
  RASTER_GROUNDED: "bg-emerald-400",
  ZONE_GROUNDED: "bg-violet-400",
  PROXY_SPATIAL: "bg-sky-400",
  UNIFORM: "bg-amber-400",
};

// ── Main Component ────────────────────────────────────────────────────────────
export default function ContextualAnalysisDrawer({
  data,
  activeMode,
  selectedZoneId,
  onOpenMethodology,
  onClose,
  detailMode = "farmer",
}: ContextualAnalysisDrawerProps) {
  if (!data) return null;

  const surfaceType = MODE_SURFACE_MAP[activeMode];
  const activeSurface = data.surfaces?.find((s) => s.type === surfaceType);
  const activeZone = selectedZoneId
    ? data.zones?.find((z) => z.zone_id === selectedZoneId)
    : null;

  // ── 3-priority metric resolution (WS1) ─────────────────────────────────────
  // Priority 1: pre-computed surface_stats for this exact surface (same-origin zone)
  // Priority 2: zone histogram (cross-surface, already computed by zone_hist.py)
  // Priority 3: inline computation from activeSurface.values + cell_indices
  // NEVER: zone.severity
  let currentMean: number | null = null;
  let currentStd: number | null = null;
  let currentP10: number | null = null;
  let currentP90: number | null = null;
  let metricSource: "surface_stats" | "zone_histogram" | "inline" | "field" | null = null;

  if (activeZone) {
    // Priority 1
    const statsForSurface = activeZone.surface_stats?.[surfaceType];
    if (statsForSurface?.mean !== undefined) {
      currentMean = statsForSurface.mean;
      currentStd = statsForSurface.std ?? null;
      currentP10 = statsForSurface.p10 ?? null;
      currentP90 = statsForSurface.p90 ?? null;
      metricSource = "surface_stats";
    }

    // Priority 2: zone histogram from zone_hist.py (cross-surface capable)
    if (currentMean === null) {
      const zoneHist = data.histograms.zone?.find(
        (h) => h.surface_type === surfaceType && h.region_id === activeZone.zone_id
      );
      if (zoneHist) {
        currentMean = zoneHist.mean;
        currentStd = zoneHist.std ?? null;
        currentP10 = zoneHist.p10 ?? null;
        currentP90 = zoneHist.p90 ?? null;
        metricSource = "zone_histogram";
      }
    }

    // Priority 3: inline computation
    if (currentMean === null && activeSurface?.values && activeZone.cell_indices?.length) {
      currentMean = computeZonalMean(activeSurface.values, activeZone.cell_indices as [number, number][]);
      if (currentMean !== null) {
        currentStd = computeZonalStd(activeSurface.values, activeZone.cell_indices as [number, number][]);
        currentP10 = computeZonalP10(activeSurface.values, activeZone.cell_indices as [number, number][]);
        currentP90 = computeZonalP90(activeSurface.values, activeZone.cell_indices as [number, number][]);
        metricSource = "inline";
      }
    }
    // If still null → show Unavailable (never severity)
  } else {
    // Field average: use histogram mean first (most stable), else raster mean
    const fieldHist = data.histograms.field?.find((h) => h.surface_type === surfaceType);
    if (fieldHist) {
      currentMean = fieldHist.mean;
      currentStd = fieldHist.std ?? null;
      currentP10 = fieldHist.p10 ?? null;
      currentP90 = fieldHist.p90 ?? null;
      metricSource = "field";
    } else if (activeSurface?.values) {
      // Fallback inline field mean (already skips nulls — those are outside polygon)
      let sum = 0, count = 0;
      for (const row of activeSurface.values)
        for (const v of row)
          if (v !== null && v !== undefined && !Number.isNaN(v)) { sum += v; count++; }
      currentMean = count > 0 ? sum / count : null;
      metricSource = "field";
    }
  }

  // ── Field mask validity guard (WS8) ───────────────────────────────────────
  const fieldHist = data.histograms.field?.find((h) => h.surface_type === surfaceType);
  const coverageRatio =
    fieldHist?.valid_pixels != null && fieldHist?.total_pixels
      ? fieldHist.valid_pixels / fieldHist.total_pixels
      : null;
  const partialCoverage = coverageRatio !== null && coverageRatio < 0.7;

  // ── Derived display values ─────────────────────────────────────────────────
  const meanFmt = currentMean !== null ? currentMean.toFixed(3) : null;

  // ── Context label (WS4) ───────────────────────────────────────────────────
  const zoneSurfaceOrigin = activeZone?.top_drivers?.[0] ?? null;
  const isCrossSurface =
    activeZone !== null &&
    zoneSurfaceOrigin !== null &&
    zoneSurfaceOrigin !== surfaceType;

  const modeLabel = activeMode.replace(/_/g, " ").toUpperCase();
  const zoneTypeLabel = activeZone
    ? activeZone.zone_type?.replace(/_/g, " ") || "ZONE"
    : null;

  let drawerTitle = `${modeLabel} — Field`;
  if (activeZone && !isCrossSurface) {
    drawerTitle = `${modeLabel} — Zone`;
  } else if (activeZone && isCrossSurface) {
    drawerTitle = `${modeLabel} in ${zoneTypeLabel}`;
  }

  // ── Provenance / freshness ─────────────────────────────────────────────────
  const provenance = activeSurface?.provenance || {};
  let dataFreshness = provenance.timestamp
    ? new Date(provenance.timestamp as string).toLocaleDateString()
    : "Live Compute";
  if (activeZone) {
    const areaPercent = (activeZone.area_fraction * 100).toFixed(1);
    dataFreshness = `Zone: ${areaPercent}% of field`;
  }

  // ── Histogram for field context ────────────────────────────────────────────
  const activePack = data.explainability_pack?.[surfaceType];
  const groundingClass = activeSurface?.grounding_class ?? "UNIFORM";
  const stretchLabel =
    detailMode === "expert" ? "P01–P99 field stretch" : "P02–P98 field stretch";

  // ── Metric source badge ────────────────────────────────────────────────────
  const sourceBadge =
    metricSource === "inline"
      ? "computed on-the-fly"
      : metricSource === "zone_histogram"
      ? "cross-surface zonal"
      : null;

  return (
    <div className="absolute top-4 right-4 w-64 bg-slate-900/80 backdrop-blur-xl border border-slate-700/60 rounded-xl shadow-2xl flex flex-col overflow-hidden pointer-events-auto z-10 animate-fade-in-left">
      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div className="px-4 py-3 bg-slate-800/40 border-b border-slate-700/50 flex flex-col gap-1.5">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-bold text-slate-200 tracking-wider uppercase">
            {drawerTitle}
          </h3>
          <div className="flex items-center gap-2">
            <div
              className={`px-1.5 py-0.5 rounded text-[9px] font-mono ${
                selectedZoneId
                  ? "bg-indigo-500/20 text-indigo-300 border border-indigo-500/30"
                  : "bg-slate-700/50 text-slate-400"
              }`}
            >
              {selectedZoneId && activeZone
                ? activeZone.label || activeZone.zone_type?.replace(/_/g, " ") || selectedZoneId
                : "FIELD AVG"}
            </div>
            <button
              onClick={onClose}
              className="text-slate-400 hover:text-white transition-colors p-1"
              title="Close Panel"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>
        </div>

        {/* Grounding truth label */}
        <div className="flex items-center gap-1.5">
          <span className={`w-1.5 h-1.5 rounded-full ${GROUNDING_DOT[groundingClass] ?? "bg-amber-400"}`} />
          <span className={`text-[10px] font-semibold uppercase tracking-widest ${GROUNDING_COLOR[groundingClass] ?? "text-amber-500"}`}>
            {GROUNDING_TEXT[groundingClass] ?? "Field-level proxy"}
          </span>
        </div>

        {/* Cross-surface warning badge (WS4) */}
        {isCrossSurface && (
          <div className="flex items-center gap-1 bg-amber-500/10 border border-amber-500/20 rounded px-1.5 py-0.5">
            <span className="text-amber-400 text-[8px]">⚠</span>
            <span className="text-[8px] text-amber-400">
              Zone origin: {zoneSurfaceOrigin?.replace(/_/g, " ")}
            </span>
          </div>
        )}

        {/* Stretch disclosure (WS7) */}
        <span className="text-[9px] text-slate-500 italic">{stretchLabel}</span>

        {/* Partial coverage warning (WS8) */}
        {partialCoverage && (
          <span className="text-[9px] text-amber-400">
            ⚠ Partial field coverage ({((coverageRatio ?? 0) * 100).toFixed(0)}%)
          </span>
        )}

        {/* Cross-surface metric source attribution */}
        {sourceBadge && (
          <span className="text-[8px] text-slate-500 italic">
            Metric: {sourceBadge} from {surfaceType.replace(/_/g, " ")}
          </span>
        )}
      </div>

      {/* ── Body ───────────────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-4 py-1 max-h-[50vh] scrollbar-thin scrollbar-thumb-slate-700">

        {/* ── VEGETATION ───────────────────────────────────────────────────── */}
        {activeMode === "vegetation" && (
          <>
            <MetricRow
              onOpenMethodology={onOpenMethodology}
              label="Current Baseline"
              value={
                meanFmt !== null ? (
                  <span className={`text-xl font-bold ${groundingClass === "UNIFORM" ? "opacity-80" : ""}`}>
                    {meanFmt}{" "}
                    <span className="text-sm font-normal text-slate-500">NDVI</span>
                  </span>
                ) : (
                  <Unavailable reason="no valid raster cells" />
                )
              }
              subtext={`Acquired: ${dataFreshness}`}
              metricKey="vegetation_baseline"
              state={meanFmt !== null ? "measured" : "unavailable"}
            />
            {currentP10 !== null && currentP90 !== null && (
              <MetricRow
                onOpenMethodology={onOpenMethodology}
                label="P10 — P90 Range"
                value={
                  <span className="text-sm font-semibold text-slate-300">
                    {currentP10.toFixed(3)} – {currentP90.toFixed(3)}
                  </span>
                }
                subtext="10th–90th percentile spread"
                metricKey="vegetation_spread"
                state="measured"
              />
            )}
            {currentStd !== null && (
              <MetricRow
                onOpenMethodology={onOpenMethodology}
                label="Spatial Std Dev"
                value={<span className="text-sm font-semibold text-slate-300">±{currentStd.toFixed(3)}</span>}
                subtext="Within-zone heterogeneity"
                metricKey="vegetation_std"
                state="measured"
              />
            )}
            <MetricRow
              onOpenMethodology={onOpenMethodology}
              label="7-Day Delta"
              value={
                data.histograms.delta?.find((d) => d.surface_type === "NDVI_CLEAN")
                  ?.mean_change != null ? (
                  <span className="text-emerald-500 font-bold">
                    {(
                      data.histograms.delta.find((d) => d.surface_type === "NDVI_CLEAN")!
                        .mean_change * 100
                    ).toFixed(1)}
                    %
                  </span>
                ) : (
                  <Unavailable reason="requires historical frame" />
                )
              }
              subtext="Trailing anomaly"
              metricKey="vegetation_delta"
              state={data.histograms.delta?.find((d) => d.surface_type === "NDVI_CLEAN") ? "measured" : "unavailable"}
            />
            <MetricRow
              onOpenMethodology={onOpenMethodology}
              label="Biomass Estimate"
              value={<Unavailable reason="needs local calibration" />}
              subtext="Allometric model not loaded"
              metricKey="biomass_estimate"
              state="unavailable"
            />
            <MetricRow
              onOpenMethodology={onOpenMethodology}
              label="Stability Class"
              value={
                provenance.phenology_stage ? (
                  <span className="font-semibold text-slate-300">
                    {provenance.phenology_stage.toString().replace(/_/g, " ")}
                  </span>
                ) : (
                  <Unavailable reason="no phenology data" />
                )
              }
              subtext="Phenological context"
              metricKey="phenology_stability"
              state={provenance.phenology_stage ? "estimated" : "unavailable"}
            />
          </>
        )}

        {/* ── WATER STRESS ─────────────────────────────────────────────────── */}
        {activeMode === "water_stress" && (
          <>
            <MetricRow
              onOpenMethodology={onOpenMethodology}
              label="Stress Probability"
              value={
                meanFmt !== null ? (
                  <span className="text-xl font-bold text-amber-500">
                    {(currentMean! * 100).toFixed(1)}%
                  </span>
                ) : (
                  <Unavailable reason="no valid cells" />
                )
              }
              subtext="SAR/thermal fusion proxy"
              metricKey="water_probability"
              state={meanFmt !== null ? "estimated" : "unavailable"}
            />
            <MetricRow
              onOpenMethodology={onOpenMethodology}
              label="Est. Soil Deficit"
              value={<Unavailable reason="requires field capacity depth" />}
              subtext="Pedological model not loaded"
              metricKey="water_depletion"
              state="unavailable"
            />
            <MetricRow
              onOpenMethodology={onOpenMethodology}
              label="ETc Deficit"
              value={<Unavailable reason="requires micrometeorology" />}
              subtext="No weather station data"
              metricKey="water_et"
              state="unavailable"
            />
            <MetricRow
              onOpenMethodology={onOpenMethodology}
              label="Recent Irrigation"
              value={<Unavailable reason="no event log" />}
              subtext="Requires logged irrigation events"
              metricKey="irrigation_memory"
              state="unavailable"
            />
          </>
        )}

        {/* ── NUTRIENT RISK ─────────────────────────────────────────────────── */}
        {activeMode === "nutrient_risk" && (
          <>
            <MetricRow
              onOpenMethodology={onOpenMethodology}
              label="Nutrient Deficit Prob."
              value={
                meanFmt !== null ? (
                  <span className="text-lg font-bold text-rose-400">
                    {(currentMean! * 100).toFixed(0)}%
                  </span>
                ) : (
                  <Unavailable reason="no valid cells" />
                )
              }
              subtext="Chlorophyll anomaly proxy"
              metricKey="nutrient_stress_prob"
              state={meanFmt !== null ? "estimated" : "unavailable"}
            />
            <MetricRow
              onOpenMethodology={onOpenMethodology}
              label="NDRE / Red-Edge"
              value={<Unavailable reason="Sentinel-2 missing bands" />}
              subtext="Band 5 (703nm) not available"
              metricKey="ndre_proxy"
              state="unavailable"
            />
            <MetricRow
              onOpenMethodology={onOpenMethodology}
              label="Expected Gain"
              value={<Unavailable reason="requires Rx response model" />}
              subtext="No response curve loaded"
              metricKey="expected_gain"
              state="unavailable"
            />
            <MetricRow
              onOpenMethodology={onOpenMethodology}
              label="Soil Chemistry"
              value={<Unavailable reason="requires NPK baseline" />}
              subtext="Upload latest soil test"
              metricKey="soil_chemistry_freshness"
              state="unavailable"
            />
          </>
        )}

        {/* ── COMPOSITE RISK ────────────────────────────────────────────────── */}
        {activeMode === "composite_risk" && (
          <>
            <MetricRow
              onOpenMethodology={onOpenMethodology}
              label="Overall Field Risk"
              value={
                meanFmt !== null ? (
                  <span className="text-lg font-bold text-amber-500">
                    {(currentMean! * 10).toFixed(1)} / 10
                  </span>
                ) : (
                  <Unavailable reason="no valid cells" />
                )
              }
              subtext="Multi-factor intersection"
              metricKey="composite_overall"
              state={meanFmt !== null ? "estimated" : "unavailable"}
            />
            <MetricRow
              onOpenMethodology={onOpenMethodology}
              label="Top Driver 1"
              value={
                activePack?.top_drivers?.[0] ? (
                  <span className="font-semibold text-slate-300">
                    {activePack.top_drivers[0].name}
                  </span>
                ) : (
                  <Unavailable reason="insufficient variance" />
                )
              }
              subtext={
                activePack?.top_drivers?.[0]
                  ? `${(activePack.top_drivers[0].value * 100).toFixed(0)}% weight`
                  : undefined
              }
              metricKey="top_driver_1"
              state={activePack?.top_drivers?.[0] ? "measured" : "unavailable"}
            />
            <MetricRow
              onOpenMethodology={onOpenMethodology}
              label="Top Driver 2"
              value={
                activePack?.top_drivers?.[1] ? (
                  <span className="font-semibold text-slate-300">
                    {activePack.top_drivers[1].name}
                  </span>
                ) : (
                  <Unavailable reason="insufficient variance" />
                )
              }
              subtext={
                activePack?.top_drivers?.[1]
                  ? `${(activePack.top_drivers[1].value * 100).toFixed(0)}% weight`
                  : undefined
              }
              metricKey="top_driver_2"
              state={activePack?.top_drivers?.[1] ? "measured" : "unavailable"}
            />
            <MetricRow
              onOpenMethodology={onOpenMethodology}
              label="Stage Vulnerability"
              value={<Unavailable reason="awaiting L2-Phenology" />}
              subtext="Crop stage model not loaded"
              metricKey="stage_weighting"
              state="unavailable"
            />
          </>
        )}

        {/* ── UNCERTAINTY ───────────────────────────────────────────────────── */}
        {activeMode === "uncertainty" && (
          <>
            <MetricRow
              onOpenMethodology={onOpenMethodology}
              label="Uncertainty Sigma"
              value={
                meanFmt !== null ? (
                  `±${currentMean!.toFixed(3)}`
                ) : (
                  <Unavailable reason="no sigma surface" />
                )
              }
              subtext="Mean spatial variance"
              metricKey="uncertainty_sigma"
              state={meanFmt !== null ? "measured" : "unavailable"}
            />
            {currentP10 !== null && currentP90 !== null && (
              <MetricRow
                onOpenMethodology={onOpenMethodology}
                label="Sigma P10 – P90"
                value={
                  <span className="text-sm font-semibold text-slate-300">
                    {currentP10.toFixed(3)} – {currentP90.toFixed(3)}
                  </span>
                }
                subtext="Low–high uncertainty spread"
                metricKey="uncertainty_spread"
                state="measured"
              />
            )}
            {/* Expert-mode trust source (WS6) */}
            {detailMode === "expert" && (
              <MetricRow
                onOpenMethodology={onOpenMethodology}
                label="Trust Source"
                value={
                  <span className="text-slate-300 text-[10px]">
                    inverted sigma fallback
                  </span>
                }
                subtext="DATA_RELIABILITY not available"
                metricKey="trust_source"
                state="estimated"
              />
            )}
            <MetricRow
              onOpenMethodology={onOpenMethodology}
              label="Source Dominance"
              value="Sentinel-2 L2A"
              subtext="Primary optic contributor"
              metricKey="source_dominance"
              state="measured"
            />
            <MetricRow
              onOpenMethodology={onOpenMethodology}
              label="Atmospheric Haze"
              value={<Unavailable reason="cloud masking unavailable" />}
              subtext="No cloud metadata"
              metricKey="cloud_contamination"
              state="unavailable"
            />
            <MetricRow
              onOpenMethodology={onOpenMethodology}
              label="Last Ground Truth"
              value={<Unavailable reason="no sensor data" />}
              subtext="Requires local sensors"
              metricKey="sensor_grounding"
              state="unavailable"
            />
          </>
        )}
      </div>

      {/* ── Footer ─────────────────────────────────────────────────────────── */}
      <div className="px-4 py-3 bg-indigo-900/10 border-t border-slate-700/50">
        <div className="flex items-center justify-between">
          <span className="text-[10px] text-slate-400">Layer Context</span>
          <span className="text-[9px] uppercase tracking-wider text-indigo-400 font-bold">
            L10 Output
          </span>
        </div>
      </div>
    </div>
  );
}
