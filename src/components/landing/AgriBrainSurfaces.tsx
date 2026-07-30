"use client";
import { Reveal, AnimBar, Counter, Sparkline } from "@/components/landing/LandingPrimitives";

const GROUNDING = [
  { cls: "RASTER", icon: "🛰️", level: "Highest", conf: 95, desc: "Direct pixel-level sensor measurement", color: "#4ade80", size: "100%" },
  { cls: "ZONE", icon: "🗺️", level: "High", conf: 82, desc: "Zone-level value from heterogeneity", color: "#22d3ee", size: "82%" },
  { cls: "PROXY", icon: "📊", level: "Medium", conf: 65, desc: "Field diagnostic + NDVI spatial proxy", color: "#fbbf24", size: "65%" },
  { cls: "SYNTHETIC", icon: "⚙️", level: "Low", conf: 40, desc: "Uniform field value, no spatial data", color: "#f87171", size: "40%" },
];

const SURFACES = [
  { name: "Water Stress", icon: "💧", color: "#f87171", data: [0.12, 0.15, 0.22, 0.38, 0.52, 0.61, 0.55, 0.48, 0.42, 0.35] },
  { name: "Vegetation", icon: "🌿", color: "#4ade80", data: [0.35, 0.42, 0.55, 0.68, 0.74, 0.78, 0.72, 0.65, 0.58, 0.52] },
  { name: "Nutrients", icon: "🧪", color: "#fbbf24", data: [0.80, 0.75, 0.70, 0.62, 0.55, 0.48, 0.52, 0.58, 0.62, 0.68] },
  { name: "Yield", icon: "📊", color: "#60a5fa", data: [2.1, 2.4, 2.8, 3.2, 3.6, 3.9, 4.1, 4.0, 3.8, 3.5] },
  { name: "Risk", icon: "⚠️", color: "#c084fc", data: [0.15, 0.18, 0.25, 0.42, 0.55, 0.48, 0.38, 0.30, 0.25, 0.20] },
  { name: "VPD Stress", icon: "🌡️", color: "#ef4444", data: [0.05, 0.08, 0.15, 0.32, 0.48, 0.55, 0.42, 0.30, 0.20, 0.12] },
];

const WATER_STEPS = [
  { icon: "🎯", title: "Anchor", desc: "L3 diagnostic sets the field-level water stress probability", color: "#22d3ee", visual: "85%" },
  { icon: "🗺️", title: "Hotspot Zones", desc: "If L3 identified hotspot zones → rasterize directly with ±15% NDVI modulation", color: "#4ade80", visual: "72%" },
  { icon: "🔬", title: "Composite Moisture", desc: "NDMI (w=3) + SAR VV (w=2) + IoT (w=4) + SWB (w=2.5) → z-score normalized", color: "#818cf8", visual: "88%" },
  { icon: "⚖️", title: "Rescale", desc: "Multiplicative scaling: composite mean → match L3 anchor. Preserves spatial variation.", color: "#fbbf24", visual: "92%" },
  { icon: "📍", title: "Spatial Output", desc: "Each pixel: stress probability + grounding class + source provenance chain", color: "#fb923c", visual: "95%" },
];

export default function AgriBrainSurfaces() {
  return (
    <>
      {/* ═══ SURFACE GALLERY ═════════════════════════════════ */}
      <section style={{ padding: "120px 0", borderTop: "1px solid rgba(71,85,105,0.08)" }}>
        <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "0 24px" }}>
          <Reveal>
            <div style={{ textAlign: "center", marginBottom: "64px" }}>
              <div style={{ display: "inline-flex", padding: "6px 16px", borderRadius: "20px", fontSize: "12px", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.1em", background: "rgba(248,113,113,0.08)", border: "1px solid rgba(248,113,113,0.15)", color: "#f87171", marginBottom: "20px" }}>Surface Artifacts</div>
              <h2 style={{ fontSize: "clamp(2.4rem, 5vw, 3.6rem)", fontWeight: 200, margin: "0 0 16px" }}>
                What SIRE <span style={{ fontWeight: 800, color: "#f8fafc" }}>Renders</span>
              </h2>
              <p style={{ fontSize: "19px", color: "#64748b", maxWidth: "550px", margin: "0 auto" }}>Six pixel-level surface maps. Each with its own time-series history.</p>
            </div>
          </Reveal>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "16px" }}>
            {SURFACES.map((s, i) => (
              <Reveal key={i} delay={0.05 + i * 0.06}>
                <div className="hp-fcard" style={{ padding: "28px", borderRadius: "20px", background: "rgba(15,23,42,0.45)", border: "1px solid rgba(71,85,105,0.08)", textAlign: "center" }}>
                  <div style={{ fontSize: "2.5rem", marginBottom: "10px" }}>{s.icon}</div>
                  <div style={{ fontSize: "18px", fontWeight: 700, color: s.color, marginBottom: "12px" }}>{s.name}</div>
                  <Sparkline data={s.data} width={220} height={56} color={s.color} strokeW={2.5} />
                  <div style={{ display: "flex", justifyContent: "space-between", marginTop: "8px", fontSize: "11px", color: "#475569" }}>
                    <span>10 weeks ago</span><span>Now</span>
                  </div>
                  <div style={{ marginTop: "14px" }}>
                    <AnimBar value={70 + i * 5} color={s.color} height={5} label="Confidence" />
                  </div>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ GROUNDING VISUAL ═════════════════════════════════ */}
      <section style={{ padding: "0 0 120px" }}>
        <div style={{ maxWidth: "1000px", margin: "0 auto", padding: "0 24px" }}>
          <Reveal>
            <div style={{ textAlign: "center", marginBottom: "48px" }}>
              <h2 style={{ fontSize: "clamp(2rem, 4.5vw, 3rem)", fontWeight: 200, margin: "0 0 14px" }}>
                Data <span style={{ fontWeight: 800, color: "#f8fafc" }}>Grounding</span>
              </h2>
              <p style={{ fontSize: "18px", color: "#64748b" }}>How confident is each pixel? It depends on the source.</p>
            </div>
          </Reveal>

          {/* Visual pyramid / tower */}
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "10px" }}>
            {GROUNDING.map((g, i) => (
              <Reveal key={i} delay={0.08 + i * 0.08}>
                <div style={{
                  width: g.size, maxWidth: "100%", minWidth: "280px",
                  padding: "24px 32px", borderRadius: "18px",
                  background: `${g.color}08`, border: `2px solid ${g.color}20`,
                  display: "flex", alignItems: "center", gap: "18px",
                  transition: "all 0.3s ease", margin: "0 auto",
                }}>
                  <span style={{ fontSize: "2rem" }}>{g.icon}</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: "flex", alignItems: "baseline", gap: "10px" }}>
                      <span style={{ fontSize: "20px", fontWeight: 800, color: g.color }}>{g.cls}</span>
                      <span style={{ fontSize: "14px", color: "#64748b" }}>— {g.level}</span>
                    </div>
                    <p style={{ fontSize: "15px", color: "#94a3b8", margin: "4px 0 0" }}>{g.desc}</p>
                  </div>
                  <div style={{ textAlign: "center", minWidth: "70px" }}>
                    <div style={{ fontSize: "28px", fontWeight: 800, color: g.color }}><Counter end={g.conf} suffix="%" /></div>
                  </div>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ WATER PIPELINE SCHEMA ════════════════════════════ */}
      <section style={{ padding: "0 0 120px" }}>
        <div style={{ maxWidth: "1000px", margin: "0 auto", padding: "0 24px" }}>
          <Reveal>
            <div style={{ textAlign: "center", marginBottom: "48px" }}>
              <div style={{ display: "inline-flex", padding: "6px 16px", borderRadius: "20px", fontSize: "12px", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.1em", background: "rgba(34,211,238,0.08)", border: "1px solid rgba(34,211,238,0.15)", color: "#22d3ee", marginBottom: "20px" }}>Case Study</div>
              <h2 style={{ fontSize: "clamp(2rem, 4.5vw, 3rem)", fontWeight: 200, margin: "0 0 14px" }}>
                Water Stress <span style={{ fontWeight: 800, color: "#f8fafc" }}>Pipeline</span>
              </h2>
            </div>
          </Reveal>

          <div style={{ position: "relative" }}>
            {/* Vertical connector */}
            <div style={{ position: "absolute", left: "39px", top: "30px", bottom: "30px", width: "2px", background: "linear-gradient(180deg, #22d3ee30, #fb923c30)", zIndex: 0 }} />

            <div style={{ display: "flex", flexDirection: "column", gap: "16px", position: "relative", zIndex: 1 }}>
              {WATER_STEPS.map((s, i) => (
                <Reveal key={i} delay={0.06 + i * 0.08}>
                  <div style={{ display: "flex", gap: "20px", alignItems: "center" }}>
                    {/* Node */}
                    <div style={{ width: "60px", height: "60px", borderRadius: "18px", background: `${s.color}12`, border: `2px solid ${s.color}30`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: "1.6rem", flexShrink: 0 }}>{s.icon}</div>
                    {/* Card */}
                    <div className="hp-fcard" style={{ flex: 1, padding: "22px 28px", borderRadius: "18px", background: "rgba(15,23,42,0.45)", border: "1px solid rgba(71,85,105,0.08)", display: "flex", alignItems: "center", gap: "20px" }}>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontSize: "18px", fontWeight: 700, color: s.color, marginBottom: "4px" }}>Step {i + 1}: {s.title}</div>
                        <p style={{ fontSize: "15px", color: "#94a3b8", margin: 0, lineHeight: 1.6 }}>{s.desc}</p>
                      </div>
                      <div style={{ width: "100px", flexShrink: 0 }}>
                        <AnimBar value={parseInt(s.visual)} color={s.color} height={6} label="Coverage" />
                      </div>
                    </div>
                  </div>
                </Reveal>
              ))}
            </div>
          </div>

          {/* Source weights visual */}
          <Reveal delay={0.5}>
            <div style={{ marginTop: "40px", padding: "32px", borderRadius: "20px", background: "rgba(15,23,42,0.4)", border: "1px solid rgba(71,85,105,0.06)" }}>
              <div style={{ fontSize: "14px", fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "20px", textAlign: "center" }}>Composite Moisture Source Weights</div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "14px" }}>
                {[
                  { name: "IoT Ground Truth", w: 4.0, icon: "📡", color: "#818cf8" },
                  { name: "NDMI Canopy Water", w: 3.0, icon: "🛰️", color: "#4ade80" },
                  { name: "SWB Ks Coefficient", w: 2.5, icon: "⚗️", color: "#fbbf24" },
                  { name: "SAR VV Backscatter", w: 2.0, icon: "📡", color: "#22d3ee" },
                ].map((src, i) => (
                  <div key={i} style={{ textAlign: "center", padding: "20px", borderRadius: "16px", background: `${src.color}06`, border: `1px solid ${src.color}10` }}>
                    <div style={{ fontSize: "2rem", marginBottom: "8px" }}>{src.icon}</div>
                    <div style={{ fontSize: "28px", fontWeight: 800, color: src.color }}>{src.w}</div>
                    <div style={{ fontSize: "11px", color: "#475569", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", marginTop: "4px" }}>Weight</div>
                    <div style={{ fontSize: "13px", color: "#94a3b8", fontWeight: 600, marginTop: "6px" }}>{src.name}</div>
                  </div>
                ))}
              </div>
            </div>
          </Reveal>
        </div>
      </section>
    </>
  );
}
