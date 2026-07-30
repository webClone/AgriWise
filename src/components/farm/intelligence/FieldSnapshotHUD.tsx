"use client";

import { useMemo } from "react";
import { useLayer10, type Layer10Result, type MapMode } from "@/hooks/useLayer10";
import { sanitizeRecommendedAction } from "@/lib/agribrain/plot-map-evidence-state";

let _usePlotIntelligence: any = null;
try {
  _usePlotIntelligence = require("@/hooks/usePlotIntelligence").usePlotIntelligence;
} catch { /* not available */ }

interface FieldSnapshotHUDProps {
  data: Layer10Result;
  activeMode: MapMode;
  activeSurfaceType?: string;
}

/** Mode-specific fact definitions */
interface HUDFact {
  label: string;
  value: string;
  accent?: string; // tailwind text color
}

function computeSurfaceStats(data: Layer10Result, surfaceType: string) {
  const surface = data.surfaces.find((s) => s.type === surfaceType);
  if (!surface) return null;

  const vals: number[] = [];
  for (const row of surface.values) {
    for (const v of row) {
      if (v !== null && v !== undefined && !isNaN(v)) vals.push(v);
    }
  }
  if (vals.length === 0) return null;

  const sum = vals.reduce((a, b) => a + b, 0);
  const mean = sum / vals.length;
  const sorted = [...vals].sort((a, b) => a - b);
  const p10 = sorted[Math.floor(vals.length * 0.1)];
  const p90 = sorted[Math.floor(vals.length * 0.9)];
  const std = Math.sqrt(vals.reduce((a, v) => a + (v - mean) ** 2, 0) / vals.length);
  const totalCells = data.grid.height * data.grid.width;
  const coverage = totalCells > 0 ? vals.length / totalCells : 1;

  return { mean, std, p10, p90, coverage, count: vals.length };
}

function getModeFacts(data: Layer10Result, mode: MapMode, activeSurfaceType?: string, weatherFallbackFacts?: HUDFact[]): HUDFact[] {
  const quality = data.quality;
  const reliabilityScore = quality?.reliability_score ?? 0;
  const reliabilityLabel =
    reliabilityScore > 0.8 ? "High" : reliabilityScore > 0.5 ? "Moderate" : "Low";
  const reliabilityColor =
    reliabilityScore > 0.8 ? "text-emerald-400" : reliabilityScore > 0.5 ? "text-amber-400" : "text-rose-400";

  switch (mode) {
    case "canopy":
    case "vegetation": {
      const stats = computeSurfaceStats(data, "NDVI_CLEAN");
      if (!stats) {
        // Fallback: show current conditions from intelligence data
        return weatherFallbackFacts || [{ label: "Status", value: "Awaiting data" }];
      }
      const vigorColor =
        stats.mean > 0.6 ? "text-emerald-400" : stats.mean > 0.35 ? "text-amber-400" : "text-rose-400";
      return [
        { label: "Mean Vigor", value: stats.mean.toFixed(2), accent: vigorColor },
        { label: "Consistency", value: `σ ${stats.std.toFixed(3)}` },
        { label: "Coverage", value: `${(stats.coverage * 100).toFixed(0)}%` },
        { label: "Confidence", value: reliabilityLabel, accent: reliabilityColor },
      ];
    }
    case "veg_attention": {
      // Patch 6: Use dynamic surface type instead of hardcoding NDVI_DEVIATION
      const surfaceType = activeSurfaceType || "NDVI_DEVIATION"; // passed from parent
      const stats = computeSurfaceStats(data, surfaceType);
      
      const backendState = data.quality?.zone_state_by_surface?.[surfaceType];
      if (backendState === "no_data") return [{ label: "Status", value: "No data" }];
      if (!stats) return [{ label: "Status", value: "No data" }];
      
      const threshold = Math.max(-(1.2 * stats.std), -0.08);
      const aboveThresholdCount = stats.count > 0
        ? data.surfaces.find(s => s.type === surfaceType)?.values
            .flat()
            .filter((v): v is number => v !== null && v !== undefined && v < threshold)
            .length ?? 0
        : 0;
      const anomalyCoverage = stats.count > 0 ? (aboveThresholdCount / stats.count * 100) : 0;
      
      // Patch 6 logic: read backend state first!
      let statusLabel = "Normal";
      let statusAccent = "text-emerald-400";
      if (backendState === "field_wide") {
          statusLabel = "Field-Wide";
          statusAccent = "text-amber-400";
      } else if (backendState === "localized") {
          statusLabel = "Localized";
          statusAccent = "text-rose-400";
      }
      
      return [
        { label: "Anomaly Coverage", value: backendState === "field_wide" ? "100%" : `${anomalyCoverage.toFixed(1)}%`, accent: anomalyCoverage > 5 ? "text-rose-400" : "text-emerald-400" },
        { label: "P10 Deviation", value: stats.p10.toFixed(3) },
        { label: "Surface Mode", value: surfaceType.replace("_", " "), accent: statusAccent },
        { label: "System State", value: statusLabel, accent: statusAccent },
      ];
    }
    case "water_stress": {
      const stats = computeSurfaceStats(data, "WATER_STRESS_PROB");
      if (!stats) return [{ label: "Status", value: "No data" }];
      const stressLevel =
        stats.mean > 0.6 ? "High" : stats.mean > 0.3 ? "Moderate" : "Low";
      const stressColor =
        stats.mean > 0.6 ? "text-rose-400" : stats.mean > 0.3 ? "text-amber-400" : "text-emerald-400";
      return [
        { label: "Stress Level", value: stressLevel, accent: stressColor },
        { label: "Mean Prob.", value: stats.mean.toFixed(2) },
        { label: "P90", value: stats.p90.toFixed(2) },
        { label: "Confidence", value: reliabilityLabel, accent: reliabilityColor },
      ];
    }
    case "nutrient_risk": {
      const stats = computeSurfaceStats(data, "NUTRIENT_STRESS_PROB");
      if (!stats) return [{ label: "Status", value: "No data" }];
      const riskLevel =
        stats.mean > 0.5 ? "High" : stats.mean > 0.25 ? "Moderate" : "Low";
      const riskColor =
        stats.mean > 0.5 ? "text-rose-400" : stats.mean > 0.25 ? "text-amber-400" : "text-emerald-400";
      return [
        { label: "Nutrient Risk", value: riskLevel, accent: riskColor },
        { label: "Mean Prob.", value: stats.mean.toFixed(2) },
        { label: "P90", value: stats.p90.toFixed(2) },
        { label: "Confidence", value: reliabilityLabel, accent: reliabilityColor },
      ];
    }
    case "salinity": {
      const stats = computeSurfaceStats(data, "SALINITY_STRESS");
      if (!stats) return [{ label: "Status", value: "No data" }];
      const salinityLevel =
        stats.mean > 0.6 ? "Severe" : stats.mean > 0.3 ? "Moderate" : stats.mean > 0.15 ? "Mild" : "Non-saline";
      const salinityColor =
        stats.mean > 0.6 ? "text-rose-400" : stats.mean > 0.3 ? "text-amber-400" : stats.mean > 0.15 ? "text-cyan-400" : "text-emerald-400";
      return [
        { label: "Salinity Level", value: salinityLevel, accent: salinityColor },
        { label: "Mean Prob.", value: stats.mean.toFixed(2) },
        { label: "P90 ECe Proxy", value: stats.p90.toFixed(2) },
        { label: "Confidence", value: reliabilityLabel, accent: reliabilityColor },
      ];
    }
    case "composite_risk": {
      const stats = computeSurfaceStats(data, "COMPOSITE_RISK");
      if (!stats) return [{ label: "Status", value: "No data" }];
      const severity =
        stats.mean > 0.6 ? "High" : stats.mean > 0.3 ? "Moderate" : "Low";
      const sevColor =
        stats.mean > 0.6 ? "text-rose-400" : stats.mean > 0.3 ? "text-amber-400" : "text-emerald-400";
      return [
        { label: "Severity", value: severity, accent: sevColor },
        { label: "Mean Score", value: stats.mean.toFixed(2) },
        { label: "Peak (P90)", value: stats.p90.toFixed(2) },
        { label: "Confidence", value: reliabilityLabel, accent: reliabilityColor },
      ];
    }
    case "uncertainty": {
      // Fallback rule: prefer DATA_RELIABILITY, fallback to 1 - UNCERTAINTY_SIGMA, otherwise no data
      let stats = computeSurfaceStats(data, "DATA_RELIABILITY");
      let meanVal = stats ? stats.mean : 0.0;
      let p10Val = stats ? stats.p10 : 0.0;
      let p90Val = stats ? stats.p90 : 0.0;
      let coverageVal = stats ? stats.coverage : 0.0;

      if (!stats) {
        const sigmaStats = computeSurfaceStats(data, "UNCERTAINTY_SIGMA");
        if (sigmaStats) {
          meanVal = 1 - sigmaStats.mean;
          p10Val = 1 - sigmaStats.p90;
          p90Val = 1 - sigmaStats.p10;
          coverageVal = sigmaStats.coverage;
          stats = sigmaStats;
        }
      }

      if (!stats) return [{ label: "Status", value: "No data" }];

      const qualityLabel =
        meanVal > 0.8 ? "Excellent" : meanVal > 0.5 ? "Good" : "Low";
      const qualityColor =
        meanVal > 0.8 ? "text-emerald-400" : meanVal > 0.5 ? "text-amber-400" : "text-rose-400";

      return [
        { label: "Data Reliability", value: qualityLabel, accent: qualityColor },
        { label: "Mean Score", value: meanVal.toFixed(3) },
        { label: "Worst P10", value: p10Val.toFixed(3), accent: p10Val < 0.4 ? "text-rose-400" : "text-slate-200" },
        { label: "Coverage", value: `${(coverageVal * 100).toFixed(0)}%` },
      ];
    }
    case "resolution_coverage": {
      const resSurface = data.surfaces.find((s) => s.type === "RESOLUTION_COVERAGE");
      let count3cm = 0, count1m = 0, count2m = 0, count3m = 0, count5m = 0, count10m = 0, totalValid = 0;
      if (resSurface) {
        for (const row of resSurface.values) {
          for (const v of row) {
            if (v !== null && v !== undefined && !isNaN(v)) {
              totalValid++;
              // RESOLUTION_COVERAGE is categorical, not a physical-metre raster:
              // 0=external 3 cm, 1=advisory fine detail, 2/3/4=model-assisted,
              // 5=native 10 m evidence.
              const classCode = Math.round(Number(v));
              if (classCode === 0) count3cm++;
              else if (classCode === 1) count1m++;
              else if (classCode === 2) count2m++;
              else if (classCode === 3) count3m++;
              else if (classCode === 4) count5m++;
              else if (classCode === 5) count10m++;
              else totalValid--;
            }
          }
        }
      }

      if (totalValid > 0) {
        const pct3cm = (count3cm / totalValid) * 100;
        const pct1m = (count1m / totalValid) * 100;
        const pct2m = (count2m / totalValid) * 100;
        const pct3m = (count3m / totalValid) * 100;
        const pct5m = (count5m / totalValid) * 100;
        const pct10m = (count10m / totalValid) * 100;

        let verdict = "Mixed resolution";
        let verdictColor = "text-slate-300";
        if (pct3cm > 80) { verdict = "Ultra High GSD"; verdictColor = "text-cyan-400"; }
        else if (pct1m + pct2m + pct3m + pct5m > 80) { verdict = "Model-assisted detail"; verdictColor = "text-emerald-400"; }
        else if (pct10m > 80) { verdict = "Native 10 m evidence"; verdictColor = "text-slate-400"; }

        // Build facts based on what dominant resolutions exist (top 3)
        const dominantResFacts: { label: string; value: string; accent?: string }[] = [];
        if (pct3cm > 0) dominantResFacts.push({ label: "UAV 3cm", value: `${pct3cm.toFixed(0)}%`, accent: "text-cyan-400" });
        if (pct1m > 0) dominantResFacts.push({ label: "Advisory fine detail", value: `${pct1m.toFixed(0)}%`, accent: "text-emerald-400" });
        if (pct2m > 0) dominantResFacts.push({ label: "Model-assisted 2m", value: `${pct2m.toFixed(0)}%`, accent: "text-teal-400" });
        if (pct3m > 0) dominantResFacts.push({ label: "Model-assisted 3m", value: `${pct3m.toFixed(0)}%`, accent: "text-blue-400" });
        if (pct5m > 0) dominantResFacts.push({ label: "Model-assisted 5m", value: `${pct5m.toFixed(0)}%`, accent: "text-amber-400" });
        if (pct10m > 0) dominantResFacts.push({ label: "Native 10m evidence", value: `${pct10m.toFixed(0)}%`, accent: "text-slate-400" });

        const resultFacts = dominantResFacts.slice(0, 3);
        resultFacts.push({ label: "Verdict", value: verdict, accent: verdictColor });
        return resultFacts;
      }

      // Fallback to ground truth summary if no surface values are present
      const gts = data.ground_truth_summary;
      if (!gts) return [{ label: "Status", value: "No ground truth" }];
      const rp = gts.resolution_percentages;
      const threeCm = rp?.three_cm_pct ?? rp?.three_cm_external_ground_truth_pct ?? 0;
      const fallback = rp?.fallback_pct ?? rp?.adaptive_production_fallback_pct ?? 100;
      const droneStatus = gts.drone_3cm?.status ?? "absent";
      const verdict = threeCm >= 80 ? "3cm Validated" : threeCm > 0 ? "Partial 3cm" : "Fallback Only";
      const verdictColor = threeCm >= 80 ? "text-cyan-400" : threeCm > 0 ? "text-amber-400" : "text-slate-400";
      return [
        { label: "3cm Coverage", value: `${threeCm.toFixed(0)}%`, accent: threeCm > 0 ? "text-cyan-400" : "text-slate-400" },
        { label: "Fallback", value: `${fallback.toFixed(0)}%` },
        { label: "Drone", value: droneStatus === "available" ? "Active" : "None", accent: droneStatus === "available" ? "text-emerald-400" : "text-slate-500" },
        { label: "Verdict", value: verdict, accent: verdictColor },
      ];
    }
    default:
      return [{ label: "Status", value: "Active" }];
  }
}

/** Provenance "why" line */
function getWhyLine(data: Layer10Result, mode: MapMode): string {
  const prov = data.provenance as Record<string, unknown>;
  const pipeline = (prov?.pipeline as string) || "SIRE";
  const grid = (prov?.grid as string) || "";

  switch (mode) {
    case "canopy":
    case "vegetation":
      return `Derived from cleaned NDVI · ${pipeline} · ${grid}`;
    case "veg_attention":
      return `Anomaly from mean-centered deviation · adaptive threshold`;
    case "water_stress":
      return `Modeled from spectral + weather indices · ${pipeline}`;
    case "nutrient_risk":
      return `Estimated from spectral signatures · ${pipeline}`;
    case "salinity":
      return `Soil salinity probability derived from EC/pH sensors · ${pipeline}`;
    case "composite_risk":
      return `Composite of water, nutrient, biotic risk · ${pipeline}`;
    case "uncertainty":
      return `Pixel-level confidence estimate · ${pipeline}`;
    case "resolution_coverage":
      return `Resolution class from ground truth registry · V61 categorical surface`;
    default:
      return `${pipeline} · ${grid}`;
  }
}

export default function FieldSnapshotHUD({ data, activeMode, activeSurfaceType }: FieldSnapshotHUDProps) {
  // Try to get current conditions from intelligence data
  let piData: any = null;
  try {
    if (_usePlotIntelligence) {
      const pi = _usePlotIntelligence();
      piData = pi?.data;
    }
  } catch { /* not inside provider */ }

  const weatherFallbackFacts = useMemo((): HUDFact[] => {
    const weather = piData?.current?.weather;
    if (!weather) return [{ label: "Status", value: "Awaiting data" }];
    const temp = weather?.temperature?.current ?? weather?.temp;
    const humidity = weather?.humidity;
    const wind = weather?.wind?.speed_ms;
    const condition = weather?.weather?.condition ?? weather?.weather?.description;
    return [
      { label: "Temperature", value: temp != null ? `${Number(temp).toFixed(1)}°C` : "—", accent: "text-amber-400" },
      { label: "Humidity", value: humidity != null ? `${humidity}%` : "—" },
      { label: "Wind", value: wind != null ? `${Number(wind).toFixed(1)} m/s` : "—" },
      { label: "Condition", value: condition || "—", accent: "text-sky-400" },
    ];
  }, [piData]);

  const facts = useMemo(() => getModeFacts(data, activeMode, activeSurfaceType, weatherFallbackFacts), [data, activeMode, activeSurfaceType, weatherFallbackFacts]);
  const whyLine = useMemo(() => getWhyLine(data, activeMode), [data, activeMode]);

  const activePack = useMemo(() => {
    const modeToSurfaceType: Record<string, string> = {
      canopy: "NDVI_CLEAN",
      vegetation: "NDVI_CLEAN",
      veg_attention: activeSurfaceType || "NDVI_DEVIATION",
      water_stress: "WATER_STRESS_PROB",
      nutrient_risk: "NUTRIENT_STRESS_PROB",
      salinity: "SALINITY_STRESS",
      composite_risk: "COMPOSITE_RISK",
      uncertainty: "DATA_RELIABILITY",
      resolution_coverage: "RESOLUTION_COVERAGE",
    };
    const sType = modeToSurfaceType[activeMode];
    return data?.explainability_pack?.[sType];
  }, [data, activeMode, activeSurfaceType]);

  const l10Context = useLayer10();
  const evidenceState = l10Context.evidenceState;
  const sanitizedAction = useMemo(() => {
    return sanitizeRecommendedAction(activePack?.recommended_action || null, evidenceState);
  }, [activePack?.recommended_action, evidenceState]);

  return (
    <div className="bg-slate-900/40 border border-white/12 rounded-xl p-3 shadow-[0_8px_32px_rgba(0,0,0,0.3),inset_0_1px_0_rgba(255,255,255,0.06)] w-full mb-3" id="field-snapshot-hud">
      {/* Facts grid */}
      <div className="grid grid-cols-2 gap-2 mb-2">
        {facts.map((fact) => (
          <div key={fact.label} className="bg-slate-800/40 rounded-lg px-2.5 py-1.5 border border-white/5">
            <div className={`text-[12px] font-bold leading-tight ${fact.accent || "text-slate-200"}`}>
              {fact.value}
            </div>
            <div className="text-[9px] font-medium uppercase tracking-wider text-slate-500 mt-0.5">
              {fact.label}
            </div>
          </div>
        ))}
      </div>

      {/* Why line */}
      <div className="text-[10px] text-slate-500 leading-snug border-t border-slate-700/40 pt-1.5 mt-1">
        {whyLine}
      </div>

      {/* Recommended Action Footer (V63F) */}
      {sanitizedAction.text && (
        <div className="text-[10px] leading-snug border-t border-slate-700/40 pt-1.5 mt-1.5 flex flex-col gap-0.5" id="hud-action-footer">
          <div className="flex items-center gap-1.5 justify-between">
            <span className="text-indigo-400 font-bold uppercase tracking-wider text-[8px]">Recommended Action</span>
            {sanitizedAction.actionLevel && (
              <span className="text-[8px] px-1.5 py-0.5 rounded font-bold uppercase tracking-wide bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
                {sanitizedAction.actionLevel}
              </span>
            )}
          </div>
          <div className="text-slate-300 font-semibold">{sanitizedAction.text}</div>
          {sanitizedAction.suppressed && (
            <div className="text-[8px] px-1.5 py-0.5 rounded font-bold bg-amber-500/10 border border-amber-500/20 text-amber-400 self-start mt-0.5">
              ⚠️ Action adjusted to current map evidence
            </div>
          )}
        </div>
      )}
    </div>
  );
}
