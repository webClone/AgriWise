"use client";
import { Reveal, Sparkline, AnimBar, LiveTicker, Marquee } from "./LandingPrimitives";

const TELEMETRY = [
  { icon: "🌡️", label: "Soil Temperature", value: "22.4°C", color: "#f87171" },
  { icon: "💧", label: "Soil Moisture", value: "34.7%", color: "#22d3ee" },
  { icon: "🌬️", label: "Wind Speed", value: "12 km/h", color: "#94a3b8" },
  { icon: "☀️", label: "Solar Radiation", value: "842 W/m²", color: "#fbbf24" },
  { icon: "💦", label: "Humidity", value: "61%", color: "#60a5fa" },
  { icon: "🌧️", label: "Rainfall 24h", value: "2.1mm", color: "#818cf8" },
  { icon: "📡", label: "EC Conductivity", value: "1.2 dS/m", color: "#4ade80" },
  { icon: "🔋", label: "Sensor Battery", value: "94%", color: "#34d399" },
];

const NDVI_HISTORY = [0.32, 0.35, 0.41, 0.48, 0.55, 0.62, 0.68, 0.71, 0.74, 0.72, 0.69, 0.65, 0.58, 0.52];
const MOISTURE_HISTORY = [42, 38, 35, 31, 28, 33, 40, 44, 41, 37, 34, 30, 36, 42];
const SAR_HISTORY = [0.18, 0.21, 0.19, 0.23, 0.26, 0.24, 0.28, 0.31, 0.29, 0.27, 0.25, 0.22, 0.20, 0.24];

export default function DataSection() {
  return (
    <>
      {/* ═══ LIVE TELEMETRY MARQUEE ══════════════════════════ */}
      <section style={{ borderTop: "1px solid rgba(71,85,105,0.08)", borderBottom: "1px solid rgba(71,85,105,0.08)", padding: "16px 0", overflow: "hidden" }}>
        <Marquee speed={40}>
          <div style={{ display: "flex", gap: "32px", paddingRight: "32px" }}>
            {TELEMETRY.map((t, i) => (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: "8px", whiteSpace: "nowrap" }}>
                <span style={{ fontSize: "0.9rem" }}>{t.icon}</span>
                <span style={{ fontSize: "11px", color: "#475569" }}>{t.label}</span>
                <span style={{ fontSize: "12px", fontWeight: 700, color: t.color, fontFamily: "monospace" }}>{t.value}</span>
                <div style={{ width: "5px", height: "5px", borderRadius: "50%", background: t.color, opacity: 0.4 }} />
              </div>
            ))}
          </div>
        </Marquee>
      </section>

      {/* ═══ DATA OBSERVATORY ═════════════════════════════════ */}
      <section id="data" style={{ padding: "110px 0", borderBottom: "1px solid rgba(71,85,105,0.08)" }}>
        <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "0 24px" }}>
          <Reveal>
            <div style={{ textAlign: "center", marginBottom: "56px" }}>
              <div style={{ display: "inline-flex", padding: "5px 14px", borderRadius: "20px", fontSize: "11px", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.1em", background: "rgba(248,113,113,0.08)", border: "1px solid rgba(248,113,113,0.15)", color: "#f87171", marginBottom: "18px" }}>Live Data Observatory</div>
              <h2 style={{ fontSize: "clamp(2rem, 4.5vw, 3.2rem)", fontWeight: 200, margin: "0 0 14px" }}>
                Every Metric, <span style={{ fontWeight: 800, color: "#f8fafc" }}>Visualized</span>
              </h2>
              <p style={{ fontSize: "17px", color: "#64748b", maxWidth: "600px", margin: "0 auto", lineHeight: 1.65 }}>Real-time sparklines, animated progress bars, and live tickers turn raw sensor data into instant insight.</p>
            </div>
          </Reveal>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "16px", marginBottom: "24px" }}>
            {/* Sparkline cards */}
            {[
              { title: "NDVI Vegetation Index", data: NDVI_HISTORY, color: "#4ade80", current: "0.72", trend: "+8.2%", trendUp: true },
              { title: "Soil Moisture (%)", data: MOISTURE_HISTORY, color: "#22d3ee", current: "34.7%", trend: "-3.1%", trendUp: false },
              { title: "SAR Backscatter (σ₀)", data: SAR_HISTORY, color: "#818cf8", current: "0.24 dB", trend: "+2.4%", trendUp: true },
            ].map((card, i) => (
              <Reveal key={i} delay={0.05 + i * 0.08}>
                <div className="hp-fcard" style={{ padding: "24px", borderRadius: "16px", background: "rgba(15,23,42,0.4)", border: "1px solid rgba(71,85,105,0.08)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "14px" }}>
                    <div>
                      <div style={{ fontSize: "10px", color: "#64748b", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "4px" }}>{card.title}</div>
                      <div style={{ fontSize: "1.5rem", fontWeight: 800, color: card.color }}>{card.current}</div>
                    </div>
                    <span style={{ fontSize: "11px", fontWeight: 700, color: card.trendUp ? "#4ade80" : "#f87171", padding: "2px 8px", borderRadius: "6px", background: card.trendUp ? "rgba(34,197,94,0.08)" : "rgba(248,113,113,0.08)" }}>
                      {card.trendUp ? "▲" : "▼"} {card.trend}
                    </span>
                  </div>
                  <Sparkline data={card.data} width={260} height={48} color={card.color} />
                  <div style={{ display: "flex", justifyContent: "space-between", marginTop: "8px" }}>
                    <span style={{ fontSize: "9px", color: "#334155" }}>14 days ago</span>
                    <span style={{ fontSize: "9px", color: "#334155" }}>Now</span>
                  </div>
                </div>
              </Reveal>
            ))}
          </div>

          {/* Live tickers row */}
          <Reveal delay={0.3}>
            <div style={{ display: "flex", gap: "12px", justifyContent: "center", flexWrap: "wrap", marginBottom: "32px" }}>
              <LiveTicker items={[
                { icon: "🌡️", label: "Soil Temp", value: "22.4°C", color: "#f87171" },
                { icon: "🌡️", label: "Air Temp", value: "28.1°C", color: "#fb923c" },
                { icon: "🌡️", label: "Canopy Temp", value: "25.7°C", color: "#fbbf24" },
              ]} interval={2500} />
              <LiveTicker items={[
                { icon: "💧", label: "Soil 10cm", value: "34.7%", color: "#22d3ee" },
                { icon: "💧", label: "Soil 30cm", value: "41.2%", color: "#60a5fa" },
                { icon: "💧", label: "Soil 60cm", value: "52.8%", color: "#818cf8" },
              ]} interval={3200} />
              <LiveTicker items={[
                { icon: "📡", label: "Signal Strength", value: "-42 dBm", color: "#4ade80" },
                { icon: "🔋", label: "Battery", value: "94%", color: "#34d399" },
                { icon: "⚡", label: "Solar Charging", value: "842 W/m²", color: "#fbbf24" },
              ]} interval={2800} />
            </div>
          </Reveal>

          {/* Progress bars — analysis confidence */}
          <Reveal delay={0.35}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "24px" }}>
              <div style={{ padding: "24px", borderRadius: "16px", background: "rgba(15,23,42,0.35)", border: "1px solid rgba(71,85,105,0.06)" }}>
                <div style={{ fontSize: "12px", fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "16px" }}>AI Layer Confidence</div>
                <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                  <AnimBar value={97} color="#4ade80" label="L0 Data Ingestion" height={5} />
                  <AnimBar value={94} color="#34d399" label="L1 Radiometric Calibration" height={5} />
                  <AnimBar value={91} color="#22d3ee" label="L3 Time-Series Kalman" height={5} />
                  <AnimBar value={88} color="#60a5fa" label="L5 Anomaly Detection" height={5} />
                  <AnimBar value={85} color="#818cf8" label="L7 Zone Segmentation" height={5} />
                  <AnimBar value={82} color="#a78bfa" label="L9 Prescription Engine" height={5} />
                </div>
              </div>
              <div style={{ padding: "24px", borderRadius: "16px", background: "rgba(15,23,42,0.35)", border: "1px solid rgba(71,85,105,0.06)" }}>
                <div style={{ fontSize: "12px", fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "16px" }}>Perception Source Coverage</div>
                <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                  <AnimBar value={100} color="#4ade80" label="🛰️ Satellite — Global" height={5} />
                  <AnimBar value={72} color="#22d3ee" label="🚁 Drone — Plot-targeted" height={5} />
                  <AnimBar value={85} color="#818cf8" label="📡 Sensors — Deployed" height={5} />
                  <AnimBar value={64} color="#fbbf24" label="📸 Photos — Ground truth" height={5} />
                  <AnimBar value={92} color="#f87171" label="🧠 Fusion Confidence" height={5} />
                  <AnimBar value={88} color="#e879f9" label="🎯 Prescription Readiness" height={5} />
                </div>
              </div>
            </div>
          </Reveal>

          {/* Technical specs grid */}
          <Reveal delay={0.4}>
            <div style={{ marginTop: "24px", display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: "10px" }}>
              {[
                { v: "B02-B12", l: "Spectral Bands", c: "#4ade80" },
                { v: "L2A", l: "Processing Level", c: "#22d3ee" },
                { v: "Kalman", l: "Filter Engine", c: "#818cf8" },
                { v: "GeoJSON", l: "Plot Format", c: "#fbbf24" },
                { v: "WebGL", l: "Map Renderer", c: "#f87171" },
                { v: "LoRa", l: "Sensor Protocol", c: "#34d399" },
              ].map((s, i) => (
                <div key={i} style={{ padding: "16px 12px", borderRadius: "12px", background: "rgba(15,23,42,0.35)", border: "1px solid rgba(71,85,105,0.06)", textAlign: "center" }}>
                  <div style={{ fontSize: "14px", fontWeight: 800, color: s.c, fontFamily: "monospace" }}>{s.v}</div>
                  <div style={{ fontSize: "9px", color: "#475569", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", marginTop: "3px" }}>{s.l}</div>
                </div>
              ))}
            </div>
          </Reveal>
        </div>
      </section>
    </>
  );
}
