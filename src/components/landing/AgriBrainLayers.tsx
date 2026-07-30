"use client";
import { Reveal, AnimBar, Sparkline, Counter } from "@/components/landing/LandingPrimitives";
import { useState } from "react";

const LAYERS = [
  { id: "L0", name: "Ingest", icon: "📥", color: "#4ade80", sources: ["🛰️", "🚁", "📡", "📸"] },
  { id: "L1", name: "Fuse", icon: "🔗", color: "#34d399", sources: ["🗺️", "📊"] },
  { id: "L2", name: "Index", icon: "📈", color: "#2dd4bf", sources: ["NDVI", "NDMI", "EVI"] },
  { id: "L3", name: "Water", icon: "💧", color: "#22d3ee", sources: ["ET₀", "VPD", "SWB"] },
  { id: "L4", name: "Nutrients", icon: "🧪", color: "#60a5fa", sources: ["N", "P", "K"] },
  { id: "L5", name: "Bio", icon: "🌿", color: "#818cf8", sources: ["LAI", "fAPAR"] },
  { id: "L6", name: "Yield", icon: "📊", color: "#a78bfa", sources: ["P10", "P50", "P90"] },
  { id: "L7", name: "Risk", icon: "⚠️", color: "#c084fc", sources: ["🔥", "💧", "🦠"] },
  { id: "L8", name: "Prescribe", icon: "💊", color: "#e879f9", sources: ["VRA", "Rx"] },
  { id: "L9", name: "Explain", icon: "💬", color: "#f472b6", sources: ["NLP", "📋"] },
  { id: "L10", name: "Render", icon: "🎨", color: "#fb923c", sources: ["SIRE", "WebGL"] },
];

const DETAILS = [
  { title: "Data Ingestion", desc: "Multi-source ingest: Sentinel-2 L2A (B02–B12), Sentinel-1 SAR (VV/VH), weather, IoT sensors, drone orthomosaics, farmer photos.", inputs: "Raw tiles · JSON · GeoTIFF", outputs: "Unified field_tensor" },
  { title: "Fusion & Calibration", desc: "Radiometric calibration to surface reflectance. SAR terrain correction. Raster resampling to plot grid. IoT kriging to spatial field.", inputs: "field_tensor", outputs: "raster_maps · zone_masks · weather_history" },
  { title: "Vegetation Intelligence", desc: "NDVI, NDMI, EVI, SAVI, NDRE. Kalman-filtered time series. Phenology via GDD + NDVI inflection. LAI from red-edge.", inputs: "L1 rasters", outputs: "indices · phenology · time_series" },
  { title: "Water Diagnostics", desc: "FAO-56 Penman-Monteith ET₀. Kc by phenology. Soil water balance: deficit = Σ(ETc − rain). Hotspot zone ID.", inputs: "L1 weather + L2 pheno", outputs: "diagnoses · deficit_mm · recommendations" },
  { title: "Nutrient Analysis", desc: "Red-edge for chlorophyll → N status. SWIR for K mobility. Soil lab integration (pH, CEC, OC). Zone-level N/P/K scoring.", inputs: "L1 spectral + soil data", outputs: "deficiency_scores · fertilizer_recs" },
  { title: "Biophysical Modeling", desc: "Biomass = fAPAR × PAR × LUE. LAI from NDVI regression. Growth rate anomaly vs GDD-expected trajectory.", inputs: "L2 veg + L1 weather", outputs: "biomass_kg_ha · lai · growth_anomaly" },
  { title: "Yield Forecasting", desc: "Biomass × harvest index. P10/P50/P90 from Monte Carlo weather. Profit surface: yield × price − costs.", inputs: "L5 biomass + market", outputs: "yield t/ha · profit_surface" },
  { title: "Risk Composite", desc: "Water × nutrients × disease × weather. Severity per zone. Confidence-adjusted. Temporal trajectory.", inputs: "L3–L6 outputs", outputs: "severity[] · risk_trajectory · threats[]" },
  { title: "Prescriptive Engine", desc: "Zone-level protocols: irrigate, fertilize, spray, wait. Variable-rate maps. Cost-benefit. Timing from phenology.", inputs: "L7 risk + forecast", outputs: "action_protocols · VRA_maps" },
  { title: "Explainability", desc: "Natural language per diagnosis. Evidence chains: pixel → index → diagnosis → Rx. Source attribution.", inputs: "All layers", outputs: "explanations · evidence_chains" },
  { title: "SIRE Renderer", desc: "Pixel-level surfaces: water stress, vegetation, nutrients, risk, yield, uncertainty. Multi-source grounding. WebGL palettes.", inputs: "All layers + rasters", outputs: "SurfaceArtifact[] with provenance" },
];

export default function AgriBrainLayers() {
  const [active, setActive] = useState<number | null>(null);

  return (
    <section style={{ padding: "0 0 120px" }}>
      <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "0 24px" }}>
        <Reveal>
          <div style={{ textAlign: "center", marginBottom: "64px" }}>
            <div style={{ display: "inline-flex", padding: "5px 14px", borderRadius: "20px", fontSize: "12px", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.1em", background: "rgba(129,140,248,0.08)", border: "1px solid rgba(129,140,248,0.15)", color: "#818cf8", marginBottom: "20px" }}>Architecture</div>
            <h2 style={{ fontSize: "clamp(2.4rem, 5vw, 3.6rem)", fontWeight: 200, margin: "0 0 16px" }}>
              The <span style={{ fontWeight: 800, color: "#f8fafc" }}>11-Layer Pipeline</span>
            </h2>
            <p style={{ fontSize: "19px", color: "#64748b", maxWidth: "600px", margin: "0 auto", lineHeight: 1.65 }}>Click any layer to explore its inputs, outputs, and algorithms.</p>
          </div>
        </Reveal>

        {/* ── ANIMATED PIPELINE DIAGRAM ─────────────────────── */}
        <Reveal delay={0.1}>
          <div style={{ padding: "40px 32px", borderRadius: "24px", background: "rgba(15,23,42,0.5)", border: "1px solid rgba(71,85,105,0.08)", marginBottom: "32px" }}>
            {/* Layer nodes */}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "6px", flexWrap: "wrap", marginBottom: "28px" }}>
              {LAYERS.map((l, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                  <button
                    onClick={() => setActive(active === i ? null : i)}
                    className="ab-node"
                    style={{
                      display: "flex", flexDirection: "column", alignItems: "center", gap: "6px",
                      padding: "14px 10px", borderRadius: "16px", border: `2px solid ${active === i ? l.color : l.color + "20"}`,
                      background: active === i ? `${l.color}15` : "rgba(15,23,42,0.6)",
                      cursor: "pointer", transition: "all 0.3s ease", minWidth: "72px",
                      transform: active === i ? "scale(1.08)" : "scale(1)",
                      boxShadow: active === i ? `0 0 24px ${l.color}30` : "none",
                    }}>
                    <span style={{ fontSize: "1.5rem" }}>{l.icon}</span>
                    <span style={{ fontSize: "13px", fontWeight: 800, color: l.color, fontFamily: "monospace" }}>{l.id}</span>
                    <span style={{ fontSize: "10px", color: "#94a3b8", fontWeight: 600 }}>{l.name}</span>
                  </button>
                  {i < LAYERS.length - 1 && (
                    <div style={{ display: "flex", alignItems: "center" }}>
                      <div style={{ width: "20px", height: "2px", background: `linear-gradient(90deg, ${l.color}40, ${LAYERS[i + 1].color}40)` }} />
                      <div style={{ width: 0, height: 0, borderTop: "5px solid transparent", borderBottom: "5px solid transparent", borderLeft: `6px solid ${LAYERS[i + 1].color}40` }} />
                    </div>
                  )}
                </div>
              ))}
            </div>

            {/* Detail panel */}
            {active !== null && (
              <div style={{ padding: "28px 32px", borderRadius: "18px", background: `${LAYERS[active].color}06`, border: `1px solid ${LAYERS[active].color}15`, animation: "fadeSlideUp 0.35s ease" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "14px", marginBottom: "16px" }}>
                  <span style={{ fontSize: "2.2rem" }}>{LAYERS[active].icon}</span>
                  <div>
                    <div style={{ fontSize: "22px", fontWeight: 800, color: LAYERS[active].color }}>{LAYERS[active].id} — {DETAILS[active].title}</div>
                    <div style={{ display: "flex", gap: "6px", marginTop: "4px" }}>
                      {LAYERS[active].sources.map((s, j) => (
                        <span key={j} style={{ padding: "2px 8px", borderRadius: "6px", background: "rgba(71,85,105,0.12)", fontSize: "11px", color: "#94a3b8", fontWeight: 600 }}>{s}</span>
                      ))}
                    </div>
                  </div>
                </div>
                <p style={{ fontSize: "16px", color: "#94a3b8", lineHeight: 1.7, margin: "0 0 18px" }}>{DETAILS[active].desc}</p>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                  <div style={{ padding: "16px 20px", borderRadius: "14px", background: "rgba(8,12,25,0.5)", border: "1px solid rgba(71,85,105,0.06)" }}>
                    <div style={{ fontSize: "11px", color: "#475569", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "6px" }}>📥 Inputs</div>
                    <div style={{ fontSize: "15px", color: "#94a3b8", fontWeight: 600 }}>{DETAILS[active].inputs}</div>
                  </div>
                  <div style={{ padding: "16px 20px", borderRadius: "14px", background: `${LAYERS[active].color}06`, border: `1px solid ${LAYERS[active].color}10` }}>
                    <div style={{ fontSize: "11px", color: LAYERS[active].color, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "6px" }}>📤 Outputs</div>
                    <div style={{ fontSize: "15px", color: "#e2e8f0", fontWeight: 600 }}>{DETAILS[active].outputs}</div>
                  </div>
                </div>
              </div>
            )}

            {active === null && (
              <div style={{ textAlign: "center", padding: "20px", color: "#475569", fontSize: "15px" }}>
                👆 Click a layer node above to explore
              </div>
            )}
          </div>
        </Reveal>

        {/* ── ANIMATED VERTICAL FLOW ───────────────────────── */}
        <Reveal delay={0.2}>
          <div style={{ display: "grid", gridTemplateColumns: "60px 1fr", gap: "0", position: "relative" }}>
            {/* Vertical line */}
            <div style={{ position: "relative" }}>
              <div style={{ position: "absolute", left: "29px", top: 0, bottom: 0, width: "2px", background: "linear-gradient(180deg, #4ade80, #22d3ee, #818cf8, #c084fc, #e879f9, #fb923c)", opacity: 0.2 }} />
              {LAYERS.map((l, i) => (
                <div key={i} style={{ position: "relative", height: "80px", display: "flex", alignItems: "center" }}>
                  <div style={{ width: "20px", height: "20px", borderRadius: "50%", background: `${l.color}20`, border: `2px solid ${l.color}50`, position: "absolute", left: "20px", display: "flex", alignItems: "center", justifyContent: "center" }}>
                    <div style={{ width: "8px", height: "8px", borderRadius: "50%", background: l.color, animation: `pulse 2s ease-in-out infinite`, animationDelay: `${i * 0.2}s` }} />
                  </div>
                </div>
              ))}
            </div>
            {/* Cards */}
            <div style={{ display: "flex", flexDirection: "column" }}>
              {LAYERS.map((l, i) => (
                <Reveal key={i} delay={0.05 + i * 0.03}>
                  <div style={{ height: "80px", display: "flex", alignItems: "center", paddingLeft: "16px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "12px", padding: "10px 20px", borderRadius: "12px", background: "rgba(15,23,42,0.4)", border: "1px solid rgba(71,85,105,0.06)", flex: 1 }}>
                      <span style={{ fontSize: "1.3rem" }}>{l.icon}</span>
                      <span style={{ fontSize: "15px", fontWeight: 800, color: l.color, fontFamily: "monospace", width: "36px" }}>{l.id}</span>
                      <span style={{ fontSize: "15px", fontWeight: 600, color: "#e2e8f0" }}>{DETAILS[i].title}</span>
                      <div style={{ display: "flex", gap: "4px", marginLeft: "auto" }}>
                        {l.sources.map((s, j) => (
                          <span key={j} style={{ padding: "2px 6px", borderRadius: "4px", background: `${l.color}08`, fontSize: "10px", color: l.color, fontWeight: 700 }}>{s}</span>
                        ))}
                      </div>
                      <div style={{ width: "80px" }}>
                        <AnimBar value={97 - i * 1.2} color={l.color} height={4} suffix="%" />
                      </div>
                    </div>
                  </div>
                </Reveal>
              ))}
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
