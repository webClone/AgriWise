"use client";

import { useMemo } from "react";
import type { Layer10Result, MapMode } from "@/hooks/useLayer10";

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

function getModeFacts(data: Layer10Result, mode: MapMode, activeSurfaceType?: string): HUDFact[] {
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
      if (!stats) return [{ label: "Status", value: "No data" }];
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
      const stats = computeSurfaceStats(data, "UNCERTAINTY_SIGMA");
      if (!stats) return [{ label: "Status", value: "No data" }];
      const qualityLabel =
        stats.mean < 0.1 ? "Excellent" : stats.mean < 0.2 ? "Good" : "Low";
      const qualityColor =
        stats.mean < 0.1 ? "text-emerald-400" : stats.mean < 0.2 ? "text-amber-400" : "text-rose-400";
      return [
        { label: "Data Quality", value: qualityLabel, accent: qualityColor },
        { label: "Mean σ", value: stats.mean.toFixed(3) },
        { label: "Worst (P90)", value: stats.p90.toFixed(3) },
        { label: "Coverage", value: `${(stats.coverage * 100).toFixed(0)}%` },
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
    case "composite_risk":
      return `Composite of water, nutrient, biotic risk · ${pipeline}`;
    case "uncertainty":
      return `Pixel-level confidence estimate · ${pipeline}`;
    default:
      return `${pipeline} · ${grid}`;
  }
}

export default function FieldSnapshotHUD({ data, activeMode, activeSurfaceType }: FieldSnapshotHUDProps) {
  const facts = useMemo(() => getModeFacts(data, activeMode, activeSurfaceType), [data, activeMode, activeSurfaceType]);
  const whyLine = useMemo(() => getWhyLine(data, activeMode), [data, activeMode]);

  return (
    <div className="absolute top-24 left-4 z-10 pointer-events-none select-none" id="field-snapshot-hud">
      <div className="bg-slate-900/80 backdrop-blur-md border border-slate-700/50 rounded-xl p-3 shadow-xl w-56 pointer-events-auto">
        {/* Facts grid */}
        <div className="grid grid-cols-2 gap-2 mb-2">
          {facts.map((fact) => (
            <div key={fact.label} className="bg-slate-800/40 rounded-lg px-2.5 py-1.5">
              <div className={`text-[11px] font-bold leading-tight ${fact.accent || "text-slate-200"}`}>
                {fact.value}
              </div>
              <div className="text-[8px] font-medium uppercase tracking-wider text-slate-500 mt-0.5">
                {fact.label}
              </div>
            </div>
          ))}
        </div>

        {/* Why line */}
        <div className="text-[9px] text-slate-500 leading-snug border-t border-slate-700/40 pt-1.5">
          {whyLine}
        </div>
      </div>
    </div>
  );
}
