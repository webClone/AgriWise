"use client";
import Image from "next/image";
import { Reveal, Counter } from "./LandingPrimitives";

const FEATURES = [
  { icon: "🛰️", title: "Sentinel Satellite Fusion", desc: "Sentinel-2 optical + Sentinel-1 SAR fused every 5 days. NDVI, NDMI, and backscatter at 10m. Cloud-penetrating all-weather monitoring.", color: "#4ade80" },
  { icon: "🚁", title: "Drone Mission Control", desc: "Plan autonomous flight paths, upload multispectral orthomosaics at 2cm resolution. Stitch into field-wide maps automatically.", color: "#22d3ee" },
  { icon: "📡", title: "IoT Sensor Network", desc: "Soil moisture probes, weather stations, flow meters. Real-time telemetry streamed into the fusion engine. LoRa + cellular supported.", color: "#818cf8" },
  { icon: "📸", title: "Photo Ground Truth", desc: "GPS-tagged field photos with AI disease detection. Upload from your phone. Geolocated evidence validates satellite findings.", color: "#fbbf24" },
  { icon: "🧠", title: "AgriBrain 10-Layer Engine", desc: "Deep reasoning pipeline fusing ALL perception sources: from raw pixels → calibrated surfaces → prescriptions in 30 seconds.", color: "#a78bfa" },
  { icon: "💧", title: "Water Stress Detection", desc: "SAR soil moisture + sensor probes + VPD + ET₀ modeling. Catch drought 5 days before visible symptoms with multi-source confidence.", color: "#06b6d4" },
  { icon: "🎯", title: "Precision Zone Mapping", desc: "Heterogeneity zones from satellite + drone overlay. Severity scores validated by sensor data and photo evidence.", color: "#f59e0b" },
  { icon: "📊", title: "Yield Forecasting", desc: "Biomass-calibrated predictions using satellite time-series + sensor-measured soil conditions. P10/P50/P90 confidence intervals.", color: "#f87171" },
  { icon: "🌿", title: "Crop Phenology", desc: "Growth stage detection from satellite phenology curves + GDD from weather sensors. Never miss a critical intervention window.", color: "#34d399" },
  { icon: "🔬", title: "Nutrient & Disease Maps", desc: "Red-edge spectral analysis + drone multispectral + photo AI for leaf-level pathogen detection. Variable-rate prescriptions per zone.", color: "#fb923c" },
];

const STATS = [
  { value: 10, suffix: "m", label: "Satellite Resolution", desc: "Sentinel-2 L2A" },
  { value: 2, suffix: "cm", label: "Drone Resolution", desc: "Multispectral" },
  { value: 10, suffix: "", label: "AI Layers", desc: "Deep reasoning" },
  { value: 4, suffix: "", label: "Perception Sources", desc: "Sat · Drone · Sensor · Photo" },
];

const PERCEPTION = [
  { name: "Satellites", icon: "🛰️", res: "10m", freq: "5-day revisit", data: "NDVI, SAR, NDMI, Thermal", color: "#4ade80", img: "/landing/feature-satellite.png" },
  { name: "Drones", icon: "🚁", res: "2cm", freq: "On-demand flights", data: "RGB, Multispectral, LiDAR", color: "#22d3ee", img: "/landing/drone.png" },
  { name: "Sensors", icon: "📡", res: "Point-level", freq: "Real-time stream", data: "Soil moisture, Temp, EC, Flow", color: "#818cf8", img: "/landing/sensor.png" },
  { name: "Photos", icon: "📸", res: "Leaf-level", freq: "Farmer uploads", data: "Disease ID, Growth stage, Damage", color: "#fbbf24", img: "/landing/zones.png" },
];

export default function FeaturesSection() {
  return (
    <>
      {/* ═══ STATS STRIP ═════════════════════════════════════ */}
      <section style={{ borderTop: "1px solid rgba(71,85,105,0.08)", borderBottom: "1px solid rgba(71,85,105,0.08)", padding: "50px 0" }}>
        <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "0 24px", display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "24px", textAlign: "center" }}>
          {STATS.map((s, i) => (
            <Reveal key={i} delay={i * 0.08}>
              <div>
                <div style={{ fontSize: "clamp(2.2rem, 4.5vw, 3.5rem)", fontWeight: 800, color: "#4ade80", lineHeight: 1 }}><Counter end={s.value} suffix={s.suffix} /></div>
                <div style={{ fontSize: "13px", color: "#94a3b8", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", marginTop: "6px" }}>{s.label}</div>
                <div style={{ fontSize: "10px", color: "#334155", marginTop: "2px" }}>{s.desc}</div>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      {/* ═══ PERCEPTION STACK ═════════════════════════════════ */}
      <section id="perception" style={{ padding: "110px 0", borderBottom: "1px solid rgba(71,85,105,0.08)" }}>
        <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "0 24px" }}>
          <Reveal>
            <div style={{ textAlign: "center", marginBottom: "64px" }}>
              <div style={{ display: "inline-flex", alignItems: "center", gap: "6px", padding: "5px 14px", borderRadius: "20px", fontSize: "11px", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.1em", background: "rgba(34,211,238,0.08)", border: "1px solid rgba(34,211,238,0.15)", color: "#22d3ee", marginBottom: "18px" }}>Multi-Source Perception</div>
              <h2 style={{ fontSize: "clamp(2rem, 4.5vw, 3.2rem)", fontWeight: 200, margin: "0 0 14px" }}>
                Four Eyes on <span style={{ fontWeight: 800, color: "#f8fafc" }}>Every Field</span>
              </h2>
              <p style={{ fontSize: "17px", color: "#64748b", maxWidth: "620px", margin: "0 auto", lineHeight: 1.65 }}>No single sensor tells the full story. AgriWise fuses satellite, drone, IoT, and photo data into one unified intelligence layer — each source validating the others.</p>
            </div>
          </Reveal>

          {/* Perception cards with images */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "16px" }}>
            {PERCEPTION.map((p, i) => (
              <Reveal key={i} delay={0.05 + i * 0.08}>
                <div className="hp-fcard" style={{ borderRadius: "18px", background: "rgba(15,23,42,0.4)", border: "1px solid rgba(71,85,105,0.08)", overflow: "hidden", display: "flex", flexDirection: i % 2 === 0 ? "row" : "row-reverse" }}>
                  <div style={{ flex: "0 0 42%", position: "relative", minHeight: "220px" }}>
                    <Image src={p.img} alt={p.name} fill style={{ objectFit: "cover" }} />
                    <div style={{ position: "absolute", inset: 0, background: i % 2 === 0 ? "linear-gradient(90deg, transparent 60%, rgba(15,23,42,0.95) 100%)" : "linear-gradient(270deg, transparent 60%, rgba(15,23,42,0.95) 100%)" }} />
                  </div>
                  <div style={{ flex: 1, padding: "28px", display: "flex", flexDirection: "column", justifyContent: "center" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "12px" }}>
                      <span style={{ fontSize: "1.6rem" }}>{p.icon}</span>
                      <h3 style={{ fontSize: "1.2rem", fontWeight: 700, color: p.color, margin: 0 }}>{p.name}</h3>
                    </div>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px", marginBottom: "14px" }}>
                      <div style={{ padding: "8px 12px", borderRadius: "8px", background: "rgba(15,23,42,0.5)", border: "1px solid rgba(71,85,105,0.06)" }}>
                        <div style={{ fontSize: "14px", fontWeight: 800, color: p.color }}>{p.res}</div>
                        <div style={{ fontSize: "9px", color: "#475569", textTransform: "uppercase", letterSpacing: "0.06em" }}>Resolution</div>
                      </div>
                      <div style={{ padding: "8px 12px", borderRadius: "8px", background: "rgba(15,23,42,0.5)", border: "1px solid rgba(71,85,105,0.06)" }}>
                        <div style={{ fontSize: "12px", fontWeight: 700, color: "#94a3b8" }}>{p.freq}</div>
                        <div style={{ fontSize: "9px", color: "#475569", textTransform: "uppercase", letterSpacing: "0.06em" }}>Frequency</div>
                      </div>
                    </div>
                    <p style={{ fontSize: "13px", color: "#64748b", lineHeight: 1.5, margin: 0 }}><span style={{ fontWeight: 600, color: "#94a3b8" }}>Data:</span> {p.data}</p>
                  </div>
                </div>
              </Reveal>
            ))}
          </div>

          {/* Fusion diagram */}
          <Reveal delay={0.4}>
            <div style={{ marginTop: "40px", padding: "32px", borderRadius: "18px", background: "rgba(15,23,42,0.35)", border: "1px solid rgba(71,85,105,0.08)", textAlign: "center" }}>
              <div style={{ fontSize: "11px", fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: "20px" }}>Perception Fusion Pipeline</div>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "12px", flexWrap: "wrap" }}>
                {["🛰️ Satellite", "🚁 Drone", "📡 Sensor", "📸 Photo"].map((s, i) => (
                  <div key={i} style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <span style={{ padding: "8px 14px", borderRadius: "10px", background: "rgba(71,85,105,0.1)", border: "1px solid rgba(71,85,105,0.08)", fontSize: "12px", fontWeight: 600, color: "#94a3b8" }}>{s}</span>
                    {i < 3 && <span style={{ color: "#334155", fontSize: "16px" }}>+</span>}
                  </div>
                ))}
                <span style={{ color: "#475569", fontSize: "20px", margin: "0 8px" }}>→</span>
                <span style={{ padding: "10px 20px", borderRadius: "12px", background: "linear-gradient(135deg, rgba(34,197,94,0.1), rgba(129,140,248,0.08))", border: "1px solid rgba(34,197,94,0.15)", fontSize: "13px", fontWeight: 800, color: "#4ade80" }}>🧠 AgriBrain Fusion</span>
                <span style={{ color: "#475569", fontSize: "20px", margin: "0 8px" }}>→</span>
                <span style={{ padding: "10px 20px", borderRadius: "12px", background: "rgba(251,191,36,0.08)", border: "1px solid rgba(251,191,36,0.12)", fontSize: "13px", fontWeight: 700, color: "#fbbf24" }}>🎯 Prescriptions</span>
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ═══ FEATURES GRID ═══════════════════════════════════ */}
      <section id="features" style={{ padding: "110px 0" }}>
        <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "0 24px" }}>
          <Reveal>
            <div style={{ textAlign: "center", marginBottom: "64px" }}>
              <div style={{ display: "inline-flex", padding: "5px 14px", borderRadius: "20px", fontSize: "11px", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.1em", background: "rgba(129,140,248,0.08)", border: "1px solid rgba(129,140,248,0.15)", color: "#818cf8", marginBottom: "18px" }}>Intelligence Stack</div>
              <h2 style={{ fontSize: "clamp(2rem, 4.5vw, 3.2rem)", fontWeight: 200, margin: "0 0 14px" }}>
                Ten Layers of <span style={{ fontWeight: 800, color: "#f8fafc" }}>Deep Intelligence</span>
              </h2>
              <p style={{ fontSize: "17px", color: "#64748b", maxWidth: "620px", margin: "0 auto", lineHeight: 1.65 }}>Every data source — satellite, drone, sensor, photo — flows through our AI pipeline.</p>
            </div>
          </Reveal>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: "12px" }}>
            {FEATURES.map((f, i) => (
              <Reveal key={i} delay={0.03 + i * 0.04}>
                <div className="hp-fcard" style={{ padding: "24px", borderRadius: "14px", background: "rgba(15,23,42,0.4)", border: "1px solid rgba(71,85,105,0.06)", position: "relative", overflow: "hidden", height: "100%" }}>
                  <div style={{ position: "absolute", top: 0, left: "15%", right: "15%", height: "1px", background: `linear-gradient(90deg, transparent, ${f.color}15, transparent)` }} />
                  <div style={{ width: "44px", height: "44px", borderRadius: "12px", background: `${f.color}06`, border: `1px solid ${f.color}0d`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: "1.3rem", marginBottom: "12px" }}>{f.icon}</div>
                  <h3 style={{ fontSize: "14px", fontWeight: 700, color: "#f1f5f9", margin: "0 0 6px" }}>{f.title}</h3>
                  <p style={{ fontSize: "12px", color: "#64748b", lineHeight: 1.55, margin: 0 }}>{f.desc}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ SHOWCASE PANELS ═════════════════════════════════ */}
      <section style={{ padding: "0 0 110px" }}>
        <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "0 24px", display: "flex", flexDirection: "column", gap: "80px" }}>
          {/* Zone Intelligence */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "48px", alignItems: "center" }}>
            <Reveal>
              <div>
                <div style={{ display: "inline-flex", padding: "5px 14px", borderRadius: "20px", fontSize: "11px", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.1em", background: "rgba(34,211,238,0.08)", border: "1px solid rgba(34,211,238,0.15)", color: "#22d3ee", marginBottom: "20px" }}>Zone Intelligence</div>
                <h2 style={{ fontSize: "clamp(1.6rem, 3vw, 2.4rem)", fontWeight: 200, margin: "0 0 14px" }}>Satellite + Drone <span style={{ fontWeight: 800, color: "#f8fafc" }}>Zone Fusion</span></h2>
                <p style={{ fontSize: "15px", color: "#64748b", lineHeight: 1.7, marginBottom: "24px" }}>Satellite zones at 10m, then drill down with 2cm drone scans. Sensor probes validate soil moisture in each zone. Photos confirm visual diagnosis. Four layers of truth.</p>
                {["10m satellite zones → 2cm drone detail", "Sensor probes validate per-zone soil data", "Photo evidence confirms visual diagnosis", "Confidence score rises with each source", "Multi-step action protocols per zone", "Variable-rate prescription maps"].map((t, i) => (
                  <div key={i} style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "9px" }}>
                    <div style={{ width: "18px", height: "18px", borderRadius: "6px", background: "rgba(34,197,94,0.08)", border: "1px solid rgba(34,197,94,0.1)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#4ade80" strokeWidth="3"><path d="M20 6L9 17l-5-5"/></svg>
                    </div>
                    <span style={{ fontSize: "13px", color: "#94a3b8" }}>{t}</span>
                  </div>
                ))}
              </div>
            </Reveal>
            <Reveal delay={0.15}>
              <div style={{ borderRadius: "18px", overflow: "hidden", border: "1px solid rgba(71,85,105,0.1)", boxShadow: "0 16px 60px rgba(0,0,0,0.4)" }}>
                <Image src="/landing/zones.png" alt="Zones" width={600} height={400} style={{ width: "100%", height: "auto", display: "block" }} />
              </div>
            </Reveal>
          </div>

          {/* AI Engine */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "48px", alignItems: "center" }}>
            <Reveal>
              <div style={{ borderRadius: "18px", overflow: "hidden", border: "1px solid rgba(71,85,105,0.1)", boxShadow: "0 16px 60px rgba(0,0,0,0.4)" }}>
                <Image src="/landing/ai-brain.png" alt="AI" width={600} height={400} style={{ width: "100%", height: "auto", display: "block" }} />
              </div>
            </Reveal>
            <Reveal delay={0.15}>
              <div>
                <div style={{ display: "inline-flex", padding: "5px 14px", borderRadius: "20px", fontSize: "11px", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.1em", background: "rgba(129,140,248,0.08)", border: "1px solid rgba(129,140,248,0.15)", color: "#818cf8", marginBottom: "20px" }}>AgriBrain Engine</div>
                <h2 style={{ fontSize: "clamp(1.6rem, 3vw, 2.4rem)", fontWeight: 200, margin: "0 0 14px" }}>All Sources, <span style={{ fontWeight: 800, color: "#f8fafc" }}>One Brain</span></h2>
                <p style={{ fontSize: "15px", color: "#64748b", lineHeight: 1.7, marginBottom: "24px" }}>Satellite imagery, drone orthomosaics, sensor telemetry, and farmer photos all flow into one 10-layer reasoning engine. Each layer cross-validates against every available source.</p>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
                  {[
                    { n: "L0-L2", t: "Ingest & Calibrate", s: "🛰️ 📡" }, { n: "L3-L4", t: "Time Series + Spatial", s: "🛰️ 🚁" },
                    { n: "L5-L6", t: "Anomaly + Risk", s: "📡 📸" }, { n: "L7-L8", t: "Zones + Prescriptions", s: "🧠 🎯" },
                    { n: "L9", t: "Explainability", s: "📊 ✅" }, { n: "Fusion", t: "Cross-Source Validation", s: "🛰️🚁📡📸" },
                  ].map((l, i) => (
                    <div key={i} style={{ display: "flex", alignItems: "center", gap: "8px", padding: "8px 12px", borderRadius: "8px", background: "rgba(15,23,42,0.5)", border: "1px solid rgba(71,85,105,0.06)" }}>
                      <span style={{ fontSize: "10px", fontWeight: 800, color: "#818cf8", fontFamily: "monospace" }}>{l.n}</span>
                      <span style={{ fontSize: "11px", color: "#94a3b8", flex: 1 }}>{l.t}</span>
                      <span style={{ fontSize: "10px" }}>{l.s}</span>
                    </div>
                  ))}
                </div>
              </div>
            </Reveal>
          </div>

          {/* Water + Sensors */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "48px", alignItems: "center" }}>
            <Reveal>
              <div>
                <div style={{ display: "inline-flex", padding: "5px 14px", borderRadius: "20px", fontSize: "11px", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.1em", background: "rgba(251,191,36,0.08)", border: "1px solid rgba(251,191,36,0.15)", color: "#fbbf24", marginBottom: "20px" }}>Multi-Source Detection</div>
                <h2 style={{ fontSize: "clamp(1.6rem, 3vw, 2.4rem)", fontWeight: 200, margin: "0 0 14px" }}>Sensors + Satellites = <span style={{ fontWeight: 800, color: "#f8fafc" }}>Early Warning</span></h2>
                <p style={{ fontSize: "15px", color: "#64748b", lineHeight: 1.7, marginBottom: "24px" }}>SAR detects surface moisture from space. Soil probes measure at root depth. Weather sensors track VPD. Drone thermal confirms canopy temp. All fused → 5-day early warning.</p>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
                  {[
                    { v: "🛰️ SAR", l: "Surface moisture", c: "#4ade80" },
                    { v: "📡 Probe", l: "Root-depth moisture", c: "#818cf8" },
                    { v: "🌡️ Weather", l: "VPD + ET₀ demand", c: "#f87171" },
                    { v: "🚁 Thermal", l: "Canopy temperature", c: "#22d3ee" },
                  ].map((m, i) => (
                    <div key={i} style={{ padding: "14px", borderRadius: "12px", background: "rgba(15,23,42,0.4)", border: "1px solid rgba(71,85,105,0.06)", textAlign: "center" }}>
                      <div style={{ fontSize: "1.1rem", marginBottom: "4px" }}>{m.v}</div>
                      <div style={{ fontSize: "11px", color: "#64748b", fontWeight: 600 }}>{m.l}</div>
                    </div>
                  ))}
                </div>
              </div>
            </Reveal>
            <Reveal delay={0.15}>
              <div style={{ borderRadius: "18px", overflow: "hidden", border: "1px solid rgba(71,85,105,0.1)", boxShadow: "0 16px 60px rgba(0,0,0,0.4)" }}>
                <Image src="/landing/water-stress.png" alt="Water" width={600} height={400} style={{ width: "100%", height: "auto", display: "block" }} />
              </div>
            </Reveal>
          </div>
        </div>
      </section>
    </>
  );
}
