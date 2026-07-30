"use client";
import Link from "next/link";
import { Particles, Reveal, TypeWriter, OrbitRing } from "@/components/landing/LandingPrimitives";
import AgriBrainVisuals from "@/components/landing/AgriBrainVisuals";
import AgriBrainLayers from "@/components/landing/AgriBrainLayers";
import AgriBrainSurfaces from "@/components/landing/AgriBrainSurfaces";
import AgriBrainTutorial from "@/components/landing/AgriBrainTutorial";
import { ThemeProvider, ThemeToggle, useTheme } from "@/components/landing/ThemeProvider";
import { ThemeLogo } from "@/components/landing/ThemeLogo";
import "@/components/landing/agribrain-theme.css";

function AgriBrainContent() {
  const { theme } = useTheme();
  return (
    <div data-theme={theme} style={{ minHeight: "100vh", background: "#050a14", color: "#e2e8f0", fontFamily: "'Inter', system-ui, sans-serif", overflowX: "hidden" }}>
      {/* Nav */}
      <nav style={{ position: "fixed", top: 0, left: 0, right: 0, zIndex: 100, padding: "14px 24px", background: "rgba(5,10,20,0.82)", backdropFilter: "blur(20px)", borderBottom: "1px solid rgba(71,85,105,0.06)" }}>
        <div style={{ maxWidth: "1200px", margin: "0 auto", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <Link href="/" style={{ display: "flex", alignItems: "center", textDecoration: "none" }}>
            <ThemeLogo height={80} />
          </Link>
          <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
            <Link href="/" style={{ fontSize: "13px", color: "#94a3b8", textDecoration: "none", fontWeight: 500 }}>← Home</Link>
            <ThemeToggle />
            <Link href="/farm" className="hp-cta-nav" style={{ padding: "8px 20px", borderRadius: "10px", background: "linear-gradient(135deg,#22c55e,#16a34a)", color: "#fff", fontSize: "13px", fontWeight: 700, textDecoration: "none", boxShadow: "0 2px 12px rgba(34,197,94,0.2)" }}>Launch App</Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section style={{ position: "relative", paddingTop: "160px", paddingBottom: "80px", overflow: "hidden", textAlign: "center" }}>
        <Particles n={30} color="rgba(129,140,248,0.25)" />
        <div style={{ position: "absolute", top: "8%", right: "8%", opacity: 0.1 }}><OrbitRing size={240} color="#818cf8" /></div>
        <div style={{ maxWidth: "900px", margin: "0 auto", padding: "0 24px", position: "relative", zIndex: 1 }}>
          <Reveal>
            <div style={{ display: "inline-flex", alignItems: "center", gap: "8px", padding: "6px 16px", borderRadius: "24px", fontSize: "11px", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.1em", background: "rgba(129,140,248,0.08)", border: "1px solid rgba(129,140,248,0.15)", color: "#818cf8", marginBottom: "24px" }}>
              <div style={{ width: "6px", height: "6px", borderRadius: "50%", background: "#818cf8", boxShadow: "0 0 8px #818cf880", animation: "pulse 2s ease-in-out infinite" }} />
              Technical Architecture Documentation
            </div>
          </Reveal>
          <Reveal delay={0.1}>
            <h1 style={{ fontSize: "clamp(2.5rem, 5.5vw, 4rem)", fontWeight: 200, margin: "0 0 16px", lineHeight: 1.1 }}>
              How <span style={{ fontWeight: 800, background: "linear-gradient(135deg, #818cf8, #c084fc, #e879f9)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>AgriBrain</span> Works
            </h1>
          </Reveal>
          <Reveal delay={0.2}>
            <p style={{ fontSize: "clamp(16px, 2vw, 19px)", color: "#64748b", maxWidth: "680px", margin: "0 auto 32px", lineHeight: 1.7 }}>
              An 11-layer deep reasoning pipeline. From raw Sentinel-2 radiance at 10m resolution through Kalman-filtered time-series, FAO-56 water balance equations, and zone-level heterogeneity segmentation — to pixel-level prescriptions with full provenance chains.
            </p>
          </Reveal>
          <Reveal delay={0.3}>
            <div style={{ display: "flex", gap: "20px", justifyContent: "center", flexWrap: "wrap" }}>
              {[
                { l: "11 Processing Layers", c: "#818cf8" },
                { l: "7 Surface Artifacts", c: "#f87171" },
                { l: "4 Grounding Classes", c: "#fbbf24" },
                { l: "FAO-56 Physics", c: "#22d3ee" },
                { l: "Kalman Filtering", c: "#4ade80" },
              ].map((b, i) => (
                <span key={i} style={{ padding: "6px 14px", borderRadius: "8px", fontSize: "11px", fontWeight: 700, background: `${b.c}08`, border: `1px solid ${b.c}12`, color: b.c }}>{b.l}</span>
              ))}
            </div>
          </Reveal>
        </div>
      </section>

      {/* Data flow visual */}
      <section style={{ padding: "0 0 80px" }}>
        <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "0 24px" }}>
          <Reveal>
            <div style={{ padding: "36px", borderRadius: "24px", background: "rgba(15,23,42,0.5)", border: "1px solid rgba(71,85,105,0.08)", overflowX: "auto" }}>
              <div style={{ fontSize: "13px", fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: "24px", textAlign: "center" }}>End-to-End Data Flow</div>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", justifyContent: "center", flexWrap: "wrap" }}>
                {[
                  { n: "🛰️ Satellite", c: "#4ade80" }, { n: "📡 Sensors", c: "#818cf8" }, { n: "🚁 Drone", c: "#22d3ee" }, { n: "📸 Photos", c: "#fbbf24" },
                ].map((s, i) => (
                  <span key={i} style={{ padding: "10px 18px", borderRadius: "12px", background: `${s.c}08`, border: `1px solid ${s.c}15`, fontSize: "14px", fontWeight: 700, color: s.c }}>{s.n}</span>
                ))}
                <span style={{ color: "#334155", fontWeight: 800, fontSize: "20px" }}>→</span>
                {["L0", "L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8", "L9", "L10"].map((l, i) => (
                  <span key={l} style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}>
                    <span style={{ padding: "6px 10px", borderRadius: "8px", background: "rgba(71,85,105,0.12)", border: "1px solid rgba(71,85,105,0.08)", fontSize: "13px", fontWeight: 800, color: "#94a3b8", fontFamily: "monospace" }}>{l}</span>
                    {i < 10 && <span style={{ color: "#334155", fontSize: "14px" }}>→</span>}
                  </span>
                ))}
                <span style={{ color: "#334155", fontWeight: 800, fontSize: "20px" }}>→</span>
                <span style={{ padding: "10px 18px", borderRadius: "12px", background: "rgba(34,197,94,0.1)", border: "1px solid rgba(34,197,94,0.15)", fontSize: "15px", fontWeight: 800, color: "#4ade80" }}>🎯 Prescriptions</span>
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      <AgriBrainVisuals />
      <AgriBrainLayers />
      <AgriBrainSurfaces />
      <AgriBrainTutorial />

      {/* CTA */}
      <section style={{ padding: "60px 0 100px" }}>
        <div style={{ maxWidth: "800px", margin: "0 auto", padding: "0 24px", textAlign: "center" }}>
          <Reveal>
            <div style={{ padding: "56px 40px", borderRadius: "24px", background: "linear-gradient(135deg, rgba(129,140,248,0.06), rgba(34,197,94,0.04))", border: "1px solid rgba(129,140,248,0.1)", position: "relative", overflow: "hidden" }}>
              <Particles color="rgba(129,140,248,0.12)" n={20} />
              <div style={{ position: "relative", zIndex: 1 }}>
                <h2 style={{ fontSize: "clamp(1.6rem, 3.5vw, 2.4rem)", fontWeight: 200, margin: "0 0 14px" }}>
                  See It <span style={{ fontWeight: 800, color: "#f8fafc" }}>In Action</span>
                </h2>
                <p style={{ fontSize: "16px", color: "#64748b", maxWidth: "440px", margin: "0 auto 28px", lineHeight: 1.6 }}>Draw a field boundary. The 11-layer pipeline runs in under 30 seconds.</p>
                <Link href="/farm" style={{ display: "inline-flex", padding: "16px 40px", borderRadius: "14px", background: "linear-gradient(135deg, #22c55e, #16a34a)", color: "#fff", fontSize: "17px", fontWeight: 800, textDecoration: "none", boxShadow: "0 4px 30px rgba(34,197,94,0.3)" }}>Open Dashboard →</Link>
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      <style>{`
        @keyframes spin { from{transform:rotate(0)} to{transform:rotate(360deg)} }
        @keyframes pulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:0.5;transform:scale(1.5)} }
        @keyframes fadeSlideUp { from{opacity:0;transform:translateY(12px)} to{opacity:1;transform:translateY(0)} }
        @keyframes beamDown { 0%{top:-12px;opacity:0} 30%{opacity:1} 100%{top:40px;opacity:0} }
        @keyframes float { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-6px)} }
        @keyframes pulseBg { 0%,100%{opacity:0.3;transform:scale(1)} 50%{opacity:0.6;transform:scale(1.05)} }
        .hp-fcard { transition: all 0.25s cubic-bezier(0.16,1,0.3,1); }
        .hp-fcard:hover { border-color:rgba(100,116,139,0.18) !important; transform:translateY(-3px); box-shadow:0 14px 50px rgba(0,0,0,0.3); }
        .hp-cta-nav { transition: all 0.15s ease; }
        .hp-cta-nav:hover { transform:translateY(-1px); box-shadow:0 4px 16px rgba(34,197,94,0.3) !important; }
        .ab-node { transition: all 0.25s ease; }
        .ab-node:hover { transform:scale(1.06) !important; }
        .ab-source-node { transition: all 0.25s ease; }
        .ab-source-node:hover { transform:translateY(-4px); border-color:rgba(100,116,139,0.2) !important; }
        .ab-zoom-img:hover img { transform:scale(1.08) !important; }
        @media (max-width: 900px) {
          section [style*="grid-template-columns: repeat(6"] { grid-template-columns: repeat(3,1fr) !important; }
          section [style*="grid-template-columns: repeat(4"] { grid-template-columns: repeat(2,1fr) !important; }
          section [style*="grid-template-columns: repeat(3"] { grid-template-columns: 1fr !important; }
          section [style*="grid-template-columns: 1fr 1fr"] { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </div>
  );
}

export default function AgriBrainPage() {
  return (
    <ThemeProvider>
      <AgriBrainContent />
    </ThemeProvider>
  );
}
