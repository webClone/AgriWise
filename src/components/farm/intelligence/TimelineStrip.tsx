"use client";

/**
 * TimelineStrip — Production-grade bottom timeline bar.
 *
 * 7 days past ← TODAY → 7 days forward
 *
 * Features:
 *   - Multi-metric sparkline overlay (temp, rain, NDVI, ET₀)
 *   - Animated scrubber with gradient fill
 *   - Day-cell hover cards with detailed data
 *   - Observed vs Forecast confidence indicator
 *   - Responsive, no-overlap layout
 */

import { useState, useMemo, useRef, useCallback, useEffect } from "react";
import { usePlotIntelligence } from "@/hooks/usePlotIntelligence";
import { useParcelAssessment } from "@/hooks/useParcelAssessment";
import { usePlotTelemetry } from "@/hooks/usePlotTelemetry";
import { classifyManifestEvidence, classifyTelemetryObservation, TELEMETRY_STATUS, type TelemetryObservation, type TelemetryStatus } from "@/lib/agribrain/telemetry-contract";

type MetricKey = "temp" | "rain" | "ndvi" | "et0" | "humidity";

interface MetricConfig {
  key: MetricKey;
  label: string;
  unit: string;
  color: string;
  gradient: [string, string];
  icon: string;
  format: (v: number) => string;
}

const METRICS: MetricConfig[] = [
  {
    key: "temp", label: "Temperature", unit: "°C",
    color: "#f97316", gradient: ["#f9731620", "#f9731605"],
    icon: "🌡️",
    format: (v) => `${v.toFixed(1)}°`,
  },
  {
    key: "rain", label: "Rainfall", unit: "mm",
    color: "#60a5fa", gradient: ["#60a5fa20", "#60a5fa05"],
    icon: "🌧️",
    format: (v) => `${v.toFixed(1)}`,
  },
  {
    key: "ndvi", label: "NDVI", unit: "",
    color: "#4ade80", gradient: ["#4ade8020", "#4ade8005"],
    icon: "🌿",
    format: (v) => v.toFixed(2),
  },
  {
    key: "et0", label: "ET₀", unit: "mm/d",
    color: "#a78bfa", gradient: ["#a78bfa20", "#a78bfa05"],
    icon: "💧",
    format: (v) => v.toFixed(1),
  },
  {
    key: "humidity", label: "Humidity", unit: "%",
    color: "#22d3ee", gradient: ["#22d3ee20", "#22d3ee05"],
    icon: "💨",
    format: (v) => `${v.toFixed(0)}`,
  },
];

interface DayCell {
  date: string;
  dayLabel: string;
  weekday: string;
  dayNum: number;
  isToday: boolean;
  isPast: boolean;
  values: Record<MetricKey, number | null>;
  source: "observed" | "forecast" | "estimated" | "unverified" | "gap";
  metricStatuses: Record<MetricKey, TelemetryStatus>;
  metricDotColors: Record<MetricKey, string>;
  certifiedManifestEventCount: number;
  cutoffDay: boolean;
  assessmentSnapshotId: string | null;
  ndviSource?: string;        // "observed" | "kalman" from backend
  ndviConfidence?: number;    // 0-1 from Kalman engine
  tempRange: { min: number | null; max: number | null };
  operationalObservations: Array<{
    id: string;
    source: string;
    metric: string;
    value: number;
    unit: string;
    observedAt: string;
    ingestedAt: string;
    timeBasis?: "server_received_at" | "source_observation_at" | "day_bucket_unverified";
    dayBucketDate?: string;
    obsType?: string;
    status: TelemetryStatus;
  }>;
}


const STATUS_LABEL: Record<TelemetryStatus, string> = {
  CERTIFIED_MANIFEST: "Certified in publication manifest",
  LIVE_UNCERTIFIED: "Live observation · uncertified",
  MODEL_FORECAST: "Model forecast · not observed",
  LATE_ARRIVING_UNADMITTED: "Historical observation · not admitted to manifest",
  UNVERIFIED: "Time, source or admission unverified",
};

// A PI timeline row cannot self-certify a scientific assessment.
// Require an explicit provider/model identity and a full observation timestamp.
function classifyTimelineDatum(
  datum: Record<string, unknown> | undefined,
  kind: "observation" | "forecast",
  cutoff: string | null,
  now: string
): TelemetryStatus {
  if (!datum) return TELEMETRY_STATUS.UNVERIFIED;
  const observedAt = datum.observedAt ?? datum.observed_at ?? datum.timestamp ?? datum.date;
  const ingestedAt = datum.ingestedAt ?? datum.ingested_at ?? datum.fetchedAt ?? datum.fetched_at;
  const validAt = datum.validAt ?? datum.valid_at ?? datum.date ?? datum.timestamp;
  const candidate: TelemetryObservation = {
    id: String(datum.id || datum.observation_id || "timeline-record"),
    kind,
    source: typeof datum.source === "string"
      ? datum.source : typeof datum.provider === "string" ? datum.provider : "",
    observedAt: typeof observedAt === "string" ? observedAt : undefined,
    ingestedAt: typeof ingestedAt === "string" ? ingestedAt : undefined,
    validAt: typeof validAt === "string" ? validAt : undefined,
    modelId: typeof datum.modelId === "string"
      ? datum.modelId : typeof datum.model_id === "string" ? datum.model_id : undefined,
  };
  return classifyTelemetryObservation(candidate, cutoff, now);
}

interface ResolvedMetricSupplier {
  value: number | null;
  supplier?: Record<string, unknown>;
  kind: "observation" | "forecast";
}

function resolveTimelineMetric(
  primaryRecord: Record<string, unknown> | undefined,
  primaryFields: string | string[],
  fallbackRecord: Record<string, unknown> | undefined,
  fallbackFields: string | string[],
  primaryKind: "observation" | "forecast" = "observation",
  fallbackKind: "observation" | "forecast" = "forecast"
): ResolvedMetricSupplier {
  const getNum = (rec: Record<string, unknown> | undefined, fields: string | string[]): number | null => {
    if (!rec) return null;
    const list = Array.isArray(fields) ? fields : [fields];
    for (const f of list) {
      const v = rec[f];
      if (v != null && Number.isFinite(Number(v))) {
        return Number(v);
      }
    }
    return null;
  };

  const primaryValue = getNum(primaryRecord, primaryFields);
  if (primaryValue !== null) {
    return { value: primaryValue, supplier: primaryRecord, kind: primaryKind };
  }

  const fallbackValue = getNum(fallbackRecord, fallbackFields);
  if (fallbackValue !== null) {
    return { value: fallbackValue, supplier: fallbackRecord, kind: fallbackKind };
  }

  return { value: null, supplier: undefined, kind: primaryKind };
}

function resolveEt0Metric(
  weatherObs: Record<string, unknown> | undefined,
  wbObs: Record<string, unknown> | undefined,
  forecastObs: Record<string, unknown> | undefined
): ResolvedMetricSupplier {
  if (weatherObs?.et0 != null && Number.isFinite(Number(weatherObs.et0))) {
    return { value: Number(weatherObs.et0), supplier: weatherObs, kind: "observation" };
  }
  if (wbObs?.et0 != null && Number.isFinite(Number(wbObs.et0))) {
    return { value: Number(wbObs.et0), supplier: wbObs, kind: "observation" };
  }
  if (forecastObs?.et0 != null && Number.isFinite(Number(forecastObs.et0))) {
    return { value: Number(forecastObs.et0), supplier: forecastObs, kind: "forecast" };
  }
  return { value: null, supplier: undefined, kind: "observation" };
}

function getMetricDotColor(
  status: TelemetryStatus | undefined,
  metricKey: MetricKey,
  ndviSource?: string
): string {
  if (metricKey === "ndvi") {
    if (["observed", "sentinel2", "sentinel-2", "s2", "satellite_observed"].includes(ndviSource || "")) {
      return "#4ade80";
    }
    if (["kalman", "estimated", "model", "interpolated"].includes(ndviSource || "")) {
      return "#a78bfa";
    }
    return "#64748b";
  }
  if (status === TELEMETRY_STATUS.CERTIFIED_MANIFEST || status === TELEMETRY_STATUS.LIVE_UNCERTIFIED) {
    return "#4ade80";
  }
  if (status === TELEMETRY_STATUS.MODEL_FORECAST) {
    return "#60a5fa";
  }
  return "#64748b";
}

/* ─── Sparkline SVG ────────────────────────────────────────────────────── */
function Sparkline({ values, color, gradientId, width = 100, height = 28 }: {
  values: (number | null)[];
  color: string;
  gradientId: string;
  width?: number;
  height?: number;
}) {
  const validValues = values.filter((v): v is number => v !== null);
  if (validValues.length < 2) return <div style={{ width, height }} />;

  const min = Math.min(...validValues);
  const max = Math.max(...validValues);
  const range = max - min || 1;
  const pad = 3;

  const pts = values.map((v, i) => {
    if (v === null) return null;
    const x = (i / (values.length - 1)) * width;
    const y = height - pad - ((v - min) / range) * (height - pad * 2);
    return { x, y };
  }).filter(Boolean) as { x: number; y: number }[];

  if (pts.length < 2) return <div style={{ width, height }} />;

  const line = pts.map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");
  const area = `${line} L${pts[pts.length - 1].x.toFixed(1)},${height} L${pts[0].x.toFixed(1)},${height} Z`;

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} style={{ display: "block" }}>
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.25" />
          <stop offset="100%" stopColor={color} stopOpacity="0.02" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#${gradientId})`} />
      <path d={line} fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      {/* Last value dot */}
      <circle cx={pts[pts.length - 1].x} cy={pts[pts.length - 1].y} r="2.5" fill={color} />
    </svg>
  );
}

/* ─── Day Hover Tooltip ───────────────────────────────────────────────── */
function DayTooltip({ day, metric, style }: {
  day: DayCell;
  metric: MetricConfig;
  style?: React.CSSProperties;
}) {
  return (
    <div className="tl-tooltip" style={{
      position: "absolute", bottom: "100%", left: "50%", transform: "translateX(-50%)",
      marginBottom: "8px", padding: "10px 14px", borderRadius: "10px",
      background: "rgba(15, 23, 42, 0.96)", border: "1px solid rgba(71, 85, 105, 0.3)",
      backdropFilter: "blur(12px)", boxShadow: "0 8px 24px rgba(0,0,0,0.5)",
      fontSize: "0.78rem", color: "#e2e8f0", minWidth: "140px",
      zIndex: 100, pointerEvents: "none", whiteSpace: "nowrap",
      ...style,
    }}>
      <div style={{ fontWeight: 700, fontSize: "0.82rem", marginBottom: "6px", color: "#f8fafc" }}>
        {day.weekday}, {day.dayLabel}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: "3px" }}>
        {METRICS.map(m => {
          const v = day.values[m.key];
          return (
            <div key={m.key} style={{
              display: "flex", justifyContent: "space-between", gap: "12px",
              opacity: m.key === metric.key ? 1 : 0.6,
              fontWeight: m.key === metric.key ? 600 : 400,
            }}>
              <span style={{ color: m.color }}>{m.icon} {m.label}</span>
              <span style={{ fontFamily: "monospace", color: v !== null ? "#f8fafc" : "#475569" }}>
                {v !== null ? `${m.format(v)} ${m.unit}` : "—"}
              </span>
            </div>
          );
        })}
      </div>
      <div data-testid="timeline-metric-status" style={{
        marginTop: "7px", paddingTop: "6px",
        borderTop: "1px solid rgba(71,85,105,0.2)",
        color: "#fbbf24", whiteSpace: "normal", maxWidth: "240px",
      }}>
        {STATUS_LABEL[day.metricStatuses[metric.key]]}
        {metric.key === "ndvi" && ["kalman", "estimated", "model", "interpolated"].includes(day.ndviSource || "")
          ? " · Model-estimated NDVI, not a satellite observation" : ""}
      </div>
      {day.certifiedManifestEventCount > 0 && (
        <div style={{ color: "#86efac", marginTop: "4px", whiteSpace: "normal", maxWidth: "240px" }}>
          {day.certifiedManifestEventCount} verified manifest event(s) on this day. That does not certify every displayed metric.
        </div>
      )}
      {day.assessmentSnapshotId && (
        <div style={{ fontSize: "0.63rem", color: "#94a3b8", marginTop: "3px" }}>
          Assessment: {day.assessmentSnapshotId}
        </div>
      )}
      {day.tempRange.min !== null && day.tempRange.max !== null && (
        <div style={{ marginTop: "6px", paddingTop: "5px", borderTop: "1px solid rgba(71,85,105,0.2)",
          fontSize: "0.72rem", color: "#94a3b8" }}>
          Range: {day.tempRange.min.toFixed(1)}° – {day.tempRange.max.toFixed(1)}°
        </div>
      )}
      {day.operationalObservations.length > 0 && (
        <div data-testid="timeline-operational-telemetry" style={{
          marginTop: "8px", paddingTop: "6px",
          borderTop: "1px solid rgba(71,85,105,0.3)",
          display: "flex", flexDirection: "column", gap: "4px",
        }}>
          <div style={{ fontSize: "0.7rem", fontWeight: 600, color: "#38bdf8", display: "flex", justifyContent: "space-between" }}>
            <span>Operational Stream ({day.operationalObservations.length})</span>
            <span style={{ fontSize: "0.62rem", color: "#94a3b8" }}>Uncertified</span>
          </div>
          {day.operationalObservations.map((obs) => (
            <div key={obs.id} style={{
              display: "flex", flexDirection: "column", gap: "1px",
              padding: "4px 6px", borderRadius: "5px",
              background: "rgba(255, 255, 255, 0.04)",
              fontSize: "0.68rem",
            }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontWeight: 600, color: "#f8fafc" }}>
                  {obs.metric}: {obs.value} {obs.unit}
                </span>
                <span style={{
                  fontSize: "0.6rem", padding: "1px 4px", borderRadius: "3px",
                  background: obs.status === "LIVE_UNCERTIFIED"
                    ? "rgba(56, 189, 248, 0.15)"
                    : obs.status === "LATE_ARRIVING_UNADMITTED"
                    ? "rgba(251, 191, 36, 0.15)"
                    : "rgba(148, 163, 184, 0.15)",
                  color: obs.status === "LIVE_UNCERTIFIED"
                    ? "#38bdf8"
                    : obs.status === "LATE_ARRIVING_UNADMITTED"
                    ? "#fbbf24"
                    : "#94a3b8",
                  fontWeight: 600,
                }}>
                  {obs.status === "LIVE_UNCERTIFIED"
                    ? "LIVE UNCERTIFIED"
                    : obs.status === "LATE_ARRIVING_UNADMITTED"
                    ? "LATE-ARRIVING UNADMITTED"
                    : "UNVERIFIED"}
                </span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.62rem", color: "#94a3b8" }}>
                <span>Source: {obs.source}{obs.obsType ? ` · ${obs.obsType}` : ""}</span>
                <span>Basis: {obs.timeBasis === "server_received_at" ? "server receipt" : obs.timeBasis === "source_observation_at" ? "source observation time" : "daily bucket · time unknown"}</span>
              </div>
              <div style={{ fontSize: "0.6rem", color: "#64748b" }}>
                Observed: {obs.timeBasis === "day_bucket_unverified" ? "unknown (daily bucket)" : obs.observedAt ? new Date(obs.observedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "unknown"} · Ingested: {obs.ingestedAt ? new Date(obs.ingestedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "unrecorded"}
              </div>
            </div>
          ))}
        </div>
      )}
      <div style={{
        position: "absolute", bottom: "-5px", left: "50%", transform: "translateX(-50%) rotate(45deg)",
        width: "10px", height: "10px", background: "rgba(15,23,42,0.96)",
        borderRight: "1px solid rgba(71,85,105,0.3)", borderBottom: "1px solid rgba(71,85,105,0.3)",
      }} />
    </div>
  );
}


/* ─── Main Timeline Component ─────────────────────────────────────────── */
export default function TimelineStrip({ docked = false }: { docked?: boolean } = {}) {
  const { timeline, loading, selectedDate, setSelectedDate } = usePlotIntelligence();
  const parcel = useParcelAssessment();
  const { stream: liveTelemetryStream } = usePlotTelemetry();
  const assessment = parcel.assessment;
  const evidenceCutoffAt = assessment?.identity.evidenceCutoffAt ?? null;
  const [activeMetric, setActiveMetric] = useState<MetricKey>("temp");
  const [hoveredDay, setHoveredDay] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to today on mount
  useEffect(() => {
    const container = scrollRef.current;
    if (!container) return;
    const todayEl = container.querySelector("[data-today='true']");
    if (todayEl) {
      todayEl.scrollIntoView({ inline: "center", behavior: "smooth" });
    }
  }, [timeline]);

  const days: DayCell[] = useMemo(() => {
    const result: DayCell[] = [];
    const nowIso = new Date().toISOString();
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    for (let i = -7; i <= 7; i++) {
      const d = new Date(today);
      d.setDate(d.getDate() + i);
      // Use local date string to avoid UTC offset mismatches with backend dates
      const year = d.getFullYear();
      const month = String(d.getMonth() + 1).padStart(2, "0");
      const day = String(d.getDate()).padStart(2, "0");
      const dateStr = `${year}-${month}-${day}`;
      const isPast = i < 0;
      const isToday = i === 0;

      const weatherObs = (timeline?.weather || []).find((w: any) =>
        w.timestamp?.startsWith(dateStr) || w.date?.startsWith(dateStr)
      ) as Record<string, unknown> | undefined;

      const forecastObs = (timeline?.forecast || []).find((f: any) =>
        f.date?.startsWith(dateStr)
      ) as Record<string, unknown> | undefined;

      const ndviObs = (timeline?.ndvi || []).find((n: any) =>
        n.timestamp?.startsWith(dateStr) || n.date?.startsWith(dateStr)
      ) as Record<string, unknown> | undefined;

      const wbObs = (timeline?.waterBalance || []).find((w: any) =>
        w.date?.startsWith(dateStr)
      ) as Record<string, unknown> | undefined;

      // Only explicit provider observation classes qualify as observed.
      // A Kalman propagation is an estimate, not a satellite acquisition
      // or a weather forecast. Unknown source identity remains unverified.
      const ndviSource = typeof ndviObs?.source === "string"
        ? ndviObs.source.toLowerCase().trim() : undefined;
      const observedOptical = !!ndviObs && !!ndviSource
        && ["observed", "sentinel2", "sentinel-2", "s2", "satellite_observed"].includes(ndviSource);
      const sarObs = (timeline?.sar || []).find((s: any) =>
        s.timestamp?.startsWith(dateStr) || s.date?.startsWith(dateStr)
      ) as Record<string, unknown> | undefined;
      const sarSource = typeof sarObs?.source === "string"
        ? sarObs.source.toLowerCase().trim() : "";
      const observedSar = !!sarObs
        && ["observed", "sentinel1", "sentinel-1", "s1", "satellite_observed"].includes(sarSource);
      const estimatedNdvi = !!ndviObs && ["kalman", "estimated", "model", "interpolated"].includes(ndviSource || "");

      // This strip reports availability by day; individual variables have
      // their own source types, and selecting a day does not load a historic map.
      const source: DayCell["source"] = weatherObs || observedOptical || observedSar
        ? "observed"
        : forecastObs ? "forecast"
        : estimatedNdvi ? "estimated"
        : ndviObs ? "unverified"
        : "gap";

      const ndviRaw = (ndviObs?.ndvi_mean != null ? ndviObs.ndvi_mean : ndviObs?.ndvi) as number | undefined;
      const ndviValue = ndviRaw != null && Number.isFinite(Number(ndviRaw)) ? Number(ndviRaw) : null;
      let ndviStatus: TelemetryStatus = TELEMETRY_STATUS.UNVERIFIED;
      if (ndviValue !== null && ndviObs) {
        if (estimatedNdvi) {
          // Kalman interpolation is a model estimate, never an optical observation.
          ndviStatus = TELEMETRY_STATUS.UNVERIFIED;
        } else {
          ndviStatus = classifyTimelineDatum(ndviObs, "observation", evidenceCutoffAt, nowIso);
        }
      }

      // C3 P7-01: Select each metric's value and supplier together so fallback
      // forecast values are not mislabeled as observations.
      const tempMetric = resolveTimelineMetric(weatherObs, "temp", forecastObs, "temp");
      const rainMetric = resolveTimelineMetric(weatherObs, ["rain", "rain_mm"], forecastObs, ["rain_mm", "rain"]);
      const humidityMetric = resolveTimelineMetric(weatherObs, "humidity", forecastObs, "humidity");
      const et0Metric = resolveEt0Metric(weatherObs, wbObs, forecastObs);

      const metricStatuses: Record<MetricKey, TelemetryStatus> = {
        temp: classifyTimelineDatum(tempMetric.supplier, tempMetric.kind, evidenceCutoffAt, nowIso),
        rain: classifyTimelineDatum(rainMetric.supplier, rainMetric.kind, evidenceCutoffAt, nowIso),
        humidity: classifyTimelineDatum(humidityMetric.supplier, humidityMetric.kind, evidenceCutoffAt, nowIso),
        et0: classifyTimelineDatum(et0Metric.supplier, et0Metric.kind, evidenceCutoffAt, nowIso),
        ndvi: ndviStatus,
      };

      const metricDotColors: Record<MetricKey, string> = {
        temp: getMetricDotColor(metricStatuses.temp, "temp", ndviSource),
        rain: getMetricDotColor(metricStatuses.rain, "rain", ndviSource),
        humidity: getMetricDotColor(metricStatuses.humidity, "humidity", ndviSource),
        et0: getMetricDotColor(metricStatuses.et0, "et0", ndviSource),
        ndvi: getMetricDotColor(metricStatuses.ndvi, "ndvi", ndviSource),
      };

      const certifiedManifestEventCount = assessment?.evidenceTimeline.filter(
        event => event.observedAt?.startsWith(dateStr)
          && classifyManifestEvidence(assessment, event) === TELEMETRY_STATUS.CERTIFIED_MANIFEST
      ).length ?? 0;

      const tempMin = (weatherObs?.temp_min != null && Number.isFinite(Number(weatherObs.temp_min)))
        ? Number(weatherObs.temp_min)
        : (forecastObs?.temp_min != null && Number.isFinite(Number(forecastObs.temp_min)))
          ? Number(forecastObs.temp_min)
          : null;
      const tempMax = (weatherObs?.temp_max != null && Number.isFinite(Number(weatherObs.temp_max)))
        ? Number(weatherObs.temp_max)
        : (forecastObs?.temp_max != null && Number.isFinite(Number(forecastObs.temp_max)))
          ? Number(forecastObs.temp_max)
          : null;

      const operationalForDay = (
        (typeof liveTelemetryStream !== "undefined" && Array.isArray(liveTelemetryStream?.observations))
          ? liveTelemetryStream.observations
          : []
      )
        .filter((obs: any) => typeof obs?.observedAt === "string" && (obs.dayBucketDate || obs.observedAt.slice(0, 10)) === dateStr)
        .map((obs: any) => ({
          id: String(obs.id || "op-telemetry"),
          source: String(obs.source || "unknown"),
          metric: String(obs.metric || "unknown"),
          value: Number(obs.value ?? 0),
          unit: String(obs.unit || ""),
          observedAt: String(obs.observedAt || ""),
          ingestedAt: String(obs.ingestedAt || ""),
          timeBasis: obs.timeBasis,
          dayBucketDate: obs.dayBucketDate,
          obsType: obs.obsType,
          status: classifyTelemetryObservation(obs, evidenceCutoffAt, nowIso),
        }));

      result.push({
        date: dateStr,
        dayLabel: d.toLocaleDateString("en-US", { month: "short", day: "numeric" }),
        weekday: d.toLocaleDateString("en-US", { weekday: "short" }),
        dayNum: d.getDate(),
        isToday,
        isPast,
        source,
        metricStatuses,
        metricDotColors,
        certifiedManifestEventCount,
        cutoffDay: !!evidenceCutoffAt && dateStr === evidenceCutoffAt.slice(0, 10),
        assessmentSnapshotId: assessment?.identity.snapshotId ?? null,
        ndviSource,
        ndviConfidence: ndviObs?.confidence as number | undefined,
        values: {
          temp: tempMetric.value,
          rain: rainMetric.value,
          ndvi: ndviValue,
          et0: et0Metric.value,
          humidity: humidityMetric.value,
        },
        tempRange: {
          min: tempMin,
          max: tempMax,
        },
        operationalObservations: operationalForDay,
      });
    }
    return result;
  }, [timeline, assessment, evidenceCutoffAt, liveTelemetryStream]);

  const sparklineValues = days.map(d => d.values[activeMetric]);
  const activeConfig = METRICS.find(m => m.key === activeMetric)!;

  // Count how many days have data for this metric
  const dataCount = sparklineValues.filter(v => v !== null).length;
  const observedCount = days.filter(d => {
    const s = d.metricStatuses[activeMetric];
    return s === TELEMETRY_STATUS.CERTIFIED_MANIFEST || s === TELEMETRY_STATUS.LIVE_UNCERTIFIED;
  }).length;
  const forecastCount = days.filter(d => d.metricStatuses[activeMetric] === TELEMETRY_STATUS.MODEL_FORECAST).length;
  const estimatedCount = days.filter(d => {
    if (activeMetric === "ndvi") {
      return ["kalman", "estimated", "model", "interpolated"].includes(d.ndviSource || "");
    }
    return false;
  }).length;

  const handleDayClick = useCallback((date: string) => {
    setSelectedDate(selectedDate === date ? null : date);
  }, [selectedDate, setSelectedDate]);

  if (loading && !timeline) {
    return (
      <div style={{
        position: docked ? "relative" : "absolute",
        bottom: docked ? undefined : "52px",
        left: docked ? undefined : "50%",
        transform: docked ? undefined : "translateX(-50%)",
        zIndex: 20, pointerEvents: "auto",
        width: "100%", maxWidth: docked ? "none" : "860px",
        padding: "0 12px", boxSizing: "border-box",
      }}>
        <div className="tl-panel" style={{
          background: "rgba(8, 12, 25, 0.94)", backdropFilter: "blur(20px)",
          border: "1px solid rgba(71, 85, 105, 0.15)", borderRadius: "10px",
          padding: "10px", textAlign: "center", display: "flex", alignItems: "center",
          justifyContent: "center", gap: "8px",
        }}>
          <div style={{
            width: "14px", height: "14px", border: "2px solid rgba(99,102,241,0.3)",
            borderTop: "2px solid #6366f1", borderRadius: "50%",
            animation: "spin 1s linear infinite",
          }} />
          <span style={{ color: "#94a3b8", fontSize: "0.72rem" }}>Loading timeline…</span>
        </div>
      </div>
    );
  }

  return (
    <div style={{
      position: docked ? "relative" : "absolute",
        bottom: docked ? undefined : "52px",
        left: docked ? undefined : "50%",
        transform: docked ? undefined : "translateX(-50%)",
        zIndex: 20, pointerEvents: "auto",
        width: "100%", maxWidth: docked ? "none" : "860px",
      padding: "0 12px", boxSizing: "border-box",
    }}>
      <div className="tl-panel" style={{
        background: "rgba(8, 12, 25, 0.92)",
        backdropFilter: "blur(24px)",
        border: "1px solid rgba(71, 85, 105, 0.18)",
        borderRadius: "10px",
        overflow: "hidden",
        boxShadow: "0 -2px 20px rgba(0,0,0,0.35), 0 0 0 1px rgba(71,85,105,0.06) inset",
      }}>

        {/* P2-C: precise cutoff is temporal, not blanket certification of prior dates. */}
        <div data-testid="timeline-cutoff-boundary" style={{
          padding: "6px 10px", borderBottom: "1px solid rgba(148,163,184,0.18)",
          fontSize: "0.65rem", color: "#cbd5e1", lineHeight: 1.5,
        }}>
          {evidenceCutoffAt ? (
            <span>
              Published evidence cutoff: <strong>{new Date(evidenceCutoffAt).toUTCString()}</strong>
              {" · "}snapshot {assessment?.identity.snapshotId}
              {parcel.isApplicable ? "" : " · historical assessment, not current-use"}
            </span>
          ) : <span>No validated publication cutoff available</span>}
          <span style={{ marginLeft: "8px", color: "#fbbf24" }}>
            Historical dates are not proof of admission; post-cutoff readings are uncertified.
            {" "}Operational buffer: {liveTelemetryStream.observations.length} unsealed item(s) (
              {(liveTelemetryStream.observations || []).filter(o => classifyTelemetryObservation(o, evidenceCutoffAt, new Date().toISOString()) === TELEMETRY_STATUS.LIVE_UNCERTIFIED).length} live uncertified,
              {" "}{(liveTelemetryStream.observations || []).filter(o => classifyTelemetryObservation(o, evidenceCutoffAt, new Date().toISOString()) === TELEMETRY_STATUS.LATE_ARRIVING_UNADMITTED).length} late-arriving unadmitted
              {(liveTelemetryStream.observations || []).some(o => classifyTelemetryObservation(o, evidenceCutoffAt, new Date().toISOString()) === TELEMETRY_STATUS.UNVERIFIED)
                ? `, ${(liveTelemetryStream.observations || []).filter(o => classifyTelemetryObservation(o, evidenceCutoffAt, new Date().toISOString()) === TELEMETRY_STATUS.UNVERIFIED).length} unverified`
                : ""}
            ).
          </span>
        </div>

        {/* ── Top Row: Metric tabs + Sparkline ──────────────────────────── */}
        <div style={{
          display: "flex", alignItems: "center",
          padding: "5px 10px",
          borderBottom: "1px solid rgba(71, 85, 105, 0.1)",
          gap: "2px",
        }}>
          {METRICS.map(m => {
            const isActive = activeMetric === m.key;
            return (
              <button
                key={m.key}
                onClick={() => setActiveMetric(m.key)}
                style={{
                  padding: "3px 8px", borderRadius: "6px",
                  fontSize: "0.68rem", fontWeight: 600, cursor: "pointer",
                  border: "none",
                  background: isActive ? `${m.color}15` : "transparent",
                  color: isActive ? m.color : "#64748b",
                  transition: "all 0.15s ease",
                  display: "flex", alignItems: "center", gap: "4px",
                  whiteSpace: "nowrap",
                }}
                id={`timeline-metric-${m.key}`}
              >
                <span style={{ fontSize: "0.72rem" }}>{m.icon}</span>
                <span>{m.label}</span>
              </button>
            );
          })}

          {/* Sparkline + counts on right */}
          <div style={{
            marginLeft: "auto",
            display: "flex", alignItems: "center", gap: "8px",
          }}>
            {dataCount > 0 ? (
              <Sparkline
                values={sparklineValues}
                color={activeConfig.color}
                gradientId={`timeline-spark-${activeConfig.key}`}
                width={90}
                height={20}
              />
            ) : (
              <span style={{ width: "150px", color: "#fbbf24", fontSize: "0.62rem", textAlign: "right" }}>
                {activeMetric === "ndvi" ? "Satellite refresh unavailable" : "Weather refresh unavailable"}
              </span>
            )}
          <div style={{
              display: "flex", alignItems: "center", gap: "6px",
              fontSize: "0.6rem", color: "#475569", fontWeight: 500,
            }}>
              {activeMetric === "ndvi" ? (
                <>
                  <span style={{ display: "flex", alignItems: "center", gap: "2px" }}>
                    <span style={{ width: "4px", height: "4px", borderRadius: "50%", background: "#4ade80" }} />
                    <span style={{ color: "#4ade80" }}>S2</span>
                  </span>
                  <span style={{ display: "flex", alignItems: "center", gap: "2px" }}>
                    <span style={{ width: "4px", height: "4px", borderRadius: "50%", background: "#a78bfa" }} />
                    <span style={{ color: "#a78bfa" }}>KF</span>
                  </span>
                </>
              ) : (
                <>
                  <span style={{ display: "flex", alignItems: "center", gap: "2px" }}>
                    <span style={{ width: "4px", height: "4px", borderRadius: "50%", background: "#4ade80" }} />
                    {observedCount}
                  </span>
                  <span style={{ display: "flex", alignItems: "center", gap: "2px" }}>
                    <span style={{ width: "4px", height: "4px", borderRadius: "50%", background: "#60a5fa" }} />
                    {forecastCount}
                  </span>
                  <span title="Model estimate, not an observation" style={{ display: "flex", alignItems: "center", gap: "2px" }}>
                    <span style={{ width: "4px", height: "4px", borderRadius: "50%", background: "#a78bfa" }} />
                    {estimatedCount}
                  </span>
                </>
              )}
            </div>
          </div>
        </div>

        {/* ── Bottom Row: Day cells ─────────────────────────────────────── */}
        <div
          ref={scrollRef}
          style={{
            display: "flex", alignItems: "stretch",
            padding: "5px 6px 6px",
            gap: "2px",
            overflowX: "auto",
          }}
          className="custom-scrollbar"
        >
          {days.map((day) => {
            const isSelected = selectedDate === day.date;
            const isHovered = hoveredDay === day.date;
            const value = day.values[activeMetric];
            const hasData = value !== null;

            return (
              <div key={day.date} style={{ position: "relative", flex: "1 0 auto" }}>
                <button
                  data-today={day.isToday ? "true" : undefined}
                  onClick={() => handleDayClick(day.date)}
                  title={STATUS_LABEL[day.metricStatuses[activeMetric]] + (day.cutoffDay ? " · Publication cutoff day" : "")}
                  onMouseEnter={() => setHoveredDay(day.date)}
                  onMouseLeave={() => setHoveredDay(null)}
                  style={{
                    minWidth: "48px", width: "100%",
                    padding: "5px 4px",
                    borderRadius: "7px",
                    border: isSelected
                      ? `1px solid ${activeConfig.color}50`
                      : day.isToday
                      ? "1px solid rgba(34, 197, 94, 0.35)"
                      : "1px solid transparent",
                    background: isSelected
                      ? `${activeConfig.color}0D`
                      : isHovered
                      ? "rgba(71, 85, 105, 0.12)"
                      : day.isToday
                      ? "rgba(34, 197, 94, 0.05)"
                      : "transparent",
                    cursor: "pointer",
                    display: "flex", flexDirection: "column",
                    alignItems: "center", gap: "2px",
                    transition: "all 0.12s ease",
                    // Only dim if there's genuinely NO data for the active metric on this day
                    opacity: hasData ? 1 : day.source === "gap" ? 0.3 : 0.75,
                  }}
                  id={`timeline-day-${day.date}`}
                >
                  {/* Weekday */}
                  <span style={{
                    fontSize: "0.6rem", fontWeight: 700,
                    color: day.isToday ? "#4ade80" : day.isPast ? "#94a3b8" : "#64748b",
                    letterSpacing: "0.03em", textTransform: "uppercase",
                    lineHeight: 1,
                  }}>
                    {day.isToday ? "NOW" : day.weekday}
                  </span>

                  {/* Day number */}
                  <span style={{
                    fontSize: "0.75rem", fontWeight: 700,
                    color: day.isToday ? "#4ade80" : "#e2e8f0",
                    lineHeight: 1,
                  }}>
                    {day.dayNum}
                  </span>

                  {day.cutoffDay && <span title="Exact cutoff timestamp is shown above" style={{ fontSize: "0.53rem", color: "#fbbf24" }}>CUTOFF</span>}

                  {/* Value */}
                  <span style={{
                    fontSize: "0.7rem", fontWeight: 600,
                    color: hasData ? "#f1f5f9" : "#334155",
                    fontFamily: "'Inter', system-ui, monospace",
                    lineHeight: 1, marginTop: "1px",
                  }}>
                    {hasData ? activeConfig.format(value!) : "—"}
                  </span>

                  {/* Source dot — derived from active metric status while preserving NDVI estimate semantics */}
                  <div style={{
                    width: "3px", height: "3px", borderRadius: "50%",
                    background: day.metricDotColors[activeMetric],
                    marginTop: "1px",
                  }} />

                  {day.operationalObservations.length > 0 && (
                    <span
                      data-testid="telemetry-pill"
                      title={`${day.operationalObservations.length} operational telemetry observation(s)`}
                      style={{
                        fontSize: "0.50rem",
                        color: "#38bdf8",
                        background: "rgba(56, 189, 248, 0.12)",
                        border: "1px solid rgba(56, 189, 248, 0.25)",
                        borderRadius: "3px",
                        padding: "0 2px",
                        lineHeight: "1.1",
                        marginTop: "1px",
                        fontWeight: 600,
                      }}
                    >
                      📡 {day.operationalObservations.length}
                    </span>
                  )}
                </button>

                {/* Tooltip on hover */}
                {isHovered && (
                  <DayTooltip day={day} metric={activeConfig} />
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
