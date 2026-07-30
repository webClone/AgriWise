"use client";
import { Reveal, Sparkline, AnimBar } from "./LandingPrimitives";

const INDICES = [
  { name: "NDVI", formula: "(B08 − B04) / (B08 + B04)", range: "−1 → +1", use: "Canopy chlorophyll density & photosynthetic activity", color: "#4ade80", band: "NIR / Red", typical: "0.2–0.9 cropland" },
  { name: "NDMI", formula: "(B08 − B11) / (B08 + B11)", range: "−1 → +1", use: "Leaf water content & canopy moisture stress", color: "#22d3ee", band: "NIR / SWIR", typical: "0.0–0.6 healthy" },
  { name: "EVI", formula: "2.5 × (B08 − B04) / (B08 + 6B04 − 7.5B02 + 1)", range: "−1 → +1", use: "Enhanced vegetation in high-biomass canopy. Corrects atmospheric + soil background.", color: "#34d399", band: "NIR / Red / Blue", typical: "0.2–0.8 cropland" },
  { name: "SAVI", formula: "(B08 − B04)(1 + L) / (B08 + B04 + L)", range: "−1 → +1", use: "Soil-adjusted vegetation for sparse canopy & early-season crops", color: "#fbbf24", band: "NIR / Red + L", typical: "L=0.5 standard" },
  { name: "NDRE", formula: "(B08 − B05) / (B08 + B05)", range: "−1 → +1", use: "Red-edge chlorophyll — detects N deficiency before NDVI drops", color: "#f87171", band: "NIR / Red Edge", typical: "0.1–0.6 crops" },
  { name: "σ₀ VV/VH", formula: "10 log₁₀(σ₀)", range: "−25 → 0 dB", use: "SAR backscatter — soil moisture, surface roughness, crop structure", color: "#818cf8", band: "C-band 5.4 GHz", typical: "−15 to −5 dB ag" },
];

const PHENOLOGY = [
  { stage: "Germination", gdd: "0–120", desc: "Seed imbibition → radicle emergence. NDVI ~0.15. SAR signature changes as soil is disturbed.", icon: "🌱", ndvi: 0.15 },
  { stage: "Emergence", gdd: "120–200", desc: "Coleoptile breaks surface. First leaf unfolds. NDVI rises to 0.2–0.3. Drone photos confirm stand count.", icon: "🌿", ndvi: 0.25 },
  { stage: "Tillering", gdd: "200–450", desc: "Lateral shoots develop. Canopy closure begins. NDVI 0.4–0.6. Critical N uptake window.", icon: "🍃", ndvi: 0.50 },
  { stage: "Stem Extension", gdd: "450–700", desc: "Internode elongation. Leaf area index peaks. NDVI 0.65–0.8. Water demand rises sharply.", icon: "📏", ndvi: 0.72 },
  { stage: "Heading", gdd: "700–900", desc: "Spike emergence. Pollen viability sensitive to heat stress >32°C. Peak biomass. NDVI ~0.8.", icon: "🌾", ndvi: 0.80 },
  { stage: "Grain Fill", gdd: "900–1200", desc: "Starch accumulation. NDVI declines as canopy senesces. Yield is determined. Moisture ~30% grain.", icon: "✨", ndvi: 0.65 },
  { stage: "Maturity", gdd: "1200–1500", desc: "Physiological maturity. NDVI drops below 0.4. Grain moisture <14% target for harvest.", icon: "🏆", ndvi: 0.35 },
];

const SOIL_PARAMS = [
  { param: "Volumetric Moisture", unit: "m³/m³", source: "SAR σ₀ + IoT TDR", range: "0.05–0.45", critical: "< 0.15 = wilting", color: "#22d3ee" },
  { param: "Electrical Conductivity", unit: "dS/m", source: "IoT EC probe", range: "0–4.0", critical: "> 2.0 = saline stress", color: "#fbbf24" },
  { param: "Temperature (10cm)", unit: "°C", source: "IoT thermocouple", range: "5–35", critical: "< 8 = slow germination", color: "#f87171" },
  { param: "Organic Carbon", unit: "g/kg", source: "Lab + SWIR proxy", range: "5–50", critical: "< 10 = low fertility", color: "#4ade80" },
  { param: "pH (H₂O)", unit: "—", source: "Lab analysis", range: "4.5–8.5", critical: "< 5.5 or > 7.5 = lockout", color: "#818cf8" },
  { param: "CEC", unit: "cmol⁺/kg", source: "Lab analysis", range: "5–40", critical: "< 10 = low retention", color: "#c084fc" },
];

const WATER_MODELS = [
  { model: "ET₀ (Penman-Monteith)", eq: "ET₀ = [0.408Δ(Rn−G) + γ(900/(T+273))u₂(eₛ−eₐ)] / [Δ + γ(1+0.34u₂)]", desc: "FAO-56 reference evapotranspiration. Requires: net radiation, soil heat flux, air temperature, wind speed, saturation deficit.", color: "#22d3ee" },
  { model: "VPD (Vapor Pressure Deficit)", eq: "VPD = eₛ(T) − eₐ = 0.6108·exp(17.27T/(T+237.3)) − eₐ", desc: "Atmospheric drying power. VPD > 2.5 kPa triggers stomatal closure. Drives transpiration demand modeling.", color: "#f87171" },
  { model: "Crop Water Stress Index", eq: "CWSI = (Tc − Ta − LLB) / (ULB − LLB)", desc: "Canopy-to-air temperature differential normalized between well-watered (LLB) and fully-stressed (ULB) baselines. Drone thermal + weather sensor.", color: "#fbbf24" },
];

export default function ScienceSection() {
  return (
    <>
      {/* ═══ SPECTRAL INDICES ════════════════════════════════ */}
      <section id="science" style={{ padding: "110px 0", borderTop: "1px solid rgba(71,85,105,0.08)" }}>
        <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "0 24px" }}>
          <Reveal>
            <div style={{ textAlign: "center", marginBottom: "56px" }}>
              <div style={{ display: "inline-flex", padding: "5px 14px", borderRadius: "20px", fontSize: "11px", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.1em", background: "rgba(34,197,94,0.08)", border: "1px solid rgba(34,197,94,0.15)", color: "#4ade80", marginBottom: "18px" }}>Spectral Science</div>
              <h2 style={{ fontSize: "clamp(2rem, 4.5vw, 3rem)", fontWeight: 200, margin: "0 0 14px" }}>
                Vegetation Indices <span style={{ fontWeight: 800, color: "#f8fafc" }}>We Compute</span>
              </h2>
              <p style={{ fontSize: "16px", color: "#64748b", maxWidth: "620px", margin: "0 auto", lineHeight: 1.65 }}>Every pixel undergoes multi-band spectral decomposition. Six core indices — optical and radar — feed our diagnostic pipeline.</p>
            </div>
          </Reveal>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(350px, 1fr))", gap: "14px" }}>
            {INDICES.map((idx, i) => (
              <Reveal key={i} delay={0.03 + i * 0.05}>
                <div className="hp-fcard" style={{ padding: "24px", borderRadius: "16px", background: "rgba(15,23,42,0.4)", border: "1px solid rgba(71,85,105,0.06)", height: "100%", position: "relative", overflow: "hidden" }}>
                  <div style={{ position: "absolute", top: 0, left: "10%", right: "10%", height: "1px", background: `linear-gradient(90deg, transparent, ${idx.color}18, transparent)` }} />
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "10px" }}>
                    <span style={{ fontSize: "18px", fontWeight: 800, color: idx.color, fontFamily: "monospace" }}>{idx.name}</span>
                    <span style={{ fontSize: "9px", padding: "3px 8px", borderRadius: "6px", background: `${idx.color}0a`, border: `1px solid ${idx.color}15`, color: idx.color, fontWeight: 700 }}>{idx.band}</span>
                  </div>
                  <div style={{ fontFamily: "monospace", fontSize: "11px", color: "#94a3b8", padding: "8px 12px", borderRadius: "8px", background: "rgba(8,12,25,0.5)", border: "1px solid rgba(71,85,105,0.06)", marginBottom: "10px", wordBreak: "break-all" }}>{idx.formula}</div>
                  <p style={{ fontSize: "12px", color: "#64748b", lineHeight: 1.55, margin: "0 0 8px" }}>{idx.use}</p>
                  <div style={{ display: "flex", gap: "12px", fontSize: "10px" }}>
                    <span style={{ color: "#475569" }}>Range: <span style={{ color: "#94a3b8", fontFamily: "monospace" }}>{idx.range}</span></span>
                    <span style={{ color: "#475569" }}>Typical: <span style={{ color: "#94a3b8", fontFamily: "monospace" }}>{idx.typical}</span></span>
                  </div>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ PHENOLOGY TIMELINE ═══════════════════════════════ */}
      <section style={{ padding: "110px 0", borderTop: "1px solid rgba(71,85,105,0.08)" }}>
        <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "0 24px" }}>
          <Reveal>
            <div style={{ textAlign: "center", marginBottom: "56px" }}>
              <div style={{ display: "inline-flex", padding: "5px 14px", borderRadius: "20px", fontSize: "11px", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.1em", background: "rgba(251,191,36,0.08)", border: "1px solid rgba(251,191,36,0.15)", color: "#fbbf24", marginBottom: "18px" }}>Crop Phenology</div>
              <h2 style={{ fontSize: "clamp(2rem, 4.5vw, 3rem)", fontWeight: 200, margin: "0 0 14px" }}>
                Growth Stage <span style={{ fontWeight: 800, color: "#f8fafc" }}>Detection Pipeline</span>
              </h2>
              <p style={{ fontSize: "16px", color: "#64748b", maxWidth: "640px", margin: "0 auto", lineHeight: 1.65 }}>NDVI time-series aligned to Growing Degree Day (GDD) accumulation. Each stage has satellite-detectable spectral signatures confirmed by drone and photo ground truth.</p>
            </div>
          </Reveal>

          {/* GDD-indexed NDVI curve */}
          <Reveal delay={0.1}>
            <div style={{ marginBottom: "32px", padding: "24px 28px", borderRadius: "16px", background: "rgba(15,23,42,0.35)", border: "1px solid rgba(71,85,105,0.06)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "14px" }}>
                <span style={{ fontSize: "11px", fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.08em" }}>NDVI Phenology Curve — Wheat (T. aestivum)</span>
                <span style={{ fontSize: "10px", color: "#475569", fontFamily: "monospace" }}>GDD base 0°C</span>
              </div>
              <Sparkline data={PHENOLOGY.map(p => p.ndvi)} width={1100} height={64} color="#4ade80" strokeW={2} />
              <div style={{ display: "flex", justifyContent: "space-between", marginTop: "8px" }}>
                {PHENOLOGY.map((p, i) => (
                  <div key={i} style={{ textAlign: "center", flex: 1 }}>
                    <div style={{ fontSize: "12px" }}>{p.icon}</div>
                    <div style={{ fontSize: "8px", color: "#475569", fontWeight: 600 }}>{p.gdd}</div>
                  </div>
                ))}
              </div>
            </div>
          </Reveal>

          {/* Stage cards */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(155px, 1fr))", gap: "10px" }}>
            {PHENOLOGY.map((p, i) => (
              <Reveal key={i} delay={0.05 + i * 0.04}>
                <div className="hp-fcard" style={{ padding: "18px", borderRadius: "14px", background: "rgba(15,23,42,0.4)", border: "1px solid rgba(71,85,105,0.06)", height: "100%", textAlign: "center" }}>
                  <div style={{ fontSize: "1.5rem", marginBottom: "6px" }}>{p.icon}</div>
                  <div style={{ fontSize: "13px", fontWeight: 700, color: "#f1f5f9", marginBottom: "4px" }}>{p.stage}</div>
                  <div style={{ fontSize: "10px", fontFamily: "monospace", color: "#4ade80", fontWeight: 700, marginBottom: "6px" }}>GDD {p.gdd}</div>
                  <AnimBar value={p.ndvi * 100} color="#4ade80" height={3} label={`NDVI ${p.ndvi}`} suffix="" />
                  <p style={{ fontSize: "10px", color: "#64748b", lineHeight: 1.45, margin: "8px 0 0", textAlign: "left" }}>{p.desc}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ SOIL SCIENCE ═════════════════════════════════════ */}
      <section style={{ padding: "110px 0", borderTop: "1px solid rgba(71,85,105,0.08)" }}>
        <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "0 24px" }}>
          <Reveal>
            <div style={{ textAlign: "center", marginBottom: "56px" }}>
              <div style={{ display: "inline-flex", padding: "5px 14px", borderRadius: "20px", fontSize: "11px", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.1em", background: "rgba(192,132,252,0.08)", border: "1px solid rgba(192,132,252,0.15)", color: "#c084fc", marginBottom: "18px" }}>Soil Science</div>
              <h2 style={{ fontSize: "clamp(2rem, 4.5vw, 3rem)", fontWeight: 200, margin: "0 0 14px" }}>
                Below-Ground <span style={{ fontWeight: 800, color: "#f8fafc" }}>Intelligence</span>
              </h2>
              <p style={{ fontSize: "16px", color: "#64748b", maxWidth: "620px", margin: "0 auto", lineHeight: 1.65 }}>SAR backscatter estimates surface moisture. IoT probes measure at root depth. Lab data feeds fertility models. All triangulated in real-time.</p>
            </div>
          </Reveal>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(350px, 1fr))", gap: "12px", marginBottom: "40px" }}>
            {SOIL_PARAMS.map((s, i) => (
              <Reveal key={i} delay={0.03 + i * 0.05}>
                <div className="hp-fcard" style={{ padding: "20px 22px", borderRadius: "14px", background: "rgba(15,23,42,0.4)", border: "1px solid rgba(71,85,105,0.06)", display: "flex", alignItems: "center", gap: "16px" }}>
                  <div style={{ width: "48px", height: "48px", borderRadius: "12px", background: `${s.color}06`, border: `1px solid ${s.color}10`, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                    <span style={{ fontSize: "14px", fontWeight: 800, color: s.color, fontFamily: "monospace" }}>{s.unit}</span>
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: "14px", fontWeight: 700, color: "#f1f5f9" }}>{s.param}</div>
                    <div style={{ fontSize: "10px", color: "#475569", marginTop: "2px" }}>Source: <span style={{ color: "#94a3b8" }}>{s.source}</span></div>
                    <div style={{ display: "flex", gap: "12px", marginTop: "4px", fontSize: "10px" }}>
                      <span style={{ color: "#475569" }}>Range: <span style={{ color: s.color, fontFamily: "monospace", fontWeight: 700 }}>{s.range}</span></span>
                      <span style={{ color: "#64748b" }}>⚠ {s.critical}</span>
                    </div>
                  </div>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ WATER BALANCE MODELS ═════════════════════════════ */}
      <section style={{ padding: "0 0 110px" }}>
        <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "0 24px" }}>
          <Reveal>
            <div style={{ marginBottom: "32px" }}>
              <div style={{ display: "inline-flex", padding: "5px 14px", borderRadius: "20px", fontSize: "11px", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.1em", background: "rgba(34,211,238,0.08)", border: "1px solid rgba(34,211,238,0.15)", color: "#22d3ee", marginBottom: "16px" }}>Hydrological Models</div>
              <h2 style={{ fontSize: "clamp(1.6rem, 3vw, 2.4rem)", fontWeight: 200, margin: 0 }}>
                Water Balance <span style={{ fontWeight: 800, color: "#f8fafc" }}>Equations We Run</span>
              </h2>
            </div>
          </Reveal>

          <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
            {WATER_MODELS.map((m, i) => (
              <Reveal key={i} delay={0.05 + i * 0.08}>
                <div className="hp-fcard" style={{ padding: "24px 28px", borderRadius: "16px", background: "rgba(15,23,42,0.4)", border: "1px solid rgba(71,85,105,0.06)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
                    <span style={{ fontSize: "15px", fontWeight: 700, color: m.color }}>{m.model}</span>
                    <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                      <div style={{ width: "6px", height: "6px", borderRadius: "50%", background: m.color }} />
                      <span style={{ fontSize: "9px", color: "#475569" }}>Active</span>
                    </div>
                  </div>
                  <div style={{ fontFamily: "monospace", fontSize: "12px", color: "#94a3b8", padding: "10px 14px", borderRadius: "8px", background: "rgba(8,12,25,0.5)", border: "1px solid rgba(71,85,105,0.06)", marginBottom: "10px", overflowX: "auto", whiteSpace: "nowrap" }}>{m.eq}</div>
                  <p style={{ fontSize: "13px", color: "#64748b", lineHeight: 1.6, margin: 0 }}>{m.desc}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>
    </>
  );
}
