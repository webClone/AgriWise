"use client";
import { useEffect, useRef, useState } from "react";
import { Reveal, Counter } from "@/components/landing/LandingPrimitives";

/* ── Animated Pixel Heatmap Grid ─────────────────────────── */
function HeatmapGrid({ rows = 12, cols = 20, palette = "stress" }: { rows?: number; cols?: number; palette?: string }) {
  const [cells, setCells] = useState<number[][]>([]);
  const [phase, setPhase] = useState(0);

  useEffect(() => {
    // Generate initial random data
    const gen = () => Array.from({ length: rows }, (_, r) =>
      Array.from({ length: cols }, (_, c) => {
        const cx = cols / 2, cy = rows / 2;
        const dist = Math.sqrt((c - cx) ** 2 + (r - cy) ** 2) / Math.sqrt(cx ** 2 + cy ** 2);
        return Math.max(0, Math.min(1, 0.3 + dist * 0.5 + (Math.random() - 0.5) * 0.3));
      })
    );
    setCells(gen());
    const t = setInterval(() => {
      setCells(prev => prev.map(row => row.map(v => Math.max(0, Math.min(1, v + (Math.random() - 0.5) * 0.06)))));
      setPhase(p => p + 1);
    }, 800);
    return () => clearInterval(t);
  }, [rows, cols]);

  const getColor = (v: number) => {
    if (palette === "stress") {
      if (v < 0.3) return `rgba(34,197,94,${0.3 + v})`;
      if (v < 0.6) return `rgba(251,191,36,${0.3 + v * 0.5})`;
      return `rgba(248,113,113,${0.3 + v * 0.5})`;
    }
    return `rgba(74,222,128,${0.15 + v * 0.6})`;
  };

  if (!cells.length) return null;
  return (
    <div style={{ display: "grid", gridTemplateColumns: `repeat(${cols}, 1fr)`, gap: "2px", borderRadius: "12px", overflow: "hidden" }}>
      {cells.flat().map((v, i) => (
        <div key={i} style={{
          aspectRatio: "1", background: getColor(v), borderRadius: "2px",
          transition: "background 0.6s ease",
        }} />
      ))}
    </div>
  );
}

/* ── Live Processing Simulation ──────────────────────────── */
function ProcessingSim() {
  const [step, setStep] = useState(0);
  const [progress, setProgress] = useState(0);
  const steps = [
    { label: "Ingesting Sentinel-2 L2A tile...", icon: "🛰️", color: "#4ade80" },
    { label: "Fusing SAR + optical rasters...", icon: "🔗", color: "#34d399" },
    { label: "Computing NDVI, NDMI, EVI...", icon: "📈", color: "#2dd4bf" },
    { label: "Running FAO-56 ET₀ equation...", icon: "💧", color: "#22d3ee" },
    { label: "Analyzing N/P/K deficiency...", icon: "🧪", color: "#60a5fa" },
    { label: "Estimating biomass (fAPAR×LUE)...", icon: "🌿", color: "#818cf8" },
    { label: "Monte Carlo yield forecast...", icon: "📊", color: "#a78bfa" },
    { label: "Scoring multi-factor risk...", icon: "⚠️", color: "#c084fc" },
    { label: "Generating VRA prescriptions...", icon: "💊", color: "#e879f9" },
    { label: "Building evidence chains...", icon: "💬", color: "#f472b6" },
    { label: "Rendering SIRE surfaces...", icon: "🎨", color: "#fb923c" },
  ];

  useEffect(() => {
    const t = setInterval(() => {
      setProgress(p => {
        if (p >= 100) {
          setStep(s => (s + 1) % steps.length);
          return 0;
        }
        return p + Math.random() * 15 + 5;
      });
    }, 200);
    return () => clearInterval(t);
  }, []);

  const s = steps[step];
  return (
    <div style={{ padding: "24px 28px", borderRadius: "18px", background: "rgba(15,23,42,0.5)", border: "1px solid rgba(71,85,105,0.08)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "14px" }}>
        <div style={{ width: "8px", height: "8px", borderRadius: "50%", background: s.color, boxShadow: `0 0 10px ${s.color}80`, animation: "pulse 1s ease-in-out infinite" }} />
        <span style={{ fontSize: "13px", fontWeight: 700, color: "#475569", textTransform: "uppercase", letterSpacing: "0.1em" }}>Live Processing Simulation</span>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: "14px", marginBottom: "12px" }}>
        <span style={{ fontSize: "1.8rem" }}>{s.icon}</span>
        <span key={step} style={{ fontSize: "18px", fontWeight: 600, color: s.color, animation: "fadeSlideUp 0.3s ease" }}>{s.label}</span>
        <span style={{ fontSize: "16px", fontWeight: 800, color: "#94a3b8", fontFamily: "monospace", marginLeft: "auto" }}>{Math.min(100, Math.round(progress))}%</span>
      </div>
      <div style={{ height: "6px", borderRadius: "6px", background: "rgba(71,85,105,0.12)", overflow: "hidden" }}>
        <div style={{ height: "100%", borderRadius: "6px", width: `${Math.min(100, progress)}%`, background: `linear-gradient(90deg, ${s.color}cc, ${s.color})`, transition: "width 0.2s ease", boxShadow: `0 0 12px ${s.color}40` }} />
      </div>
      {/* Mini layer indicators */}
      <div style={{ display: "flex", gap: "4px", marginTop: "12px" }}>
        {steps.map((st, i) => (
          <div key={i} style={{
            flex: 1, height: "4px", borderRadius: "2px",
            background: i < step ? st.color : i === step ? `${st.color}60` : "rgba(71,85,105,0.1)",
            transition: "background 0.3s ease",
          }} />
        ))}
      </div>
    </div>
  );
}

/* ── Animated Data Flow Beam ─────────────────────────────── */
function DataFlowBeam() {
  return (
    <div style={{ position: "relative", padding: "40px 0" }}>
      {/* Source nodes */}
      <div style={{ display: "flex", justifyContent: "space-around", marginBottom: "24px" }}>
        {[
          { icon: "🛰️", label: "Sentinel-2", sub: "13 spectral bands", color: "#4ade80" },
          { icon: "📡", label: "Sentinel-1", sub: "SAR C-band 5.4GHz", color: "#22d3ee" },
          { icon: "🚁", label: "Drone", sub: "2cm multispectral", color: "#60a5fa" },
          { icon: "📡", label: "IoT Sensors", sub: "LoRa real-time", color: "#818cf8" },
          { icon: "📸", label: "Field Photos", sub: "GPS-tagged AI", color: "#fbbf24" },
          { icon: "🌤️", label: "Weather", sub: "Open-Meteo hourly", color: "#f87171" },
        ].map((s, i) => (
          <div key={i} className="ab-source-node" style={{ textAlign: "center", padding: "16px", borderRadius: "16px", background: `${s.color}06`, border: `1px solid ${s.color}12`, minWidth: "110px" }}>
            <div style={{ fontSize: "2rem", marginBottom: "6px", animation: `float ${3 + i * 0.5}s ease-in-out infinite` }}>{s.icon}</div>
            <div style={{ fontSize: "13px", fontWeight: 700, color: s.color }}>{s.label}</div>
            <div style={{ fontSize: "10px", color: "#475569", marginTop: "2px" }}>{s.sub}</div>
          </div>
        ))}
      </div>

      {/* Animated beams */}
      <div style={{ display: "flex", justifyContent: "center", gap: "24px", margin: "8px 0 24px" }}>
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} style={{ width: "2px", height: "40px", background: "rgba(71,85,105,0.15)", position: "relative", overflow: "hidden" }}>
            <div style={{ position: "absolute", width: "2px", height: "12px", background: "#4ade8080", borderRadius: "2px", animation: `beamDown 1.5s ease-in-out infinite`, animationDelay: `${i * 0.2}s` }} />
          </div>
        ))}
      </div>

      {/* Fusion core */}
      <div style={{ display: "flex", justifyContent: "center" }}>
        <div style={{ padding: "24px 40px", borderRadius: "20px", background: "linear-gradient(135deg, rgba(129,140,248,0.08), rgba(34,197,94,0.06))", border: "2px solid rgba(129,140,248,0.15)", textAlign: "center", position: "relative", overflow: "hidden" }}>
          <div style={{ position: "absolute", inset: 0, background: "radial-gradient(circle at 50% 50%, rgba(129,140,248,0.04), transparent 70%)", animation: "pulseBg 3s ease-in-out infinite" }} />
          <div style={{ position: "relative", zIndex: 1 }}>
            <div style={{ fontSize: "2.5rem", marginBottom: "8px" }}>🧠</div>
            <div style={{ fontSize: "22px", fontWeight: 800, color: "#818cf8" }}>AgriBrain Fusion</div>
            <div style={{ fontSize: "14px", color: "#64748b", marginTop: "4px" }}>11 layers × 4 sources × H×W pixels</div>
          </div>
        </div>
      </div>

      {/* Output beams */}
      <div style={{ display: "flex", justifyContent: "center", gap: "32px", margin: "24px 0 8px" }}>
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} style={{ width: "2px", height: "40px", background: "rgba(71,85,105,0.15)", position: "relative", overflow: "hidden" }}>
            <div style={{ position: "absolute", width: "2px", height: "12px", background: "#4ade8080", borderRadius: "2px", animation: `beamDown 1.5s ease-in-out infinite`, animationDelay: `${i * 0.3 + 0.5}s` }} />
          </div>
        ))}
      </div>

      {/* Output surfaces */}
      <div style={{ display: "flex", justifyContent: "center", gap: "16px", flexWrap: "wrap" }}>
        {[
          { icon: "💧", name: "Water Stress", color: "#f87171" },
          { icon: "🌿", name: "Vegetation", color: "#4ade80" },
          { icon: "🧪", name: "Nutrients", color: "#fbbf24" },
          { icon: "📊", name: "Yield", color: "#60a5fa" },
        ].map((o, i) => (
          <div key={i} style={{ padding: "14px 20px", borderRadius: "14px", background: `${o.color}06`, border: `1px solid ${o.color}12`, textAlign: "center" }}>
            <div style={{ fontSize: "1.6rem", marginBottom: "4px" }}>{o.icon}</div>
            <div style={{ fontSize: "13px", fontWeight: 700, color: o.color }}>{o.name}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── Animated Ring Stats ─────────────────────────────────── */
function RingStat({ value, max, label, color, size = 120 }: { value: number; max: number; label: string; color: string; size?: number }) {
  const [v, setV] = useState(0);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const obs = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setV(value); obs.disconnect(); } }, { threshold: 0.3 });
    if (ref.current) obs.observe(ref.current);
    return () => obs.disconnect();
  }, [value]);
  const pct = (v / max) * 100;
  const r = (size - 12) / 2;
  const circ = 2 * Math.PI * r;
  const offset = circ - (pct / 100) * circ;
  return (
    <div ref={ref} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "12px" }}>
      <div style={{ position: "relative", width: size, height: size }}>
        <svg width={size} height={size} style={{ transform: "rotate(-90deg)", position: "absolute", inset: 0 }}>
          <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={`${color}15`} strokeWidth="5" />
          <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth="5"
            strokeDasharray={circ} strokeDashoffset={offset} strokeLinecap="round"
            style={{ transition: "stroke-dashoffset 1.5s cubic-bezier(0.16,1,0.3,1)" }} />
        </svg>
        <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
          <div style={{ fontSize: "32px", fontWeight: 800, color, lineHeight: 1 }}><Counter end={v} /></div>
        </div>
      </div>
      <div style={{ fontSize: "13px", color: "#94a3b8", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em" }}>{label}</div>
    </div>
  );
}

/* ═══ MAIN COMPONENT ═══════════════════════════════════════ */
export default function AgriBrainVisuals() {
  return (
    <>
      {/* ── ARCHITECTURE STATS ────────────────────────────── */}
      <section style={{ padding: "0 0 80px" }}>
        <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "0 24px" }}>
          <Reveal>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: "16px", textAlign: "center" }}>
              <RingStat value={11} max={11} label="Layers" color="#818cf8" />
              <RingStat value={7} max={10} label="Surfaces" color="#f87171" />
              <RingStat value={13} max={13} label="Bands" color="#4ade80" />
              <RingStat value={6} max={6} label="Sources" color="#22d3ee" />
              <RingStat value={4} max={4} label="Grounding" color="#fbbf24" />
              <RingStat value={30} max={60} label="Seconds" color="#c084fc" />
            </div>
          </Reveal>
        </div>
      </section>

      {/* ── DATA FLOW SCHEMA ─────────────────────────────── */}
      <section style={{ padding: "0 0 100px" }}>
        <div style={{ maxWidth: "1100px", margin: "0 auto", padding: "0 24px" }}>
          <Reveal>
            <div style={{ textAlign: "center", marginBottom: "32px" }}>
              <h2 style={{ fontSize: "clamp(2rem, 4.5vw, 3rem)", fontWeight: 200, margin: 0 }}>
                Data Flow <span style={{ fontWeight: 800, color: "#f8fafc" }}>Architecture</span>
              </h2>
            </div>
          </Reveal>
          <Reveal delay={0.1}><DataFlowBeam /></Reveal>
        </div>
      </section>

      {/* ── LIVE PROCESSING + HEATMAP ────────────────────── */}
      <section style={{ padding: "0 0 100px" }}>
        <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "0 24px" }}>
          <Reveal>
            <div style={{ textAlign: "center", marginBottom: "40px" }}>
              <div style={{ display: "inline-flex", padding: "6px 16px", borderRadius: "20px", fontSize: "12px", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.1em", background: "rgba(34,197,94,0.08)", border: "1px solid rgba(34,197,94,0.15)", color: "#4ade80", marginBottom: "20px" }}>Real-Time Visualization</div>
              <h2 style={{ fontSize: "clamp(2rem, 4.5vw, 3rem)", fontWeight: 200, margin: 0 }}>
                Watch the Pipeline <span style={{ fontWeight: 800, color: "#f8fafc" }}>Process</span>
              </h2>
            </div>
          </Reveal>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px" }}>
            <Reveal delay={0.1}>
              <div>
                <ProcessingSim />
                {/* Equations */}
                <div style={{ marginTop: "16px", padding: "20px 24px", borderRadius: "16px", background: "rgba(15,23,42,0.4)", border: "1px solid rgba(71,85,105,0.06)" }}>
                  <div style={{ fontSize: "14px", fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "14px" }}>Active Equations</div>
                  {[
                    { eq: "NDVI = (B08 − B04) / (B08 + B04)", c: "#4ade80" },
                    { eq: "ET₀ = Δ(Rn−G) + γ·u₂·VPD / Δ + γ(1+0.34u₂)", c: "#22d3ee" },
                    { eq: "CWSI = (Tc−Ta−LLB) / (ULB−LLB)", c: "#fbbf24" },
                    { eq: "VPD = 0.6108·e^(17.27T/(T+237.3)) − eₐ", c: "#f87171" },
                  ].map((e, i) => (
                    <div key={i} style={{ padding: "10px 16px", borderRadius: "10px", background: "rgba(8,12,25,0.4)", border: "1px solid rgba(71,85,105,0.04)", marginBottom: "8px", fontFamily: "monospace", fontSize: "14px", color: e.c }}>
                      {e.eq}
                    </div>
                  ))}
                </div>
              </div>
            </Reveal>

            <Reveal delay={0.2}>
              <div>
                <div style={{ padding: "20px", borderRadius: "18px", background: "rgba(15,23,42,0.5)", border: "1px solid rgba(71,85,105,0.08)", marginBottom: "12px" }}>
                  <div style={{ fontSize: "14px", fontWeight: 700, color: "#f87171", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "14px" }}>💧 Water Stress Surface — Live</div>
                  <HeatmapGrid rows={10} cols={18} palette="stress" />
                  <div style={{ display: "flex", justifyContent: "space-between", marginTop: "12px", fontSize: "13px" }}>
                    <span style={{ color: "#4ade80" }}>● Low stress</span>
                    <span style={{ color: "#fbbf24" }}>● Moderate</span>
                    <span style={{ color: "#f87171" }}>● High stress</span>
                  </div>
                </div>
                <div style={{ padding: "20px", borderRadius: "18px", background: "rgba(15,23,42,0.5)", border: "1px solid rgba(71,85,105,0.08)" }}>
                  <div style={{ fontSize: "14px", fontWeight: 700, color: "#4ade80", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "14px" }}>🌿 Vegetation Vigor — Live</div>
                  <HeatmapGrid rows={10} cols={18} palette="veg" />
                </div>
              </div>
            </Reveal>
          </div>
        </div>
      </section>
    </>
  );
}
