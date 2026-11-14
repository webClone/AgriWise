"use client";

/**
 * SensorNetworkWorkspace — Fullscreen sensor management workspace.
 * 2-column layout: Left = sensor list + add device, Right = telemetry/readings/alerts tabs.
 */

import { useState, useEffect, useCallback } from "react";

interface SensorStatus {
  id: string; deviceId: string; type: string; vendor: string | null;
  status: string; isOnline: boolean; battery: number | null; rssi: number | null;
  signalQuality: string; lastSync: string | null; createdAt: string;
  latestReading: { temperature: number | null; humidity: number | null; soilMoisture: number | null; ec: number | null; windSpeed: number | null; rainfall: number | null; timestamp: string } | null;
}

const TYPE_META: Record<string, { icon: string; label: string; color: string }> = {
  MOISTURE: { icon: "💧", label: "Soil Moisture", color: "#34d399" },
  TEMP: { icon: "🌡️", label: "Temp & Humidity", color: "#f59e0b" },
  EC: { icon: "⚡", label: "EC / Salinity", color: "#a78bfa" },
  WEATHER: { icon: "🌤️", label: "Weather Station", color: "#60a5fa" },
};

function getRelativeTime(d: string | null) {
  if (!d) return "Never";
  const s = Math.floor((Date.now() - new Date(d).getTime()) / 1000);
  if (s < 60) return `${s}s ago`; if (s < 3600) return `${Math.floor(s/60)}m ago`;
  if (s < 86400) return `${Math.floor(s/3600)}h ago`; return `${Math.floor(s/86400)}d ago`;
}

type SensorTab = "readings" | "alerts" | "config";

export default function SensorNetworkWorkspace({
  plotId,
  initialSensorId = null,
  onClose,
}: {
  plotId: string;
  initialSensorId?: string | null;
  onClose: () => void;
}) {
  const [sensors, setSensors] = useState<SensorStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<string | null>(initialSensorId);
  const [activeTab, setActiveTab] = useState<SensorTab>("readings");

  useEffect(() => {
    if (initialSensorId) {
      setSelected(initialSensorId);
    }
  }, [initialSensorId]);

  const fetchSensors = useCallback(async () => {
    try {
      const res = await fetch(`/api/plots/${plotId}/sensors/status`);
      if (res.ok) { const d = await res.json(); setSensors(d.sensors || []); }
    } catch { /* swallow */ }
    setLoading(false);
  }, [plotId]);

  useEffect(() => { fetchSensors(); const i = setInterval(fetchSensors, 15000); return () => clearInterval(i); }, [fetchSensors]);

  useEffect(() => {
    document.body.style.overflow = "hidden";
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", h);
    return () => { document.body.style.overflow = ""; window.removeEventListener("keydown", h); };
  }, [onClose]);

  const onlineCount = sensors.filter(s => s.isOnline).length;
  const selectedSensor = sensors.find(s => s.id === selected) || null;

  const S = {
    card: { background: "rgba(15,23,42,0.6)", border: "1px solid rgba(71,85,105,0.15)", borderRadius: "10px", padding: "12px" } as React.CSSProperties,
    label: { fontSize: "10px", color: "#64748b", textTransform: "uppercase" as const, letterSpacing: "0.08em", fontWeight: 700 },
  };

  return (
    <div style={{ position: "fixed", inset: 0, width: "100%", height: "100%", background: "#0B1015", zIndex: 50, display: "flex", flexDirection: "column", animation: "sensorFadeIn 0.3s ease forwards" }}>
      <style>{`@keyframes sensorFadeIn { from { opacity: 0; } to { opacity: 1; } }`}</style>

      {/* Header */}
      <div style={{ padding: "16px 24px", display: "flex", alignItems: "center", justifyContent: "space-between", borderBottom: "1px solid rgba(255,255,255,0.05)", flexShrink: 0, background: "rgba(11,16,21,0.95)", backdropFilter: "blur(20px)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
          <div style={{ width: "48px", height: "48px", borderRadius: "16px", background: "rgba(34,197,94,0.1)", border: "1px solid rgba(34,197,94,0.2)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "1.4rem", boxShadow: "0 0 20px rgba(34,197,94,0.15)" }}>📡</div>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
              <h1 style={{ fontSize: "22px", fontWeight: 300, color: "#fff", margin: 0 }}>Sensor <span style={{ fontWeight: 600, color: "#22c55e" }}>Network</span></h1>
              <div style={{ padding: "2px 10px", borderRadius: "999px", fontSize: "10px", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.1em", background: "rgba(34,197,94,0.1)", color: "#4ade80", border: "1px solid rgba(34,197,94,0.2)", display: "flex", alignItems: "center", gap: "6px" }}>
                <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: "#4ade80" }} />
                {onlineCount}/{sensors.length} Online
              </div>
            </div>
            <div style={{ fontSize: "13px", color: "#94a3b8", marginTop: "4px" }}>
              IoT Ground Truth · Real-time Field Telemetry · Auto-refresh 15s
            </div>
          </div>
        </div>
        <button onClick={onClose} style={{ display: "flex", alignItems: "center", gap: "8px", padding: "8px 16px", fontSize: "14px", fontWeight: 600, color: "#94a3b8", background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.05)", borderRadius: "12px", cursor: "pointer" }}
          onMouseOver={e => { e.currentTarget.style.color = "#fff"; e.currentTarget.style.background = "rgba(255,255,255,0.1)"; }}
          onMouseOut={e => { e.currentTarget.style.color = "#94a3b8"; e.currentTarget.style.background = "rgba(255,255,255,0.05)"; }}>
          Close Workspace ✕
        </button>
      </div>

      {/* 2-Column Body */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        {/* Left: Sensor List */}
        <div style={{ width: "38%", display: "flex", flexDirection: "column", borderRight: "1px solid rgba(255,255,255,0.05)" }}>
          <div style={{ padding: "16px 24px 12px", borderBottom: "1px solid rgba(255,255,255,0.05)", flexShrink: 0, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div style={S.label}>Registered Devices ({sensors.length})</div>
          </div>
          <div style={{ flex: 1, overflowY: "auto", padding: "12px 16px" }} className="custom-scrollbar">
            {loading && <div style={{ textAlign: "center", padding: "40px 0", color: "#64748b", fontSize: "13px" }}>Loading sensors…</div>}
            {!loading && sensors.length === 0 && (
              <div style={{ textAlign: "center", padding: "60px 20px", color: "#475569" }}>
                <div style={{ fontSize: "3rem", marginBottom: "12px", opacity: 0.5 }}>📡</div>
                <div style={{ fontSize: "16px", color: "#94a3b8", fontWeight: 500 }}>No sensors registered</div>
                <div style={{ fontSize: "13px", marginTop: "6px" }}>Register an IoT device to start receiving field telemetry.</div>
              </div>
            )}
            {sensors.map(s => {
              const meta = TYPE_META[s.type] || { icon: "📟", label: s.type, color: "#94a3b8" };
              const isSelected = selected === s.id;
              return (
                <div key={s.id} onClick={() => setSelected(s.id)}
                  style={{ ...S.card, marginBottom: "8px", cursor: "pointer", transition: "all 0.15s",
                    border: isSelected ? `1px solid ${meta.color}50` : "1px solid rgba(71,85,105,0.15)",
                    background: isSelected ? `${meta.color}08` : "rgba(15,23,42,0.6)",
                  }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "8px" }}>
                    <span style={{ fontSize: "1.2rem" }}>{meta.icon}</span>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: "13px", color: "#e2e8f0", fontWeight: 700 }}>{meta.label}</div>
                      <div style={{ fontSize: "10px", color: "#64748b", fontFamily: "monospace" }}>{s.deviceId}</div>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                      <div style={{ width: "7px", height: "7px", borderRadius: "50%", background: s.isOnline ? "#4ade80" : "#64748b", boxShadow: s.isOnline ? "0 0 8px #4ade8050" : "none" }} />
                      <span style={{ fontSize: "10px", color: s.isOnline ? "#4ade80" : "#64748b", fontWeight: 700, textTransform: "uppercase" }}>{s.isOnline ? "Online" : "Offline"}</span>
                    </div>
                  </div>
                  {/* Quick stats */}
                  <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                    {s.battery != null && <span style={{ fontSize: "11px", color: s.battery > 30 ? "#4ade80" : s.battery > 15 ? "#fbbf24" : "#f87171", fontFamily: "monospace" }}>🔋 {Math.round(s.battery)}%</span>}
                    {s.signalQuality && s.signalQuality !== "None" && <span style={{ fontSize: "11px", color: "#94a3b8" }}>📶 {s.signalQuality}</span>}
                    <span style={{ fontSize: "11px", color: "#64748b" }}>⏱ {getRelativeTime(s.lastSync)}</span>
                  </div>
                  {/* Latest readings */}
                  {s.latestReading && (
                    <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", marginTop: "8px" }}>
                      {s.latestReading.temperature != null && <span style={{ fontSize: "10px", padding: "2px 8px", borderRadius: "6px", background: "rgba(249,115,22,0.1)", color: "#fb923c", border: "1px solid rgba(249,115,22,0.15)" }}>🌡 {s.latestReading.temperature.toFixed(1)}°C</span>}
                      {s.latestReading.humidity != null && <span style={{ fontSize: "10px", padding: "2px 8px", borderRadius: "6px", background: "rgba(96,165,250,0.1)", color: "#60a5fa", border: "1px solid rgba(96,165,250,0.15)" }}>💧 {s.latestReading.humidity.toFixed(1)}%</span>}
                      {s.latestReading.soilMoisture != null && <span style={{ fontSize: "10px", padding: "2px 8px", borderRadius: "6px", background: "rgba(52,211,153,0.1)", color: "#34d399", border: "1px solid rgba(52,211,153,0.15)" }}>🌱 {s.latestReading.soilMoisture.toFixed(1)}%</span>}
                      {s.latestReading.ec != null && <span style={{ fontSize: "10px", padding: "2px 8px", borderRadius: "6px", background: "rgba(167,139,250,0.1)", color: "#a78bfa", border: "1px solid rgba(167,139,250,0.15)" }}>⚡ {s.latestReading.ec.toFixed(2)} mS</span>}
                      {s.latestReading.windSpeed != null && <span style={{ fontSize: "10px", padding: "2px 8px", borderRadius: "6px", background: "rgba(56,189,248,0.1)", color: "#38bdf8", border: "1px solid rgba(56,189,248,0.15)" }}>💨 {s.latestReading.windSpeed.toFixed(1)} km/h</span>}
                      {s.latestReading.rainfall != null && <span style={{ fontSize: "10px", padding: "2px 8px", borderRadius: "6px", background: "rgba(34,211,238,0.1)", color: "#22d3ee", border: "1px solid rgba(34,211,238,0.15)" }}>🌧 {s.latestReading.rainfall.toFixed(1)} mm</span>}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Right: Detail / Tabs */}
        <div style={{ width: "62%", display: "flex", flexDirection: "column", background: "#0B1015" }}>
          {/* Tabs */}
          <div style={{ display: "flex", padding: "0 24px", borderBottom: "1px solid rgba(255,255,255,0.05)", flexShrink: 0 }}>
            {([
              { id: "readings" as SensorTab, label: "Live Readings", icon: "📊" },
              { id: "alerts" as SensorTab, label: "Alerts & Health", icon: "⚠️" },
              { id: "config" as SensorTab, label: "Configuration", icon: "⚙️" },
            ]).map(tab => (
              <button key={tab.id} onClick={() => setActiveTab(tab.id)} style={{
                minWidth: "120px", padding: "16px 8px", fontSize: "14px", fontWeight: 500,
                border: "none", cursor: "pointer", background: "transparent",
                color: activeTab === tab.id ? "#a5b4fc" : "#64748b",
                borderBottom: activeTab === tab.id ? "2px solid #6366f1" : "2px solid transparent",
                transition: "all 0.15s",
              }}>{tab.icon} {tab.label}</button>
            ))}
          </div>

          {/* Tab Content */}
          <div style={{ flex: 1, overflowY: "auto", padding: "24px" }} className="custom-scrollbar">
            {!selectedSensor ? (
              <div style={{ textAlign: "center", padding: "80px 0", color: "#475569" }}>
                <div style={{ fontSize: "3rem", marginBottom: "12px", opacity: 0.5 }}>📡</div>
                <div style={{ fontSize: "16px", color: "#94a3b8", fontWeight: 500 }}>{sensors.length > 0 ? "Select a sensor from the left" : "No sensors registered"}</div>
                <div style={{ fontSize: "13px", marginTop: "6px" }}>Click a device to view its detailed readings and configuration.</div>
              </div>
            ) : (
              <>
                {/* Sensor header */}
                <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "20px" }}>
                  <span style={{ fontSize: "1.6rem" }}>{(TYPE_META[selectedSensor.type] || { icon: "📟" }).icon}</span>
                  <div>
                    <div style={{ fontSize: "18px", color: "#f1f5f9", fontWeight: 700 }}>{(TYPE_META[selectedSensor.type] || { label: selectedSensor.type }).label}</div>
                    <div style={{ fontSize: "12px", color: "#64748b", fontFamily: "monospace" }}>{selectedSensor.deviceId} · {selectedSensor.vendor || "Unknown vendor"}</div>
                  </div>
                  <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: "6px" }}>
                    <div style={{ width: "8px", height: "8px", borderRadius: "50%", background: selectedSensor.isOnline ? "#4ade80" : "#64748b" }} />
                    <span style={{ fontSize: "12px", color: selectedSensor.isOnline ? "#4ade80" : "#64748b", fontWeight: 700 }}>{selectedSensor.isOnline ? "Online" : "Offline"}</span>
                  </div>
                </div>

                {activeTab === "readings" && (
                  <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                    {/* Stats grid */}
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "10px" }}>
                      {[
                        { l: "Battery", v: selectedSensor.battery != null ? `${Math.round(selectedSensor.battery)}%` : "--", c: (selectedSensor.battery || 0) > 30 ? "#4ade80" : "#fbbf24", ic: "🔋" },
                        { l: "Signal", v: selectedSensor.signalQuality || "--", c: "#60a5fa", ic: "📶" },
                        { l: "RSSI", v: selectedSensor.rssi != null ? `${selectedSensor.rssi} dBm` : "--", c: "#a78bfa", ic: "📡" },
                        { l: "Last Sync", v: getRelativeTime(selectedSensor.lastSync), c: "#e2e8f0", ic: "⏱" },
                        { l: "Registered", v: selectedSensor.createdAt ? new Date(selectedSensor.createdAt).toLocaleDateString() : "--", c: "#94a3b8", ic: "📅" },
                        { l: "Status", v: selectedSensor.status, c: selectedSensor.isOnline ? "#4ade80" : "#f87171", ic: "●" },
                      ].map(m => (
                        <div key={m.l} style={{ ...S.card, textAlign: "center", padding: "14px" }}>
                          <div style={{ fontSize: "10px", color: "#64748b", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "4px" }}>{m.ic} {m.l}</div>
                          <div style={{ fontSize: "16px", color: m.c, fontWeight: 700, fontFamily: "monospace" }}>{m.v}</div>
                        </div>
                      ))}
                    </div>
                    {/* Latest readings detail */}
                    {selectedSensor.latestReading ? (
                      <div>
                        <div style={S.label as any}>Latest Reading · {getRelativeTime(selectedSensor.latestReading.timestamp)}</div>
                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "10px", marginTop: "10px" }}>
                          {selectedSensor.latestReading.temperature != null && <ReadingCard label="Temperature" value={`${selectedSensor.latestReading.temperature.toFixed(1)}°C`} color="#fb923c" />}
                          {selectedSensor.latestReading.humidity != null && <ReadingCard label="Humidity" value={`${selectedSensor.latestReading.humidity.toFixed(1)}%`} color="#60a5fa" />}
                          {selectedSensor.latestReading.soilMoisture != null && <ReadingCard label="Soil Moisture" value={`${selectedSensor.latestReading.soilMoisture.toFixed(1)}%`} color="#34d399" />}
                          {selectedSensor.latestReading.ec != null && <ReadingCard label="EC" value={`${selectedSensor.latestReading.ec.toFixed(2)} mS/cm`} color="#a78bfa" />}
                          {selectedSensor.latestReading.windSpeed != null && <ReadingCard label="Wind Speed" value={`${selectedSensor.latestReading.windSpeed.toFixed(1)} km/h`} color="#38bdf8" />}
                          {selectedSensor.latestReading.rainfall != null && <ReadingCard label="Rainfall" value={`${selectedSensor.latestReading.rainfall.toFixed(1)} mm`} color="#22d3ee" />}
                        </div>
                      </div>
                    ) : (
                      <div style={{ ...S.card, textAlign: "center", color: "#64748b", fontSize: "13px", padding: "30px" }}>No readings received yet from this sensor.</div>
                    )}
                  </div>
                )}

                {activeTab === "alerts" && (
                  <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                    <div style={S.label as any}>Health & Alerts</div>
                    {/* Battery alert */}
                    {selectedSensor.battery != null && selectedSensor.battery < 20 && (
                      <div style={{ ...S.card, borderColor: "rgba(248,113,113,0.3)", display: "flex", alignItems: "center", gap: "10px" }}>
                        <span style={{ fontSize: "1.2rem" }}>🔋</span>
                        <div>
                          <div style={{ fontSize: "13px", color: "#f87171", fontWeight: 700 }}>Low Battery Critical</div>
                          <div style={{ fontSize: "11px", color: "#94a3b8" }}>Battery at {Math.round(selectedSensor.battery)}%. Replace or recharge immediately.</div>
                        </div>
                      </div>
                    )}
                    {/* Offline alert */}
                    {!selectedSensor.isOnline && (
                      <div style={{ ...S.card, borderColor: "rgba(251,191,36,0.3)", display: "flex", alignItems: "center", gap: "10px" }}>
                        <span style={{ fontSize: "1.2rem" }}>⚠️</span>
                        <div>
                          <div style={{ fontSize: "13px", color: "#fbbf24", fontWeight: 700 }}>Device Offline</div>
                          <div style={{ fontSize: "11px", color: "#94a3b8" }}>Last seen {getRelativeTime(selectedSensor.lastSync)}. Data confidence degraded.</div>
                        </div>
                      </div>
                    )}
                    {/* Signal alert */}
                    {selectedSensor.signalQuality === "Weak" && (
                      <div style={{ ...S.card, borderColor: "rgba(251,191,36,0.3)", display: "flex", alignItems: "center", gap: "10px" }}>
                        <span style={{ fontSize: "1.2rem" }}>📶</span>
                        <div>
                          <div style={{ fontSize: "13px", color: "#fbbf24", fontWeight: 700 }}>Weak Signal</div>
                          <div style={{ fontSize: "11px", color: "#94a3b8" }}>RSSI: {selectedSensor.rssi} dBm. Consider repositioning or adding a repeater.</div>
                        </div>
                      </div>
                    )}
                    {/* All good */}
                    {selectedSensor.isOnline && (selectedSensor.battery == null || selectedSensor.battery >= 20) && selectedSensor.signalQuality !== "Weak" && (
                      <div style={{ ...S.card, borderColor: "rgba(74,222,128,0.3)", display: "flex", alignItems: "center", gap: "10px" }}>
                        <span style={{ fontSize: "1.2rem" }}>✅</span>
                        <div>
                          <div style={{ fontSize: "13px", color: "#4ade80", fontWeight: 700 }}>All Systems Normal</div>
                          <div style={{ fontSize: "11px", color: "#94a3b8" }}>No alerts. Device operating within normal parameters.</div>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {activeTab === "config" && (
                  <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                    <div style={S.label as any}>Device Configuration</div>
                    {[
                      { l: "Device ID", v: selectedSensor.deviceId },
                      { l: "Type", v: (TYPE_META[selectedSensor.type] || { label: selectedSensor.type }).label },
                      { l: "Vendor", v: selectedSensor.vendor || "Unknown" },
                      { l: "Registered", v: selectedSensor.createdAt ? new Date(selectedSensor.createdAt).toLocaleString() : "—" },
                      { l: "Status", v: selectedSensor.status },
                      { l: "Plot ID", v: plotId },
                    ].map(r => (
                      <div key={r.l} style={{ display: "flex", justifyContent: "space-between", padding: "10px 12px", background: "rgba(15,23,42,0.6)", borderRadius: "8px", border: "1px solid rgba(71,85,105,0.1)" }}>
                        <span style={{ fontSize: "12px", color: "#94a3b8", fontWeight: 600 }}>{r.l}</span>
                        <span style={{ fontSize: "12px", color: "#e2e8f0", fontFamily: "monospace" }}>{r.v}</span>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>

          {/* Footer */}
          <div style={{ padding: "10px 24px", borderTop: "1px solid rgba(255,255,255,0.05)", display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "11px", color: "#475569", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.08em", flexShrink: 0 }}>
            <span>AgriWise IoT v1</span>
            <span style={{ color: "#4ade80" }}>● POLLING ACTIVE</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function ReadingCard({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div style={{ background: "rgba(15,23,42,0.6)", border: "1px solid rgba(71,85,105,0.15)", borderRadius: "10px", padding: "14px", textAlign: "center" }}>
      <div style={{ fontSize: "10px", color: "#64748b", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "6px" }}>{label}</div>
      <div style={{ fontSize: "20px", color, fontWeight: 700, fontFamily: "monospace" }}>{value}</div>
    </div>
  );
}
