"use client";
import { useState } from "react";
import Image from "next/image";
import { Reveal, AnimBar, Counter } from "@/components/landing/LandingPrimitives";

/* ── Image with zoom-on-hover ────────────────────────────── */
function ZoomImage({ src, alt, caption }: { src: string; alt: string; caption: string }) {
  return (
    <div style={{ borderRadius: "18px", overflow: "hidden", position: "relative" }}>
      <div className="ab-zoom-img" style={{ position: "relative", aspectRatio: "16/10", overflow: "hidden", borderRadius: "18px" }}>
        <Image src={src} alt={alt} fill style={{ objectFit: "cover", transition: "transform 0.5s cubic-bezier(0.16,1,0.3,1)" }} />
      </div>
      <div style={{ padding: "14px 18px", background: "rgba(15,23,42,0.8)", backdropFilter: "blur(10px)", borderRadius: "0 0 18px 18px", marginTop: "-4px" }}>
        <div style={{ fontSize: "14px", fontWeight: 600, color: "#e2e8f0" }}>{alt}</div>
        <div style={{ fontSize: "12px", color: "#64748b", marginTop: "2px" }}>{caption}</div>
      </div>
    </div>
  );
}

/* ── Tutorial data ───────────────────────────────────────── */
const TUTORIAL_STEPS = [
  {
    num: "01", title: "Draw Your Field", icon: "✏️", color: "#4ade80",
    desc: "Open the map and draw your field boundary using the polygon tool. AgriWise accepts any GeoJSON geometry — from a simple rectangle to complex multi-polygon boundaries that follow real field edges.",
    detail: "The boundary is converted to a bounding box with a configurable resolution grid (default 10m, matching Sentinel-2 native pixel size). Each cell in the H×W grid becomes a pixel that carries independent spectral values through the entire pipeline.",
    image: "/agribrain/satellite.png",
    stats: [{ l: "Resolution", v: "10m" }, { l: "Grid", v: "H×W" }, { l: "Format", v: "GeoJSON" }],
  },
  {
    num: "02", title: "Multi-Source Acquisition", icon: "🛰️", color: "#22d3ee",
    desc: "AgriBrain automatically fetches the latest available data from 6 sources: Sentinel-2 optical imagery (13 bands), Sentinel-1 SAR (VV/VH), Open-Meteo weather, and any connected IoT sensors or drone missions.",
    detail: "Sentinel-2 scenes are selected by cloud coverage (<20%) and temporal proximity. SAR data provides all-weather, day/night soil moisture estimation. Weather includes ET₀, precipitation, temperature extremes, and wind speed. IoT data is ingested in real-time via LoRa or MQTT.",
    image: "/agribrain/drone.png",
    stats: [{ l: "Sentinel-2", v: "5-day" }, { l: "SAR", v: "6-day" }, { l: "Weather", v: "Hourly" }],
  },
  {
    num: "03", title: "Spectral Intelligence", icon: "📈", color: "#818cf8",
    desc: "Layer 2 computes 6 vegetation indices per pixel: NDVI for chlorophyll, NDMI for canopy water, EVI for high-biomass correction, SAVI for sparse canopy, NDRE for nitrogen detection, and SAR σ₀ for soil structure.",
    detail: "Each index is Kalman-filtered across the time-series to reject cloud shadows, sensor noise, and atmospheric artifacts. The filter maintains per-pixel state estimates with uncertainty bounds — a noisy observation widens the confidence interval rather than corrupting the trend.",
    image: "/agribrain/heatmap.png",
    stats: [{ l: "Indices", v: "6" }, { l: "Filter", v: "Kalman" }, { l: "Noise", v: "Rejected" }],
  },
  {
    num: "04", title: "Diagnostic Engine", icon: "🔬", color: "#f87171",
    desc: "Layers 3–5 run physics-based diagnostic models. FAO-56 Penman-Monteith computes reference evapotranspiration. Soil water balance tracks deficit accumulation. Nutrient analysis uses red-edge band ratios for N status.",
    detail: "The water stress engine uses a 5-strategy cascade: hotspot zones → composite moisture (NDMI+SAR+IoT+SWB weighted) → ET₀-calibrated deficit → NDVI spatial distribution. Each strategy has a grounding class that tracks how trustworthy the spatial distribution is.",
    image: "/agribrain/sensors.png",
    stats: [{ l: "ET₀ Model", v: "FAO-56" }, { l: "Strategies", v: "5" }, { l: "Grounding", v: "4 classes" }],
  },
  {
    num: "05", title: "Prescription Maps", icon: "💊", color: "#e879f9",
    desc: "Layer 8 generates zone-level action protocols with variable-rate application maps. Each zone gets specific recommendations: irrigate X mm, apply Y kg/ha N, scout for disease, or wait — with cost-benefit analysis.",
    detail: "Prescriptions are timing-optimized using phenology stage + weather forecast. Reproductive stage gets highest priority for water interventions. Variable-rate maps export as shapefiles or ISO-XML for direct upload to VRA-capable equipment.",
    image: "/agribrain/prescription.png",
    stats: [{ l: "Actions", v: "Zone-level" }, { l: "Timing", v: "GDD-optimized" }, { l: "Export", v: "SHP/XML" }],
  },
  {
    num: "06", title: "Evidence & Explainability", icon: "📋", color: "#fbbf24",
    desc: "Every diagnosis links back to its source pixel through a full evidence chain: satellite observation → spectral index value → diagnostic probability → prescription. Nothing is a black box.",
    detail: "Layer 9 generates natural language explanations for both farmer-facing (simple, actionable) and expert-facing (technical, with equations) views. Confidence scoring uses the grounding class pyramid: raster-grounded (95%) → zone (82%) → proxy (65%) → synthetic (40%).",
    image: "/agribrain/phenology.png",
    stats: [{ l: "Evidence", v: "Full chain" }, { l: "Views", v: "2 modes" }, { l: "Confidence", v: "Scored" }],
  },
];

/* ── Animated step indicator ─────────────────────────────── */
function StepIndicator({ steps, active, onSelect }: { steps: typeof TUTORIAL_STEPS; active: number; onSelect: (i: number) => void }) {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "6px", marginBottom: "48px" }}>
      {steps.map((s, i) => (
        <div key={i} style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <button
            onClick={() => onSelect(i)}
            style={{
              width: "48px", height: "48px", borderRadius: "14px",
              background: i === active ? `${s.color}15` : "rgba(15,23,42,0.4)",
              border: `2px solid ${i === active ? s.color : "rgba(71,85,105,0.1)"}`,
              cursor: "pointer", transition: "all 0.3s ease",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: "1.2rem",
              transform: i === active ? "scale(1.15)" : "scale(1)",
              boxShadow: i === active ? `0 0 20px ${s.color}30` : "none",
            }}>
            {s.icon}
          </button>
          {i < steps.length - 1 && (
            <div style={{ width: "32px", height: "2px", background: i < active ? steps[i + 1].color + "40" : "rgba(71,85,105,0.1)", transition: "background 0.3s ease" }} />
          )}
        </div>
      ))}
    </div>
  );
}

/* ═══ MAIN ═══════════════════════════════════════════════ */
export default function AgriBrainTutorial() {
  const [activeStep, setActiveStep] = useState(0);
  const step = TUTORIAL_STEPS[activeStep];

  return (
    <>
      {/* ── PERCEPTION GALLERY ───────────────────────────── */}
      <section style={{ padding: "120px 0", borderTop: "1px solid rgba(71,85,105,0.08)" }}>
        <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "0 24px" }}>
          <Reveal>
            <div style={{ textAlign: "center", marginBottom: "56px" }}>
              <div style={{ display: "inline-flex", padding: "6px 16px", borderRadius: "20px", fontSize: "12px", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.1em", background: "rgba(34,197,94,0.08)", border: "1px solid rgba(34,197,94,0.15)", color: "#4ade80", marginBottom: "20px" }}>Perception Sources</div>
              <h2 style={{ fontSize: "clamp(2.2rem, 5vw, 3.4rem)", fontWeight: 200, margin: "0 0 16px" }}>
                Every Pixel Has a <span style={{ fontWeight: 800, color: "#f8fafc" }}>Source</span>
              </h2>
              <p style={{ fontSize: "18px", color: "#64748b", maxWidth: "600px", margin: "0 auto" }}>From orbit to root depth — six perception layers feed the intelligence pipeline.</p>
            </div>
          </Reveal>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "16px" }}>
            {[
              { src: "/agribrain/satellite.png", alt: "Satellite Imagery", caption: "Sentinel-2 L2A — 13 spectral bands at 10m resolution, 5-day revisit" },
              { src: "/agribrain/drone.png", alt: "Drone Multispectral", caption: "2cm resolution orthomosaics, on-demand targeted missions" },
              { src: "/agribrain/sensors.png", alt: "IoT Ground Sensors", caption: "Real-time soil moisture, temperature, EC at root depth via LoRa" },
              { src: "/agribrain/heatmap.png", alt: "Stress Heatmaps", caption: "Pixel-level water stress probability from multi-source fusion" },
              { src: "/agribrain/prescription.png", alt: "Prescription Maps", caption: "Variable-rate application zones with cost-benefit per hectare" },
              { src: "/agribrain/phenology.png", alt: "Phenology Detection", caption: "GDD-indexed growth stages with satellite-confirmed transitions" },
            ].map((img, i) => (
              <Reveal key={i} delay={0.05 + i * 0.06}>
                <ZoomImage {...img} />
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ── INTERACTIVE TUTORIAL ──────────────────────────── */}
      <section style={{ padding: "0 0 120px" }}>
        <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "0 24px" }}>
          <Reveal>
            <div style={{ textAlign: "center", marginBottom: "40px" }}>
              <div style={{ display: "inline-flex", padding: "6px 16px", borderRadius: "20px", fontSize: "12px", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.1em", background: "rgba(129,140,248,0.08)", border: "1px solid rgba(129,140,248,0.15)", color: "#818cf8", marginBottom: "20px" }}>Step-by-Step</div>
              <h2 style={{ fontSize: "clamp(2.2rem, 5vw, 3.4rem)", fontWeight: 200, margin: "0 0 16px" }}>
                How a Field Gets <span style={{ fontWeight: 800, color: "#f8fafc" }}>Analyzed</span>
              </h2>
              <p style={{ fontSize: "18px", color: "#64748b", maxWidth: "560px", margin: "0 auto" }}>Click through each step to see the full pipeline in action.</p>
            </div>
          </Reveal>

          <StepIndicator steps={TUTORIAL_STEPS} active={activeStep} onSelect={setActiveStep} />

          {/* Active step card */}
          <div key={activeStep} style={{ animation: "fadeSlideUp 0.4s ease", display: "grid", gridTemplateColumns: "1fr 1fr", gap: "24px", alignItems: "start" }}>
            {/* Image side */}
            <div style={{ borderRadius: "20px", overflow: "hidden", position: "relative" }}>
              <div style={{ position: "relative", aspectRatio: "4/3" }}>
                <Image src={step.image} alt={step.title} fill style={{ objectFit: "cover", borderRadius: "20px" }} />
                {/* Step number overlay */}
                <div style={{ position: "absolute", top: "16px", left: "16px", width: "48px", height: "48px", borderRadius: "14px", background: `${step.color}20`, border: `2px solid ${step.color}40`, display: "flex", alignItems: "center", justifyContent: "center", backdropFilter: "blur(10px)" }}>
                  <span style={{ fontSize: "18px", fontWeight: 800, color: step.color, fontFamily: "monospace" }}>{step.num}</span>
                </div>
              </div>
            </div>

            {/* Content side */}
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "14px", marginBottom: "16px" }}>
                <span style={{ fontSize: "2.2rem" }}>{step.icon}</span>
                <h3 style={{ fontSize: "28px", fontWeight: 800, color: step.color, margin: 0 }}>{step.title}</h3>
              </div>

              <p style={{ fontSize: "17px", color: "#e2e8f0", lineHeight: 1.7, margin: "0 0 16px" }}>{step.desc}</p>
              <p style={{ fontSize: "15px", color: "#94a3b8", lineHeight: 1.7, margin: "0 0 24px" }}>{step.detail}</p>

              {/* Stats row */}
              <div style={{ display: "flex", gap: "12px", marginBottom: "24px" }}>
                {step.stats.map((s, j) => (
                  <div key={j} style={{ flex: 1, padding: "14px 16px", borderRadius: "14px", background: `${step.color}06`, border: `1px solid ${step.color}10`, textAlign: "center" }}>
                    <div style={{ fontSize: "18px", fontWeight: 800, color: step.color }}>{s.v}</div>
                    <div style={{ fontSize: "11px", color: "#64748b", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", marginTop: "2px" }}>{s.l}</div>
                  </div>
                ))}
              </div>

              {/* Progress through pipeline */}
              <div style={{ padding: "16px 20px", borderRadius: "14px", background: "rgba(15,23,42,0.4)", border: "1px solid rgba(71,85,105,0.06)" }}>
                <div style={{ fontSize: "11px", fontWeight: 700, color: "#475569", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "10px" }}>Pipeline Progress</div>
                <AnimBar value={(activeStep + 1) / TUTORIAL_STEPS.length * 100} color={step.color} height={6} label={`Step ${activeStep + 1} of ${TUTORIAL_STEPS.length}`} suffix="%" />
              </div>

              {/* Nav buttons */}
              <div style={{ display: "flex", gap: "10px", marginTop: "16px" }}>
                <button
                  onClick={() => setActiveStep(Math.max(0, activeStep - 1))}
                  disabled={activeStep === 0}
                  style={{ flex: 1, padding: "12px", borderRadius: "12px", background: "rgba(71,85,105,0.1)", border: "1px solid rgba(71,85,105,0.08)", color: activeStep === 0 ? "#334155" : "#94a3b8", fontSize: "14px", fontWeight: 700, cursor: activeStep === 0 ? "default" : "pointer", transition: "all 0.2s ease" }}>
                  ← Previous
                </button>
                <button
                  onClick={() => setActiveStep(Math.min(TUTORIAL_STEPS.length - 1, activeStep + 1))}
                  disabled={activeStep === TUTORIAL_STEPS.length - 1}
                  style={{ flex: 1, padding: "12px", borderRadius: "12px", background: `${step.color}15`, border: `1px solid ${step.color}25`, color: step.color, fontSize: "14px", fontWeight: 700, cursor: activeStep === TUTORIAL_STEPS.length - 1 ? "default" : "pointer", transition: "all 0.2s ease" }}>
                  Next Step →
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── BEFORE / AFTER COMPARISON ────────────────────── */}
      <section style={{ padding: "0 0 120px" }}>
        <div style={{ maxWidth: "1000px", margin: "0 auto", padding: "0 24px" }}>
          <Reveal>
            <div style={{ textAlign: "center", marginBottom: "48px" }}>
              <h2 style={{ fontSize: "clamp(2rem, 4.5vw, 3rem)", fontWeight: 200, margin: "0 0 14px" }}>
                Raw Data vs <span style={{ fontWeight: 800, color: "#f8fafc" }}>Intelligence</span>
              </h2>
              <p style={{ fontSize: "18px", color: "#64748b" }}>See how AgriBrain transforms satellite pixels into actionable insight.</p>
            </div>
          </Reveal>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 60px 1fr", gap: "0", alignItems: "center" }}>
            <Reveal delay={0.1}>
              <div style={{ borderRadius: "20px", overflow: "hidden" }}>
                <div style={{ position: "relative", aspectRatio: "4/3" }}>
                  <Image src="/agribrain/satellite.png" alt="Raw satellite" fill style={{ objectFit: "cover" }} />
                  <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, padding: "16px 20px", background: "linear-gradient(transparent, rgba(5,10,20,0.9))" }}>
                    <div style={{ fontSize: "16px", fontWeight: 700, color: "#94a3b8" }}>Raw Sentinel-2 Tile</div>
                    <div style={{ fontSize: "12px", color: "#475569" }}>13 bands × 10m pixels — unprocessed</div>
                  </div>
                </div>
              </div>
            </Reveal>

            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: "28px", color: "#4ade80", animation: "pulse 2s ease-in-out infinite" }}>→</div>
              <div style={{ fontSize: "10px", color: "#475569", fontWeight: 700 }}>11<br/>LAYERS</div>
            </div>

            <Reveal delay={0.2}>
              <div style={{ borderRadius: "20px", overflow: "hidden" }}>
                <div style={{ position: "relative", aspectRatio: "4/3" }}>
                  <Image src="/agribrain/heatmap.png" alt="Intelligence output" fill style={{ objectFit: "cover" }} />
                  <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, padding: "16px 20px", background: "linear-gradient(transparent, rgba(5,10,20,0.9))" }}>
                    <div style={{ fontSize: "16px", fontWeight: 700, color: "#4ade80" }}>Water Stress Surface</div>
                    <div style={{ fontSize: "12px", color: "#64748b" }}>Pixel-level probability with provenance</div>
                  </div>
                </div>
              </div>
            </Reveal>
          </div>
        </div>
      </section>
    </>
  );
}
