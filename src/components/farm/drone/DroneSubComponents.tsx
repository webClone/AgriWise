"use client";
import type { DroneStatus, WeatherInfo, PreflightCheck, FlightPlan, MissionSuggestion, MissionHistoryItem } from "@/hooks/useDroneMission";

const MISSION_TYPE_META: Record<string, { icon: string; label: string; color: string }> = {
  full_plot_map: { icon: "🗺️", label: "Full Plot Map", color: "#60a5fa" },
  rapid_scout: { icon: "⚡", label: "Rapid Scout", color: "#f59e0b" },
  row_audit: { icon: "📏", label: "Row Audit", color: "#4ade80" },
  weed_map: { icon: "🌿", label: "Weed Map", color: "#a78bfa" },
  orchard_audit: { icon: "🌳", label: "Orchard Audit", color: "#34d399" },
  concern_zone_command: { icon: "🔍", label: "Zone Inspect", color: "#f87171" },
  refly_weak_zones: { icon: "🔄", label: "Re-fly Weak", color: "#fbbf24" },
};
export { MISSION_TYPE_META };

const STATE_META: Record<string, { icon: string; label: string; color: string }> = {
  planned: { icon: "📋", label: "Planned", color: "#94a3b8" },
  uploaded: { icon: "📤", label: "Uploading", color: "#60a5fa" },
  ready: { icon: "✅", label: "Ready", color: "#4ade80" },
  arming: { icon: "⚙️", label: "Arming", color: "#f59e0b" },
  in_flight: { icon: "✈️", label: "In Flight", color: "#22d3ee" },
  paused: { icon: "⏸️", label: "Paused", color: "#f59e0b" },
  returning: { icon: "🔙", label: "Returning", color: "#a78bfa" },
  completed: { icon: "✅", label: "Completed", color: "#4ade80" },
  aborted: { icon: "🛑", label: "Aborted", color: "#f87171" },
  failed: { icon: "❌", label: "Failed", color: "#ef4444" },
};
export { STATE_META };

const S: Record<string, React.CSSProperties> = {
  card: { background: "rgba(15,23,42,0.6)", border: "1px solid rgba(71,85,105,0.15)", borderRadius: "10px", padding: "10px" },
  label: { fontSize: "0.62rem", color: "#64748b", textTransform: "uppercase" as const, letterSpacing: "0.05em", fontWeight: 700 },
  val: { fontSize: "0.95rem", color: "#f1f5f9", fontWeight: 700, fontFamily: "monospace" },
  pill: { padding: "3px 8px", borderRadius: "6px", fontSize: "0.65rem", fontWeight: 600 },
};

// ── Header Status Band ───────────────────────────────────────────────────
export function DroneHeaderBand({ drone, weather }: { drone: DroneStatus; weather: WeatherInfo }) {
  const batColor = drone.battery_pct > 50 ? "#4ade80" : drone.battery_pct > 20 ? "#fbbf24" : "#f87171";
  return (
    <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
      {/* Connection */}
      <div style={{ ...S.card, display: "flex", alignItems: "center", gap: "6px", flex: "1 1 auto", minWidth: "80px" }}>
        <div style={{ width: "8px", height: "8px", borderRadius: "50%", background: drone.connected ? "#4ade80" : "#f87171", boxShadow: drone.connected ? "0 0 8px #4ade8050" : "none", animation: drone.connected ? "nonee" : undefined }} />
        <div>
          <div style={S.label}>Status</div>
          <div style={{ fontSize: "0.78rem", color: drone.connected ? "#4ade80" : "#f87171", fontWeight: 700 }}>{drone.connected ? "Online" : "Offline"}</div>
        </div>
      </div>
      {/* Battery */}
      <div style={{ ...S.card, flex: "1 1 auto", minWidth: "70px" }}>
        <div style={S.label}>Battery</div>
        <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
          <div style={{ width: "100%", height: "4px", background: "rgba(71,85,105,0.3)", borderRadius: "2px", overflow: "hidden" }}>
            <div style={{ width: `${drone.battery_pct}%`, height: "100%", background: batColor, borderRadius: "2px", transition: "width 0.5s" }} />
          </div>
          <span style={{ fontSize: "0.75rem", color: batColor, fontWeight: 700, fontFamily: "monospace", minWidth: "30px" }}>{drone.battery_pct}%</span>
        </div>
      </div>
      {/* GPS */}
      <div style={{ ...S.card, flex: "1 1 auto", minWidth: "70px" }}>
        <div style={S.label}>GPS</div>
        <div style={{ fontSize: "0.78rem", color: "#e2e8f0", fontWeight: 600 }}>📡 {drone.gps_satellites} sats</div>
      </div>
      {/* Wind */}
      <div style={{ ...S.card, flex: "1 1 auto", minWidth: "70px" }}>
        <div style={S.label}>Wind</div>
        <div style={{ fontSize: "0.78rem", color: weather.wind_speed_m_s < 8 ? "#e2e8f0" : "#fbbf24", fontWeight: 600 }}>💨 {weather.wind_speed_m_s.toFixed(1)} m/s</div>
      </div>
    </div>
  );
}

// ── Pre-flight Checklist ─────────────────────────────────────────────────
export function PreflightChecklistWidget({ checks }: { checks: PreflightCheck[] }) {
  const statusIcon = { pass: "✅", warn: "⚠️", fail: "❌", pending: "⏳" };
  const statusColor = { pass: "#4ade80", warn: "#fbbf24", fail: "#f87171", pending: "#94a3b8" };
  const allPass = checks.every(c => c.status === "pass");
  return (
    <div style={{ ...S.card, display: "flex", flexDirection: "column", gap: "4px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
        <span style={{ ...S.label, fontSize: "0.68rem" }}>Pre-flight Checklist</span>
        <span style={{ ...S.pill, background: allPass ? "rgba(74,222,128,0.12)" : "rgba(251,191,36,0.12)", color: allPass ? "#4ade80" : "#fbbf24" }}>
          {allPass ? "ALL PASS" : `${checks.filter(c => c.status !== "pass").length} ISSUES`}
        </span>
      </div>
      {checks.map(c => (
        <div key={c.id} style={{ display: "flex", alignItems: "center", gap: "8px", padding: "3px 0", fontSize: "0.72rem" }}>
          <span>{statusIcon[c.status]}</span>
          <span style={{ color: "#e2e8f0", fontWeight: 600, flex: 1 }}>{c.label}</span>
          <span style={{ color: statusColor[c.status], fontFamily: "monospace", fontSize: "0.68rem" }}>{c.detail}</span>
        </div>
      ))}
    </div>
  );
}

// ── Weather Widget ───────────────────────────────────────────────────────
export function WeatherWidget({ weather }: { weather: WeatherInfo }) {
  const windDeg = weather.wind_direction_deg;
  const dirs = ["N","NE","E","SE","S","SW","W","NW"];
  const windDir = dirs[Math.round(windDeg / 45) % 8];
  return (
    <div style={{ ...S.card, display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: "6px" }}>
      <div style={{ textAlign: "center" }}>
        <div style={S.label}>Wind</div>
        <div style={{ fontSize: "0.82rem", color: "#e2e8f0", fontWeight: 700 }}>{weather.wind_speed_m_s.toFixed(1)}</div>
        <div style={{ fontSize: "0.6rem", color: "#64748b" }}>m/s {windDir}</div>
      </div>
      <div style={{ textAlign: "center" }}>
        <div style={S.label}>Temp</div>
        <div style={{ fontSize: "0.82rem", color: "#e2e8f0", fontWeight: 700 }}>{weather.temperature_c}°C</div>
      </div>
      <div style={{ textAlign: "center" }}>
        <div style={S.label}>Humidity</div>
        <div style={{ fontSize: "0.82rem", color: "#e2e8f0", fontWeight: 700 }}>{weather.humidity_pct}%</div>
      </div>
      <div style={{ textAlign: "center" }}>
        <div style={S.label}>Visibility</div>
        <div style={{ fontSize: "0.82rem", color: "#e2e8f0", fontWeight: 700 }}>{weather.visibility_km} km</div>
      </div>
    </div>
  );
}

// ── Flight Plan Preview ──────────────────────────────────────────────────
export function FlightPlanTab({ plan, onLaunch, onCancel, loading }: { plan: FlightPlan; onLaunch: () => void; onCancel: () => void; loading: boolean }) {
  const stats = [
    { label: "Waypoints", value: String(plan.waypoint_count), icon: "📍" },
    { label: "Altitude", value: `${plan.flight_altitude_m.toFixed(1)}m`, icon: "⬆️" },
    { label: "Flight Time", value: `${plan.estimated_flight_time_min.toFixed(1)} min`, icon: "⏱️" },
    { label: "Images", value: String(plan.estimated_image_count), icon: "📷" },
    { label: "GSD", value: `${plan.achieved_gsd_cm} cm/px`, icon: "🔬" },
    { label: "Pattern", value: plan.pattern.replace(/_/g, " "), icon: "📐" },
  ];
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
      {/* Feasibility badge */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span style={{ fontSize: "0.82rem", color: "#e2e8f0", fontWeight: 700 }}>Flight Plan Ready</span>
        <span style={{ ...S.pill, background: plan.is_feasible ? "rgba(74,222,128,0.12)" : "rgba(248,113,113,0.12)", color: plan.is_feasible ? "#4ade80" : "#f87171" }}>
          {plan.is_feasible ? "✓ Feasible" : "✗ Infeasible"}
        </span>
      </div>
      {/* Stats grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "6px" }}>
        {stats.map(s => (
          <div key={s.label} style={{ ...S.card, textAlign: "center", padding: "8px" }}>
            <div style={{ fontSize: "0.6rem", color: "#64748b", marginBottom: "2px" }}>{s.icon} {s.label}</div>
            <div style={{ fontSize: "0.82rem", color: "#f1f5f9", fontWeight: 700, fontFamily: "monospace" }}>{s.value}</div>
          </div>
        ))}
      </div>
      {plan.infeasibility_reason && (
        <div style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.15)", borderRadius: "8px", padding: "8px", fontSize: "0.72rem", color: "#fca5a5" }}>
          ⚠️ {plan.infeasibility_reason}
        </div>
      )}
      {/* Waypoint list */}
      {plan.waypoints.length > 0 && (
        <div style={S.card}>
          <div style={{ ...S.label, marginBottom: "6px" }}>Waypoint Sequence ({plan.waypoints.length})</div>
          <div style={{ maxHeight: "120px", overflowY: "auto", display: "flex", flexDirection: "column", gap: "2px" }} className="custom-scrollbar">
            {plan.waypoints.slice(0, 20).map((wp, i) => (
              <div key={i} style={{ display: "flex", gap: "8px", fontSize: "0.65rem", fontFamily: "monospace", color: "#94a3b8", padding: "2px 4px", background: i % 2 === 0 ? "rgba(0,0,0,0.15)" : "transparent", borderRadius: "4px" }}>
                <span style={{ color: "#64748b", minWidth: "18px" }}>#{i+1}</span>
                <span>{wp.lat.toFixed(5)}</span>
                <span>{wp.lon.toFixed(5)}</span>
                <span style={{ color: "#60a5fa" }}>{wp.alt_m}m</span>
                <span style={{ color: "#a78bfa" }}>{wp.action}</span>
              </div>
            ))}
            {plan.waypoints.length > 20 && <div style={{ fontSize: "0.62rem", color: "#64748b", textAlign: "center", padding: "4px" }}>+{plan.waypoints.length - 20} more waypoints</div>}
          </div>
        </div>
      )}
      {/* Actions */}
      <div style={{ display: "flex", gap: "8px", justifyContent: "flex-end" }}>
        <button onClick={onCancel} style={{ padding: "8px 18px", borderRadius: "8px", border: "1px solid rgba(71,85,105,0.3)", background: "transparent", color: "#94a3b8", fontSize: "0.75rem", fontWeight: 600, cursor: "pointer" }}>Cancel</button>
        <button onClick={onLaunch} disabled={loading || !plan.is_feasible} style={{ padding: "8px 22px", borderRadius: "8px", border: "none", background: plan.is_feasible ? "linear-gradient(135deg, #22c55e, #16a34a)" : "rgba(71,85,105,0.3)", color: plan.is_feasible ? "#fff" : "#64748b", fontSize: "0.75rem", fontWeight: 700, cursor: plan.is_feasible ? "pointer" : "not-allowed", opacity: loading ? 0.6 : 1, boxShadow: plan.is_feasible ? "0 2px 12px rgba(34,197,94,0.3)" : "none" }}>
          {loading ? "Dispatching…" : "🚀 Launch Mission"}
        </button>
      </div>
    </div>
  );
}

// ── Live Telemetry ───────────────────────────────────────────────────────
export function TelemetryTab({ mission, onControl }: { mission: { execution_id: string; state: string; telemetry?: any }; onControl?: (a: "pause"|"resume"|"abort"|"rtl") => void }) {
  const meta = STATE_META[mission.state] || STATE_META.planned;
  const t = mission.telemetry || {};
  const isActive = ["in_flight","paused","arming","uploaded","ready"].includes(mission.state);
  const progress = t.mission_progress_pct ?? 0;
  const r = 32, circ = 2 * Math.PI * r, offset = circ - (progress / 100) * circ;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
      {/* State + progress ring */}
      <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
        <div style={{ position: "relative", width: "72px", height: "72px" }}>
          <svg width="72" height="72" style={{ transform: "rotate(-90deg)" }}>
            <circle cx="36" cy="36" r={r} fill="transparent" stroke="rgba(71,85,105,0.3)" strokeWidth="5" />
            <circle cx="36" cy="36" r={r} fill="transparent" stroke={meta.color} strokeWidth="5" strokeDasharray={circ} strokeDashoffset={offset} strokeLinecap="round" style={{ transition: "stroke-dashoffset 0.5s" }} />
          </svg>
          <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", flexDirection: "column" }}>
            <span style={{ fontSize: "1.1rem", fontWeight: 800, color: "#f1f5f9", fontFamily: "monospace" }}>{progress.toFixed(0)}%</span>
          </div>
        </div>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <span style={{ fontSize: "1.1rem" }}>{meta.icon}</span>
            <span style={{ color: meta.color, fontWeight: 700, fontSize: "0.88rem" }}>{meta.label}</span>
          </div>
          <div style={{ fontSize: "0.62rem", color: "#64748b", fontFamily: "monospace", marginTop: "2px" }}>ID: {mission.execution_id.slice(0, 16)}</div>
        </div>
      </div>
      {/* Telemetry grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "6px" }}>
        {[
          { l: "Battery", v: t.battery_pct != null ? `${t.battery_pct.toFixed(0)}%` : "--", c: t.battery_pct > 30 ? "#4ade80" : "#fbbf24" },
          { l: "Altitude", v: t.altitude_m != null ? `${t.altitude_m.toFixed(1)}m` : "--", c: "#60a5fa" },
          { l: "Speed", v: t.groundspeed_m_s != null ? `${t.groundspeed_m_s.toFixed(1)} m/s` : "--", c: "#e2e8f0" },
          { l: "Captures", v: t.capture_count != null ? String(t.capture_count) : "--", c: "#a78bfa" },
          { l: "Waypoint", v: t.current_waypoint != null ? `${t.current_waypoint}/${t.total_waypoints || "?"}` : "--", c: "#e2e8f0" },
          { l: "Drift", v: t.off_track_m != null ? `${t.off_track_m.toFixed(1)}m` : "--", c: (t.off_track_m || 0) > 3 ? "#fbbf24" : "#4ade80" },
        ].map(m => (
          <div key={m.l} style={{ ...S.card, textAlign: "center", padding: "8px" }}>
            <div style={{ fontSize: "0.6rem", color: "#64748b", textTransform: "uppercase", letterSpacing: "0.04em" }}>{m.l}</div>
            <div style={{ fontSize: "0.88rem", color: m.c, fontWeight: 700, fontFamily: "monospace" }}>{m.v}</div>
          </div>
        ))}
      </div>
      {/* Control buttons */}
      {isActive && onControl && (
        <div style={{ display: "flex", gap: "6px", justifyContent: "center", flexWrap: "wrap" }}>
          {mission.state === "in_flight" && <CtrlBtn label="⏸ Pause" color="#f59e0b" onClick={() => onControl("pause")} />}
          {mission.state === "paused" && <CtrlBtn label="▶ Resume" color="#22d3ee" onClick={() => onControl("resume")} />}
          <CtrlBtn label="🔙 RTL" color="#a78bfa" onClick={() => onControl("rtl")} />
          <CtrlBtn label="🛑 Abort" color="#f87171" onClick={() => onControl("abort")} />
        </div>
      )}
    </div>
  );
}
function CtrlBtn({ label, color, onClick }: { label: string; color: string; onClick: () => void }) {
  return <button onClick={onClick} style={{ padding: "6px 14px", borderRadius: "8px", border: `1px solid ${color}40`, background: `${color}15`, color, fontSize: "0.72rem", fontWeight: 700, cursor: "pointer", transition: "all 0.15s" }}>{label}</button>;
}

// ── History Tab ──────────────────────────────────────────────────────────
export function HistoryTab({ history }: { history: MissionHistoryItem[] }) {
  if (history.length === 0) return <div style={{ textAlign: "center", color: "#64748b", fontSize: "0.78rem", padding: "30px 0" }}>No missions recorded yet</div>;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
      {history.slice(0, 10).map(m => {
        const meta = STATE_META[m.status] || STATE_META.planned;
        const typeMeta = MISSION_TYPE_META[m.mission_type] || MISSION_TYPE_META.full_plot_map;
        return (
          <div key={m.execution_id} style={{ ...S.card, display: "flex", flexDirection: "column", gap: "6px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span style={{ fontSize: "1rem" }}>{typeMeta.icon}</span>
              <span style={{ color: "#e2e8f0", fontWeight: 700, fontSize: "0.78rem", flex: 1 }}>{typeMeta.label}</span>
              <span style={{ ...S.pill, background: `${meta.color}18`, color: meta.color }}>{meta.icon} {meta.label}</span>
            </div>
            <div style={{ display: "flex", gap: "12px", fontSize: "0.65rem", color: "#94a3b8" }}>
              {m.timestamp && <span>📅 {new Date(m.timestamp).toLocaleDateString()}</span>}
              {m.duration_s != null && <span>⏱ {(m.duration_s / 60).toFixed(1)} min</span>}
              {m.coverage_pct != null && <span>📐 {m.coverage_pct.toFixed(0)}%</span>}
              {m.actual_captures != null && <span>📷 {m.actual_captures}</span>}
              {m.battery_used_pct != null && <span>🔋 -{m.battery_used_pct.toFixed(0)}%</span>}
            </div>
            <div style={{ fontSize: "0.6rem", color: "#475569", fontFamily: "monospace" }}>{m.execution_id.slice(0, 20)}</div>
          </div>
        );
      })}
    </div>
  );
}
