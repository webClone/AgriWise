"use client";

/**
 * DroneMissionPanel — Premium Mission Control Center.
 *
 * Tabbed interface: Planner | Flight Plan | Telemetry | History
 * With header status band, pre-flight checklist, and weather widget.
 */

import { useState, useEffect } from "react";
import { useDroneMission, type MissionSuggestion, type DroneTab } from "@/hooks/useDroneMission";
import {
  MISSION_TYPE_META,
  DroneHeaderBand,
  PreflightChecklistWidget,
  WeatherWidget,
  FlightPlanTab,
  TelemetryTab,
  HistoryTab,
} from "./DroneSubComponents";

// ── Pattern visual data ──────────────────────────────────────────────────
const PATTERN_OPTIONS = [
  { id: "boustrophedon", label: "Lawnmower", icon: "≋", desc: "Standard back-and-forth" },
  { id: "spiral", label: "Spiral", icon: "🌀", desc: "Orbit inward" },
  { id: "row_aligned", label: "Row Aligned", icon: "☰", desc: "Follow crop rows" },
  { id: "contour", label: "Contour", icon: "〰", desc: "Terrain-following" },
];

const FLIGHT_MODES = [
  { id: "mapping_mode", label: "Mapping", icon: "🗺️", desc: "High altitude, ortho stitching", color: "#60a5fa" },
  { id: "command_revisit", label: "Command", icon: "🔍", desc: "Low altitude, raw inspection", color: "#f59e0b" },
];

const TAB_CONFIG: { id: DroneTab; label: string; icon: string }[] = [
  { id: "planner", label: "Planner", icon: "📋" },
  { id: "flightplan", label: "Flight Plan", icon: "🛫" },
  { id: "telemetry", label: "Telemetry", icon: "📡" },
  { id: "history", label: "History", icon: "📜" },
];

// ── Planner Tab ──────────────────────────────────────────────────────────
function PlannerTab({
  selectedType, setSelectedType,
  targetGsd, setTargetGsd,
  overlapPct, setOverlapPct,
  selectedPattern, setSelectedPattern,
  flightMode, setFlightMode,
  loading, onPlan, suggestions, onPlanSuggestion,
}: {
  selectedType: string; setSelectedType: (v: string) => void;
  targetGsd: number; setTargetGsd: (v: number) => void;
  overlapPct: number; setOverlapPct: (v: number) => void;
  selectedPattern: string; setSelectedPattern: (v: string) => void;
  flightMode: string; setFlightMode: (v: string) => void;
  loading: boolean; onPlan: () => void;
  suggestions: MissionSuggestion[]; onPlanSuggestion: (s: MissionSuggestion) => void;
}) {
  const lblStyle: React.CSSProperties = { fontSize: "0.68rem", color: "#94a3b8", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: "6px" };
  const cardStyle: React.CSSProperties = { background: "rgba(15,23,42,0.6)", border: "1px solid rgba(71,85,105,0.15)", borderRadius: "10px", padding: "10px" };

  // Estimate altitude from GSD (simplified pinhole: alt ≈ gsd_cm * focal / sensor_width * img_width / 100)
  const estAltitude = (targetGsd / 100) * (4.4 / 6.3) * 4000; // ~DJI Mini approx
  const estTime = (estAltitude > 30 ? 8 : 15) + Math.random() * 3;
  const estImages = Math.round(200 * (80 / overlapPct) * (2.0 / targetGsd));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
      {/* Mission Type */}
      <div>
        <div style={lblStyle}>Mission Type</div>
        <div style={{ display: "flex", gap: "4px", flexWrap: "wrap" }}>
          {Object.entries(MISSION_TYPE_META).map(([key, meta]) => (
            <button
              key={key}
              onClick={() => setSelectedType(key)}
              style={{
                padding: "5px 10px", borderRadius: "8px",
                border: selectedType === key ? `1px solid ${meta.color}60` : "1px solid rgba(71,85,105,0.2)",
                background: selectedType === key ? `${meta.color}15` : "rgba(15,23,42,0.4)",
                color: selectedType === key ? meta.color : "#64748b",
                fontSize: "0.68rem", fontWeight: 600, cursor: "pointer",
                transition: "all 0.15s", display: "flex", alignItems: "center", gap: "4px",
              }}
            >
              {meta.icon} {meta.label}
            </button>
          ))}
        </div>
      </div>

      {/* Flight Mode */}
      <div>
        <div style={lblStyle}>Flight Mode</div>
        <div style={{ display: "flex", gap: "6px" }}>
          {FLIGHT_MODES.map(fm => (
            <button
              key={fm.id}
              onClick={() => setFlightMode(fm.id)}
              style={{
                flex: 1, padding: "10px", borderRadius: "10px",
                border: flightMode === fm.id ? `1px solid ${fm.color}50` : "1px solid rgba(71,85,105,0.15)",
                background: flightMode === fm.id ? `${fm.color}10` : "rgba(15,23,42,0.4)",
                color: flightMode === fm.id ? fm.color : "#94a3b8",
                cursor: "pointer", transition: "all 0.15s", textAlign: "left",
              }}
            >
              <div style={{ fontSize: "0.82rem", fontWeight: 700, marginBottom: "2px" }}>{fm.icon} {fm.label}</div>
              <div style={{ fontSize: "0.62rem", color: "#64748b" }}>{fm.desc}</div>
            </button>
          ))}
        </div>
      </div>

      {/* GSD + Overlap sliders */}
      <div style={{ display: "flex", gap: "8px" }}>
        <div style={{ ...cardStyle, flex: 1 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
            <span style={{ fontSize: "0.65rem", color: "#94a3b8", fontWeight: 600 }}>Target GSD</span>
            <span style={{ fontSize: "0.78rem", color: "#60a5fa", fontWeight: 700, fontFamily: "monospace" }}>{targetGsd.toFixed(1)} cm/px</span>
          </div>
          <input type="range" min="0.5" max="5" step="0.1" value={targetGsd} onChange={e => setTargetGsd(Number(e.target.value))}
            style={{ width: "100%", accentColor: "#60a5fa", height: "4px" }} />
          <div style={{ fontSize: "0.6rem", color: "#475569", marginTop: "4px" }}>≈ {estAltitude.toFixed(0)}m altitude</div>
        </div>
        <div style={{ ...cardStyle, flex: 1 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
            <span style={{ fontSize: "0.65rem", color: "#94a3b8", fontWeight: 600 }}>Overlap</span>
            <span style={{ fontSize: "0.78rem", color: "#a78bfa", fontWeight: 700, fontFamily: "monospace" }}>{overlapPct}%</span>
          </div>
          <input type="range" min="50" max="90" step="5" value={overlapPct} onChange={e => setOverlapPct(Number(e.target.value))}
            style={{ width: "100%", accentColor: "#a78bfa", height: "4px" }} />
        </div>
      </div>

      {/* Coverage Pattern */}
      <div>
        <div style={lblStyle}>Coverage Pattern</div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px" }}>
          {PATTERN_OPTIONS.map(p => (
            <button
              key={p.id}
              onClick={() => setSelectedPattern(p.id)}
              style={{
                ...cardStyle, cursor: "pointer", textAlign: "left",
                border: selectedPattern === p.id ? "1px solid rgba(99,102,241,0.4)" : "1px solid rgba(71,85,105,0.15)",
                background: selectedPattern === p.id ? "rgba(99,102,241,0.08)" : "rgba(15,23,42,0.4)",
              }}
            >
              <div style={{ fontSize: "0.82rem", marginBottom: "2px" }}>
                <span>{p.icon}</span>{" "}
                <span style={{ color: selectedPattern === p.id ? "#a5b4fc" : "#94a3b8", fontWeight: 600, fontSize: "0.72rem" }}>{p.label}</span>
              </div>
              <div style={{ fontSize: "0.58rem", color: "#475569" }}>{p.desc}</div>
            </button>
          ))}
        </div>
      </div>

      {/* Estimation cards */}
      <div style={{ display: "flex", gap: "6px" }}>
        {[
          { l: "Est. Time", v: `${estTime.toFixed(0)} min`, c: "#22d3ee" },
          { l: "Est. Images", v: String(estImages), c: "#a78bfa" },
          { l: "Est. Altitude", v: `${estAltitude.toFixed(0)}m`, c: "#60a5fa" },
        ].map(e => (
          <div key={e.l} style={{ ...cardStyle, flex: 1, textAlign: "center" }}>
            <div style={{ fontSize: "0.58rem", color: "#64748b", textTransform: "uppercase", letterSpacing: "0.04em" }}>{e.l}</div>
            <div style={{ fontSize: "0.88rem", color: e.c, fontWeight: 700, fontFamily: "monospace" }}>{e.v}</div>
          </div>
        ))}
      </div>

      {/* Generate button */}
      <button
        onClick={onPlan}
        disabled={loading}
        style={{
          padding: "10px 20px", borderRadius: "10px", border: "none",
          background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
          color: "#fff", fontSize: "0.82rem", fontWeight: 700,
          cursor: loading ? "not-allowed" : "pointer",
          opacity: loading ? 0.6 : 1, transition: "all 0.15s",
          boxShadow: "0 4px 16px rgba(99,102,241,0.3)",
        }}
      >
        {loading ? "Planning…" : "📋 Generate Flight Plan"}
      </button>

      {/* Suggestions */}
      {suggestions.length > 0 && (
        <div>
          <div style={lblStyle}>AI Suggestions ({suggestions.length})</div>
          {suggestions.map((s, i) => {
            const meta = MISSION_TYPE_META[s.mission_type] || MISSION_TYPE_META.full_plot_map;
            return (
              <div key={i} style={{ ...cardStyle, marginBottom: "6px", display: "flex", flexDirection: "column", gap: "6px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                  <span>{meta.icon}</span>
                  <span style={{ color: meta.color, fontWeight: 700, fontSize: "0.75rem" }}>{meta.label}</span>
                  <span style={{ marginLeft: "auto", fontSize: "0.65rem", color: "#e2e8f0", fontFamily: "monospace" }}>{(s.urgency_score * 100).toFixed(0)}%</span>
                </div>
                <div style={{ height: "3px", background: "rgba(71,85,105,0.3)", borderRadius: "2px", overflow: "hidden" }}>
                  <div style={{ width: `${s.urgency_score * 100}%`, height: "100%", background: `linear-gradient(90deg, #4ade80, ${s.urgency_score > 0.6 ? "#f87171" : "#f59e0b"})`, borderRadius: "2px" }} />
                </div>
                <p style={{ fontSize: "0.68rem", color: "#94a3b8", margin: 0, lineHeight: 1.4 }}>{s.reason}</p>
                {!s.suppressed && (
                  <button onClick={() => onPlanSuggestion(s)} style={{ alignSelf: "flex-end", padding: "4px 12px", borderRadius: "6px", border: "none", background: `${meta.color}18`, color: meta.color, fontSize: "0.68rem", fontWeight: 700, cursor: "pointer" }}>
                    Plan This →
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Main Panel ───────────────────────────────────────────────────────────
export default function DroneMissionPanel({
  plotId,
  polygonGeoJson,
  onClose,
}: {
  plotId: string;
  polygonGeoJson?: any;
  onClose?: () => void;
}) {
  const dm = useDroneMission(plotId, polygonGeoJson);
  const [selectedType, setSelectedType] = useState("full_plot_map");
  const [targetGsd, setTargetGsd] = useState(2.0);
  const [overlapPct, setOverlapPct] = useState(75);
  const [selectedPattern, setSelectedPattern] = useState("boustrophedon");
  const [flightMode, setFlightMode] = useState("mapping_mode");

  const handlePlan = () => {
    dm.planMission({
      mission_type: selectedType,
      flight_mode: flightMode,
      target_gsd_cm: targetGsd,
      overlap_pct: overlapPct,
    });
    dm.setActiveTab("flightplan");
  };

  const handlePlanSuggestion = (s: MissionSuggestion) => {
    dm.planMission({
      mission_type: s.mission_type,
      flight_mode: s.flight_mode,
      target_gsd_cm: s.target_gsd_cm,
    });
    dm.setActiveTab("flightplan");
  };

  const passCount = dm.preflightChecks.filter(c => c.status === "pass").length;

  // Escape key + scroll lock (matching AgriBrainWorkspace)
  useEffect(() => {
    document.body.style.overflow = "hidden";
    const handleKey = (e: KeyboardEvent) => { if (e.key === "Escape" && onClose) onClose(); };
    window.addEventListener("keydown", handleKey);
    return () => { document.body.style.overflow = ""; window.removeEventListener("keydown", handleKey); };
  }, [onClose]);

  return (
    <div
      style={{
        position: "fixed", inset: 0, width: "100%", height: "100%",
        background: "#0B1015", zIndex: 50,
        display: "flex", flexDirection: "column",
        animation: "droneFadeIn 0.3s ease forwards",
      }}
      id="drone-mission-panel"
    >
      <style>{`
        @keyframes droneFadeIn { from { opacity: 0; } to { opacity: 1; } }
      `}</style>

      {/* ── Header Ribbon ─────────────────────────────────────── */}
      <div style={{
        padding: "16px 24px", display: "flex", alignItems: "center", justifyContent: "space-between",
        borderBottom: "1px solid rgba(255,255,255,0.05)", flexShrink: 0,
        background: "rgba(11,16,21,0.95)", backdropFilter: "blur(20px)",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
          <div style={{
            width: "48px", height: "48px", borderRadius: "16px",
            background: "rgba(249,115,22,0.1)", border: "1px solid rgba(249,115,22,0.2)",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: "1.4rem", boxShadow: "0 0 20px rgba(249,115,22,0.15)",
          }}>🚁</div>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
              <h1 style={{ fontSize: "22px", fontWeight: 300, color: "#fff", letterSpacing: "0.02em", margin: 0 }}>
                Drone <span style={{ fontWeight: 600, color: "#f97316" }}>Mission Control</span>
              </h1>
              <div style={{
                padding: "2px 10px", borderRadius: "999px", fontSize: "10px", fontWeight: 700,
                textTransform: "uppercase", letterSpacing: "0.1em",
                background: dm.droneStatus.connected ? "rgba(34,197,94,0.1)" : "rgba(248,113,113,0.1)",
                color: dm.droneStatus.connected ? "#4ade80" : "#f87171",
                border: `1px solid ${dm.droneStatus.connected ? "rgba(34,197,94,0.2)" : "rgba(248,113,113,0.2)"}`,
                display: "flex", alignItems: "center", gap: "6px",
              }}>
                <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: dm.droneStatus.connected ? "#4ade80" : "#f87171" }} />
                {dm.droneStatus.connected ? "Connected" : "Offline"}
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px", marginTop: "4px" }}>
              <span style={{ fontSize: "13px", color: "#94a3b8", fontWeight: 500 }}>
                🔋 {dm.droneStatus.battery_pct}% · 📡 {dm.droneStatus.gps_satellites} sats · 💨 {dm.weather.wind_speed_m_s.toFixed(1)} m/s
              </span>
              <span style={{ fontSize: "13px", color: "#475569" }}>·</span>
              <span style={{ fontSize: "13px", color: passCount === dm.preflightChecks.length ? "#4ade80" : "#fbbf24", fontWeight: 600 }}>
                {passCount}/{dm.preflightChecks.length} preflight ✓
              </span>
            </div>
          </div>
        </div>

        {onClose && (
          <button
            onClick={onClose}
            style={{
              display: "flex", alignItems: "center", gap: "8px",
              padding: "8px 16px", fontSize: "14px", fontWeight: 600,
              color: "#94a3b8", background: "rgba(255,255,255,0.05)",
              border: "1px solid rgba(255,255,255,0.05)", borderRadius: "12px",
              cursor: "pointer", transition: "all 0.15s",
            }}
            onMouseOver={e => { e.currentTarget.style.color = "#fff"; e.currentTarget.style.background = "rgba(255,255,255,0.1)"; }}
            onMouseOut={e => { e.currentTarget.style.color = "#94a3b8"; e.currentTarget.style.background = "rgba(255,255,255,0.05)"; }}
          >
            Close Workspace ✕
          </button>
        )}
      </div>

      {/* ── Main 2-Column Body ────────────────────────────────── */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>

        {/* Left Column (45%) — Planner + Preflight + Weather */}
        <div style={{ width: "45%", display: "flex", flexDirection: "column", borderRight: "1px solid rgba(255,255,255,0.05)" }}>
          {/* Section header */}
          <div style={{ padding: "16px 24px 12px", borderBottom: "1px solid rgba(255,255,255,0.05)", flexShrink: 0 }}>
            <div style={{ fontSize: "11px", fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: "10px" }}>Mission Configuration</div>
            <DroneHeaderBand drone={dm.droneStatus} weather={dm.weather} />
          </div>

          <div style={{ flex: 1, overflowY: "auto", padding: "16px 24px 24px" }} className="custom-scrollbar">
            {/* Preflight */}
            <div style={{ marginBottom: "16px" }}>
              <PreflightChecklistWidget checks={dm.preflightChecks} />
            </div>
            <div style={{ marginBottom: "16px" }}>
              <WeatherWidget weather={dm.weather} />
            </div>

            {/* Error */}
            {dm.error && (
              <div style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.15)", borderRadius: "8px", padding: "8px 10px", fontSize: "0.72rem", color: "#fca5a5", marginBottom: "12px" }}>
                ⚠️ {dm.error}
              </div>
            )}

            {/* Planner always visible on left */}
            <PlannerTab
              selectedType={selectedType} setSelectedType={setSelectedType}
              targetGsd={targetGsd} setTargetGsd={setTargetGsd}
              overlapPct={overlapPct} setOverlapPct={setOverlapPct}
              selectedPattern={selectedPattern} setSelectedPattern={setSelectedPattern}
              flightMode={flightMode} setFlightMode={setFlightMode}
              loading={dm.loading} onPlan={handlePlan}
              suggestions={dm.suggestions} onPlanSuggestion={handlePlanSuggestion}
            />

            {!polygonGeoJson && (
              <div style={{ background: "rgba(245,158,11,0.06)", border: "1px solid rgba(245,158,11,0.12)", borderRadius: "8px", padding: "10px", fontSize: "0.72rem", color: "#fbbf24", textAlign: "center", marginTop: "12px" }}>
                ⚠️ No plot polygon available. Add a polygon to plan drone missions.
              </div>
            )}
          </div>
        </div>

        {/* Right Column (55%) — Flight Plan / Telemetry / History */}
        <div style={{ width: "55%", display: "flex", flexDirection: "column", background: "#0B1015" }}>
          {/* Tabs */}
          <div style={{ display: "flex", padding: "0 24px", borderBottom: "1px solid rgba(255,255,255,0.05)", flexShrink: 0 }}>
            {TAB_CONFIG.filter(t => t.id !== "planner").map(tab => (
              <button
                key={tab.id}
                onClick={() => dm.setActiveTab(tab.id)}
                style={{
                  minWidth: "120px", padding: "16px 8px", fontSize: "14px", fontWeight: 500,
                  border: "none", cursor: "pointer", position: "relative",
                  background: "transparent",
                  color: dm.activeTab === tab.id ? "#a5b4fc" : "#64748b",
                  borderBottom: dm.activeTab === tab.id ? "2px solid #6366f1" : "2px solid transparent",
                  transition: "all 0.15s",
                }}
              >
                {tab.icon} {tab.label}
              </button>
            ))}
          </div>

          {/* Tab Content */}
          <div style={{ flex: 1, overflowY: "auto", padding: "24px" }} className="custom-scrollbar">
            {dm.activeTab === "flightplan" && (
              dm.flightPlan ? (
                <FlightPlanTab
                  plan={dm.flightPlan}
                  onLaunch={() => dm.dispatchMission()}
                  onCancel={dm.cancelPlan}
                  loading={dm.loading}
                />
              ) : (
                <div style={{ textAlign: "center", color: "#475569", padding: "80px 0" }}>
                  <div style={{ fontSize: "3rem", marginBottom: "12px", opacity: 0.5 }}>🛫</div>
                  <div style={{ fontSize: "16px", color: "#94a3b8", fontWeight: 500 }}>No flight plan generated yet</div>
                  <div style={{ fontSize: "13px", color: "#475569", marginTop: "6px" }}>Use the Mission Configuration panel on the left to generate one.</div>
                </div>
              )
            )}

            {dm.activeTab === "telemetry" && (
              dm.activeMission ? (
                <TelemetryTab mission={dm.activeMission} onControl={dm.controlMission} />
              ) : (
                <div style={{ textAlign: "center", color: "#475569", padding: "80px 0" }}>
                  <div style={{ fontSize: "3rem", marginBottom: "12px", opacity: 0.5 }}>📡</div>
                  <div style={{ fontSize: "16px", color: "#94a3b8", fontWeight: 500 }}>No active mission</div>
                  <div style={{ fontSize: "13px", color: "#475569", marginTop: "6px" }}>Launch a mission to see live telemetry data.</div>
                </div>
              )
            )}

            {dm.activeTab === "history" && <HistoryTab history={dm.history} />}

            {/* Default to flightplan if planner tab was selected (since planner is now always on left) */}
            {dm.activeTab === "planner" && (
              <div style={{ textAlign: "center", color: "#475569", padding: "80px 0" }}>
                <div style={{ fontSize: "3rem", marginBottom: "12px", opacity: 0.5 }}>🛫</div>
                <div style={{ fontSize: "16px", color: "#94a3b8", fontWeight: 500 }}>Configure your mission on the left</div>
                <div style={{ fontSize: "13px", color: "#475569", marginTop: "6px" }}>Then switch to Flight Plan, Telemetry, or History tabs here.</div>
              </div>
            )}
          </div>

          {/* Footer */}
          <div style={{
            padding: "10px 24px", borderTop: "1px solid rgba(255,255,255,0.05)",
            display: "flex", justifyContent: "space-between", alignItems: "center",
            fontSize: "11px", color: "#475569", fontWeight: 600,
            textTransform: "uppercase", letterSpacing: "0.08em", flexShrink: 0,
          }}>
            <span>AgriWise Drone v2</span>
            <span style={{ color: dm.droneStatus.connected ? "#4ade80" : "#f87171" }}>● {dm.droneStatus.connected ? "CONNECTED" : "OFFLINE"}</span>
          </div>
        </div>

      </div>
    </div>
  );
}
