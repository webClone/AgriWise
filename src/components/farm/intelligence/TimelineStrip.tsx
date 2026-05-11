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
  source: "observed" | "forecast" | "gap";
  ndviSource?: string;        // "observed" | "kalman" from backend
  ndviConfidence?: number;    // 0-1 from Kalman engine
  tempRange: { min: number | null; max: number | null };
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
    <div style={{
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
      {day.tempRange.min !== null && day.tempRange.max !== null && (
        <div style={{ marginTop: "6px", paddingTop: "5px", borderTop: "1px solid rgba(71,85,105,0.2)",
          fontSize: "0.72rem", color: "#94a3b8" }}>
          Range: {day.tempRange.min.toFixed(1)}° – {day.tempRange.max.toFixed(1)}°
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
export default function TimelineStrip() {
  const { timeline, loading, selectedDate, setSelectedDate } = usePlotIntelligence();
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

      // ndviSource: distinguish satellite-corrected days from Kalman-only days
      const ndviSource = ndviObs?.source as string | undefined;

      // Source priority: raw weather observation > forecast > ndvi-only (Kalman) > gap
      const source: "observed" | "forecast" | "gap" = weatherObs
        ? "observed"
        : forecastObs
        ? "forecast"
        : ndviObs
        ? "forecast"   // Kalman-filled NDVI still counts as data (use forecast colour)
        : "gap";

      const ndviValue = (ndviObs?.ndvi_mean as number) ?? (ndviObs?.ndvi as number) ?? null;

      result.push({
        date: dateStr,
        dayLabel: d.toLocaleDateString("en-US", { month: "short", day: "numeric" }),
        weekday: d.toLocaleDateString("en-US", { weekday: "short" }),
        dayNum: d.getDate(),
        isToday,
        isPast,
        source,
        ndviSource,
        ndviConfidence: ndviObs?.confidence as number | undefined,
        values: {
          temp: (weatherObs?.temp as number) ?? (forecastObs?.temp as number) ?? null,
          rain: (weatherObs?.rain as number) ?? (forecastObs?.rain_mm as number) ?? null,
          ndvi: ndviValue,
          et0: (weatherObs?.et0 as number) ?? (wbObs?.et0 as number) ?? (forecastObs?.et0 as number) ?? null,
          humidity: (weatherObs?.humidity as number) ?? (forecastObs?.humidity as number) ?? null,
        },
        tempRange: {
          min: (weatherObs?.temp_min as number) ?? (forecastObs?.temp_min as number) ?? null,
          max: (weatherObs?.temp_max as number) ?? (forecastObs?.temp_max as number) ?? null,
        },
      });
    }
    return result;
  }, [timeline]);

  const sparklineValues = days.map(d => d.values[activeMetric]);
  const activeConfig = METRICS.find(m => m.key === activeMetric)!;

  // Count how many days have data for this metric
  const dataCount = sparklineValues.filter(v => v !== null).length;
  const observedCount = days.filter(d => d.source === "observed").length;
  const forecastCount = days.filter(d => d.source === "forecast").length;

  const handleDayClick = useCallback((date: string) => {
    setSelectedDate(selectedDate === date ? null : date);
  }, [selectedDate, setSelectedDate]);

  if (loading && !timeline) {
    return (
      <div style={{
        position: "absolute", bottom: "52px", left: "50%", transform: "translateX(-50%)",
        zIndex: 20, pointerEvents: "auto",
        width: "100%", maxWidth: "860px",
        padding: "0 12px", boxSizing: "border-box",
      }}>
        <div style={{
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
      position: "absolute", bottom: "52px", left: "50%", transform: "translateX(-50%)",
      zIndex: 20, pointerEvents: "auto",
      width: "100%", maxWidth: "860px",
      padding: "0 12px", boxSizing: "border-box",
    }}>
      <div style={{
        background: "rgba(8, 12, 25, 0.92)",
        backdropFilter: "blur(24px)",
        border: "1px solid rgba(71, 85, 105, 0.18)",
        borderRadius: "10px",
        overflow: "hidden",
        boxShadow: "0 -2px 20px rgba(0,0,0,0.35), 0 0 0 1px rgba(71,85,105,0.06) inset",
      }}>

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
            <Sparkline
              values={sparklineValues}
              color={activeConfig.color}
              gradientId={`timeline-spark-${activeConfig.key}`}
              width={90}
              height={20}
            />
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

                  {/* Value */}
                  <span style={{
                    fontSize: "0.7rem", fontWeight: 600,
                    color: hasData ? "#f1f5f9" : "#334155",
                    fontFamily: "'Inter', system-ui, monospace",
                    lineHeight: 1, marginTop: "1px",
                  }}>
                    {hasData ? activeConfig.format(value!) : "—"}
                  </span>

                  {/* Source dot — for NDVI metric show satellite vs Kalman fill */}
                  <div style={{
                    width: "3px", height: "3px", borderRadius: "50%",
                    background: activeMetric === "ndvi"
                      ? day.ndviSource === "observed" ? "#4ade80"   // satellite corrected
                        : day.ndviSource === "kalman" ? "#a78bfa"   // Kalman estimated
                        : hasData ? "#a78bfa" : "#334155"
                      : day.source === "observed" ? "#4ade80"
                        : day.source === "forecast" ? "#60a5fa"
                        : "#334155",
                    marginTop: "1px",
                  }} />
                </button>

                {/* Tooltip on hover */}
                {isHovered && hasData && (
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
